"""Review app server on invented data: sign-in code, safe saves, safe file serving."""

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from core.run_classifier import email_id, new_case
from data.case_store import LocalStore

SERVER = Path(__file__).resolve().parents[2] / "review_app" / "server.py"
CODE = "correct-horse-battery"
MESSAGE = {
    "id": "g1",
    "internetMessageId": "<m1@example.test>",
    "receivedDateTime": "2026-11-19T08:15:00Z",
    "subject": "Βεβαίωση",
    "from": {"emailAddress": {"name": "Πελάτης", "address": "client@example.test"}},
    "body": {"contentType": "html", "content": "<p>Καλημέρα</p><img src='cid:logo1'><script>alert(1)</script>"},
    "msg_blob_path": "messages/import/x/message.msg",
    "attachments": [
        {"name": "a.pdf", "contentType": "application/pdf", "blob_name": "att/a.pdf", "size": 4},
        {"name": "evil.html", "contentType": "text/html", "blob_name": "att/evil.html", "size": 4},
        {"name": "logo.png", "contentType": "image/png", "blob_name": "att/logo.png", "contentId": "<logo1>", "isInline": True},
    ],
}
FILES = {"att/a.pdf": b"%PDF", "att/evil.html": b"<script>", "att/logo.png": b"\x89PNG",
         "messages/import/x/message.msg": b"MSG", "bronze/import-1/emails.json": b""}


class FakeBlob:
    @staticmethod
    def download(name):
        return FILES[name]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_AUTH", "demo")
    monkeypatch.setenv("REVIEW_ACCESS_CODE", CODE)
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "0")
    spec = importlib.util.spec_from_file_location("review_server_under_test", SERVER)
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    FILES["bronze/import-1/emails.json"] = json.dumps({"messages": [MESSAGE], "removed": []}).encode()
    server.STORE = LocalStore(tmp_path)
    server._blob = FakeBlob
    case = new_case(MESSAGE, "import-1", "bronze/import-1/emails.json", "2026-11-19T08:20:00Z")
    case.update(status="CLASSIFIED", route="REVIEW", modelCategory="Βεβαίωση Οφειλής")
    server.STORE.create("cases", case)
    httpd = server.make_server()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield server, f"http://127.0.0.1:{httpd.server_address[1]}", email_id(MESSAGE)
    httpd.shutdown()


def call(url, data=None, cookie=None):
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def sign_in(base):
    status, headers, _ = call(f"{base}/api/login", {"name": "Ann Example", "email": "ann@example.test", "code": CODE})
    assert status == 200
    return headers["Set-Cookie"].split(";")[0]


def test_demo_sign_in_needs_the_access_code(app):
    _, base, _ = app
    assert call(f"{base}/api/cases")[0] == 401
    assert call(f"{base}/api/login", {"name": "Ann", "email": "ann@example.test", "code": "wrong"})[0] == 400
    cookie = sign_in(base)
    status, _, body = call(f"{base}/api/cases", cookie=cookie)
    assert status == 200 and len(json.loads(body)["items"]) == 1


def test_a_stale_save_is_refused_and_a_fresh_one_is_audited(app):
    server, base, case_id = app
    cookie = sign_in(base)
    detail = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])
    etag = detail["case"]["_etag"]
    stale = call(f"{base}/api/cases/{case_id}/review", {"_etag": "old", "finalCategory": "Βεβαίωση άρσης προσημείωσης"}, cookie)
    assert stale[0] == 409
    bad = call(f"{base}/api/cases/{case_id}/review", {"_etag": etag, "finalCategory": "Not a category"}, cookie)
    assert bad[0] == 400
    good = call(f"{base}/api/cases/{case_id}/review", {"_etag": etag, "finalCategory": "Βεβαίωση άρσης προσημείωσης"}, cookie)
    assert good[0] == 200
    saved = server.STORE.get("cases", case_id)
    assert saved["status"] == "REVIEWED" and saved["reviewedBy"]["email"] == "ann@example.test"
    assert [e["action"] for e in server.STORE.find("audit", "caseId", case_id)] == ["reviewed"]


def test_files_that_could_run_code_are_download_only(app):
    _, base, case_id = app
    cookie = sign_in(base)
    status, headers, _ = call(f"{base}/api/cases/{case_id}/files/0", cookie=cookie)
    assert status == 200 and headers["Content-Type"] == "application/pdf" and headers["Content-Disposition"].startswith("inline")
    status, headers, _ = call(f"{base}/api/cases/{case_id}/files/1", cookie=cookie)
    assert headers["Content-Type"] == "application/octet-stream" and headers["Content-Disposition"].startswith("attachment")
    status, headers, _ = call(f"{base}/api/cases/{case_id}/export/original", cookie=cookie)
    assert status == 200 and ".msg" in headers["Content-Disposition"]


def test_the_email_page_is_sandboxed_and_uses_our_inline_images(app):
    _, base, case_id = app
    cookie = sign_in(base)
    status, headers, body = call(f"{base}/api/cases/{case_id}/message", cookie=cookie)
    assert status == 200 and "sandbox" in headers["Content-Security-Policy"]
    assert "script-src" not in headers["Content-Security-Policy"]  # default-src 'none' blocks scripts
    assert f"/api/cases/{case_id}/files/2" in body.decode()


def test_static_files_cannot_escape_their_folder(app):
    _, base, _ = app
    assert call(f"{base}/../server.py")[0] == 404
    assert call(f"{base}/%2e%2e/server.py")[0] == 404
    assert call(f"{base}/healthz")[0] == 200


def test_the_activity_log_shows_who_did_what_on_which_email(app):
    _, base, case_id = app
    cookie = sign_in(base)
    etag = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])["case"]["_etag"]
    call(f"{base}/api/cases/{case_id}/review", {"_etag": etag, "finalCategory": "Βεβαίωση άρσης προσημείωσης"}, cookie)
    events = json.loads(call(f"{base}/api/activity", cookie=cookie)[2])["events"]
    assert events[0]["action"] == "reviewed" and events[0]["byName"] == "Ann Example"
    assert events[0]["subject"] == "Βεβαίωση" and events[0]["after"]["finalCategory"] == "Βεβαίωση άρσης προσημείωσης"
    listed = json.loads(call(f"{base}/api/cases", cookie=cookie)[2])["items"][0]
    assert listed["reviewedBy"]["name"] == "Ann Example"  # the list can say who reviewed it


def test_a_review_can_be_reset_back_to_the_review_queue(app):
    server, base, case_id = app
    cookie = sign_in(base)
    etag = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])["case"]["_etag"]
    assert call(f"{base}/api/cases/{case_id}/reset", {"_etag": etag}, cookie)[0] == 400  # not reviewed yet
    call(f"{base}/api/cases/{case_id}/review", {"_etag": etag, "finalCategory": "Βεβαίωση άρσης προσημείωσης"}, cookie)
    reviewed = server.STORE.get("cases", case_id)
    assert call(f"{base}/api/cases/{case_id}/reset", {"_etag": "stale"}, cookie)[0] == 409
    assert call(f"{base}/api/cases/{case_id}/reset", {"_etag": reviewed["_etag"]}, cookie)[0] == 200
    case = server.STORE.get("cases", case_id)
    assert case["status"] == "RECEIVED" and case["finalCategory"] is None and case["reviewedBy"] is None
    reset = [e for e in server.STORE.find("audit", "caseId", case_id) if e["action"] == "reset"][0]
    assert reset["before"]["finalCategory"] == "Βεβαίωση άρσης προσημείωσης" and reset["byName"] == "Ann Example"


def test_a_classified_email_returns_as_review_even_if_it_was_automatic(app):
    server, base, case_id = app
    cookie = sign_in(base)
    case = server.STORE.get("cases", case_id)
    server.STORE.replace("cases", {**case, "route": "AUTO", "classifiedAt": "2026-11-19T08:30:00Z",
                                   "status": "REVIEWED", "finalCategory": "Βεβαίωση άρσης προσημείωσης"})
    etag = server.STORE.get("cases", case_id)["_etag"]
    assert call(f"{base}/api/cases/{case_id}/reset", {"_etag": etag}, cookie)[0] == 200
    case = server.STORE.get("cases", case_id)
    assert case["status"] == "CLASSIFIED" and case["route"] == "REVIEW"
    assert case["routeReasons"][-1].startswith("review reset by Ann Example")


def test_next_fetch_time_follows_the_cron(app):
    from datetime import datetime, timezone

    server = app[0]
    at = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)  # noqa: E731
    assert server.next_run("0 */4 * * *", at("2026-11-19T10:30")) == at("2026-11-19T12:00")
    # Friday 15:00 UTC -> weekday schedule resumes Monday 06:00
    assert server.next_run("0 6,10,14 * * 1-5", at("2026-11-20T15:00")) == at("2026-11-23T06:00")
    assert server.next_run("not a cron", at("2026-11-19T10:30")) is None


def test_each_visit_renews_the_sign_in(app):
    _, base, _ = app
    cookie = sign_in(base)
    status, headers, body = call(f"{base}/api/session", cookie=cookie)
    assert json.loads(body)["user"]["name"] == "Ann Example" and "Max-Age=" in headers["Set-Cookie"]


def _highlight():
    spec = importlib.util.spec_from_file_location("highlight_under_test", SERVER.parent / "highlight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_highlights_wrap_text_only_and_cannot_inject_markup():
    hl = _highlight()
    html_in = ('<p title="ΑΦΜ 094014298">ΑΦΜ <b>094 014 298</b> &amp; παρακαλώ βεβαίωση</p>'
               "<script>var x='094014298'</script>")
    out = hl.mark_html(html_in, [("094014298", "id", "ΑΦΜ"), ("παρακαλώ βεβαίωση", "action", "<b>x</b>")])
    assert '<mark class="hl hl-id" title="ΑΦΜ">094 014 298</mark>' in out          # spaced digits still match
    assert 'title="ΑΦΜ 094014298"' in out                                          # attributes untouched
    assert "<script>var x='094014298'</script>" in out                             # scripts untouched
    assert 'title="&lt;b&gt;x&lt;/b&gt;"' in out and "&amp; " in out              # everything inserted is escaped
    evil = hl.mark_text("say <img src=x onerror=alert(1)> now", [("say", "class", "t")])
    assert "<img" not in evil and "&lt;img" in evil


def test_customer_details_win_where_marks_overlap():
    hl = _highlight()
    out = hl.mark_text("ο οφειλέτης με ΑΦΜ 094014298 ζητά", [("με ΑΦΜ 094014298 ζητά", "class", "c"), ("094014298", "id", "i")])
    assert '<mark class="hl hl-id" title="i">094014298</mark>' in out


def test_attachment_text_view_has_one_section_per_page():
    hl = _highlight()
    page = hl.text_page("one<!-- PageBreak --><table><tr><td>ΑΦΜ</td><td>094014298</td></tr></table>",
                        [("094014298", "id", "ΑΦΜ")], "a.pdf", "Σελίδα {n}")
    assert 'id="p1"' in page and 'id="p2"' in page and "hl-id" in page and "<td>" not in page


def test_chosen_actions_are_saved_cleaned_and_audited(app):
    server, base, case_id = app
    cookie = sign_in(base)
    meta = json.loads(call(f"{base}/api/meta", cookie=cookie)[2])
    assert meta["actions"]["general"] and meta["actions"]["byCategory"]  # catalogue comes from the rule table
    etag = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])["case"]["_etag"]
    bad = {"_etag": etag, "finalCategory": "Βεβαίωση άρσης προσημείωσης", "finalActions": [{"do": "rm -rf"}]}
    assert call(f"{base}/api/cases/{case_id}/review", bad, cookie)[0] == 400
    good = {"_etag": etag, "finalCategory": "Βεβαίωση άρσης προσημείωσης",
            "finalActions": [{"do": "request", "codes": ["R12"], "category": "Βεβαίωση άρσης προσημείωσης", "source": "suggested"},
                             {"do": "forward", "to": "legal@example.test", "source": "added", "extra": "<x>"}]}
    assert call(f"{base}/api/cases/{case_id}/review", good, cookie)[0] == 200
    saved = server.STORE.get("cases", case_id)["finalActions"]
    assert [a["do"] for a in saved] == ["request", "forward"] and saved[1]["to"] == ["legal@example.test"]
    assert "extra" not in saved[1] and saved[0]["codes"] == ["R12"]
    reviewed = [e for e in server.STORE.find("audit", "caseId", case_id) if e["action"] == "reviewed"][0]
    assert len(reviewed["after"]["finalActions"]) == 2


def test_case_list_carries_classifier_progress_and_ignores_a_dead_run(app):
    from datetime import datetime, timedelta, timezone

    server, base, _ = app
    cookie = sign_in(base)
    stamp = lambda s: (datetime.now(timezone.utc) - timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731

    assert json.loads(call(f"{base}/api/cases", cookie=cookie)[2])["classifier"]["running"] is False
    server.STORE.upsert("runs", {"id": "classifier-status", "state": "running", "phase": "classifying",
                                 "done": 3, "total": 10, "current": "c1", "updatedAt": stamp(30)})
    progress = json.loads(call(f"{base}/api/cases", cookie=cookie)[2])["classifier"]
    assert progress["running"] is True and (progress["done"], progress["total"]) == (3, 10)
    assert server.ingest_info()["lastRun"] is None  # the status document is not an ingest run

    server.STORE.upsert("runs", {"id": "classifier-status", "state": "running", "updatedAt": stamp(3600)})
    assert json.loads(call(f"{base}/api/cases", cookie=cookie)[2])["classifier"]["running"] is False


def test_metrics_need_sign_in_and_a_known_range(app):
    _, base, _ = app
    assert call(f"{base}/api/metrics")[0] == 401
    cookie = sign_in(base)
    assert call(f"{base}/api/metrics?days=12", cookie=cookie)[0] == 400
    status, _, body = call(f"{base}/api/metrics?days=all", cookie=cookie)
    data = json.loads(body)
    assert status == 200 and data["totals"]["received"] == 1 and data["totals"]["review"] == 1


def test_no_match_found_is_a_category_and_the_outcome_is_stored(app):
    server, base, case_id = app
    cookie = sign_in(base)
    etag = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])["case"]["_etag"]
    status, _, _ = call(f"{base}/api/cases/{case_id}/review",
                        {"_etag": etag, "finalCategory": "No Match Found", "finalActions": [{"do": "manual"}]}, cookie)
    assert status == 200
    saved = server.STORE.get("cases", case_id)
    assert (saved["finalCategory"], saved["noMatch"], saved["reviewOutcome"], saved["actionsOutcome"]) == (
        "No Match Found", True, "none_fits", "changed")
    after = server.STORE.find("audit", "caseId", case_id)[-1]["after"]
    assert after["modelCategory"] == "Βεβαίωση Οφειλής" and after["proposedActions"] == []
    items = json.loads(call(f"{base}/api/cases", cookie=cookie)[2])["items"]
    assert (items[0]["outcome"], items[0]["actionsOutcome"]) == ("none_fits", "changed")


def test_further_categories_are_kept_in_order_without_repeats(app):
    server, base, case_id = app
    cookie = sign_in(base)
    etag = json.loads(call(f"{base}/api/cases/{case_id}", cookie=cookie)[2])["case"]["_etag"]
    body = {"_etag": etag, "finalCategory": "GDPR", "otherCategories": ["Παράπονα", "GDPR", "Αγωγές", "Παράπονα", "nope"]}
    assert call(f"{base}/api/cases/{case_id}/review", body, cookie)[0] == 200
    assert server.STORE.get("cases", case_id)["otherCategories"] == ["Παράπονα", "Αγωγές"]


def test_excel_export_lists_the_requested_emails(app):
    import io

    from openpyxl import load_workbook

    _, base, case_id = app
    cookie = sign_in(base)
    status, headers, body = call(f"{base}/api/export", {"ids": [case_id, "missing-id"]}, cookie)
    assert status == 200 and headers["Content-Type"].startswith("application/vnd.openxmlformats")
    assert ".xlsx" in headers["Content-Disposition"]
    sheet = load_workbook(io.BytesIO(body)).active
    header = [c.value for c in sheet[1]]
    assert {"Κατάσταση", "Κατηγορία συστήματος", "Τελική κατηγορία", "Τελικές ενέργειες", "Ελεγκτής"} <= set(header)
    assert sheet.max_row == 2
    row = dict(zip(header, [c.value for c in sheet[2]]))
    assert (row["ID"], row["Κατάσταση"], row["Κατηγορία συστήματος"]) == (case_id, "Προς έλεγχο", "Βεβαίωση Οφειλής")
    assert call(f"{base}/api/export", {"ids": [case_id]})[0] == 401  # signed-in users only


def test_page_files_have_fixed_types_even_when_windows_says_otherwise(app, monkeypatch):
    import mimetypes

    _, base, _ = app
    monkeypatch.setattr(mimetypes, "guess_type", lambda *a, **k: ("text/plain", None))  # a Windows registry
    assert call(f"{base}/app.js")[1]["Content-Type"] == "application/javascript; charset=utf-8"
    assert call(f"{base}/app.css")[1]["Content-Type"] == "text/css; charset=utf-8"
    assert call(f"{base}/")[1]["Content-Type"] == "text/html; charset=utf-8"


def test_startup_report_explains_an_empty_case_folder(app, tmp_path, monkeypatch):
    server, _, _ = app
    monkeypatch.setenv("LOCAL_STORE_DIR", str(tmp_path / "nothing"))
    monkeypatch.delenv("LOCAL_BLOB_DIR", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("RESULT_STORAGE_ACCOUNT", raising=False)
    report = "\n".join(server.startup_report())
    assert "(0 emails)" in report and "No emails there" in report and "LOCAL_BLOB_DIR" in report


def test_startup_report_points_at_copied_runs_not_yet_registered(app, tmp_path, monkeypatch):
    server, _, _ = app
    blob, store = tmp_path / "blob", tmp_path / "store"
    for run in ("20261123T080038Z", "20261124T080000Z"):
        (blob / "bronze" / run).mkdir(parents=True)
        (blob / "bronze" / run / "emails.json").write_text("[]")
    (store / "runs").mkdir(parents=True)
    (store / "runs" / "20261123T080038Z.json").write_text("{}")
    monkeypatch.setenv("LOCAL_BLOB_DIR", str(blob))
    monkeypatch.setenv("LOCAL_STORE_DIR", str(store))
    report = "\n".join(server.startup_report())
    assert "1 copied run(s) not in the app yet (20261124T080000Z)" in report and "python -m main" in report
    assert "set in this window" in report  # typed settings win over .env, and the report says so
