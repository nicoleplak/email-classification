"""Scheduled classifier flow, on invented emails: register runs, classify, never overwrite people."""

import json

import pytest

from core import run_classifier as rc
from data.case_store import Conflict, LocalStore

T0 = "2026-11-17T08:00:00Z"


def msg(n, subject="Αίτημα βεβαίωσης", internet_id=None, graph_id=None, received="2026-11-17T07:0{}:00Z"):
    return {
        "id": graph_id or f"graph-{n}",
        "internetMessageId": internet_id or f"<msg-{n}@example.test>",
        "receivedDateTime": received.format(n),
        "conversationId": f"conv-{n}",
        "subject": subject,
        "from": {"emailAddress": {"address": f"sender{n}@example.test"}},
        "eml_blob_path": f"messages/aa/graph-{n}/message.eml",
        "attachments": [{"blob_name": f"attachments/conv-{n}/graph-{n}/file.pdf"}],
    }


class FakeBlob:
    def __init__(self, files=None, fail_uploads=False):
        self.files = dict(files or {})
        self.fail_uploads = fail_uploads

    def list_names(self, prefix):
        return sorted(n for n in self.files if n.startswith(prefix))

    def download(self, name):
        return self.files[name]

    def upload_bytes(self, name, data):
        if self.fail_uploads:
            raise RuntimeError("simulated Blob failure")
        self.files[name] = data

    def put_run(self, run, payload):
        self.files[f"bronze/{run}/emails.json"] = json.dumps(payload).encode("utf-8")


def record(category="Βεβαίωση οφειλής", confidence="100%", status="verified", **extra):
    return {"category": category, "confidence": confidence, "status": status,
            "model_votes": {category: 1.0}, "attachment_evidence_text": "long OCR text", **extra}


class FakeProcessor:
    """Answers per subject; 'boom' raises like a failed LLM call."""

    attachment_processor = None

    def __init__(self, answers=None, on_call=None):
        self.answers = answers or {}
        self.calls = []
        self.on_call = on_call

    def process_batch(self, emails, export, use_thread_context):
        (email,) = emails
        self.calls.append(email["id"])
        if self.on_call:
            self.on_call(email)
        if email["subject"] == "boom":
            raise RuntimeError("model unavailable")
        return self.answers.get(email["subject"], [record()])


@pytest.fixture
def store(tmp_path):
    return LocalStore(tmp_path / "store")


def test_email_id_is_stable_sortable_and_ignores_graph_id():
    a = rc.email_id(msg(1))
    assert a.startswith("20261117T070100Z_") and len(a) == len("20261117T070100Z_") + 8
    assert rc.email_id(msg(1, graph_id="moved-folder-id")) == a


def test_register_both_run_shapes_once_and_dedupe_resends(store):
    blob = FakeBlob()
    blob.put_run("20261027T120626Z", [msg(1)])  # older plain-list run
    blob.put_run("20261117T080000Z", {"messages": [msg(2), msg(3)], "removed": []})
    assert rc.register_runs(store, blob, T0)["new_cases"] == 3

    # A later delta run resends email 2 under a new Graph id (it moved folder).
    blob.put_run("20261117T120000Z", {"messages": [msg(2, graph_id="graph-2-moved")], "removed": []})
    totals = rc.register_runs(store, blob, T0)
    assert totals == {"runs": 1, "new_cases": 0, "resent": 1, "removed": 0, "older_skipped": 0}
    case = store.get("cases", rc.email_id(msg(2)))
    assert case["graphId"] == "graph-2-moved" and case["status"] == "RECEIVED"
    assert case["sourceRefs"]["eml"] == "messages/aa/graph-2/message.eml"
    assert len(store.find("cases", "status", "RECEIVED")) == 3
    assert len(store.find("audit", "action", "registered")) == 3


def test_removed_marks_case_left_mailbox(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(1)], "removed": []})
    blob.put_run("r2", {"messages": [], "removed": [{"id": "graph-1", "@removed": {"reason": "deleted"}}]})
    assert rc.register_runs(store, blob, T0)["removed"] == 1
    assert store.get("cases", rc.email_id(msg(1)))["mailboxState"] == "removed"
    assert store.find("audit", "action", "left mailbox")[0]["reason"] == "deleted"


@pytest.mark.parametrize("records, error, route, reason", [
    ([record()], None, "AUTO", None),
    ([record(confidence="80%")], None, "REVIEW", "confidence 80% is below 95%"),
    ([record(status="needs_identification")], None, "REVIEW", "no tax ID"),
    ([record(status="needs_review")], None, "REVIEW", "not found in the customer registry"),
    ([record(), record(category="ERB")], None, "REVIEW", "different categories"),
    ([record(category="No Match Found")], None, "REVIEW", "no category fits"),
    ([record(attachment_requires_review=True)], None, "REVIEW", "attachment could not be read"),
    ([], "RuntimeError: x", "EXCEPTION", "classification failed"),
    ([], None, "EXCEPTION", "no result"),
])
def test_decide_route(records, error, route, reason):
    got, reasons, _ = rc.decide_route(records, 0.95, error)
    assert got == route
    assert (reason is None and reasons == []) or any(reason in r for r in reasons)


def test_classify_saves_silver_then_case_and_survives_a_bad_email(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(1), msg(2, subject="boom"), msg(3, subject="unclear")], "removed": []})
    processor = FakeProcessor({"unclear": [record(confidence="60%")]})
    summary = rc.run(store, blob, lambda: processor, paused=False, threshold=0.95, now_fn=lambda: T0)

    assert summary["classification"] == {"classified": 3, "auto": 1, "review": 1, "exception": 1, "skipped_held": 0}
    auto = store.get("cases", rc.email_id(msg(1)))
    assert auto["status"] == "CLASSIFIED" and auto["route"] == "AUTO"
    assert auto["finalCategory"] == "Βεβαίωση οφειλής" and auto["confidence"] == 1.0
    assert "attachment_evidence_text" not in auto["payload"]["records"][0]
    silver = json.loads(blob.files[f"{auto['sourceRefs']['silver']}classification_20261117T080000Z.json"])
    assert silver["records"][0]["attachment_evidence_text"] == "long OCR text"  # full detail stays in silver

    failed = store.get("cases", rc.email_id(msg(2, subject="boom")))
    assert failed["route"] == "EXCEPTION" and "model unavailable" in failed["error"]
    review = store.get("cases", rc.email_id(msg(3)))
    assert review["route"] == "REVIEW" and review["finalCategory"] is None
    assert len(store.find("audit", "action", "classified")) == 3

    # Nothing left waiting: the next run classifies nothing and builds no processor.
    again = rc.run(store, blob, lambda: pytest.fail("no work, no processor"), paused=False, threshold=0.95)
    assert again["classification"]["classified"] == 0


def test_paused_registers_but_never_classifies(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(1)], "removed": []})
    summary = rc.run(store, blob, lambda: pytest.fail("paused must not classify"), paused=True, threshold=0.95)
    assert summary["classification"] == "paused"
    assert store.get("cases", rc.email_id(msg(1)))["status"] == "RECEIVED"


def test_held_or_concurrently_saved_cases_are_left_to_people(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(1), msg(2)], "removed": []})
    rc.register_runs(store, blob, T0)

    store.upsert("locks", {"id": rc.email_id(msg(1)), "holder": "reviewer@example.test",
                           "until": "2026-11-17T09:00:00Z", "ttl": 300})

    def reviewer_saves_meanwhile(email):  # a person classifies email 2 while the model works
        case = store.get("cases", rc.email_id(email))
        store.replace("cases", {**case, "status": "REVIEWED", "finalCategory": "ERB"})

    processor = FakeProcessor(on_call=reviewer_saves_meanwhile)
    totals = rc.classify_waiting(store, blob, lambda: processor, lambda: T0, 0.95)

    assert processor.calls == ["graph-2"]  # the locked one was never sent to the model
    assert totals["skipped_held"] == 1 and totals["classified"] == 0
    saved = store.get("cases", rc.email_id(msg(2)))
    assert saved["status"] == "REVIEWED" and saved["finalCategory"] == "ERB"


def test_blob_failure_stops_the_run_and_leaves_the_case_waiting(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(1)], "removed": []})
    blob.fail_uploads = True
    with pytest.raises(RuntimeError, match="simulated Blob failure"):
        rc.run(store, blob, lambda: FakeProcessor(), paused=False, threshold=0.95)
    assert store.get("cases", rc.email_id(msg(1)))["status"] == "RECEIVED"  # retried next run


def test_limit_takes_oldest_first(store):
    blob = FakeBlob()
    blob.put_run("r1", {"messages": [msg(3), msg(1), msg(2)], "removed": []})
    processor = FakeProcessor()
    rc.run(store, blob, lambda: processor, paused=False, threshold=0.95, limit=2)
    assert processor.calls == ["graph-1", "graph-2"]


def test_local_store_etag_and_create_conflicts(store):
    doc = store.create("cases", {"id": "c1", "n": 1})
    store.replace("cases", {**doc, "n": 2})
    with pytest.raises(Conflict):
        store.replace("cases", {**doc, "n": 3})  # stale etag
    with pytest.raises(Conflict):
        store.create("cases", {"id": "c1"})
    assert store.get("cases", "c1")["n"] == 2
