"""The email's data table: rows from the classifier, reviewer corrections, the decision made again."""

import pandas as pd

from core.customer_lookup import Registry
from core.data_rows import merge, redecide, rows_from_understanding

REGISTRY = Registry(pd.DataFrame([
    {"TAX_ID_NO": "094014298", "NAME": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΙΩΑΝΝΗΣ", "ACC_UNQ_CD": acc, "SRV_ACC_UNQ_CD": "", "ACC_ID": "",
     "SOURCE": "Qualco", "CST_STS_NM": "Active", "PORTAL_FLAG": "N", "CST_UNQ_CD": "C1", "PRTFL_NM": spv, "PRTFL_CD": spv[:3]}
    for acc, spv in (("1000000000001", "ALPHA"), ("1000000000002", "BETA"), ("1000000000003", "BETA"))]), "registry.csv")
UNDERSTANDING = {
    "principalCategory": "Δοσολόγιο", "otherRequests": [], "flags": [], "people": [], "customers": [],
    "extracted": [{"type": "email", "value": "c@example.test", "role": None, "identifiesCase": False,
                   "sources": [{"kind": "sender", "snippet": ""}]}],
    "actions": [{"do": "ask_identification"}], "customerFacts": {},
}


def test_classifier_rows_carry_their_source_and_reviewer_rows_survive_a_new_classification():
    found = rows_from_understanding("case1", {**UNDERSTANDING, "extracted": [
        {"type": "afm", "value": "094014298", "role": "debtor", "identifiesCase": True, "checked": True,
         "method": "pattern + check digit + model", "sources": [{"kind": "attachment", "file": "a.pdf", "page": 2, "snippet": "ΑΦΜ 094014298"}]}]})
    assert found[0]["source"] == {"kind": "attachment", "file": "a.pdf", "page": 2} and found[0]["snippet"] == "ΑΦΜ 094014298"
    added = {"id": "x", "type": "account", "value": "1000000000002", "status": "added"}
    assert [r["id"] for r in merge(found, [*found, added])] == [found[0]["id"], "x"]


def test_an_account_typed_by_the_reviewer_finds_the_customer_and_brings_the_request():
    # Δοσολόγιο needs the account; the email had none, so the rules asked for it.
    rows = rows_from_understanding("case1", UNDERSTANDING) + [
        {"id": "u1", "type": "account", "value": "1000000000002", "role": "debtor", "identifiesCase": True, "status": "added",
         "source": {"kind": "user"}}]
    new = redecide(UNDERSTANDING, rows, REGISTRY, ["Δοσολόγιο"])
    assert new["customers"][0]["taxId"] == "094014298" and new["customers"][0]["status"] == "confirmed"
    request = next(a for a in new["actions"] if a["do"] == "request")
    assert request["account"] == "1000000000002" and request["spv"] == "BETA"
    assert any(e["type"] == "account" and e["sources"][0]["kind"] == "user" for e in new["extracted"])
    # Removing it again: no customer, back to asking.
    rows[-1]["status"] = "removed"
    assert not redecide(UNDERSTANDING, rows, REGISTRY, ["Δοσολόγιο"])["customers"]


def test_a_tax_id_with_a_bad_check_digit_is_never_used_and_an_spv_row_picks_the_spv():
    rows = [{"id": "u1", "type": "afm", "value": "094014299", "identifiesCase": True, "status": "added"}]
    assert not redecide(UNDERSTANDING, rows, REGISTRY, ["Δοσολόγιο"])["customers"]
    rows = [{"id": "u1", "type": "afm", "value": "094014298", "identifiesCase": True, "status": "added"},
            {"id": "u2", "type": "spv", "value": "BETA", "status": "added"}]
    new = redecide(UNDERSTANDING, rows, REGISTRY, ["Εξουσιοδοτήσεις"])  # SPV category: one account of that SPV
    assert [a["spv"] for a in new["actions"] if a["do"] == "request"] == ["BETA"]
