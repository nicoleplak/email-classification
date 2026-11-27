"""Trigger B: find new ingest runs in bronze, open a case per email, classify waiting cases.

Two phases, every time the job runs:

1. **Register** (cheap, always): every ``bronze/<run>/emails.json`` without a
   ``runs`` marker gets one ``RECEIVED`` case per email, keyed on
   ``internetMessageId`` so a resent email never opens a second case. Emails the
   delta reports as ``removed`` are marked as gone from the mailbox.
2. **Classify** (skipped while ``CLASSIFIER_PAUSED=true``): every ``RECEIVED``
   case nobody holds is classified and saved one at a time, so a job killed by
   its timeout loses at most the email in flight. A case a person opened or saved
   meanwhile is left alone (etag check). While the model works on a case it shows
   as ``CLASSIFYING``, and ``runs/classifier-status`` says how far the run is, so
   the review app can show progress by polling (the job and the app are separate
   containers; Cosmos is what they share). A time budget stops new emails from
   being started before the job's own timeout; the rest wait for the next run.

Reviewers can work on ``RECEIVED`` cases while classification is paused.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core import senders
from core.action_rules import decide, extra_categories
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
# Progress of the current or last classifier run, in the runs container (not a timestamp, so never an ingest run).
STATUS_ID = "classifier-status"


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


def is_locked(store, case_id: str, now: str) -> bool:
    """A reviewer has the case open (lock documents expire on their own; ``until`` guards the gap)."""
    lock = store.get("locks", case_id) or {}
    return bool(lock) and str(lock.get("until", "")) > now


def received_cutoff(run: str, runs_from: str) -> str:
    """ISO time before which a mailbox email is ignored ('' for imports or no cutoff)."""
    if run.startswith("import-") or not re.fullmatch(r"\d{8}T\d{6}Z", runs_from or ""):
        return ""
    d, t = runs_from[:8], runs_from[9:15]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}T{t[:2]}:{t[2:4]}:{t[4:]}Z"


def wanted_run(run: str, runs_from: str) -> bool:
    """Imported runs always; ingest runs (named by UTC timestamp) only from ``runs_from`` on."""
    return run.startswith("import-") or not runs_from or run >= runs_from


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


def register_runs(store, blob, now: str, runs_from: str = "") -> dict[str, int]:
    totals = {"runs": 0, "new_cases": 0, "resent": 0, "removed": 0}
    for name in blob.list_names("bronze/"):
        match = RUN_FILE.match(name)
        if not match or not wanted_run(match.group(1), runs_from) or store.get("runs", match.group(1)):
            continue
        run = match.group(1)
        messages, removed = unwrap_run(json.loads(blob.download(name)))
        new = resent = gone = 0
        cutoff = received_cutoff(run, runs_from)
        for message in messages:
            # Graph delta also returns older emails that were only changed (read, moved, flagged): those
            # arrived before go-live and are not new work.
            if cutoff and str(message.get("receivedDateTime") or "") < cutoff:
                totals["older"] = totals.get("older", 0) + 1
                continue
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


NEEDS_CUSTOMER = {"request", "ask_identification"}  # actions that only make sense for a known customer


def understanding_reasons(understanding: dict[str, Any] | None) -> list[str]:
    """Extra REVIEW reasons from reading the email (business rules, Nov 2026).

    Only a tax ID or an account identifies the customer; a name or email match is complementary and is
    never a reason on its own (a name that differs from the registry owner is shown, not routed).
    The customer only matters when an action needs one: folders, forwards and activities do not.
    """
    if not understanding:
        return []
    if understanding.get("error"):
        return ["the customer details could not be read: " + understanding["error"]]
    reasons = []
    actions = understanding.get("actions") or []
    needs_customer = any(a.get("do") in NEEDS_CUSTOMER for a in actions)
    confirmed = [c for c in understanding.get("customers", []) if c.get("status") == "confirmed"]
    if needs_customer and not confirmed:
        reasons.append("no customer found in the registry by tax ID or account")
    elif any(a.get("caveat") == "account_not_identified" for a in actions):
        reasons.append("the account or portfolio (SPV) the request concerns is not identified")
    if confirmed and (understanding.get("customerFacts") or {}).get("identified_via") == "heir":
        reasons.append("the customer was identified only by an heir's tax ID or account, not the deceased debtor's")
    if understanding.get("complaintDemoted"):
        reasons.append("the complaint is not the main request: the email also asks for "
                       + str(understanding.get("principalCategory")))
    if "distress_or_threat" in (understanding.get("flags") or []):
        reasons.append("the email mentions self-harm or threatens legal action")
    return reasons


def identification_waived(understanding: dict[str, Any] | None) -> bool:
    """The classifier's own tax-ID check (no AFM / AFM not in registry) no longer decides the route when
    reading the email confirmed the customer by tax ID or account, or when no action needs a customer."""
    if not understanding or understanding.get("error"):
        return False
    actions = understanding.get("actions") or []
    confirmed = any(c.get("status") == "confirmed" for c in understanding.get("customers", []))
    return confirmed or not any(a.get("do") in NEEDS_CUSTOMER for a in actions)


def set_status(store, now: str, **fields: Any) -> None:
    store.upsert("runs", {"id": STATUS_ID, "updatedAt": now, **fields})


def classify_waiting(store, blob, processor_factory: Callable[[], Any], now_fn: Callable[[], str],
                     threshold: float, limit: int = 0,
                     understand_factory: Callable[[Any, list[dict]], Callable] | None = None,
                     budget_seconds: float = 0, clock: Callable[[], float] = time.monotonic) -> dict[str, int]:
    """``understand_factory(processor, messages)`` returns ``fn(message, records, text_dir) -> dict``.

    ``budget_seconds`` (0 = none): no new email is started once this much time has passed.
    """
    started = clock()
    totals = {"classified": 0, "auto": 0, "review": 0, "exception": 0, "skipped_held": 0, "left_waiting": 0}
    # CLASSIFYING at the start of a run means the last run was killed mid-email (the job runs one at a time).
    waiting = [*store.find("cases", "status", "RECEIVED"), *store.find("cases", "status", "CLASSIFYING")]
    waiting = sorted(waiting, key=lambda c: c.get("receivedAt") or "")
    waiting = [c for c in waiting if not is_locked(store, c["id"], now_fn())]
    if limit > 0:
        waiting = waiting[:limit]
    if not waiting:
        return totals
    progress = {"state": "running", "startedAt": now_fn(), "total": len(waiting), "done": 0, "current": None}
    set_status(store, now_fn(), **progress, phase="preparing")
    try:
        _classify_cases(store, blob, processor_factory, now_fn, threshold, understand_factory,
                        waiting, totals, progress, lambda: budget_seconds > 0 and clock() - started > budget_seconds)
    except BaseException:
        set_status(store, now_fn(), **{**progress, "state": "failed", "current": None})
        raise
    set_status(store, now_fn(), **{**progress, "state": "idle", "current": None, "finishedAt": now_fn()},
               last=totals)
    return totals


def _classify_cases(store, blob, processor_factory, now_fn, threshold, understand_factory,
                    waiting: list[dict], totals: dict[str, int], progress: dict[str, Any],
                    out_of_time: Callable[[], bool]) -> None:

    runs: dict[str, dict[str, dict]] = {}
    for case in waiting:
        run_file = case["sourceRefs"]["runFile"]
        if run_file not in runs:
            messages, _ = unwrap_run(json.loads(blob.download(run_file)))
            runs[run_file] = {email_id(m): m for m in messages}

    found = [runs[c["sourceRefs"]["runFile"]].get(c["id"]) for c in waiting]
    # Internal senders get their category by address; the registry and the model clients load only when
    # some other email is waiting.
    needs_model = [m for c, m in zip(waiting, found) if m and senders.sender_type(c.get("from")) != senders.INTERNAL]
    processor = processor_factory() if needs_model else None
    understand_fn = understand_factory(processor, needs_model) if understand_factory and processor else None
    clf_run = now_fn().replace("-", "").replace(":", "")
    for n, (case, message) in enumerate(zip(waiting, found)):
        if out_of_time():
            totals["left_waiting"] = len(waiting) - n
            break
        try:  # Shows the case as being worked on; a person who saved it meanwhile wins.
            case = store.replace("cases", {**case, "status": "CLASSIFYING", "classifyingSince": now_fn()})
        except Conflict:
            totals["skipped_held"] += 1
            progress["done"] += 1
            continue
        progress["current"] = case["id"]
        set_status(store, now_fn(), **progress, phase="classifying")
        try:
            if senders.sender_type(case.get("from")) == senders.INTERNAL:
                _classify_internal(store, blob, now_fn, clf_run, case, totals)
            else:
                _classify_one(store, blob, processor, understand_fn, threshold, now_fn, clf_run, case, message, totals)
        except BaseException:
            try:  # Back to the queue for the next run, unless a person saved it meanwhile.
                store.replace("cases", {**case, "status": "RECEIVED"})
            except Conflict:
                pass
            raise
        progress["done"] += 1


def _classify_internal(store, blob, now_fn, clf_run, case: dict, totals: dict[str, int]) -> None:
    """A doValue sender (not on the retail support list): the internal category by address, its actions from
    the rule table, handled automatically. No model call, no attachment reading, no customer lookup."""
    category = senders.internal_category()
    actions = decide([category], {}, {})
    reason = "sender at an internal domain: category by address, no model call"
    records = [{"category": category, "confidence": 1.0, "status": "internal_sender", "reasoning": reason}]
    understanding = {"principalCategory": category, "otherRequests": [], "customers": [], "actions": actions,
                     "flags": [], "evidence": [], "analysis": reason, "senderRule": True}
    silver = f"silver/{case['sourceRefs']['ingestRun']}/{case['id']}/"
    blob.upload_bytes(f"{silver}classification_{clf_run}.json", json.dumps(
        {"caseId": case["id"], "classifierRun": clf_run, "route": "AUTO", "routeReasons": [], "error": None,
         "records": records, "understanding": understanding}, ensure_ascii=False, indent=1).encode("utf-8"))
    now = now_fn()
    updated = {**case, "status": "CLASSIFIED", "route": "AUTO", "routeReasons": [], "modelCategory": category,
               "confidence": 1.0, "votes": {}, "finalCategory": category, "autoCategories": [], "otherCategories": [],
               "classifiedAt": now, "classifierRun": clf_run, "classifiedBy": "sender_rule", "error": None,
               "sourceRefs": {**case["sourceRefs"], "silver": silver}, "payload": {"records": records},
               "understanding": understanding, "updatedAt": now}
    try:
        store.replace("cases", updated)
    except Conflict:
        totals["skipped_held"] += 1
        return
    audit(store, case["id"], "classified", now, run=clf_run,
          after={"route": "AUTO", "category": category, "confidence": 1.0, "by": "sender_rule"})
    totals["classified"] += 1
    totals["auto"] += 1
    totals["internal"] = totals.get("internal", 0) + 1


def _classify_one(store, blob, processor, understand_fn, threshold, now_fn, clf_run,
                  case: dict, message: dict | None, totals: dict[str, int]) -> None:
    refs = case["sourceRefs"]
    with tempfile.TemporaryDirectory() as tmp:
        records, error, understanding = [], None, None
        if message is None:
            error = f"email not found in {refs['runFile']}"
        else:
            try:
                records = _classify_message(processor, message, Path(tmp))
            except Exception as exc:  # One bad email must not stop the rest.
                error = f"{type(exc).__name__}: {exc}"
        if understand_fn and not error:
            try:
                understanding = understand_fn(message, records, Path(tmp))
            except Exception as exc:  # The classification still counts; a person reads the details.
                understanding = {"error": f"{type(exc).__name__}: {exc}"}
        route, reasons, confidence = decide_route(records, threshold, error)
        if route == "REVIEW" and identification_waived(understanding):
            reasons = [r for r in reasons if r not in REVIEW_STATUSES.values()]
            route = "REVIEW" if reasons else "AUTO"
        extra = understanding_reasons(understanding)
        if extra and route == "AUTO":
            route = "REVIEW"
        reasons += extra

        silver = f"silver/{refs['ingestRun']}/{case['id']}/"
        blob.upload_bytes(f"{silver}classification_{clf_run}.json", json.dumps(
            {"caseId": case["id"], "classifierRun": clf_run, "route": route, "routeReasons": reasons,
             "error": error, "records": records, "understanding": understanding},
            ensure_ascii=False, indent=1, default=str).encode("utf-8"))
        # Attachment text plus its sidecar (the real file name): the review app highlights evidence in it.
        for text in sorted([*Path(tmp).glob("*.txt"), *Path(tmp).glob("*.json")]):
            blob.upload_bytes(f"{silver}text/{text.name}", text.read_bytes())

    category = records[0].get("category") if records else None
    if understanding and understanding.get("principalCategory") and (
            understanding.get("complaintDemoted") or understanding.get("principalByRule")):
        # The request, not the complaint, leads (it goes to review); a board member named makes it Διοίκηση.
        category = understanding["principalCategory"]
    # Second and third categories found with 80%+ certainty: part of the case, final when it is automatic.
    auto = extra_categories((records[0] if records else {}).get("model_other_categories") or {}, category)
    # Categories added by rule (an authorization attached, ...) count like sure ones.
    for rule in (understanding or {}).get("ruleCategories") or []:
        if rule["category"] != category and rule["category"] not in [a["category"] for a in auto]:
            auto.append({"category": rule["category"], "confidence": 1.0, "byRule": True})
    if understanding and understanding.get("principalByRule") and (records[0] if records else {}).get("category") \
            not in (None, "No Match Found", category) and records[0]["category"] not in [a["category"] for a in auto]:
        auto.append({"category": records[0]["category"], "confidence": confidence, "byRule": False})
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
        "autoCategories": auto,
        "otherCategories": [a["category"] for a in auto] if route == "AUTO" else [],
        "classifiedAt": now,
        "classifierRun": clf_run,
        "error": error,
        "sourceRefs": {**refs, "silver": silver},
        "payload": {"records": [{k: v for k, v in r.items() if k not in HEAVY_FIELDS} for r in records]},
        "understanding": understanding,
        # Marks for the list and filters, e.g. ERB when Eurobank is named in the email or an attachment.
        "markers": list((understanding or {}).get("markers") or []),
        "updatedAt": now,
    }
    try:
        store.replace("cases", updated)  # Fails if a person opened or saved it meanwhile.
    except Conflict:
        totals["skipped_held"] += 1
        return
    audit(store, case["id"], "classified", now, run=clf_run,
          after={"route": route, "category": category, "confidence": confidence})
    totals["classified"] += 1
    totals[route.lower()] += 1


def run(store, blob, processor_factory: Callable[[], Any], *, paused: bool, threshold: float,
        limit: int = 0, now_fn: Callable[[], str] = utcnow, runs_from: str = "",
        understand_factory: Callable[[Any, list[dict]], Callable] | None = None,
        budget_seconds: float = 0) -> dict[str, Any]:
    summary: dict[str, Any] = {"registered": register_runs(store, blob, now_fn(), runs_from)}
    summary["classification"] = "paused" if paused else classify_waiting(
        store, blob, processor_factory, now_fn, threshold, limit, understand_factory, budget_seconds)
    return summary
