"""Warehouse export: changed emails only, all their rows, CSV the warehouse can COPY."""

import csv
import io
import json

from core import dwh_export
from data.case_store import LocalStore


def case(case_id, updated, status="CLASSIFIED", **extra):
    return {"id": case_id, "status": status, "route": "REVIEW", "receivedAt": "2026-11-20T08:00:00Z", "from": "c@example.test",
            "subject": "Βεβαίωση, «οφειλής»", "modelCategory": "Βεβαιώσεις οφειλής", "confidence": 0.74, "updatedAt": updated,
            "classifiedAt": updated, "sourceRefs": {"ingestRun": "run1"},
            "understanding": {"customers": [{"taxId": "094014298", "name": "Χ", "status": "confirmed"}],
                              "customerFacts": {"identified_via": "debtor"},
                              "actions": [{"do": "request", "category": "Βεβαιώσεις οφειλής", "code": "105", "account": "1"}],
                              "extracted": [{"type": "afm", "value": "094014298", "identifiesCase": True,
                                             "sources": [{"kind": "body", "snippet": "ΑΦΜ 094014298"}]}]},
            **extra}


def read(files, name):
    return list(csv.DictReader(io.StringIO(files[name].decode("utf-8"))))


def test_only_changed_emails_go_out_with_all_their_rows_and_the_watermark_moves(tmp_path):
    store = LocalStore(tmp_path)
    store.create("cases", case("a", "2026-11-20T09:00:00Z"))
    store.create("cases", case("b", "2026-11-26T09:00:00Z", status="REVIEWED", reviewedAt="2026-11-26T10:00:00Z",
                               reviewedBy={"name": "Ελεγκτής"}, finalCategory="Βεβαιώσεις οφειλής",
                               finalActions=[{"do": "reply", "template": "received"}]))
    store.create("cases", {"id": "c", "status": "RECEIVED", "updatedAt": "2026-11-26T09:00:00Z"})  # not classified yet
    store.upsert("data", {"id": "a", "rows": [{"id": "r1", "type": "account", "value": "4000000000001", "status": "added",
                                               "source": {"kind": "user"}, "by": "Ελεγκτής", "at": "2026-11-26T11:00:00Z"}],
                          "updatedAt": "2026-11-26T11:00:00Z"})
    store.upsert("runs", {"id": dwh_export.STATUS_ID, "lastExportAt": "2026-11-25T00:00:00Z"})
    files = {}
    summary = dwh_export.export(store, files.__setitem__, now_fn=lambda: "2026-11-27T10:15:00Z")
    assert summary["emails"] == 2  # b was reviewed; a only had its data corrected
    email_file = summary["files"]["EMCLF_EMAIL"]["file"]
    assert email_file == "gold/dwh/EMCLF_EMAIL/2026/11/27/EMCLF_EMAIL_20261127T101500Z.csv"
    emails = {r["case_id"]: r for r in read(files, email_file)}
    assert emails["b"]["reviewed_by"] == "Ελεγκτής" and emails["a"]["customer_tax_id"] == "094014298"
    assert emails["a"]["subject"] == "Βεβαίωση, «οφειλής»"  # commas and quotes survive
    data = read(files, summary["files"]["EMCLF_EMAIL_DATA"]["file"])
    assert {(r["case_id"], r["type"], r["status"]) for r in data} == {("a", "account", "added"), ("b", "afm", "found")}
    actions = read(files, summary["files"]["EMCLF_EMAIL_ACTION"]["file"])
    assert {(r["case_id"], r["stage"], r["action"]) for r in actions} == {
        ("a", "proposed", "request"), ("b", "proposed", "request"), ("b", "final", "reply")}
    assert json.loads(files["gold/dwh/_manifests/20261127T101500Z.json"])["emails"] == 2
    # Nothing changed since: an empty run writes no files, the watermark still moves.
    files.clear()
    assert dwh_export.export(store, files.__setitem__, now_fn=lambda: "2026-11-27T14:00:00Z")["emails"] == 0 and not files
    assert store.get("runs", dwh_export.STATUS_ID)["lastExportAt"] == "2026-11-27T14:00:00Z"
    assert dwh_export.export(store, files.__setitem__, full=True, now_fn=lambda: "2026-11-27T15:00:00Z")["emails"] == 2


def test_snippets_can_be_left_out():
    rows = dwh_export.data_rows_of({"id": "a"}, [{"id": "r", "type": "afm", "value": "1", "snippet": "Παπαδόπουλος"}], "t",
                                   snippets=False)
    assert rows[0]["snippet"] is None
