from core import banks
from core.action_rules import REASONS

BODY = {"text": "Αφορά δάνειο της Τράπεζας Πειραιώς, παλαιότερα της EFG Eurobank. Χαρτοφυλάκιο Cairo.", "where": {"kind": "body"}}
STREET = {"text": "Διεύθυνση: Οδός Πειραιώς 23, Αθήνα", "where": {"kind": "attachment", "file": "a.pdf", "page": 1}}


def test_banks_are_found_with_greek_case_endings_and_eurobank_flags_erb():
    found = banks.mentions([BODY, STREET])
    assert [(m["bank"], m["written"]) for m in found] == [("Eurobank", "EFG Eurobank"), ("Τράπεζα Πειραιώς", "Τράπεζας Πειραιώς")]
    assert banks.flags(found) == ["ERB"]
    assert banks.mentions([STREET]) == []  # a street name is not the bank
    assert banks.flags(banks.mentions([{"text": "ΕΥΡΩΜΠΑΝΚ ΕΡΓΑΣΙΑΣ", "where": {}}])) == ["ERB"]


def test_spv_named_in_the_text_matches_the_customers_portfolio():
    accounts = [{"spv": "CAIRO II DAC"}, {"spv": "FRONTIER"}, {"spv": "—"}]
    assert banks.spvs_for([], [BODY["text"]], accounts) == {"CAIRO II DAC": "CAIRO II DAC"}
    assert banks.spvs_for([], ["τίποτα σχετικό"], accounts) == {}


def test_spv_listed_under_a_bank_matches(monkeypatch):
    real = banks.config()
    monkeypatch.setattr(banks, "config", lambda: {**real, "Τράπεζα Πειραιώς": {**real["Τράπεζα Πειραιώς"], "spvs": ["Sunrise I"]}})
    found = banks.mentions([BODY])
    assert banks.spvs_for(found, [BODY["text"]], [{"spv": "SUNRISE I"}, {"spv": "FRONTIER"}]) == {"SUNRISE I": "Τράπεζας Πειραιώς"}


def test_new_reasons_have_greek_text():
    assert REASONS["spv_mentioned"] and REASONS["spv_each"]
