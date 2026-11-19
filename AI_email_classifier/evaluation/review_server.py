"""Multi-user review server: a queue of classified emails, reviews, live presence and an audit log.

    python evaluation/review_server.py import probs_v1   # emails + predictions -> review.db
    python evaluation/review_server.py serve             # http://127.0.0.1:8765
    python evaluation/review_server.py export            # reviews -> business_review_server.csv
    REVIEW_DB=demo.db python evaluation/review_server.py demo   # invented emails instead

`import` keeps existing reviews and can be re-run after each classification run.
`export` writes the CSV that `evaluate.py score` already merges.

Sign-in (REVIEW_AUTH):
- `dev` (default): the page asks for a name. Listens on 127.0.0.1 only.
- `easyauth`: trusts the Entra ID headers that Azure Container Apps authentication
  adds (X-MS-CLIENT-PRINCIPAL-*) and refuses any request without them. Only use it
  behind that authentication, which strips the headers from outside requests.

The database holds client emails: keep it on this machine or in the client's Azure.
Standard library only, so the container needs nothing extra.
"""

from __future__ import annotations

import base64
import csv
import json
import os
import sqlite3
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

HERE = Path(__file__).resolve().parent
# Same default as common.OUT_DIR, without importing pandas and the classifier to serve a page.
OUT_DIR = Path(os.getenv("EVAL_OUT_DIR", HERE.parents[1] / "runs" / "eval"))
DB_PATH = Path(os.getenv("REVIEW_DB", OUT_DIR / "review.db"))
UI_FILE = HERE / "review_ui.html"
AUTH = os.getenv("REVIEW_AUTH", "dev")
PRESENCE_TTL = 25  # seconds without a heartbeat before someone counts as gone
MAX_BODY = 64_000
PAGE_MAX = 200

# What a reviewer can say should happen. Labels live here so the page and the
# server agree on the same list.
ACTIONS = {
    "request": ["Καταχώρηση αιτήματος στο Qualco", "Το προσωπικό ανοίγει αίτημα στο Qualco με τον κωδικό που φαίνεται."],
    "portal_referral": ["Παραπομπή στο Portal", "Απαντάμε ότι το αίτημα γίνεται από το Portal και καταχωρούμε activity «Παραπομπή Portal»."],
    "forward": ["Προώθηση σε άλλο τμήμα", "Το email προωθείται στους παραλήπτες που ορίζει η προδιαγραφή."],
    "manual": ["Χειρισμός από το προσωπικό", "Δεν γίνεται αυτόματη ενέργεια. Το email το εξετάζει το προσωπικό στο Outlook."],
    "activity": ["Καταχώρηση activity", "Η αλληλογραφία επισυνάπτεται στο αίτημα που είναι ήδη ανοιχτό."],
    "reply": ["Απαντητικό email", "Απαντάμε στον αποστολέα και ζητάμε ό,τι λείπει."],
    "bank_referral": ["Παραπομπή στην τράπεζα", "Ενημερώνουμε τον αποστολέα να απευθυνθεί στην τράπεζα."],
    "no_action": ["Καμία ενέργεια", "Το email δεν χρειάζεται χειρισμό."],
    "ask_identification": ["Αίτημα ταυτοποίησης", "Απαντάμε και ζητάμε τα στοιχεία που χρειάζονται για να βρούμε την υπόθεση."],
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS emails(
  id TEXT PRIMARY KEY, received TEXT, dataset TEXT, sender TEXT, subject TEXT,
  cat TEXT, top_p INTEGER, second_p INTEGER, dos TEXT, n_att INTEGER,
  classified_at TEXT, version INTEGER NOT NULL DEFAULT 0,
  search TEXT NOT NULL, doc TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS emails_received ON emails(received);
CREATE TABLE IF NOT EXISTS reviews(
  email_id TEXT PRIMARY KEY REFERENCES emails(id), cats TEXT NOT NULL, actions TEXT NOT NULL,
  comment TEXT NOT NULL, by TEXT NOT NULL, by_name TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, user TEXT NOT NULL,
  user_name TEXT NOT NULL, email_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS audit_email ON audit(email_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(text: str | None) -> str:
    """Lower case without accents, so «Βεβαίωση» and «βεβαιωση» match."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("ς", "σ")


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def config(con: sqlite3.Connection) -> dict:
    row = con.execute("SELECT value FROM meta WHERE key='config'").fetchone()
    return json.loads(row["value"]) if row else {"categories": [], "spec": {}, "high": 90, "also": 50}


def audit(con, user: tuple[str, str], kind: str, email_id: str | None, detail: dict) -> None:
    con.execute(
        "INSERT INTO audit(at, user, user_name, email_id, kind, detail) VALUES (?,?,?,?,?,?)",
        (now(), user[0], user[1], email_id, kind, json.dumps(detail, ensure_ascii=False)),
    )


# ---------------------------------------------------------------- import / export


def _search_text(e: dict) -> str:
    action = e.get("action") or {}
    parts = [e.get("subject"), e.get("sender"), e.get("cat")]
    parts += [m.get("body") for m in e.get("chain") or []]
    parts += [f"{a.get('file')} {a.get('summary')}" for a in e.get("attachments") or []]
    parts += [v["value"] for f in action.get("fields") or [] for v in f.get("values") or []]
    return norm(" ".join(p for p in parts if p))


def load_emails(data: dict, source: str) -> dict:
    """Insert or refresh emails; reviews are never touched. Returns counts."""
    stamp, counts = now(), {"new": 0, "updated": 0}
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        cfg = {k: data[k] for k in ("categories", "spec", "high", "also")}
        con.execute("INSERT OR REPLACE INTO meta VALUES ('config', ?)", (json.dumps(cfg, ensure_ascii=False),))
        for e in data["emails"]:
            old = con.execute("SELECT cat, classified_at FROM emails WHERE id=?", (e["id"],)).fetchone()
            top = e.get("top3") or []
            dos = sorted({a["do"] for a in (e.get("action") or {}).get("items") or []})
            classified_at = None
            if e.get("cat"):
                same = old and old["cat"] == e["cat"] and old["classified_at"]
                classified_at = old["classified_at"] if same else stamp
            row = (
                e.get("received") or "", e.get("dataset") or "", e.get("sender") or "", e.get("subject") or "",
                e.get("cat"), top[0]["p"] if top else None, top[1]["p"] if len(top) > 1 else None,
                "|" + "|".join(dos) + "|", len(e.get("attachments") or []), classified_at,
                _search_text(e), json.dumps(e, ensure_ascii=False),
            )
            if old:
                con.execute(
                    "UPDATE emails SET received=?, dataset=?, sender=?, subject=?, cat=?, top_p=?, second_p=?,"
                    " dos=?, n_att=?, classified_at=?, search=?, doc=? WHERE id=?",
                    (*row, e["id"]),
                )
                counts["updated"] += 1
            else:
                con.execute(
                    "INSERT INTO emails(received, dataset, sender, subject, cat, top_p, second_p, dos, n_att,"
                    " classified_at, search, doc, id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*row, e["id"]),
                )
                counts["new"] += 1
        audit(con, ("system", "Σύστημα"), "imported", None, {"source": source, **counts})
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return counts


def export_csv(path: Path) -> int:
    """Reviews in the columns of the old per-reviewer export, for evaluate.py score."""
    con = connect()
    try:
        rows = con.execute("SELECT * FROM reviews ORDER BY at").fetchall()
    finally:
        con.close()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "business_category", "business_comment", "reviewer", "reviewed_at",
                    "business_category_2", "business_category_3", "business_actions"])
        for r in rows:
            cats = json.loads(r["cats"]) + ["", "", ""]
            w.writerow([r["email_id"], cats[0], r["comment"], r["by_name"], r["at"], cats[1], cats[2],
                        "; ".join(json.loads(r["actions"]))])
    return len(rows)


# ---------------------------------------------------------------- presence

# ponytail: one process holds presence in memory. Several replicas would need it in the database.
_presence: dict[str, dict] = {}
_lock = threading.Lock()


def touch(user: tuple[str, str], email_id: str | None) -> None:
    with _lock:
        _presence[user[0]] = {"user": user[0], "name": user[1], "email": email_id, "t": time.time()}


def present() -> list[dict]:
    cutoff = time.time() - PRESENCE_TTL
    with _lock:
        for k in [k for k, v in _presence.items() if v["t"] < cutoff]:
            del _presence[k]
        return [{"user": v["user"], "name": v["name"], "email": v["email"]} for v in _presence.values()]


# ---------------------------------------------------------------- queries

# A review wins: an email someone classified by hand counts as reviewed, not unclassified.
STATUS = {
    "unclassified": "e.cat IS NULL AND r.email_id IS NULL",
    "classified": "e.cat IS NOT NULL AND r.email_id IS NULL",
    "reviewed": "r.email_id IS NOT NULL",
}
DATE_FIELD = {"received": "e.received", "classified": "e.classified_at", "reviewed": "r.at"}
SORT = {
    "new": "e.received DESC, e.id",
    "old": "e.received ASC, e.id",
    "uncertain": "e.top_p IS NULL DESC, e.top_p ASC, e.received DESC",
    "reviewed": "r.at IS NULL, r.at DESC, e.received DESC",
}


def _like(word: str) -> str:
    return "%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def where(p: dict, user: tuple[str, str], cfg: dict, status: bool = True) -> tuple[str, list]:
    """SQL condition for the queue filters. Every value is bound, never pasted in."""
    sql, args = ["1=1"], []

    def add(clause: str, *values) -> None:
        sql.append(clause)
        args.extend(values)

    # ponytail: LIKE scans every row; fine for tens of thousands. Switch to FTS5 (trigram) beyond that.
    for word in norm(p.get("q")).split()[:8]:
        add("e.search LIKE ? ESCAPE '\\'", _like(word))
    if p.get("cat"):
        # The category a reviewer gave wins over the model's.
        add("COALESCE(json_extract(r.cats, '$[0]'), e.cat) = ?", p["cat"])
    level = p.get("level")
    if level == "high":
        add("e.top_p >= ?", cfg["high"])
    elif level == "low":
        add("e.top_p < ?", cfg["high"])
    elif level == "second":
        add("e.second_p >= ?", cfg["also"])
    if p.get("action") in ACTIONS:
        add("e.dos LIKE ?", f"%|{p['action']}|%")
    if p.get("dataset"):
        add("e.dataset = ?", p["dataset"])
    if p.get("reviewer"):
        add("r.by = ?", user[0] if p["reviewer"] == "me" else p["reviewer"])
    if p.get("agree") == "no":
        add("r.email_id IS NOT NULL AND json_extract(r.cats, '$[0]') IS NOT e.cat")
    column = DATE_FIELD.get(p.get("datefield") or "received", "e.received")
    if p.get("from"):
        add(f"substr({column}, 1, 10) >= ?", p["from"][:10])
    if p.get("to"):
        add(f"substr({column}, 1, 10) <= ?", p["to"][:10])
    if status and p.get("status") in STATUS:
        add(STATUS[p["status"]])
    return " AND ".join(sql), args


FROM = "FROM emails e LEFT JOIN reviews r ON r.email_id = e.id"
LIGHT = (
    "e.id, e.received, e.dataset, e.sender, e.subject, e.cat, e.top_p, e.n_att, e.classified_at,"
    " r.by AS reviewed_by, r.by_name AS reviewed_by_name, r.at AS reviewed_at,"
    " json_extract(r.cats, '$[0]') AS reviewed_cat"
)


def list_emails(p: dict, user) -> dict:
    con = connect()
    try:
        cfg = config(con)
        cond, args = where(p, user, cfg)
        limit = max(1, min(PAGE_MAX, int(p.get("limit") or 50)))
        offset = max(0, int(p.get("offset") or 0))
        order = SORT.get(p.get("sort") or "new", SORT["new"])
        total = con.execute(f"SELECT COUNT(*) {FROM} WHERE {cond}", args).fetchone()[0]
        rows = con.execute(
            f"SELECT {LIGHT} {FROM} WHERE {cond} ORDER BY {order} LIMIT ? OFFSET ?", [*args, limit, offset]
        ).fetchall()
        bare, bare_args = where(p, user, cfg, status=False)
        c = con.execute(
            f"SELECT COUNT(*) AS everything, SUM({STATUS['unclassified']}) AS unclassified,"
            f" SUM({STATUS['classified']}) AS classified, SUM({STATUS['reviewed']}) AS reviewed"
            f" {FROM} WHERE {bare}",
            bare_args,
        ).fetchone()
        today = datetime.now(timezone.utc).date().isoformat()
        mine = con.execute(
            "SELECT COUNT(*) FROM reviews WHERE by = ? AND substr(at, 1, 10) = ?", (user[0], today)
        ).fetchone()[0]
    finally:
        con.close()
    counts = {k: c[k] or 0 for k in ("everything", "unclassified", "classified", "reviewed")}
    return {"total": total, "offset": offset, "limit": limit, "counts": {**counts, "mine_today": mine},
            "rows": [dict(r) for r in rows]}


def next_email(p: dict, user) -> str | None:
    """The first email still to review that nobody else has open."""
    busy = {v["email"] for v in present() if v["user"] != user[0] and v["email"]}
    q = {**p, "status": p.get("status") if p.get("status") in ("unclassified", "classified") else "classified"}
    con = connect()
    try:
        cond, args = where(q, user, config(con))
        order = SORT.get(p.get("sort") or "new", SORT["new"])
        ids = [r[0] for r in con.execute(f"SELECT e.id {FROM} WHERE {cond} ORDER BY {order} LIMIT 300", args)]
    finally:
        con.close()
    return next((i for i in ids if i not in busy and i != p.get("after")), None)


def _review(row) -> dict | None:
    if not row:
        return None
    return {"cats": json.loads(row["cats"]), "actions": json.loads(row["actions"]), "comment": row["comment"],
            "by": row["by"], "by_name": row["by_name"], "at": row["at"]}


def _events(rows) -> list[dict]:
    return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


def get_email(email_id: str) -> dict | None:
    con = connect()
    try:
        e = con.execute("SELECT doc, version, classified_at FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not e:
            return None
        r = con.execute("SELECT * FROM reviews WHERE email_id = ?", (email_id,)).fetchone()
        hist = con.execute(
            "SELECT id, at, user, user_name, kind, detail FROM audit WHERE email_id = ? ORDER BY id DESC LIMIT 50",
            (email_id,),
        ).fetchall()
        return {"email": json.loads(e["doc"]), "version": e["version"], "classified_at": e["classified_at"],
                "review": _review(r), "history": _events(hist)}
    finally:
        con.close()


class Conflict(Exception):
    pass


def save_review(email_id: str, body: dict, user) -> dict:
    """Save or clear a review, but only if nobody else saved since the reviewer loaded it."""
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        e = con.execute("SELECT version FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not e:
            raise KeyError(email_id)
        before = _review(con.execute("SELECT * FROM reviews WHERE email_id = ?", (email_id,)).fetchone())
        try:
            base = int(body.get("base_version"))
        except (TypeError, ValueError):
            raise ValueError("base_version is required") from None
        if base != e["version"]:
            raise Conflict({"version": e["version"], "review": before})
        known = set(config(con)["categories"])
        cats = list(dict.fromkeys(c for c in body.get("cats") or [] if c in known))[:3]
        actions = list(dict.fromkeys(a for a in body.get("actions") or [] if a in ACTIONS))
        comment = str(body.get("comment") or "").strip()[:2000]
        if body.get("clear"):
            if before is None:
                con.execute("ROLLBACK")
                return get_email(email_id)
            con.execute("DELETE FROM reviews WHERE email_id = ?", (email_id,))
            kind, after = "review_cleared", None
        elif not cats:
            raise ValueError("Χρειάζεται τουλάχιστον μία κατηγορία.")
        else:
            con.execute(
                "INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?)",
                (email_id, json.dumps(cats, ensure_ascii=False), json.dumps(actions), comment,
                 user[0], user[1], now()),
            )
            kind, after = "review_saved", {"cats": cats, "actions": actions, "comment": comment}
        version = e["version"] + 1
        con.execute("UPDATE emails SET version = ? WHERE id = ?", (version, email_id))
        kept = before and {k: before[k] for k in ("cats", "actions", "comment", "by_name")}
        audit(con, user, kind, email_id, {"before": kept, "after": after, "version": version})
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return get_email(email_id)


AUDIT_JOIN = (
    "SELECT a.id, a.at, a.user, a.user_name, a.email_id, a.kind, a.detail, e.subject"
    " FROM audit a LEFT JOIN emails e ON e.id = a.email_id"
)


def activity(p: dict) -> list[dict]:
    sql, args = ["1=1"], []
    if p.get("before"):
        sql.append("a.id < ?")
        args.append(int(p["before"]))
    if p.get("user"):
        sql.append("a.user = ?")
        args.append(p["user"])
    limit = max(1, min(PAGE_MAX, int(p.get("limit") or 50)))
    con = connect()
    try:
        rows = con.execute(f"{AUDIT_JOIN} WHERE {' AND '.join(sql)} ORDER BY a.id DESC LIMIT ?", [*args, limit])
        return _events(rows.fetchall())
    finally:
        con.close()


def sync(body: dict, user) -> dict:
    """Heartbeat: records what this reviewer has open; returns changes since `since` and who is online."""
    viewing = body.get("viewing")
    touch(user, viewing if isinstance(viewing, str) and viewing else None)
    con = connect()
    try:
        last = con.execute("SELECT COALESCE(MAX(id), 0) FROM audit").fetchone()[0]
        since = body.get("since")
        events = []
        if isinstance(since, int) and not isinstance(since, bool):
            events = _events(con.execute(f"{AUDIT_JOIN} WHERE a.id > ? ORDER BY a.id LIMIT 200", (since,)).fetchall())
    finally:
        con.close()
    return {"last": last, "events": events, "presence": present()}


def meta(user) -> dict:
    con = connect()
    try:
        cfg = config(con)
        datasets = [r[0] for r in con.execute("SELECT DISTINCT dataset FROM emails ORDER BY dataset")]
        reviewers = [dict(r) for r in con.execute(
            "SELECT by AS id, MAX(by_name) AS name, COUNT(*) AS n FROM reviews GROUP BY by ORDER BY name")]
    finally:
        con.close()
    return {**cfg, "actions": ACTIONS, "datasets": datasets, "reviewers": reviewers,
            "me": {"id": user[0], "name": user[1]}, "auth": AUTH}


# ---------------------------------------------------------------- HTTP


def _principal(headers) -> tuple[str, str] | None:
    """The signed-in Entra user, from the headers Container Apps authentication sets."""
    upn = headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if not upn:
        return None
    name = upn
    try:
        claims = json.loads(base64.b64decode(headers.get("X-MS-CLIENT-PRINCIPAL", "")))["claims"]
        name = next((c["val"] for c in claims if c.get("typ") == "name"), upn)
    except (ValueError, KeyError, TypeError):
        pass
    return headers.get("X-MS-CLIENT-PRINCIPAL-ID") or upn, name


def _clean_name(raw: str) -> str:
    return " ".join("".join(ch for ch in raw if ch.isprintable()).split())[:60]


class Handler(BaseHTTPRequestHandler):
    server_version = "review"

    def log_message(self, fmt, *args):  # no URLs in logs: searches can hold tax IDs
        pass

    def user(self) -> tuple[str, str] | None:
        if AUTH == "easyauth":
            return _principal(self.headers)
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None
        name = _clean_name(unquote(jar["reviewer"].value)) if "reviewer" in jar else ""
        return (f"dev:{norm(name)}", name) if name else None

    def send(self, status: int, body: bytes, kind: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
            " img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, status: int, data, headers: dict | None = None) -> None:
        self.send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", headers)

    def body(self) -> dict:
        size = int(self.headers.get("Content-Length") or 0)
        if size > MAX_BODY:
            raise ValueError("request too large")
        data = json.loads(self.rfile.read(size) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        return data

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self.send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
        self.api("GET", url)

    def do_POST(self):
        self.api("POST", urlparse(self.path))

    def do_PUT(self):
        self.api("PUT", urlparse(self.path))

    def api(self, method: str, url) -> None:
        try:
            path, q = url.path, {k: v[-1] for k, v in parse_qs(url.query).items()}
            # A custom header forces a CORS preflight, so other sites cannot post here.
            if method != "GET" and self.headers.get("X-Requested-With") != "review":
                return self.json(403, {"error": "missing header"})
            if path == "/api/login" and method == "POST" and AUTH == "dev":
                name = _clean_name(str(self.body().get("name") or ""))
                if not name:
                    return self.json(400, {"error": "Γράψτε το όνομά σας."})
                cookie = f"reviewer={quote(name)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000"
                return self.json(200, {"ok": True}, {"Set-Cookie": cookie})
            if path == "/api/logout" and method == "POST" and AUTH == "dev":
                return self.json(200, {"ok": True}, {"Set-Cookie": "reviewer=; Path=/; Max-Age=0; SameSite=Strict"})
            user = self.user()
            if not user:
                return self.json(401, {"error": "sign in", "auth": AUTH})
            if path == "/api/meta" and method == "GET":
                return self.json(200, meta(user))
            if path == "/api/emails" and method == "GET":
                return self.json(200, list_emails(q, user))
            if path == "/api/next" and method == "GET":
                return self.json(200, {"id": next_email(q, user)})
            if path == "/api/activity" and method == "GET":
                return self.json(200, {"events": activity(q)})
            if path == "/api/sync" and method == "POST":
                return self.json(200, sync(self.body(), user))
            parts = path.split("/")
            if path.startswith("/api/emails/") and len(parts) in (4, 5):
                email_id = unquote(parts[3])
                if len(parts) == 4 and method == "GET":
                    found = get_email(email_id)
                    return self.json(200, found) if found else self.json(404, {"error": "not found"})
                if len(parts) == 5 and parts[4] == "review" and method == "PUT":
                    try:
                        return self.json(200, save_review(email_id, self.body(), user))
                    except Conflict as c:
                        return self.json(409, {"error": "conflict", **c.args[0]})
                    except KeyError:
                        return self.json(404, {"error": "not found"})
            return self.json(404, {"error": "not found"})
        except ValueError as e:
            return self.json(400, {"error": str(e)})
        except Exception as e:  # keep serving; the page shows a retry message
            sys.stderr.write(f"{method} {url.path} failed: {e!r}\n")
            return self.json(500, {"error": "server error"})


def make_server(port: int) -> ThreadingHTTPServer:
    # Dev sign-in has no password, so it never listens beyond this machine.
    host = "0.0.0.0" if AUTH == "easyauth" else "127.0.0.1"
    connect().close()
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    command = argv[0] if argv else "serve"
    if command == "import":
        sys.path.insert(0, str(HERE))
        import review_app  # heavy: pandas, the classifier and the registry

        name = argv[1] if len(argv) > 1 else "probs_v1"
        counts = load_emails(review_app.payload(name, unclassified=True), name)
        print(f"imported {name}: {counts['new']} new, {counts['updated']} updated -> {DB_PATH}")
    elif command == "demo":  # invented emails, to try the app without client data
        sys.path.insert(0, str(HERE / "browser_test"))
        import synthetic

        counts = load_emails(synthetic.payload(), "demo")
        print(f"demo: {counts['new']} new, {counts['updated']} updated -> {DB_PATH}")
    elif command == "export":
        path = OUT_DIR / "business_review_server.csv"
        print(f"exported {export_csv(path)} reviews -> {path}")
    elif command == "serve":
        port = int(os.getenv("PORT") or (argv[1] if len(argv) > 1 else 8765))
        server = make_server(port)
        print(f"review server: http://127.0.0.1:{server.server_port}  (sign-in: {AUTH}, db: {DB_PATH})")
        server.serve_forever()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
