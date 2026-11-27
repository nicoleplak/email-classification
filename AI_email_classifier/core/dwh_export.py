"""Export for the data warehouse: emails, their data table and their actions, as CSV files in blob storage.

Three tables (see deployment/dwh/emclf_tables.sql for the Synapse side):

    EMCLF_EMAIL         one row per email: routing, categories, customer, review
    EMCLF_EMAIL_DATA    one row per value of the email's data table (core.data_rows): what, where, whose, status
    EMCLF_EMAIL_ACTION  one row per action: proposed by the rules, and final (chosen by the reviewer)

Incremental: each run exports the emails that changed (classified, reviewed, data corrected) since the last
export, with ALL their rows, so the warehouse replaces an email's rows by case_id (delete + insert). The
watermark is the document ``dwh-export-status`` in the runs collection; ``full=True`` exports everything.

Files: gold/dwh/<TABLE>/<yyyy>/<mm>/<dd>/<TABLE>_<stamp>.csv, UTF-8 with header, comma separated, every
field quoted, timestamps ISO 8601 UTC; plus gold/dwh/_manifests/<stamp>.json listing them.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

from core import senders
from core.action_rules import code_name

log = logging.getLogger(__name__)
STATUS_ID = "dwh-export-status"
PREFIX = "gold/dwh"

EMAIL_COLUMNS = [
    "case_id", "received_at", "from_address", "sender_type", "subject", "status", "route", "route_reasons",
    "model_category", "confidence", "final_category", "other_categories", "auto_categories", "no_match", "markers",
    "customer_tax_id", "customer_name", "identified_via", "customers_confirmed", "customers_possible",
    "reviewed_by", "reviewed_at", "review_outcome", "actions_outcome", "review_comment",
    "classified_at", "classifier_run", "ingest_run", "updated_at", "exported_at",
]
DATA_COLUMNS = [
    "case_id", "row_id", "type", "value", "role", "identifies_case", "checked", "method", "source_kind",
    "source_file", "source_page", "snippet", "status", "original_value", "changed_by", "changed_at", "exported_at",
]
ACTION_COLUMNS = [
    "case_id", "stage", "seq", "action", "category", "code", "code_name", "account", "spv", "account_state",
    "template", "folder", "forward_to", "for_request", "follow_up", "caveat", "exported_at",
]


def _changed_at(case: dict) -> str:
    return max(str(case.get(k) or "") for k in ("updatedAt", "reviewedAt", "classifiedAt", "createdAt"))


def _flag(value: Any) -> str:
    return "1" if value else "0"


def email_row(case: dict, now: str) -> dict:
    u = case.get("understanding") or {}
    customers = u.get("customers") or []
    confirmed = [c for c in customers if c.get("status") == "confirmed"]
    first = confirmed[0] if confirmed else {}
    return {
        "case_id": case["id"], "received_at": case.get("receivedAt"), "from_address": case.get("from"),
        "sender_type": senders.sender_type(case.get("from")), "subject": case.get("subject"),
        "status": case.get("status"), "route": case.get("route"), "route_reasons": "; ".join(case.get("routeReasons") or []),
        "model_category": case.get("modelCategory"), "confidence": case.get("confidence"),
        "final_category": case.get("finalCategory"), "other_categories": "; ".join(case.get("otherCategories") or []),
        "auto_categories": "; ".join(a.get("category", "") for a in case.get("autoCategories") or []),
        "no_match": _flag(case.get("noMatch")), "markers": "; ".join(case.get("markers") or []),
        "customer_tax_id": first.get("taxId"), "customer_name": first.get("name"),
        "identified_via": (u.get("customerFacts") or {}).get("identified_via"),
        "customers_confirmed": len(confirmed), "customers_possible": len(customers) - len(confirmed),
        "reviewed_by": (case.get("reviewedBy") or {}).get("name"), "reviewed_at": case.get("reviewedAt"),
        "review_outcome": case.get("reviewOutcome"), "actions_outcome": case.get("actionsOutcome"),
        "review_comment": case.get("reviewComment"), "classified_at": case.get("classifiedAt"),
        "classifier_run": case.get("classifierRun"), "ingest_run": (case.get("sourceRefs") or {}).get("ingestRun"),
        "updated_at": _changed_at(case), "exported_at": now,
    }


def data_rows_of(case: dict, rows: list[dict], now: str, snippets: bool = True) -> list[dict]:
    out = []
    for r in rows:
        src = r.get("source") or {}
        out.append({
            "case_id": case["id"], "row_id": r.get("id"), "type": r.get("type"), "value": r.get("value"),
            "role": r.get("role"), "identifies_case": _flag(r.get("identifiesCase")), "checked": _flag(r.get("checked")),
            "method": r.get("method"), "source_kind": src.get("kind"), "source_file": src.get("file"),
            "source_page": src.get("page"), "snippet": r.get("snippet") if snippets else None, "status": r.get("status"),
            "original_value": (r.get("original") or {}).get("value"), "changed_by": r.get("by"), "changed_at": r.get("at"),
            "exported_at": now,
        })
    return out


def action_rows_of(case: dict, now: str) -> list[dict]:
    stages = [("proposed", (case.get("understanding") or {}).get("actions") or [])]
    if case.get("status") == "REVIEWED":
        stages.append(("final", case.get("finalActions") or []))
    out = []
    for stage, actions in stages:
        for seq, a in enumerate(actions, 1):
            code = a.get("code") or next(iter(a.get("codes") or []), None)
            out.append({
                "case_id": case["id"], "stage": stage, "seq": seq, "action": a.get("do"), "category": a.get("category"),
                "code": code, "code_name": a.get("codeName") or (code_name(code) if code else None),
                "account": a.get("account"), "spv": a.get("spv"), "account_state": a.get("accountState"),
                "template": a.get("template"), "folder": a.get("folder"),
                "forward_to": "; ".join(a["to"] if isinstance(a.get("to"), list) else [a["to"]]) if a.get("to") else None,
                "for_request": a.get("forRequest"), "follow_up": _flag(a.get("followUp")), "caveat": a.get("caveat"),
                "exported_at": now,
            })
    return out


def to_csv(columns: list[str], rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "" if row.get(k) is None else row[k] for k in columns})
    return buffer.getvalue().encode("utf-8")


def export(store, upload: Callable[[str, bytes], None], *, full: bool = False, since: str | None = None,
           now_fn: Callable[[], str] | None = None, snippets: bool | None = None) -> dict[str, Any]:
    """Export the emails changed since the last export (or ``since``, or all with ``full``). Returns a summary."""
    from core.data_rows import rows_from_understanding

    now = (now_fn or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))()
    snippets = os.getenv("DWH_EXPORT_SNIPPETS", "true").strip().lower() == "true" if snippets is None else snippets
    status = store.get("runs", STATUS_ID) or {}
    mark = "" if full else (since or status.get("lastExportAt") or "")
    light = store.all("cases", ["id", "updatedAt", "reviewedAt", "classifiedAt", "createdAt", "status"])
    data_changed = {d["id"] for d in store.all("data", ["id", "updatedAt"]) if str(d.get("updatedAt") or "") >= mark}
    wanted = [c["id"] for c in light
              if c.get("status") in ("CLASSIFIED", "REVIEWED") and (_changed_at(c) >= mark or c["id"] in data_changed)]
    emails, data, actions = [], [], []
    for case_id in wanted:
        case = store.get("cases", case_id)
        if not case:
            continue
        doc = store.get("data", case_id)
        rows = doc["rows"] if doc and doc.get("rows") is not None else rows_from_understanding(case_id, case.get("understanding"))
        emails.append(email_row(case, now))
        data.extend(data_rows_of(case, rows, now, snippets))
        actions.extend(action_rows_of(case, now))
    stamp = now.replace("-", "").replace(":", "")
    day = now[:10].replace("-", "/")
    files = {}
    if emails:
        for table, columns, rows in (("EMCLF_EMAIL", EMAIL_COLUMNS, emails), ("EMCLF_EMAIL_DATA", DATA_COLUMNS, data),
                                     ("EMCLF_EMAIL_ACTION", ACTION_COLUMNS, actions)):
            name = f"{PREFIX}/{table}/{day}/{table}_{stamp}.csv"
            upload(name, to_csv(columns, rows))
            files[table] = {"file": name, "rows": len(rows)}
    summary = {"exportedAt": now, "from": mark or None, "full": full, "emails": len(emails), "files": files}
    if emails:
        upload(f"{PREFIX}/_manifests/{stamp}.json", json.dumps(summary, ensure_ascii=False, indent=1).encode("utf-8"))
    # The watermark is the export's own start: anything saved while it ran goes out next time (at most twice).
    store.upsert("runs", {**status, "id": STATUS_ID, "lastExportAt": now, "lastSummary": summary})
    log.info("DWH export: %s emails, %s", len(emails), {t: f["rows"] for t, f in files.items()})
    return summary
