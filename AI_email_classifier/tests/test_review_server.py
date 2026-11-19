"""Review server on invented emails: queue states, filters, reviews, conflicts, audit, presence, HTTP sign-in."""

import base64
import csv
import json
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from evaluation import review_server as rs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation" / "browser_test"))
import synthetic  # noqa: E402

ANNA, NIKOS = ("dev:anna", "Άννα"), ("dev:nikos", "Νίκος")
DEBT = "Βεβαιώσεις οφειλής"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "DB_PATH", tmp_path / "review.db")
    rs._presence.clear()
    data = synthetic.payload(28)
    rs.load_emails(data, "test")
    return data


def counts(**filters):
    return rs.list_emails(filters, ANNA)["counts"]


def review(email_id, user=ANNA, **body):
    version = rs.get_email(email_id)["version"]
    return rs.save_review(email_id, {"cats": [DEBT], "actions": ["request"], "base_version": version, **body}, user)


def test_queue_states_and_review(db):
    unclassified = sum(1 for e in db["emails"] if not e["cat"])
    assert counts() == {"everything": 28, "unclassified": unclassified, "classified": 28 - unclassified, "reviewed": 0, "mine_today": 0}
    saved = review("syn000", comment="  σωστό  ")
    assert saved["review"]["cats"] == [DEBT] and saved["review"]["comment"] == "σωστό" and saved["version"] == 1
    assert counts()["reviewed"] == 1 and counts()["mine_today"] == 1
    # Someone can also classify an email the model has not.
    review("syn003", user=NIKOS)
    c = counts()
    assert c["reviewed"] == 2 and c["unclassified"] == unclassified - 1
    rows = rs.list_emails({"status": "reviewed"}, ANNA)["rows"]
    assert {r["id"]: r["reviewed_by_name"] for r in rows} == {"syn000": "Άννα", "syn003": "Νίκος"}


def test_filters_dates_and_accent_free_search(db):
    assert rs.list_emails({"q": "ΣΥΝΘΕΤΙΚΟ αιτημα 12 "}, ANNA)["total"] == 1
    assert rs.list_emails({"q": "100%_"}, ANNA)["total"] == 0  # wildcards are literal
    assert rs.list_emails({"q": "000000005"}, ANNA)["total"] == 1  # an extracted tax ID is searchable
    today = datetime.now().date().isoformat()
    on_today = sum(1 for e in db["emails"] if e["received"].startswith(today))
    assert rs.list_emails({"from": today, "to": today}, ANNA)["total"] == on_today > 0
    week_ago = (datetime.now() - timedelta(days=6)).date().isoformat()
    assert 0 < rs.list_emails({"from": week_ago}, ANNA)["total"] < 28
    review("syn001")
    assert rs.list_emails({"datefield": "reviewed", "from": today, "to": today}, ANNA)["total"] == 1
    assert rs.list_emails({"status": "classified", "level": "low"}, ANNA)["total"] == sum(
        1 for e in db["emails"] if e["cat"] and e["top3"][0]["p"] < 90)
    review("syn002", cats=["GDPR"])
    assert [r["id"] for r in rs.list_emails({"agree": "no"}, ANNA)["rows"]] == ["syn002"]
    assert rs.list_emails({"cat": "GDPR"}, ANNA)["total"] == 1  # the reviewer's category counts
    assert rs.list_emails({"reviewer": "me"}, NIKOS)["total"] == 0


def test_conflict_clear_and_audit(db):
    stale = rs.get_email("syn004")["version"]
    review("syn004", user=NIKOS)
    with pytest.raises(rs.Conflict) as err:
        rs.save_review("syn004", {"cats": ["GDPR"], "base_version": stale}, ANNA)
    assert err.value.args[0]["review"]["by_name"] == "Νίκος"
    with pytest.raises(ValueError):
        review("syn004", cats=["not a category"])  # dropped, leaving none
    cleared = review("syn004", clear=True)
    assert cleared["review"] is None
    kinds = [(h["kind"], h["user_name"]) for h in cleared["history"]]
    assert kinds == [("review_cleared", "Άννα"), ("review_saved", "Νίκος")]
    assert cleared["history"][0]["detail"]["before"]["cats"] == [DEBT]
    feed = rs.activity({})
    assert feed[0]["kind"] == "review_cleared" and feed[-1]["kind"] == "imported"


def test_reimport_keeps_reviews(db):
    review("syn005")
    db["emails"][5]["subject"] = "Νέο θέμα"
    assert rs.load_emails(db, "again") == {"new": 0, "updated": 28}
    again = rs.get_email("syn005")
    assert again["review"]["cats"] == [DEBT] and again["email"]["subject"] == "Νέο θέμα"


def test_next_skips_emails_others_have_open(db):
    first = rs.next_email({}, ANNA)
    rs.touch(NIKOS, first)
    second = rs.next_email({}, ANNA)
    assert second and second != first
    assert rs.next_email({}, NIKOS) == first  # your own open email is not skipped
    seen = rs.sync({"since": 0, "viewing": second}, ANNA)
    assert {p["name"]: p["email"] for p in seen["presence"]} == {"Νίκος": first, "Άννα": second}
    assert seen["events"][0]["kind"] == "imported"


def test_export_csv(db, tmp_path):
    review("syn006", cats=[DEBT, "GDPR"], actions=["request", "forward"], comment="ok")
    path = tmp_path / "out.csv"
    assert rs.export_csv(path) == 1
    row = next(csv.DictReader(path.open(encoding="utf-8-sig")))
    assert (row["id"], row["business_category"], row["business_category_2"], row["business_actions"], row["reviewer"]) == (
        "syn006", DEBT, "GDPR", "request; forward", "Άννα")


@pytest.fixture()
def server(db):
    srv = rs.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    srv.server_close()


def call(base, path, method="GET", body=None, headers=None):
    request = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request) as r:
            raw = r.read()
            return r.status, json.loads(raw) if r.headers.get_content_type() == "application/json" else raw, r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def test_http_sign_in_and_review(server):
    xhr = {"X-Requested-With": "review"}
    assert call(server, "/api/meta")[0] == 401
    assert call(server, "/api/login", "POST", {"name": "Άννα"})[0] == 403  # no custom header
    status, _, headers = call(server, "/api/login", "POST", {"name": " Άννα \n"}, xhr)
    assert status == 200 and "HttpOnly" in headers["Set-Cookie"]
    me = {"Cookie": headers["Set-Cookie"].split(";")[0], **xhr}
    status, meta, headers = call(server, "/api/meta", headers=me)
    assert status == 200 and meta["me"]["name"] == "Άννα" and "default-src 'self'" in headers["Content-Security-Policy"]
    status, page, _ = call(server, "/api/emails?status=classified&limit=5", headers=me)
    assert status == 200 and len(page["rows"]) == 5
    email_id = page["rows"][0]["id"]
    status, saved, _ = call(server, f"/api/emails/{email_id}/review", "PUT", {"cats": [DEBT], "base_version": 0}, me)
    assert status == 200 and saved["review"]["by_name"] == "Άννα"
    status, clash, _ = call(server, f"/api/emails/{email_id}/review", "PUT", {"cats": ["GDPR"], "base_version": 0}, me)
    assert status == 409 and clash["version"] == 1
    assert call(server, "/api/emails/nope", headers=me)[0] == 404
    assert call(server, "/api/emails/x/review", "PUT", {"cats": [DEBT], "base_version": 0}, me)[0] == 404
    status, html, _ = call(server, "/")
    assert status == 200 and b"<title>" in html


def test_easyauth_trusts_only_the_entra_headers(server, monkeypatch):
    monkeypatch.setattr(rs, "AUTH", "easyauth")
    assert call(server, "/api/meta", headers={"Cookie": "reviewer=anna"})[0] == 401
    claims = base64.b64encode(json.dumps({"claims": [{"typ": "name", "val": "Άννα Παπά"}]}).encode()).decode()
    status, meta, _ = call(server, "/api/meta", headers={"X-MS-CLIENT-PRINCIPAL-NAME": "anna@dovalue.example",
                                                         "X-MS-CLIENT-PRINCIPAL-ID": "oid-1", "X-MS-CLIENT-PRINCIPAL": claims})
    assert status == 200 and meta["me"] == {"id": "oid-1", "name": "Άννα Παπά"} and meta["auth"] == "easyauth"
    assert call(server, "/api/login", "POST", {"name": "x"}, {"X-Requested-With": "review"})[0] == 401
