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
    assert out["facts"] == {"identified": True, "known": True, "portal": False, "erb": True, "is_3869": True}


def test_an_email_used_in_past_requests_plus_a_name_confirms(registry):
    history = RequestHistory(pd.DataFrame([{"AFM": "094014298", "EMAIL": "client@example.test",
                                            "REQUEST_TYPE_DSC": "Βεβαίωση οφειλής", "REQUEST_STATUS": "Closed",
                                            "REQUEST_CREATED": "2026-10-01", "CLOSED_REQUEST_FLAG": "Y",
                                            "ACC_ID": "", "CUST_FIRST_NM": "", "CUST_LAST_NM": ""}]))
    out = find_customers(registry, history, [], [], [{"value": "Client@Example.test", "where": {}}], NAME)
    confirmed = [c for c in out["customers"] if c["status"] == "confirmed"]
    assert [c["taxId"] for c in confirmed] == ["094014298"]
    assert confirmed[0]["recentRequests"][0]["type"] == "Βεβαίωση οφειλής"


def test_a_tax_id_whose_owner_has_another_name_is_flagged(registry):
    out = find_customers(registry, RequestHistory.empty(), [{"value": "111111111", "where": {}}], [], [], NAME)
    maria = next(c for c in out["customers"] if c["taxId"] == "111111111")
    assert maria["status"] == "confirmed" and maria.get("nameMismatch") is True
    assert rc.understanding_reasons({"customers": out["customers"]})  # sends the case to review


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


def test_an_email_with_no_customer_goes_to_review():
    assert rc.understanding_reasons({"customers": []}) == ["no customer found in the registry"]
    assert rc.understanding_reasons({"customers": [{"status": "confirmed"}]}) == []


def test_old_ingest_runs_are_skipped_but_imports_are_not():
    assert rc.wanted_run("import-20261119T120000Z", "20261119T130000Z")
    assert not rc.wanted_run("20261027T120626Z", "20261119T130000Z")
    assert rc.wanted_run("20261119T160000Z", "20261119T130000Z")
    assert rc.wanted_run("20261027T120626Z", "")
