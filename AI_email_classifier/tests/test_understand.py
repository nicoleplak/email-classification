"""Customer lookup and email reading, on invented data only."""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from core import run_classifier as rc
from core.customer_lookup import Registry, RequestHistory, find_customers, normalize_name
from core.understand import documents, understand

# 094014298 and 090000045 pass the AFM check digit; the people are invented.
REGISTRY = pd.DataFrame(
    [
        {"TAX_ID_NO": "094014298", "NAME": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΙΩΑΝΝΗΣ ΤΟΥ ΓΕΩΡΓΙΟΥ", "ACC_UNQ_CD": "1000000000001",
         "SRV_ACC_UNQ_CD": "", "ACC_ID": "", "SOURCE": "Qualco", "CST_STS_NM": "Active", "PORTAL_FLAG": "Y",
         "CST_UNQ_CD": "C1", "PRTFL_NM": "Portfolio A"},
        {"TAX_ID_NO": "090000045", "NAME": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΙΩΑΝΝΗΣ ΤΟΥ ΝΙΚΟΛΑΟΥ", "ACC_UNQ_CD": "1000000000002",
         "SRV_ACC_UNQ_CD": "", "ACC_ID": "", "SOURCE": "Datamart", "CST_STS_NM": "Ν.3869", "PORTAL_FLAG": "N",
         "CST_UNQ_CD": "C2", "PRTFL_NM": "Portfolio B"},
        {"TAX_ID_NO": "111111111", "NAME": "ΓΕΩΡΓΙΟΥ ΜΑΡΙΑ", "ACC_UNQ_CD": "1000000000003",
         "SRV_ACC_UNQ_CD": "", "ACC_ID": "", "SOURCE": "Qualco", "CST_STS_NM": "Active", "PORTAL_FLAG": "N",
         "CST_UNQ_CD": "C3", "PRTFL_NM": "Portfolio A"},
    ]
)
NAME = [{"value": "Ιωάννης Παπαδόπουλος", "where": {"kind": "body"}, "principal": True, "role": "debtor"}]


@pytest.fixture
def registry():
    return Registry(REGISTRY, "in/qualco_output_20261119.csv")


def test_names_ignore_accents_and_case():
    assert normalize_name("Παπαδόπουλος  Γιώργος-Ιωάννης") == "ΠΑΠΑΔΟΠΟΥΛΟΣ ΓΙΩΡΓΟΣ ΙΩΑΝΝΗΣ"


def test_a_shared_name_lists_everyone_and_confirms_no_one(registry):
    out = find_customers(registry, RequestHistory.empty(), [], [], [], NAME)
    assert sorted(c["taxId"] for c in out["customers"]) == ["090000045", "094014298"]
    assert {c["status"] for c in out["customers"]} == {"possible"}
    assert all(c["sameNameCount"] == 2 for c in out["customers"])
    assert out["facts"]["known"] is False


def test_an_account_number_picks_out_one_of_the_namesakes(registry):
    out = find_customers(registry, RequestHistory.empty(), [], [{"value": "1000000000002", "where": {}}], [], NAME)
    first = out["customers"][0]
    assert first["taxId"] == "090000045" and first["status"] == "confirmed" and first["principal"]
    facts = {k: out["facts"][k] for k in ("identified", "known", "portal", "erb", "is_3869", "named_accounts")}
    assert facts == {"identified": True, "known": True, "portal": False, "erb": True, "is_3869": True,
                     "named_accounts": ["1000000000002"]}
    assert [(a["account"], a["spv"], a["state"], a["is3869"]) for a in out["facts"]["accounts"]] == [
        ("1000000000002", "Portfolio B", "unknown", True)]


def test_an_email_used_in_past_requests_plus_a_name_stays_possible(registry):
    """Names and emails are complementary: together they still do not identify the customer."""
    history = RequestHistory(pd.DataFrame([{"AFM": "094014298", "EMAIL": "client@example.test",
                                            "REQUEST_TYPE_DSC": "Βεβαίωση οφειλής", "REQUEST_STATUS": "Closed",
                                            "REQUEST_CREATED": "2026-10-01", "CLOSED_REQUEST_FLAG": "Y",
                                            "ACC_ID": "", "CUST_FIRST_NM": "", "CUST_LAST_NM": ""}]))
    out = find_customers(registry, history, [], [], [{"value": "Client@Example.test", "where": {}}], NAME)
    assert not [c for c in out["customers"] if c["status"] == "confirmed"]
    ioannis = next(c for c in out["customers"] if c["taxId"] == "094014298")
    assert ioannis["status"] == "possible" and {e["kind"] for e in ioannis["matchedOn"]} == {"email", "name"}
    assert ioannis["recentRequests"][0]["type"] == "Βεβαίωση οφειλής"
    assert out["facts"]["known"] is False and out["facts"]["identified"] is False


def test_open_or_closed_comes_from_the_configured_column(registry, monkeypatch):
    df = REGISTRY.assign(ACC_STATE=["Ανοιχτός", "Κλειστός", ""])
    reg = Registry(df, "x")
    assert {a["state"] for a in reg.accounts("094014298")} == {"unknown"}  # column not configured yet
    monkeypatch.setenv("ACCOUNT_STATUS_COLUMN", "ACC_STATE")
    assert [a["state"] for a in reg.accounts("094014298")] == ["open"]
    assert [a["state"] for a in reg.accounts("090000045")] == ["closed"]
    assert [a["state"] for a in reg.accounts("111111111")] == ["unknown"]


def test_a_tax_id_whose_owner_has_another_name_is_flagged(registry):
    out = find_customers(registry, RequestHistory.empty(), [{"value": "111111111", "where": {}}], [], [], NAME)
    maria = next(c for c in out["customers"] if c["taxId"] == "111111111")
    assert maria["status"] == "confirmed" and maria.get("nameMismatch") is True
    # Shown to the reviewer, but a name is complementary: it does not send the case to review.
    assert rc.understanding_reasons({"customers": out["customers"], "actions": [{"do": "request"}]}) == []


def test_unknown_identifiers_are_reported_not_dropped(registry):
    out = find_customers(registry, RequestHistory.empty(), [{"value": "999999999", "where": {}}], [], [], [])
    assert out["unmatched"][0]["value"] == "999999999" and out["customers"] == []


def test_documents_know_the_attachment_and_page(tmp_path):
    (tmp_path / "Aitisi_x1.txt").write_text("σελίδα ένα<!-- PageBreak -->ΑΦΜ 094014298", encoding="utf-8")
    (tmp_path / "Aitisi_x1.json").write_text(json.dumps({"filename": "Αίτηση.pdf"}), encoding="utf-8")
    docs = documents({"subject": "Θέμα", "body": {"body_clean": "κείμενο"}}, tmp_path)
    assert docs[-1]["where"] == {"kind": "attachment", "file": "Αίτηση.pdf", "page": 2}


class FakeClient:
    """Answers the one structured call the way the model would, for the candidates it is shown."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        from core.action_rules import FLAGS

        user = json.loads(kwargs["messages"][1]["content"])
        answer = {
            "analysis": "debt certificate request",
            "candidates": [
                {"id": c["id"], "field": "afm" if c["hint"] == "afm" else "other", "role": "debtor",
                 "identifies_case": c["hint"] == "afm", "certainty": "high"}
                for c in user["candidates"]
            ],
            "people": [{"name": "Γιάννης Παπαδόπουλος", "registry_form": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΙΩΑΝΝΗΣ", "role": "debtor",
                        "is_principal": True, "evidence": "ο οφειλέτης Γιάννης Παπαδόπουλος", "source": "body"}],
            "flags": {k: k == "asks_debt_certificate" for k in FLAGS},
            "other_requests": [],
            "evidence": [
                {"quote": "Παρακαλώ βεβαίωση οφειλής", "supports": "action", "flag": "asks_debt_certificate", "source": "body"},
                {"quote": "the sender clearly wants a certificate", "supports": "category", "flag": "", "source": "body"},
            ],
        }
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))])


def test_understand_ties_every_value_to_its_source(registry):
    message = {
        "id": "m1",
        "subject": "Βεβαίωση οφειλής",
        "from": {"emailAddress": {"address": "lawyer@example.test", "name": "Δικηγόρος"}},
        "body": {"body_clean": "Παρακαλώ βεβαίωση οφειλής για τον οφειλέτη Γιάννης Παπαδόπουλος, ΑΦΜ 094014298."},
    }
    out = understand(client=FakeClient(), model="m", message=message, records=[{"category": "Βεβαίωση Οφειλής"}],
                     text_dir=None, categories=["Βεβαίωση Οφειλής"], registry=registry,
                     history=RequestHistory.empty())
    afm = next(e for e in out["extracted"] if e["type"] == "afm")
    assert afm["value"] == "094014298" and afm["checked"] and afm["sources"][0]["kind"] == "body"
    assert "094014298" in afm["sources"][0]["snippet"]
    assert any(e["type"] == "email" and e["sources"][0]["kind"] == "sender" for e in out["extracted"])
    assert out["customers"][0]["taxId"] == "094014298" and out["customers"][0]["status"] == "confirmed"
    assert out["people"][0]["principal"] and out["flags"] == ["asks_debt_certificate"]
    assert out["actions"] and all(a["reasons"] for a in out["actions"])
    assert out["registrySource"] == "in/qualco_output_20261119.csv"
    # an exact quote is kept as evidence; a paraphrase the sender never wrote is dropped
    assert [e["quote"] for e in out["evidence"]] == ["Παρακαλώ βεβαίωση οφειλής"]
    assert out["evidence"][0]["where"]["kind"] == "body" and out["evidence"][0]["flag"] == "asks_debt_certificate"


def test_an_email_with_no_customer_goes_to_review_only_when_an_action_needs_one():
    request = [{"do": "request"}]
    assert rc.understanding_reasons({"customers": [], "actions": request}) == [
        "no customer found in the registry by tax ID or account"]
    assert rc.understanding_reasons({"customers": [{"status": "possible"}], "actions": request}) == [
        "no customer found in the registry by tax ID or account"]  # a name match is not enough
    assert rc.understanding_reasons({"customers": [{"status": "confirmed"}], "actions": request}) == []
    assert rc.understanding_reasons({"customers": [], "actions": [{"do": "forward"}]}) == []
    assert not rc.identification_waived({"customers": [], "actions": request})
    assert rc.identification_waived({"customers": [{"status": "confirmed"}], "actions": request})
    assert rc.identification_waived({"customers": [], "actions": [{"do": "outlook_folder"}]})


def test_account_complaint_and_distress_reasons():
    u = {"customers": [{"status": "confirmed"}], "actions": [{"do": "request", "caveat": "account_not_identified"}],
         "complaintDemoted": True, "principalCategory": "GDPR", "flags": ["distress_or_threat"]}
    assert rc.understanding_reasons(u) == [
        "the account or portfolio (SPV) the request concerns is not identified",
        "the complaint is not the main request: the email also asks for GDPR",
        "the email mentions self-harm or threatens legal action"]


def test_old_ingest_runs_are_skipped_but_imports_are_not():
    assert rc.wanted_run("import-20261119T120000Z", "20261119T130000Z")
    assert not rc.wanted_run("20261027T120626Z", "20261119T130000Z")
    assert rc.wanted_run("20261119T160000Z", "20261119T130000Z")
    assert rc.wanted_run("20261027T120626Z", "")


def test_older_emails_that_only_changed_are_not_new_work():
    assert rc.received_cutoff("20261119T130000Z", "20261119T125515Z") == "2026-11-19T12:55:15Z"
    assert rc.received_cutoff("import-20261119T103340Z", "20261119T125515Z") == ""
    from data.case_store import LocalStore
    import tempfile

    class Blob:
        def list_names(self, prefix):
            return ["bronze/20261119T130000Z/emails.json"]

        def download(self, name):
            msgs = [{"id": "old", "internetMessageId": "<old@x>", "receivedDateTime": "2026-11-12T09:00:00Z"},
                    {"id": "new", "internetMessageId": "<new@x>", "receivedDateTime": "2026-11-19T13:01:00Z"}]
            return json.dumps({"messages": msgs, "removed": []}).encode()

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(tmp)
        totals = rc.register_runs(store, Blob(), "2026-11-19T13:05:00Z", "20261119T125515Z")
        assert totals["new_cases"] == 1 and totals["older"] == 1


def test_a_confident_second_category_brings_its_actions(registry):
    message = {
        "id": "m1", "subject": "Βεβαίωση οφειλής και σύμβαση",
        "from": {"emailAddress": {"address": "lawyer@example.test", "name": "Δικηγόρος"}},
        "body": {"body_clean": "Παρακαλώ βεβαίωση οφειλής και αντίγραφο σύμβασης, ΑΦΜ 094014298."},
    }
    records = [{"category": "Βεβαιώσεις οφειλής", "model_other_categories": {"Αντίγραφα συμβάσεων": 0.8, "GDPR": 0.4}}]
    out = understand(client=FakeClient(), model="m", message=message, records=records, text_dir=None,
                     categories=["Βεβαιώσεις οφειλής", "Αντίγραφα συμβάσεων", "GDPR"], registry=registry,
                     history=RequestHistory.empty())
    assert out["autoCategories"] == [{"category": "Αντίγραφα συμβάσεων", "confidence": 0.8}]
    assert "Αντίγραφα συμβάσεων" in out["otherRequests"] and "GDPR" not in out["otherRequests"]
    assert any(a["category"] == "Αντίγραφα συμβάσεων" and a["do"] == "request" for a in out["actions"])
