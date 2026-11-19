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

from data.case_store import Conflict, open_store  # noqa: E402

AUTH = os.getenv("REVIEW_AUTH", "dev").strip().lower()
ACCESS_CODE = os.getenv("REVIEW_ACCESS_CODE", "")
SESSION_SECRET = (os.getenv("REVIEW_SESSION_SECRET") or secrets.token_hex(32)).encode()
SESSION_DAYS = 180
LOCK_SECONDS = 300
PRESENCE_TTL = 40
CASE_CACHE_SECONDS = 5
MAX_BODY = 64_000
STATIC = HERE / "static"
CATEGORIES = [c["Categories"].strip() for c in json.loads((APP / "inputs" / "categories.json").read_text("utf-8"))]
LIGHT = ["id", "subject", "from", "receivedAt", "status", "route", "routeReasons", "modelCategory",
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
    attachments = [
        {
            "n": n,
            "name": a.get("name"),
            "contentType": a.get("contentType"),
            "size": a.get("size") or a.get("decoded_size"),
            "inline": bool(a.get("isInline")),
            "viewable": _content_type(a) in INLINE_TYPES,
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


def save_review(user: dict, case_id: str, body: dict) -> tuple[int, dict]:
    case = store().get("cases", case_id)
    if case is None:
        return 404, {"error": "not_found"}
    if body.get("_etag") != case.get("_etag"):
        return 409, {"error": "changed", "case": case_detail(case_id)}
    final = str(body.get("finalCategory") or "").strip()
    no_match = bool(body.get("noMatch"))
    if not no_match and final not in CATEGORIES:
        return 400, {"error": "category"}
    others = [c for c in body.get("otherCategories") or [] if c in CATEGORIES and c != final][:5]
    before = {k: case.get(k) for k in ("status", "finalCategory", "otherCategories", "reviewComment")}
    updated = {
        **case,
        "status": "REVIEWED",
        "finalCategory": None if no_match else final,
        "noMatch": no_match,
        "otherCategories": others,
        "reviewComment": str(body.get("comment") or "")[:2000],
        "reviewedBy": public_user(user),
        "reviewedAt": now(),
        "updatedAt": now(),
    }
    try:
        saved = store().replace("cases", updated)
    except Conflict:
        return 409, {"error": "changed", "case": case_detail(case_id)}
    after = {k: saved.get(k) for k in ("status", "finalCategory", "otherCategories", "reviewComment")}
    store().create("audit", {"id": uuid.uuid4().hex, "caseId": case_id, "at": now(), "by": user["id"],
                             "byName": user.get("name"), "action": "reviewed", "before": before, "after": after})
    release_lock(user, case_id)
    CASES.drop()
    return 200, {"ok": True, "_etag": saved.get("_etag")}


def _content_type(attachment: dict) -> str:
    kind = (attachment.get("contentType") or "").split(";")[0].strip().lower()
    if not kind or kind == "application/octet-stream":
        kind = mimetypes.guess_type(attachment.get("name") or "")[0] or "application/octet-stream"
    return kind


def _disposition(kind: str, name: str) -> str:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


CID_RE = re.compile(r"""(["'(])cid:([^"')\s]+)""", re.IGNORECASE)


def message_html(case: dict, show_images: bool) -> bytes:
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
    images = "img-src 'self' data: https:" if show_images else "img-src 'self' data:"
    head = ("<meta charset='utf-8'><base target='_blank'>"
            "<style>body{font:14px/1.5 'Segoe UI',Arial,sans-serif;color:#1d2733;margin:16px;word-wrap:break-word}"
            "img{max-width:100%;height:auto}table{max-width:100%}</style>")
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
        if size > MAX_BODY:
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
                return self.json(200, {"mode": AUTH, "user": public_user(user) if user else None})
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
            return self.json(200, {"categories": CATEGORIES, "user": public_user(user), "mode": AUTH})
        if path == "/api/cases" and method == "GET":
            return self.json(200, {"items": CASES.get(), "serverTime": now()})
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
            if tail == ["review"] and method == "POST":
                status, data = save_review(user, case_id, self.body())
                return self.json(status, data)
            case = store().get("cases", case_id)
            if case is None:
                return self.json(404, {"error": "not_found"})
            if tail == ["message"] and method == "GET":
                page, csp = message_html(case, query.get("images") == ["1"])
                return self.send(200, page, "text/html; charset=utf-8", {"Content-Security-Policy": csp})
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
