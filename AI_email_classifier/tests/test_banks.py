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


def test_the_spv_mapping_maps_names_codes_and_banks_to_the_customers_accounts(monkeypatch, tmp_path):
    csv = tmp_path / "spvmapping.csv"
    csv.write_text("SPVNAME;SPVCODE;BANK;ALIASES\nSUNRISE I DAC;SUN1;Τράπεζα Πειραιώς;\n"
                   "FRONTIER II;FRT2;;Frontier 2|Φροντίερ\n", encoding="utf-8")
    monkeypatch.setattr(banks, "CSV_FILE", csv)
    banks._cache.clear()
    accounts = [{"spv": "SUNRISE I DAC", "spvCode": "SUN1"}, {"spv": "Frontier II (renamed)", "spvCode": "FRT2"},
                {"spv": "CAIRO", "spvCode": "CAI"}]
    # The bank the SPV came from (BANK column), its code, an alias.
    found = banks.mentions([BODY])
    assert banks.spvs_for(found, ["δάνειο της Τράπεζας Πειραιώς"], accounts)["SUNRISE I DAC"] == "Τράπεζας Πειραιώς"
    assert banks.spvs_for([], ["κωδικός χαρτοφυλακίου FRT2"], accounts) == {"Frontier II (renamed)": "FRT2"}
    assert banks.spvs_for([], ["το δάνειο του Φροντίερ"], accounts) == {"Frontier II (renamed)": "Φροντίερ"}
    assert banks.spvs_for([], ["τίποτα σχετικό"], accounts) == {}
    banks._cache.clear()


def test_new_reasons_have_greek_text():
    assert REASONS["spv_mentioned"] and REASONS["spv_each"]
