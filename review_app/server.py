"""Review app: one process serves the page and the API (Container App ca-emclf-llm-gr, 1 replica).

    python review_app/server.py            # http://127.0.0.1:8765 (PORT, HOST to change)

Reads cases from the case store the classifier writes (Cosmos in Azure), and email bodies, original
messages and attachments from blob storage. Stdlib only, so the image needs nothing new.

Sign-in (REVIEW_AUTH):
- demo   name + email + the shared access code (REVIEW_ACCESS_CODE). Each browser is its own user,
         remembered by a signed cookie (REVIEW_SESSION_SECRET). Records store the user id, name and email;
         when Entra arrives, users are matched by that email.
- dev    name + email, no code; only listens on 127.0.0.1. For local work.
Presence ("who has what open") is held in memory: run exactly one replica.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

HERE = Path(__file__).resolve().parent
APP = HERE.parent / "AI_email_classifier"
sys.path.insert(0, str(APP))

sys.path.insert(0, str(HERE))

from data.case_store import Conflict, open_store  # noqa: E402
from highlight import STYLE as HL_STYLE  # noqa: E402
from highlight import mark_html, text_page  # noqa: E402
import metrics  # noqa: E402

AUTH = os.getenv("REVIEW_AUTH", "dev").strip().lower()
ACCESS_CODE = os.getenv("REVIEW_ACCESS_CODE", "")
def _session_secret() -> bytes:
    """Azure: REVIEW_SESSION_SECRET (a Container App secret). Locally: a key kept in a git-ignored file,
    so restarting the server does not sign everyone out."""
    if os.getenv("REVIEW_SESSION_SECRET"):
        return os.environ["REVIEW_SESSION_SECRET"].encode()
    path = HERE / ".session_secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


SESSION_SECRET = _session_secret()
FETCH_CRON = os.getenv("FETCH_CRON", "").strip()  # the job's schedule (UTC); empty = manual only
SESSION_DAYS = 180
LOCK_SECONDS = 300
PRESENCE_TTL = 40
CASE_CACHE_SECONDS = 5
MAX_BODY = 64_000
STATIC = HERE / "static"
CATEGORIES = [c["Categories"].strip() for c in json.loads((APP / "inputs" / "categories.json").read_text("utf-8"))]
LIGHT = ["id", "subject", "from", "receivedAt", "status", "route", "routeReasons", "modelCategory", "noMatch",
         "otherCategories", "reviewOutcome", "actionsOutcome",
         "finalCategory", "confidence", "reviewedBy", "reviewedAt", "classifiedAt", "mailboxState", "sourceRefs"]
INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "text/plain"}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_in(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- storage
STORE = None
_blob = None


def store():
    global STORE
    if STORE is None:
        STORE = open_store()
    return STORE


def blob():
    global _blob
    if _blob is None:
        from data import blob_output

        _blob = blob_output
    return _blob


class CaseCache:
    """All cases' list fields, refreshed at most every few seconds (one replica, a few thousand cases)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.at = 0.0
        self.items: list[dict] = []

    def get(self) -> list[dict]:
        with self.lock:
            if time.monotonic() - self.at > CASE_CACHE_SECONDS:
                self.items = store().all("cases", LIGHT)
                self.at = time.monotonic()
            return self.items

    def drop(self) -> None:
        with self.lock:
            self.at = 0.0


CASES = CaseCache()
_runs: dict[str, dict] = {}
_runs_lock = threading.Lock()


def run_message(case: dict) -> dict | None:
    """The email as ingested (Graph shape), from its bronze run file; small LRU over run files."""
    from core.run_classifier import email_id, unwrap_run

    run_file = case["sourceRefs"]["runFile"]
    with _runs_lock:
        if run_file not in _runs:
            messages, _ = unwrap_run(json.loads(blob().download(run_file)))
            if len(_runs) > 20:
                _runs.pop(next(iter(_runs)))
            _runs[run_file] = {email_id(m): m for m in messages}
        return _runs[run_file].get(case["id"])


# ---------------------------------------------------------------- users and sessions
def _sign(value: str) -> str:
    return hmac.new(SESSION_SECRET, value.encode(), hashlib.sha256).hexdigest()


def make_session(user_id: str) -> str:
    expiry = str(int(time.time()) + SESSION_DAYS * 86400)
    return f"{user_id}|{expiry}|{_sign(user_id + '|' + expiry)}"


def read_session(token: str) -> str | None:
    try:
        user_id, expiry, signature = token.split("|")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(user_id + "|" + expiry)) or int(expiry) < time.time():
        return None
    return user_id


class MetricsCache:
    """The fields the Metrics view needs from every case, read at most every 30 s (understanding is large)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.at = 0.0
        self.items: list[dict] = []

    def get(self) -> list[dict]:
        with self.lock:
            if time.monotonic() - self.at > 30:
                self.items = store().all("cases", metrics.FIELDS)
                self.at = time.monotonic()
            return self.items


METRICS = MetricsCache()


def list_items() -> list[dict]:
    """The email list, with what its filters need: category and actions outcome, review reasons.

    Reviews saved since Nov 2026 carry their outcome; older ones get it from the metrics read (30 s cache).
    """
    items = CASES.get()
    missing = any(i.get("status") == "REVIEWED" and not i.get("actionsOutcome") for i in items)
    older = {c["id"]: metrics.case_facts(c) for c in METRICS.get()} if missing else {}
    out = []
    for item in items:
        facts = older.get(item["id"]) or {}
        out.append({**item, "outcome": metrics.outcome(item),
                    "actionsOutcome": item.get("actionsOutcome") or facts.get("actionsOutcome"),
                    "reasonKeys": sorted({metrics.reason_key(r) for r in item.get("routeReasons") or []})})
    return out
METRIC_RANGES = {"7": 7, "30": 30, "90": 90, "all": 0}

_users: dict[str, dict] = {}


def user_doc(user_id: str) -> dict | None:
    if user_id not in _users:
        doc = store().get("users", user_id)
        if doc is None:
            return None
        _users[user_id] = doc
    return _users[user_id]


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_attempts: dict[str, list[float]] = {}


def too_many_attempts(ip: str) -> bool:
    recent = [t for t in _attempts.get(ip, []) if t > time.time() - 600]
    _attempts[ip] = recent
    return len(recent) >= 10


def login(body: dict, ip: str, current: str | None) -> tuple[dict | None, str | None]:
    """Create (or update) this browser's user. Returns (user, error)."""
    name = " ".join(str(body.get("name") or "").split())[:80]
    email = str(body.get("email") or "").strip().lower()[:120]
    if not name or not EMAIL_RE.match(email):
        return None, "name_email"
    if AUTH == "demo":
        if too_many_attempts(ip):
            return None, "too_many"
        if not ACCESS_CODE or not hmac.compare_digest(str(body.get("code") or ""), ACCESS_CODE):
            _attempts.setdefault(ip, []).append(time.time())
            return None, "code"
    user_id = current if current and current.startswith(("demo-", "dev-")) else f"{AUTH}-{uuid.uuid4().hex}"
    existing = user_doc(user_id) or {}
    doc = {**existing, "id": user_id, "name": name, "email": email, "kind": AUTH,
           "createdAt": existing.get("createdAt") or now(), "lastSeen": now()}
    doc = store().upsert("users", doc)
    _users[user_id] = doc
    return doc, None


def public_user(doc: dict) -> dict:
    return {"id": doc["id"], "name": doc.get("name"), "email": doc.get("email")}


# ---------------------------------------------------------------- presence and locks
_presence: dict[str, dict] = {}  # user id -> {name, caseId, at}
_presence_lock = threading.Lock()


def touch(user: dict, case_id: str | None) -> list[dict]:
    with _presence_lock:
        _presence[user["id"]] = {"name": user.get("name"), "caseId": case_id, "at": time.time()}
        cutoff = time.time() - PRESENCE_TTL
        for key in [k for k, v in _presence.items() if v["at"] < cutoff]:
            _presence.pop(key)
        return [{"userId": k, "name": v["name"], "caseId": v["caseId"]} for k, v in _presence.items()]


def take_lock(user: dict, case_id: str) -> dict:
    """Hold the case while it is open; someone else's live lock is reported, not taken over."""
    lock = store().get("locks", case_id)
    if lock and lock.get("holder") != user["id"] and str(lock.get("until", "")) > now():
        return {"held": False, "holder": lock.get("holderName")}
    store().upsert("locks", {"id": case_id, "holder": user["id"], "holderName": user.get("name"),
                             "until": _utc_in(LOCK_SECONDS), "ttl": LOCK_SECONDS})
    return {"held": True}


def release_lock(user: dict, case_id: str) -> None:
    lock = store().get("locks", case_id)
    if lock and lock.get("holder") == user["id"]:
        store().delete("locks", case_id)


# ---------------------------------------------------------------- cases
def case_detail(case_id: str) -> dict | None:
    case = store().get("cases", case_id)
    if case is None:
        return None
    events = sorted(store().find("audit", "caseId", case_id), key=lambda e: e.get("at") or "")
    message = run_message(case) or {}
    silver = (case.get("sourceRefs") or {}).get("silver")
    has_text = bool(silver) and any(n.endswith(".txt") for n in blob().list_names(silver + "text/"))
    read = {r.get("filename") for rec in (case.get("payload") or {}).get("records", [])[:1]
            for r in rec.get("attachment_records") or [] if r.get("status") == "ANALYZED"}
    attachments = [
        {
            "n": n,
            "name": a.get("name"),
            "contentType": a.get("contentType"),
            "size": a.get("size") or a.get("decoded_size"),
            "inline": bool(a.get("isInline")),
            "viewable": _content_type(a) in INLINE_TYPES,
            "hasText": has_text and a.get("name") in read,  # the classifier read it, so a text view exists
        }
        for n, a in enumerate(message.get("attachments") or [])
        if a.get("blob_name")
    ]
    lock = store().get("locks", case_id)
    return {
        "case": {k: v for k, v in case.items() if not k.startswith("_") or k == "_etag"},
        "message": {
            "from": message.get("from"),
            "to": message.get("toRecipients"),
            "cc": message.get("ccRecipients"),
            "subject": message.get("subject"),
            "received": message.get("receivedDateTime"),
            "original": "msg" if message.get("msg_blob_path") else ("eml" if message.get("eml_blob_path") else None),
        },
        "attachments": attachments,
        "events": [{k: e.get(k) for k in ("at", "by", "byName", "action", "before", "after", "comment")} for e in events],
        "lock": {"holderName": lock.get("holderName"), "holder": lock.get("holder")}
        if lock and str(lock.get("until", "")) > now() else None,
    }


def reset_review(user: dict, case_id: str, body: dict) -> tuple[int, dict]:
    """Undo a review: the email goes back to the 'to review' queue; the audit log keeps what it was."""
    case = store().get("cases", case_id)
    if case is None:
        return 404, {"error": "not_found"}
    if case.get("status") != "REVIEWED":
        return 400, {"error": "not_reviewed"}
    if body.get("_etag") != case.get("_etag"):
        return 409, {"error": "changed", "case": case_detail(case_id)}
    fields = ("status", "route", "finalCategory", "noMatch", "otherCategories", "finalActions", "reviewComment",
              "reviewedBy", "reviewedAt")
    before = {k: case.get(k) for k in fields}
    classified = bool(case.get("classifiedAt"))
    reason = f"review reset by {user.get('name')}"
    updated = {
        **case,
        # Classified emails return as REVIEW (even if they were AUTO); unclassified ones wait for the classifier.
        "status": "CLASSIFIED" if classified else "RECEIVED",
        "route": "REVIEW" if classified else None,
        "routeReasons": [*(r for r in case.get("routeReasons") or [] if not r.startswith("review reset by")), reason]
        if classified else [],
        "finalCategory": None,
        "noMatch": False,
        "otherCategories": [],
        "finalActions": [],
        "reviewComment": "",
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewOutcome": None,
        "actionsOutcome": None,
        "updatedAt": now(),
    }
    try:
        saved = store().replace("cases", updated)
    except Conflict:
        return 409, {"error": "changed", "case": case_detail(case_id)}
    store().create("audit", {"id": uuid.uuid4().hex, "caseId": case_id, "at": now(), "by": user["id"],
                             "byName": user.get("name"), "action": "reset", "before": before,
                             "after": {k: saved.get(k) for k in ("status", "route")}})
    CASES.drop()
    return 200, {"ok": True}


def _cron_field(spec: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for part in spec.split(","):
        part, _, step = part.partition("/")
        first, last = (low, high) if part == "*" else (int(part.split("-")[0]), int(part.split("-")[-1]))
        values.update(range(first, last + 1, int(step or 1)))
    return values


def next_run(cron: str, after: datetime) -> datetime | None:
    """Next start of a 5-field cron (UTC), standard day-of-month / day-of-week rules; None if unparsable."""
    try:
        minute, hour, dom, month, dow = cron.split()
        minutes, hours = _cron_field(minute, 0, 59), _cron_field(hour, 0, 23)
        days, months = _cron_field(dom, 1, 31), _cron_field(month, 1, 12)
        weekdays = {d % 7 for d in _cron_field(dow, 0, 7)}
    except ValueError:
        return None
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 8):  # a week and a day is enough for any weekly schedule
        dom_ok, dow_ok = t.day in days, t.isoweekday() % 7 in weekdays
        day_ok = (dom_ok or dow_ok) if dom != "*" and dow != "*" else (dom_ok and dow_ok)
        if t.minute in minutes and t.hour in hours and t.month in months and day_ok:
            return t
        t += timedelta(minutes=1)
    return None


def _run_time(run_id: str) -> str | None:
    try:
        stamp = datetime.strptime(run_id.removeprefix("import-"), "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


CLASSIFIER_STALE_SECONDS = 900  # no word from a "running" classifier for this long: the job died


def classifier_info() -> dict:
    """Progress of the classifier job (it writes runs/classifier-status as it goes; see core/run_classifier)."""
    from core.run_classifier import STATUS_ID

    doc = store().get("runs", STATUS_ID) or {}
    try:
        updated = datetime.strptime(doc.get("updatedAt", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated).total_seconds()
    except ValueError:
        age = float("inf")
    return {
        "running": doc.get("state") == "running" and age < CLASSIFIER_STALE_SECONDS,
        "phase": doc.get("phase"),
        "done": doc.get("done", 0),
        "total": doc.get("total", 0),
        "current": doc.get("current"),
        "finishedAt": doc.get("finishedAt"),
    }


def ingest_info() -> dict:
    """For the clock in the top bar: how emails arrive, when they last did, when they next will."""
    runs = [r for r in store().all("runs") if _run_time(r.get("id", ""))]
    last = max(runs, key=lambda r: _run_time(r["id"]), default=None)
    upcoming = next_run(FETCH_CRON, datetime.now(timezone.utc)) if FETCH_CRON else None
    return {
        "mode": "schedule" if FETCH_CRON else "manual",
        "cron": FETCH_CRON or None,
        "nextRun": upcoming.strftime("%Y-%m-%dT%H:%M:%SZ") if upcoming else None,
        "lastRun": {"at": _run_time(last["id"]), "emails": last.get("emails"), "newCases": last.get("newCases"),
                    "imported": last["id"].startswith("import-")} if last else None,
    }


ACTION_KINDS = {"request", "portal_referral", "ask_identification", "manual", "forward", "reply", "bank_referral",
                "activity", "no_action", "outlook_folder"}
GENERIC_ACTIONS = [
    {"do": "reply", "template": "received"},
    {"do": "reply", "template": "in_progress"},
    {"do": "portal_referral", "template": "portal"},
    {"do": "ask_identification", "template": "need_more_info", "missing": ["afm", "account"]},
    {"do": "bank_referral", "template": "erb_branch"},
    {"do": "manual"},
    {"do": "no_action"},
]


def _option(rule: dict) -> dict:
    """One pickable action from a rule: a request carries its open-case code (the _cust one only for closed cases)."""
    from core.action_rules import code_name

    if rule["do"] != "request":
        return {k: rule[k] for k in ("do", "codes", "to", "folder", "template") if rule.get(k)}
    code = (rule.get("codes") or [rule.get("open")])[0]
    return {"do": "request", "code": code, "codes": [code], "openCode": code, "closedCode": rule.get("closed"),
            "codeName": code_name(code)}


def action_catalog() -> dict:
    """Every action the rule table allows, per category (inputs/action_rules.json), plus general ones."""
    from core.action_rules import RULES

    catalog: dict[str, list[dict]] = {}
    for category, spec in RULES.items():
        seen, options = set(), []
        for rule in (spec or {}).get("rules", []) if isinstance(spec, dict) else []:
            if rule.get("do") not in ACTION_KINDS:
                continue
            option = _option(rule)
            key = json.dumps(option, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                options.append(option)
        if options:
            catalog[category] = options
    return {"byCategory": catalog, "general": GENERIC_ACTIONS}


def reply_templates() -> dict:
    """Template labels and texts for the page (inputs/reply_templates.json)."""
    from core.action_rules import REPLIES, render_reply

    return {key: {"label": spec["label"], "name": spec["name"], "text": render_reply(key, ["afm", "account"])}
            for key, spec in REPLIES["templates"].items()}


def clean_actions(raw) -> tuple[list[dict], str | None]:
    """The reviewer's chosen actions, kept to known kinds and short plain values."""
    from core.action_rules import REPLIES

    if raw is None:
        return [], None
    if not isinstance(raw, list) or len(raw) > 20:
        return [], "actions"
    out = []
    text = lambda v: str(v)[:120]  # noqa: E731
    for item in raw:
        if not isinstance(item, dict) or item.get("do") not in ACTION_KINDS:
            return [], "actions"
        out.append({
            "do": item["do"],
            "category": item.get("category") if item.get("category") in CATEGORIES else None,
            "codes": [text(c) for c in (item.get("codes") or [])][:10],
            "code": text(item["code"]) if item.get("code") else None,
            "open": text(item["open"]) if item.get("open") else None,
            "closed": text(item["closed"]) if item.get("closed") else None,
            "to": [text(t) for t in ([item["to"]] if isinstance(item.get("to"), str) else item.get("to") or [])][:5],
            "account": text(item["account"]) if item.get("account") else None,
            "spv": text(item["spv"]) if item.get("spv") else None,
            "accountState": item.get("accountState") if item.get("accountState") in ("open", "closed", "unknown") else None,
            "folder": text(item["folder"]) if item.get("folder") else None,
            "template": item.get("template") if item.get("template") in REPLIES["templates"] else None,
            "source": "suggested" if item.get("source") == "suggested" else "added",
        })
    return out, None


def save_review(user: dict, case_id: str, body: dict) -> tuple[int, dict]:
    case = store().get("cases", case_id)
    if case is None:
        return 404, {"error": "not_found"}
    if body.get("_etag") != case.get("_etag"):
        return 409, {"error": "changed", "case": case_detail(case_id)}
    final = str(body.get("finalCategory") or "").strip()
    # "No Match Found" is a category of its own (manual handling): no other category has to be picked.
    no_match = bool(body.get("noMatch")) or final == metrics.NO_MATCH
    if no_match:
        final = metrics.NO_MATCH
    elif final not in CATEGORIES:
        return 400, {"error": "category"}
    others = list(dict.fromkeys(c for c in body.get("otherCategories") or [] if c in CATEGORIES and c != final))[:5]
    actions, error = clean_actions(body.get("finalActions"))
    if error:
        return 400, {"error": error}
    fields = ("status", "finalCategory", "otherCategories", "finalActions", "reviewComment")
    before = {k: case.get(k) for k in fields}
    updated = {
        **case,
        "status": "REVIEWED",
        "finalCategory": final,
        "noMatch": no_match,
        "otherCategories": others,
        "finalActions": actions,
        "reviewComment": str(body.get("comment") or "")[:2000],
        "reviewedBy": public_user(user),
        "reviewedAt": now(),
        "updatedAt": now(),
        "reviewOutcome": None,
        "actionsOutcome": None,
    }
    # Stored with the review, so the email list can filter on them without reading the proposals.
    updated["reviewOutcome"] = metrics.outcome(updated)
    updated["actionsOutcome"] = metrics.actions_outcome(updated)
    try:
        saved = store().replace("cases", updated)
    except Conflict:
        return 409, {"error": "changed", "case": case_detail(case_id)}
    after = {k: saved.get(k) for k in fields}
    # The system's category and actions at the time, so the history can show what was changed.
    after["modelCategory"] = saved.get("modelCategory")
    proposed = (saved.get("understanding") or {}).get("actions") or []
    after["proposedActions"] = [{k: a.get(k) for k in ("do", "code", "account", "template", "folder") if a.get(k)}
                                for a in proposed]
    store().create("audit", {"id": uuid.uuid4().hex, "caseId": case_id, "at": now(), "by": user["id"],
                             "byName": user.get("name"), "action": "reviewed", "before": before, "after": after})
    release_lock(user, case_id)
    CASES.drop()
    return 200, {"ok": True, "_etag": saved.get("_etag")}


STATUS_TEXT = {"REVIEWED": "Ελέγχθηκε", "CLASSIFYING": "Χωρίς ταξινόμηση", "RECEIVED": "Χωρίς ταξινόμηση"}
ROUTE_TEXT = {"AUTO": "Αυτόματα", "REVIEW": "Προς έλεγχο", "EXCEPTION": "Σφάλμα (έλεγχος)"}
OUTCOME_TEXT = {"accepted": "Σωστή", "changed": "Άλλαξε", "none_fits": "No Match Found", "same": "Χωρίς αλλαγή"}
REASON_TEXT = {
    "low_confidence": "Χαμηλή βεβαιότητα", "no_tax_id": "Δεν βρέθηκε ΑΦΜ", "tax_id_unknown": "Ο ΑΦΜ δεν είναι στο μητρώο",
    "split_categories": "ΑΦΜ με διαφορετικές κατηγορίες", "no_category": "Καμία κατηγορία δεν ταιριάζει",
    "attachment_unread": "Συνημμένο δεν διαβάστηκε", "failed": "Η ταξινόμηση απέτυχε", "no_result": "Χωρίς αποτέλεσμα",
    "name_mismatch": "Το όνομα διαφέρει", "possible_customer": "Μόνο πιθανός πελάτης", "no_customer": "Δεν βρέθηκε πελάτης",
    "details_unread": "Στοιχεία πελάτη δεν διαβάστηκαν", "email_missing": "Λείπει το email", "reset": "Επαναφορά ελέγχου",
    "account_unknown": "Δεν ταυτοποιήθηκε λογαριασμός/SPV", "complaint_secondary": "Παράπονο μαζί με άλλο αίτημα",
    "distress": "Αυτοτραυματισμός ή απειλή νομικών μέτρων", "other": "Άλλο",
}
ACTION_TEXT = {"request": "Αίτημα Qualco", "portal_referral": "Παραπομπή στο Portal", "ask_identification": "Need more Info",
               "manual": "Χειρισμός από το προσωπικό", "forward": "Προώθηση", "reply": "Απάντηση",
               "bank_referral": "Παραπομπή σε Eurobank", "activity": "Activity Qualco", "no_action": "Καμία ενέργεια",
               "outlook_folder": "Φάκελος Outlook"}


def action_line(action: dict) -> str:
    """One action as a line of plain Greek, for the Excel export."""
    from core.action_rules import REPLIES, code_name

    text = ACTION_TEXT.get(action.get("do"), action.get("do") or "")
    code = action.get("code") or next(iter(action.get("codes") or []), None)
    if action.get("do") in ("request", "activity") and code:
        text += f" {code} {code_name(code)}".rstrip()
    if action.get("account"):
        text += f" (λογ. {action['account']}{', ' + action['spv'] if action.get('spv') else ''})"
    if action.get("to"):
        text += ": " + ", ".join(action["to"])
    if action.get("folder"):
        text += f": {action['folder']}"
    if action.get("template") in REPLIES["templates"]:
        text += f": {REPLIES['templates'][action['template']]['label']}"
    return text


def _people(items) -> str:
    return ", ".join(((x or {}).get("emailAddress") or {}).get("address", "") for x in items or [] if x)


def export_xlsx(ids: list[str]) -> bytes:
    """The listed emails as an Excel sheet: email, categories, actions, reviewer, status."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    columns = [
        ("Λήψη (ώρα Ελλάδας)", 17), ("Από", 28), ("Προς", 28), ("Κοιν.", 28), ("Θέμα", 40), ("Κατάσταση", 16),
        ("Δρομολόγηση", 16), ("Λόγοι ελέγχου", 34), ("Κατηγορία συστήματος", 30), ("Βεβαιότητα", 11),
        ("Τελική κατηγορία", 30), ("Επιπλέον κατηγορίες", 30), ("Κατηγορία: αποτέλεσμα", 18),
        ("Προτεινόμενες ενέργειες", 50), ("Τελικές ενέργειες", 50), ("Ενέργειες: αποτέλεσμα", 18),
        ("Ελεγκτής", 22), ("Ημ. ελέγχου (ώρα Ελλάδας)", 17), ("Σχόλιο", 40), ("ID", 26),
    ]
    book = Workbook()
    sheet = book.active
    sheet.title = "Emails"
    sheet.append([name for name, _ in columns])
    for n, (_, width) in enumerate(columns, 1):
        sheet.column_dimensions[get_column_letter(n)].width = width
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="155E8F")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    wanted = set(ids)
    rows = sorted((c for c in (store().get("cases", i) for i in wanted) if c), key=lambda c: c.get("receivedAt") or "",
                  reverse=True)
    for case in rows:
        try:
            message = run_message(case) or {}
        except Exception:  # noqa: BLE001 - the sheet still has everything from the case itself
            message = {}
        reviewed = case.get("status") == "REVIEWED"
        proposed = (case.get("understanding") or {}).get("actions") or []
        reasons = sorted({metrics.reason_key(r) for r in case.get("routeReasons") or []})
        sheet.append([
            metrics.athens_time(case.get("receivedAt")),
            case.get("from") or "",
            _people(message.get("toRecipients")),
            _people(message.get("ccRecipients")),
            case.get("subject") or "",
            STATUS_TEXT.get(case.get("status")) or ROUTE_TEXT.get(case.get("route") or "", "Χωρίς ταξινόμηση"),
            ROUTE_TEXT.get(case.get("route") or "", ""),
            "; ".join(REASON_TEXT.get(r, r) for r in reasons),
            case.get("modelCategory") or "",
            None if case.get("confidence") is None else round(float(case["confidence"]), 2),
            (metrics.NO_MATCH if case.get("noMatch") else case.get("finalCategory") or "") if reviewed else "",
            ", ".join(case.get("otherCategories") or [a["category"] for a in case.get("autoCategories") or []]),
            OUTCOME_TEXT.get(metrics.outcome(case) or "", ""),
            "\n".join(action_line(a) for a in proposed),
            "\n".join(action_line(a) for a in case.get("finalActions") or []) if reviewed else "",
            OUTCOME_TEXT.get(metrics.actions_outcome(case) or "", "") if reviewed else "",
            ((case.get("reviewedBy") or {}).get("name") or "") if reviewed else "",
            metrics.athens_time(case.get("reviewedAt")) if reviewed else None,
            case.get("reviewComment") or "",
            case["id"],
        ])
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        row[0].number_format = row[17].number_format = "dd/mm/yyyy hh:mm"
        row[9].number_format = "0%"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _content_type(attachment: dict) -> str:
    kind = (attachment.get("contentType") or "").split(";")[0].strip().lower()
    if not kind or kind == "application/octet-stream":
        kind = mimetypes.guess_type(attachment.get("name") or "")[0] or "application/octet-stream"
    return kind


def _disposition(kind: str, name: str) -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


CID_RE = re.compile(r"""(["'(])cid:([^"')\s]+)""", re.IGNORECASE)
ID_TITLES = {"afm": "ΑΦΜ", "account": "Δανειακός λογαριασμός", "contract": "Αρ. σύμβασης", "payment_code": "Κωδικός πληρωμής",
             "adt": "Αρ. ταυτότητας", "iban": "IBAN", "phone": "Τηλέφωνο", "case_ref": "Αρ. υπόθεσης", "email": "Email"}


def evidence_terms(case: dict, file: str | None = None) -> list[tuple[str, str, str]]:
    """What to mark in one document: the email body (file=None) or one attachment (its file name).

    Customer details are marked wherever they appear; quotes only in the document they were taken from.
    """
    from core.action_rules import REASONS

    u = case.get("understanding") or {}
    terms: list[tuple[str, str, str]] = []
    for e in u.get("extracted") or []:
        terms.append((e["value"], "id", f"{ID_TITLES.get(e['type'], e['type'])} · στοιχείο πελάτη"))
    for p in u.get("people") or []:
        if p.get("principal") or p.get("role") in ("debtor", "co_debtor", "deceased_debtor", "heir"):
            terms.append((p["name"], "id", "Πρόσωπο · στοιχείο πελάτη"))

    def here(where: dict) -> bool:
        return where.get("file") == file if file else where.get("kind") in ("body", "subject")

    for e in u.get("evidence") or []:
        if not here(e.get("where") or {}):
            continue
        if e["supports"] == "category":
            terms.append((e["quote"], "class", f"Τεκμήριο κατηγορίας: {case.get('modelCategory') or ''}"))
        else:
            terms.append((e["quote"], "action", REASONS.get(f"{e.get('flag')}=true", "Τεκμήριο ενέργειας")))
    if file:  # phrases the attachment reader itself flagged as supporting the category
        for record in (case.get("payload") or {}).get("records", [])[:1]:
            for item in record.get("attachment_records") or []:
                if item.get("filename") == file:
                    terms += [(q, "class", "Τεκμήριο κατηγορίας (από το συνημμένο)") for q in item.get("evidence_phrases") or []]
    return terms


def attachment_text(case: dict, name: str) -> str | None:
    """The attachment's OCR text the classifier saved in silver, found through its sidecar (real file name)."""
    prefix = ((case.get("sourceRefs") or {}).get("silver") or "") + "text/"
    if prefix == "text/":
        return None
    names = blob().list_names(prefix)
    for sidecar in (n for n in names if n.endswith(".json")):
        if json.loads(blob().download(sidecar)).get("filename") == name:
            text = sidecar[:-5] + ".txt"
            return blob().download(text).decode("utf-8") if text in names else None
    # Runs before sidecars existed: the reader names the file after the attachment's own name.
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("_") or "attachment"
    guess = [n for n in names if n.rsplit("/", 1)[-1].startswith(stem + "_") and n.endswith(".txt")]
    return blob().download(guess[0]).decode("utf-8") if len(guess) == 1 else None


def message_html(case: dict, show_images: bool, highlight: bool = False) -> bytes:
    """The email body as sent, made safe to show: no scripts (CSP + sandboxed frame), inline images
    pointed at our own attachment URLs, remote images blocked unless asked for."""
    message = run_message(case) or {}
    body = message.get("body") or {}
    content = body.get("content") if isinstance(body, dict) else str(body or "")
    if (body.get("contentType") or "html").lower() != "html":
        content = "<pre style='white-space:pre-wrap;font:14px/1.5 Segoe UI,Arial'>" + (content or "").replace(
            "&", "&amp;").replace("<", "&lt;") + "</pre>"
    by_cid = {(a.get("contentId") or "").strip("<>").lower(): n
              for n, a in enumerate(message.get("attachments") or []) if a.get("contentId")}

    def swap(match):
        n = by_cid.get(match.group(2).strip("<>").lower())
        return f"{match.group(1)}/api/cases/{quote(case['id'])}/files/{n}" if n is not None else match.group(0)

    content = CID_RE.sub(swap, content or "")
    if highlight:
        content = mark_html(content, evidence_terms(case))
    images = "img-src 'self' data: https:" if show_images else "img-src 'self' data:"
    head = ("<meta charset='utf-8'><base target='_blank'>"
            "<style>body{font:14px/1.5 'Segoe UI',Arial,sans-serif;color:#1d2733;margin:16px;word-wrap:break-word}"
            f"img{{max-width:100%;height:auto}}table{{max-width:100%}}{HL_STYLE}</style>")
    page = f"<!doctype html><html><head>{head}</head><body>{content}</body></html>"
    return page.encode("utf-8"), f"default-src 'none'; {images}; style-src 'unsafe-inline'; font-src data:; sandbox"


def attachment(case: dict, n: int) -> tuple[dict, bytes] | None:
    message = run_message(case) or {}
    items = message.get("attachments") or []
    if not 0 <= n < len(items) or not items[n].get("blob_name"):
        return None
    return items[n], blob().download(items[n]["blob_name"])


def original(case: dict) -> tuple[str, bytes] | None:
    message = run_message(case) or {}
    path = message.get("msg_blob_path") or message.get("eml_blob_path")
    if not path:
        return None
    subject = re.sub(r"[^\w\- ]+", "", message.get("subject") or "email", flags=re.UNICODE).strip()[:60] or "email"
    return f"{subject}{Path(path).suffix}", blob().download(path)


def export_zip(case: dict) -> tuple[str, bytes]:
    buffer = io.BytesIO()
    message = run_message(case) or {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        found = original(case)
        if found:
            archive.writestr(found[0], found[1])
        used = set()
        for n, item in enumerate(message.get("attachments") or []):
            if not item.get("blob_name"):
                continue
            name = item.get("name") or f"attachment{n + 1}"
            if name in used:
                name = f"{n + 1:02d}_{name}"
            used.add(name)
            archive.writestr(f"attachments/{name}", blob().download(item["blob_name"]))
    return f"{case['id']}.zip", buffer.getvalue()


# ---------------------------------------------------------------- HTTP
PAGE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


class Handler(BaseHTTPRequestHandler):
    server_version = "review"
    sys_version = ""

    def log_message(self, fmt, *args):  # paths only, never query strings: searches can hold tax IDs
        sys.stderr.write(f"{self.command} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}\n")

    # -- helpers
    def send(self, status: int, body: bytes, kind: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, status: int, data, headers: dict | None = None) -> None:
        self.send(status, json.dumps(data, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8",
                  headers)

    def body(self) -> dict:
        size = int(self.headers.get("Content-Length") or 0)
        limit = MAX_BODY * 16 if urlparse(self.path).path == "/api/export" else MAX_BODY  # a list of case ids
        if size > limit:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(size) or b"{}")

    def cookie_user_id(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie") or "")
        return read_session(cookie["rv_session"].value) if "rv_session" in cookie else None

    def user(self) -> dict | None:
        user_id = self.cookie_user_id()
        return user_doc(user_id) if user_id else None

    def session_cookie(self, user_id: str | None) -> str:
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        if user_id is None:
            return f"rv_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
        return (f"rv_session={make_session(user_id)}; Path=/; HttpOnly; SameSite=Lax; "
                f"Max-Age={SESSION_DAYS * 86400}{secure}")

    # -- routing
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method: str) -> None:
        url = urlparse(self.path)
        path = url.path
        try:
            if path == "/healthz":
                return self.send(200, b"ok", "text/plain")
            if not path.startswith("/api/"):
                return self.static(path)
            if path == "/api/session" and method == "GET":
                user = self.user()
                # Each visit renews the cookie, so people who use the app are never signed out.
                renew = {"Set-Cookie": self.session_cookie(user["id"])} if user else None
                return self.json(200, {"mode": AUTH, "user": public_user(user) if user else None}, renew)
            if path == "/api/login" and method == "POST":
                doc, error = login(self.body(), self.client_address[0], self.cookie_user_id())
                if error:
                    return self.json(429 if error == "too_many" else 400, {"error": error})
                return self.json(200, {"user": public_user(doc)}, {"Set-Cookie": self.session_cookie(doc["id"])})
            if path == "/api/logout" and method == "POST":
                return self.json(200, {"ok": True}, {"Set-Cookie": self.session_cookie(None)})
            user = self.user()
            if user is None:
                return self.json(401, {"error": "signin"})
            return self.api(method, path, parse_qs(url.query), user)
        except (ValueError, json.JSONDecodeError):
            return self.json(400, {"error": "bad_request"})
        except Exception as exc:  # noqa: BLE001 - one bad request must not take the app down
            sys.stderr.write(f"error {type(exc).__name__} on {path}\n")
            return self.json(500, {"error": "server"})

    def static(self, path: str) -> None:
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            return self.send(404, b"not found", "text/plain")
        kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if kind.startswith("text/") or kind in ("application/javascript",):
            kind += "; charset=utf-8"
        self.send(200, target.read_bytes(), kind, {"Content-Security-Policy": PAGE_CSP})

    def api(self, method: str, path: str, query: dict, user: dict) -> None:
        parts = path.strip("/").split("/")  # api, cases, <id>, ...
        if path == "/api/meta" and method == "GET":
            from core.action_rules import QUALCO

            return self.json(200, {"categories": CATEGORIES, "actions": action_catalog(), "templates": reply_templates(),
                                   "codeNames": {**QUALCO["requests"], **QUALCO["activities"]},
                                   "user": public_user(user), "mode": AUTH})
        if path == "/api/cases" and method == "GET":
            return self.json(200, {"items": list_items(), "classifier": classifier_info(), "serverTime": now()})
        if path == "/api/export" and method == "POST":
            ids = [str(i) for i in (self.body().get("ids") or [])][:20000]
            data = export_xlsx(ids)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            return self.send(200, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             {"Content-Disposition": _disposition("attachment", f"emails-{stamp}.xlsx")})
        if path == "/api/metrics" and method == "GET":
            days = METRIC_RANGES.get((query.get("days") or ["30"])[0])
            if days is None:
                return self.json(400, {"error": "days"})
            return self.json(200, metrics.compute(METRICS.get(), days, metrics.athens_day(now())))
        if path == "/api/ingest" and method == "GET":
            return self.json(200, ingest_info())
        if path == "/api/activity" and method == "GET":
            # ponytail: reads the whole audit log and sorts it here; page it in Cosmos once it grows large.
            subjects = {c["id"]: c.get("subject") for c in CASES.get()}
            events = sorted(store().all("audit"), key=lambda e: e.get("at") or "", reverse=True)[:300]
            return self.json(200, {"events": [
                {**{k: e.get(k) for k in ("at", "by", "byName", "action", "before", "after", "comment", "caseId")},
                 "subject": subjects.get(e.get("caseId"))} for e in events]})
        if path == "/api/sync" and method == "POST":
            body = self.body()
            case_id = body.get("open")
            if case_id:
                take_lock(user, case_id)
            return self.json(200, {"presence": touch(user, case_id)})
        if len(parts) >= 3 and parts[1] == "cases":
            case_id = parts[2]
            if not re.fullmatch(r"[\w\-]{6,80}", case_id):
                return self.json(404, {"error": "not_found"})
            tail = parts[3:]
            if not tail and method == "GET":
                detail = case_detail(case_id)
                return self.json(200, detail) if detail else self.json(404, {"error": "not_found"})
            if tail == ["open"] and method == "POST":
                touch(user, case_id)
                return self.json(200, take_lock(user, case_id))
            if tail == ["release"] and method == "POST":
                release_lock(user, case_id)
                touch(user, None)
                return self.json(200, {"ok": True})
            if tail == ["reset"] and method == "POST":
                status, data = reset_review(user, case_id, self.body())
                return self.json(status, data)
            if tail == ["review"] and method == "POST":
                status, data = save_review(user, case_id, self.body())
                return self.json(status, data)
            case = store().get("cases", case_id)
            if case is None:
                return self.json(404, {"error": "not_found"})
            if tail == ["message"] and method == "GET":
                page, csp = message_html(case, query.get("images") == ["1"], query.get("hl") == ["1"])
                return self.send(200, page, "text/html; charset=utf-8", {"Content-Security-Policy": csp})
            if len(tail) == 3 and tail[0] == "files" and tail[1].isdigit() and tail[2] == "text" and method == "GET":
                found = run_message(case) or {}
                items = found.get("attachments") or []
                n = int(tail[1])
                if not 0 <= n < len(items):
                    return self.json(404, {"error": "not_found"})
                name = items[n].get("name") or ""
                text = attachment_text(case, name)
                if text is None:
                    return self.json(404, {"error": "no_text"})
                terms = evidence_terms(case, name) if query.get("hl") == ["1"] else []
                page = text_page(text, terms, name, "Σελίδα {n}").encode("utf-8")
                return self.send(200, page, "text/html; charset=utf-8",
                                 {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})
            if len(tail) == 2 and tail[0] == "files" and tail[1].isdigit() and method == "GET":
                found = attachment(case, int(tail[1]))
                if not found:
                    return self.json(404, {"error": "not_found"})
                item, data = found
                kind = _content_type(item)
                download = query.get("download") == ["1"] or kind not in INLINE_TYPES
                headers = {"Content-Disposition": _disposition("attachment" if download else "inline",
                                                               item.get("name") or "file")}
                if kind.startswith("image/") or kind == "text/plain":
                    headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
                return self.send(200, data, kind if not download else "application/octet-stream", headers)
            if tail == ["export", "original"] and method == "GET":
                found = original(case)
                if not found:
                    return self.json(404, {"error": "not_found"})
                name, data = found
                kind = "application/vnd.ms-outlook" if name.endswith(".msg") else "message/rfc822"
                return self.send(200, data, kind, {"Content-Disposition": _disposition("attachment", name)})
            if tail == ["export", "zip"] and method == "GET":
                name, data = export_zip(case)
                return self.send(200, data, "application/zip", {"Content-Disposition": _disposition("attachment", name)})
        return self.json(404, {"error": "not_found"})


def make_server() -> ThreadingHTTPServer:
    host = os.getenv("HOST", "0.0.0.0" if AUTH == "demo" else "127.0.0.1")
    if AUTH not in ("demo", "dev"):
        raise SystemExit(f"REVIEW_AUTH must be demo or dev (got {AUTH!r}); entra is not built yet")
    if AUTH == "dev" and host != "127.0.0.1":
        raise SystemExit("REVIEW_AUTH=dev only listens on 127.0.0.1")
    if AUTH == "demo" and len(ACCESS_CODE) < 12:
        raise SystemExit("REVIEW_AUTH=demo needs REVIEW_ACCESS_CODE of at least 12 characters")
    port = int(os.getenv("PORT", "8765"))
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    server = make_server()
    print(f"Review app ({AUTH}) on http://{server.server_address[0]}:{server.server_address[1]}", flush=True)
    server.serve_forever()
