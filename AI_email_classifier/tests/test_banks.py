from core import banks
from core.action_rules import REASONS

BODY = {"text": "Αφορά δάνειο της Τράπεζας Πειραιώς, παλαιότερα της EFG Eurobank. Χαρτοφυλάκιο Cairo.", "where": {"kind": "body"}}
STREET = {"text": "Διεύθυνση: Οδός Πειραιώς 23, Αθήνα", "where": {"kind": "attachment", "file": "a.pdf", "page": 1}}


def test_eurobank_is_found_in_any_spelling_and_flags_erb():
    found = banks.mentions([BODY, STREET])
    assert [(m["bank"], m["written"]) for m in found] == [("Eurobank", "EFG Eurobank")]
    assert banks.flags(found) == ["ERB"]
    assert banks.mentions([STREET]) == []
    assert banks.flags(banks.mentions([{"text": "της ΕΥΡΩΜΠΑΝΚ ΕΡΓΑΣΙΑΣ", "where": {}}])) == ["ERB"]
    assert banks.flags(banks.mentions([{"text": "Τράπεζα Εργασίας", "where": {}}])) == ["ERB"]


def test_spv_named_in_the_text_matches_the_customers_portfolio():
    accounts = [{"spv": "CAIRO II DAC"}, {"spv": "FRONTIER"}, {"spv": "—"}]
    assert banks.spvs_for([], [BODY["text"]], accounts) == {"CAIRO II DAC": "CAIRO II DAC"}
    assert banks.spvs_for([], ["τίποτα σχετικό"], accounts) == {}


def test_the_spv_mapping_maps_names_and_codes_to_the_customers_accounts(monkeypatch, tmp_path):
    csv = tmp_path / "spvmapping.csv"
    csv.write_text("SPVNAME;SPVCODE\nSUNRISE I DAC;SUN1\nFRONTIER II;FRT2\n", encoding="utf-8-sig")  # as Excel saves it
    monkeypatch.setattr(banks, "CSV_FILE", csv)
    banks._cache.clear()
    accounts = [{"spv": "SUNRISE I DAC", "spvCode": "SUN1"}, {"spv": "Frontier 2 Designated Activity", "spvCode": "FRT2"},
                {"spv": "CAIRO", "spvCode": "CAI"}]
    # The name or the code written in the text; matched to the account by code even when the names differ.
    assert banks.spvs_for([], ["δάνειο του Sunrise"], accounts) == {"SUNRISE I DAC": "Sunrise"}
    assert banks.spvs_for([], ["κωδικός χαρτοφυλακίου FRT2"], accounts) == {"Frontier 2 Designated Activity": "FRT2"}
    assert banks.spvs_for([], ["Frontier II"], accounts) == {"Frontier 2 Designated Activity": "Frontier"}
    assert banks.spvs_for([], ["τίποτα σχετικό"], accounts) == {}
    csv.write_text("SPVNAME,SPVCODE\nSUNRISE I DAC,SUN1\n", encoding="utf-8")  # commas work too
    banks._cache.clear()
    assert [r["code"] for r in banks.spv_rows()] == ["SUN1"]
    banks._cache.clear()


def test_new_reasons_have_greek_text():
    assert REASONS["spv_mentioned"] and REASONS["spv_each"]
