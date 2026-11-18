"""Trigger B: find new ingest runs in bronze, open a case per email, classify waiting cases.

Two phases, every time the job runs:

1. **Register** (cheap, always): every ``bronze/<run>/emails.json`` without a
   ``runs`` marker gets one ``RECEIVED`` case per email, keyed on
   ``internetMessageId`` so a resent email never opens a second case. Emails the
   delta reports as ``removed`` are marked as gone from the mailbox.
2. **Classify** (skipped while ``CLASSIFIER_PAUSED=true``): every ``RECEIVED``
   case nobody holds is classified and saved one at a time, so a job killed by
   its timeout loses at most the email in flight. A case a person opened or saved
   meanwhile is left alone (etag check).

Reviewers can work on ``RECEIVED`` cases while classification is paused.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.processor import EmailProcessor
from data.case_store import Conflict

RUN_FILE = re.compile(r"^bronze/([^/]+)/emails\.json$")
NO_CATEGORY = {"", "No Match Found", "UNKNOWN"}
REVIEW_STATUSES = {
    "needs_identification": "no tax ID (AFM) found in the email or its attachments",
    "needs_review": "tax ID not found in the customer registry",
}
# Large and already in silver; keeps Cosmos documents well under the 2 MB limit.
HEAVY_FIELDS = ("attachment_evidence_text",)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def email_id(message: dict[str, Any]) -> str:
    """``<received UTC>_<8 hex of sha256(internetMessageId)>``: stable, sortable, path-safe."""
    key = message.get("internetMessageId") or message["id"]
    try:
        received = datetime.fromisoformat(str(message.get("receivedDateTime")).replace("Z", "+00:00"))
        stamp = received.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        stamp = "00000000T000000Z"
    return f"{stamp}_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]}"


def unwrap_run(raw: Any) -> tuple[list[dict], list[dict]]:
    """Delta runs are ``{"messages": [...], "removed": [...]}``; older runs a plain list."""
    if isinstance(raw, dict):
        return list(raw.get("messages") or []), list(raw.get("removed") or [])
    if isinstance(raw, list):
        return raw, []
    raise TypeError(f"Unexpected run file shape: {type(raw).__name__}")


def is_locked(case: dict[str, Any], now: str) -> bool:
    lock = case.get("lock") or {}
    return bool(lock) and str(lock.get("until", "")) > now


def audit(store, case_id: str, action: str, now: str, **details: Any) -> None:
    store.create("audit", {"id": uuid.uuid4().hex, "caseId": case_id, "at": now,
                           "by": "classifier", "action": action, **details})


def new_case(message: dict[str, Any], run: str, run_file: str, now: str) -> dict[str, Any]:
    return {
        "id": email_id(message),
        "type": "case",
        "status": "RECEIVED",
        "route": None,
        "routeReasons": [],
        "internetMessageId": message.get("internetMessageId"),
        "graphId": message["id"],
        "conversationId": message.get("conversationId"),
        "subject": message.get("subject") or "",
        "from": ((message.get("from") or {}).get("emailAddress") or {}).get("address", ""),
        "receivedAt": message.get("receivedDateTime"),
        "mailboxState": "present",
        "modelCategory": None,
        "confidence": None,
        "votes": {},
        "finalCategory": None,
        "categories": [],
        "reviewedBy": None,
        "reviewedAt": None,
        "lock": None,
        "sourceRefs": {
            "ingestRun": run,
            "runFile": run_file,
            "eml": message.get("eml_blob_path"),
            "attachments": [a["blob_name"] for a in message.get("attachments") or [] if a.get("blob_name")],
        },
        "payload": None,
        "createdAt": now,
        "updatedAt": now,
    }


def _removed_reason(item: dict[str, Any]) -> Any:
    nested = item.get("@removed")
    return nested.get("reason") if isinstance(nested, dict) else item.get("@removed.reason")


def register_runs(store, blob, now: str) -> dict[str, int]:
    totals = {"runs": 0, "new_cases": 0, "resent": 0, "removed": 0}
    for name in blob.list_names("bronze/"):
        match = RUN_FILE.match(name)
        if not match or store.get("runs", match.group(1)):
            continue
        run = match.group(1)
        messages, removed = unwrap_run(json.loads(blob.download(name)))
        new = resent = gone = 0
        for message in messages:
            case = new_case(message, run, name, now)
            existing = store.get("cases", case["id"])
            if existing is None:
                store.create("cases", case)
                audit(store, case["id"], "registered", now, run=run)
                new += 1
                continue
            resent += 1
            if existing.get("graphId") != message["id"]:  # Graph ids change when a mail moves folder.
                try:
                    store.replace("cases", {**existing, "graphId": message["id"], "updatedAt": now})
                except Conflict:
                    pass  # Someone saved it just now; the old id only matters for "removed".
        for item in removed:
            for existing in store.find("cases", "graphId", item.get("id")):
                if existing.get("mailboxState") == "removed":
                    continue
                try:
                    store.replace("cases", {**existing, "mailboxState": "removed", "updatedAt": now})
                except Conflict:
                    continue
                audit(store, existing["id"], "left mailbox", now, run=run, reason=_removed_reason(item))
                gone += 1
        store.create("runs", {"id": run, "registeredAt": now, "emails": len(messages),
                              "newCases": new, "resent": resent, "removed": gone})
        totals["runs"] += 1
        totals["new_cases"] += new
        totals["resent"] += resent
        totals["removed"] += gone
    return totals


def decide_route(records: list[dict[str, Any]], threshold: float,
                 error: str | None) -> tuple[str, list[str], float | None]:
    """AUTO only when every tax-ID record agrees, is confident and needs nothing from a person."""
    if error:
        return "EXCEPTION", [f"classification failed: {error}"], None
    if not records:
        return "EXCEPTION", ["the classifier returned no result"], None
    reasons = []
    categories = list(dict.fromkeys(r.get("category") or "" for r in records))
    if len(categories) > 1:
        reasons.append("its tax IDs lead to different categories: " + ", ".join(categories))
    if set(categories) & NO_CATEGORY:
        reasons.append("no category fits")
    confidence = min(EmailProcessor._normalize_confidence(r.get("confidence")) for r in records)
    if confidence < threshold:
        reasons.append(f"confidence {confidence:.0%} is below {threshold:.0%}")
    for status, text in REVIEW_STATUSES.items():
        if any(r.get("status") == status for r in records):
            reasons.append(text)
    if any(r.get("attachment_requires_review") for r in records):
        reasons.append("an attachment could not be read")
    return ("REVIEW" if reasons else "AUTO"), reasons, confidence


def _classify_message(processor, message: dict[str, Any], text_dir: Path) -> list[dict[str, Any]]:
    attachments = getattr(processor, "attachment_processor", None)
    if attachments is not None and attachments.config.save_extracted_text_debug:
        attachments.config = replace(attachments.config, extracted_text_debug_directory=str(text_dir))
    return processor.process_batch([message], export=False, use_thread_context=True)


def classify_waiting(store, blob, processor_factory: Callable[[], Any], now_fn: Callable[[], str],
                     threshold: float, limit: int = 0) -> dict[str, int]:
    totals = {"classified": 0, "auto": 0, "review": 0, "exception": 0, "skipped_held": 0}
    waiting = sorted(store.find("cases", "status", "RECEIVED"), key=lambda c: c.get("receivedAt") or "")
    waiting = [c for c in waiting if not is_locked(c, now_fn())]
    if limit > 0:
        waiting = waiting[:limit]
    if not waiting:
        return totals

    processor = processor_factory()  # Loads the registry and LLM clients only when there is work.
    clf_run = now_fn().replace("-", "").replace(":", "")
    runs: dict[str, dict[str, dict]] = {}
    for case in waiting:
        refs = case["sourceRefs"]
        if refs["runFile"] not in runs:
            messages, _ = unwrap_run(json.loads(blob.download(refs["runFile"])))
            runs[refs["runFile"]] = {email_id(m): m for m in messages}
        message = runs[refs["runFile"]].get(case["id"])

        with tempfile.TemporaryDirectory() as tmp:
            records, error = [], None
            if message is None:
                error = f"email not found in {refs['runFile']}"
            else:
                try:
                    records = _classify_message(processor, message, Path(tmp))
                except Exception as exc:  # One bad email must not stop the rest.
                    error = f"{type(exc).__name__}: {exc}"
            route, reasons, confidence = decide_route(records, threshold, error)

            silver = f"silver/{refs['ingestRun']}/{case['id']}/"
            blob.upload_bytes(f"{silver}classification_{clf_run}.json", json.dumps(
                {"caseId": case["id"], "classifierRun": clf_run, "route": route, "routeReasons": reasons,
                 "error": error, "records": records}, ensure_ascii=False, indent=1, default=str).encode("utf-8"))
            for text in sorted(Path(tmp).glob("*.txt")):
                blob.upload_bytes(f"{silver}text/{text.name}", text.read_bytes())

        category = records[0].get("category") if records else None
        now = now_fn()
        updated = {
            **case,
            "status": "CLASSIFIED",
            "route": route,
            "routeReasons": reasons,
            "modelCategory": category,
            "confidence": confidence,
            "votes": records[0].get("model_votes", {}) if records else {},
            "finalCategory": category if route == "AUTO" else None,
            "classifiedAt": now,
            "classifierRun": clf_run,
            "error": error,
            "sourceRefs": {**refs, "silver": silver},
            "payload": {"records": [{k: v for k, v in r.items() if k not in HEAVY_FIELDS} for r in records]},
            "updatedAt": now,
        }
        try:
            store.replace("cases", updated)  # Fails if a person opened or saved it meanwhile.
        except Conflict:
            totals["skipped_held"] += 1
            continue
        audit(store, case["id"], "classified", now, run=clf_run,
              after={"route": route, "category": category, "confidence": confidence})
        totals["classified"] += 1
        totals[route.lower()] += 1
    return totals


def run(store, blob, processor_factory: Callable[[], Any], *, paused: bool, threshold: float,
        limit: int = 0, now_fn: Callable[[], str] = utcnow) -> dict[str, Any]:
    summary: dict[str, Any] = {"registered": register_runs(store, blob, now_fn())}
    summary["classification"] = "paused" if paused else classify_waiting(
        store, blob, processor_factory, now_fn, threshold, limit)
    return summary
