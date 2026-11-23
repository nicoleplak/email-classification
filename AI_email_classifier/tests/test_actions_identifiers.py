"""Rule table against the spec's own worked examples, and the candidate finder on tricky text."""

import json
from pathlib import Path

import pytest

from core.action_rules import FLAGS, REASONS, REPLIES, RULES, code_name, decide, explain, order_requests
from evaluation.email_chain import split_chain
from core.identifiers import find_candidates, merge_candidates, mod97_valid
from utils.afm_utils import afm_checksum_valid
from utils.html_text import html_to_text

def acct(number, spv="SPV A", state="unknown", is3869=False):
    return {"account": number, "otherNumbers": [], "spv": spv, "state": state, "is3869": is3869, "erb": False}


ONE = [acct("4000000000001")]
TWO_SPVS = [acct("4000000000001", "SPV A"), acct("4000000000002", "SPV A"), acct("4000000000009", "SPV B")]
NO_PORTAL_CUSTOMER = {"identified": True, "known": True, "portal": False, "accounts": TWO_SPVS}
PORTAL_CUSTOMER = {**NO_PORTAL_CUSTOMER, "portal": True}
DEBT = "Βεβαιώσεις οφειλής"          # Portal = YES, request per SPV
AUTH = "Εξουσιοδοτήσεις"             # request on one account of the identified SPV
SCHEDULE = "Δοσολόγιο"               # Portal = YES, the account must be identified
COPIES = "Αντίγραφα συμβάσεων"       # the account must be identified
GDPR = "GDPR"                        # request per SPV


def make_afm(prefix: str = "12345678") -> str:
    """A checksum-valid AFM. Synthetic, so no real tax ID lives in this test."""
    total = sum(int(d) * 2 ** (8 - i) for i, d in enumerate(prefix))
    return prefix + str((total % 11) % 10)


def of(actions, do):
    return [a for a in actions if a["do"] == do]


def only(actions, do="request"):
    found = of(actions, do)
    assert len(found) == 1, actions
    return found[0]


def reply(actions):
    replies = [a for a in actions if a.get("template")]
    assert len(replies) == 1, actions
    return replies[0]["template"]


# Portal first: the Portal flag means "go to the Portal", unless the Portal has a technical problem.
def test_debt_certificate_portal_customer_gets_the_portal_reply():
    actions = decide([DEBT], {}, PORTAL_CUSTOMER)
    assert [a["do"] for a in actions] == ["portal_referral"] and reply(actions) == "portal"
    assert "has_portal" in actions[0]["because"] and "Portal" in actions[0]["text"]


def test_technical_issue_with_the_portal_opens_the_request_instead():
    actions = decide([DEBT], {"cannot_use_online": True}, PORTAL_CUSTOMER)
    assert {a["code"] for a in of(actions, "request")} == {"89"} and reply(actions) == "received"
    assert "cannot_use_online" in of(actions, "request")[0]["because"]


def test_debt_certificate_heir_opens_111_even_with_portal():
    assert {a["code"] for a in of(decide([DEBT], {"is_heir": True}, PORTAL_CUSTOMER), "request")} == {"111"}


def test_breakdown_and_3869_codes():
    assert {a["code"] for a in of(decide([DEBT], {"wants_breakdown": True}, NO_PORTAL_CUSTOMER), "request")} == {"91"}
    customer = {**NO_PORTAL_CUSTOMER, "is_3869": True}
    assert {a["code"] for a in of(decide([DEBT], {}, customer), "request")} == {"105"}


def test_3869_decision_is_registered_despite_the_portal_flag():
    action = of(decide(["Αιτήματα Ν.3869"], {"decision_3869_attached": True}, PORTAL_CUSTOMER), "request")[0]
    assert action["code"] == "161" and action["codeName"] == "Προσκόμιση απόφασης Ν.3869"


def test_one_non_online_request_cancels_every_referral():
    actions = decide([DEBT, GDPR], {}, PORTAL_CUSTOMER)
    assert not of(actions, "portal_referral") and {a["category"] for a in of(actions, "request")} == {DEBT, GDPR}
    assert "other_request_offline" in of(actions, "request")[0]["because"]


def test_all_online_requests_are_referred():
    actions = decide([DEBT, SCHEDULE], {}, PORTAL_CUSTOMER)
    assert {a["do"] for a in actions} == {"portal_referral"}


def test_unidentified_online_request_goes_to_the_portal():
    assert [a["do"] for a in decide([DEBT], {}, {})] == ["portal_referral"]


# Open-case codes only (no _cust) until the registry says an account is closed.
def test_open_case_code_without_cust_while_the_state_is_unknown():
    action = of(decide([COPIES], {"all_debts": True}, NO_PORTAL_CUSTOMER), "request")[0]
    assert (action["code"], action["closedCode"], action["accountState"]) == ("154", "155", "unknown")
    assert "account_state_unknown" in action["because"] and "_cust" not in action["codeName"].lower()


def test_closed_account_gets_the_cust_code():
    customer = {**NO_PORTAL_CUSTOMER, "accounts": [acct("4000000000001", state="closed")]}
    action = only(decide([COPIES], {}, customer))
    assert (action["code"], action["codeName"]) == ("155", "Χορήγηση_Συμβατικών Εγγράφων_cust")
    assert "account_closed" in action["because"]


# Which account: per SPV, the account itself, or one account of the SPV.
def test_per_spv_opens_one_request_per_portfolio():
    actions = of(decide([GDPR], {}, NO_PORTAL_CUSTOMER), "request")
    assert [(a["spv"], a["account"]) for a in actions] == [("SPV A", "4000000000001"), ("SPV B", "4000000000009")]
    assert all("per_spv" in a["because"] for a in actions)


def test_per_spv_uses_the_account_the_email_names():
    customer = {**NO_PORTAL_CUSTOMER, "named_accounts": ["4000000000002"]}
    assert [a["account"] for a in of(decide([GDPR], {}, customer), "request")] == ["4000000000002"]


def test_open_cases_and_3869_accounts_come_first_when_picking_one():
    customer = {**NO_PORTAL_CUSTOMER, "accounts": [acct("1", state="closed"), acct("3", is3869=True), acct("2")]}
    assert only(decide([GDPR], {}, customer))["account"] == "2"  # open case, then lowest number
    assert only(decide(["Αιτήματα Ν.3869"], {"asks_instalment": True}, customer))["account"] == "3"  # Ν.3869 account


def test_account_mode_needs_the_account():
    actions = decide([COPIES], {}, NO_PORTAL_CUSTOMER)
    assert not of(actions, "request") and reply(actions) == "need_more_info"
    ask = only(actions, "ask_identification")
    assert ask["missing"] == ["account"] and "account_not_identified" in ask["because"]
    assert "δανειακού λογαριασμού" in ask["text"]


def test_account_mode_named_single_or_all_debts():
    named = {**NO_PORTAL_CUSTOMER, "named_accounts": ["4000000000009"]}
    assert [a["account"] for a in of(decide([COPIES], {}, named), "request")] == ["4000000000009"]
    single = {**NO_PORTAL_CUSTOMER, "accounts": ONE}
    assert "single_account" in only(decide([COPIES], {}, single))["because"]
    every = of(decide([COPIES], {"all_debts": True}, NO_PORTAL_CUSTOMER), "request")
    assert len(every) == 3 and reply(decide([COPIES], {"all_debts": True}, NO_PORTAL_CUSTOMER)) == "received"


def test_spv_mode_needs_the_portfolio():
    actions = decide([AUTH], {}, NO_PORTAL_CUSTOMER)
    assert only(actions, "ask_identification")["missing"] == ["spv"]
    one_spv = {**NO_PORTAL_CUSTOMER, "accounts": TWO_SPVS[:2]}
    assert "single_spv" in only(decide([AUTH], {}, one_spv))["because"]
    named = {**NO_PORTAL_CUSTOMER, "named_accounts": ["4000000000002", "4000000000001"]}
    assert [a["account"] for a in of(decide([AUTH], {}, named), "request")] == ["4000000000001"]  # one per SPV
    assert len(of(decide([AUTH], {"all_debts": True}, NO_PORTAL_CUSTOMER), "request")) == 2


# Identification: a tax ID or an account; otherwise "Need more Info".
def test_unidentified_request_asks_for_the_tax_id():
    actions = decide([COPIES], {}, {})
    assert [a["do"] for a in actions] == ["ask_identification"] and actions[0]["missing"] == ["afm"]


def test_not_in_registry_goes_to_staff():
    actions = decide([COPIES], {}, {"identified": True})
    assert (only(actions, "manual")["note"], reply(actions)) == ("not in registry", "received")


def test_best_guess_keeps_the_request_with_a_caveat_and_asks():
    guess = decide([COPIES], {}, {}, best_guess=True)
    assert (only(guess)["code"], only(guess)["caveat"]) == ("154", "not_identified")
    assert reply(guess) == "need_more_info"
    guess = decide([COPIES], {}, NO_PORTAL_CUSTOMER, best_guess=True)
    assert only(guess)["caveat"] == "account_not_identified" and "account" not in only(guess)
    ask = only(guess, "ask_identification")
    assert (ask["missing"], ask["because"]) == (["account"], ["account_not_identified"])
    assert only(decide([COPIES], {}, {"identified": True}, best_guess=True))["caveat"] == "not_in_registry"


# One reply per email, from the spreadsheet's Outgoing Emails column.
@pytest.mark.parametrize("category, expected", [
    ("Διοίκηση", "in_progress"), ("Τιμολόγια", "in_progress"), ("Εξώδικα", "received"),
    ("Αγωγές", None), ("Βιογραφικά με επισυναπτόμενα", None), ("Παράπονα", None), ("Marketing-SPAM", None),
])
def test_reply_template_per_category(category, expected):
    templates = [a["template"] for a in decide([category], {}, {}) if a.get("template")]
    assert templates == ([expected] if expected else [])


def test_erb_case_goes_to_the_branch():
    actions = decide(["Πόθεν έσχες"], {}, {**NO_PORTAL_CUSTOMER, "erb": True})
    assert [a["do"] for a in actions] == ["bank_referral"] and reply(actions) == "erb_branch"


def test_heir_documents_open_the_request_and_the_right_activity():
    actions = decide(["Νομιμοποίηση κληρονόμων με επισύναψη εγγράφων"], {"heir_certificates_attached": True},
                     {**NO_PORTAL_CUSTOMER, "accounts": ONE})
    assert only(actions)["code"] == "44" and only(actions, "activity")["codes"] == ["5005"]


def test_folders_forwards_and_activities_need_no_identification():
    assert only(decide(["Αγωγές"], {}, {}), "forward")["to"][0] == "spdallas@dovaluegreece.gr"
    authority = decide(["Φορείς"], {}, {})
    assert only(authority, "outlook_folder")["folder"] == "ΦΟΡΕΙΣ"
    assert only(authority, "activity")["codes"] == ["6691", "2090"]
    hearing = decide(["Αναβολές δικασίμων"], {}, {"is_3869": True})
    assert [a["to"][0] for a in of(hearing, "forward")] == ["Dikografa@dovaluegreece.gr",
                                                            "law3869_finalcourtdecisions@dovaluegreece.gr"]


def test_imminent_auction_request_and_forward_both_fire():
    actions = decide(["Πλειστηριασμοί"], {"asks_negotiation": True, "auction_imminent": True}, NO_PORTAL_CUSTOMER)
    assert {a["do"] for a in actions} == {"request", "forward", "reply"}


# Priority: the most important request first; a complaint only when nothing else is asked.
def test_complaint_is_not_first_when_something_else_is_asked():
    assert order_requests("Παράπονα", [COPIES, "GDPR"]) == (["GDPR", COPIES, "Παράπονα"], True)
    assert order_requests("Παράπονα", []) == (["Παράπονα"], False)
    assert order_requests(COPIES, ["Παράπονα", "GDPR"]) == ([COPIES, "GDPR", "Παράπονα"], False)


def test_no_wizard_anywhere_in_the_rules():
    assert "wizard" not in json.dumps(RULES).lower()
    assert "wizard" not in json.dumps(FLAGS).lower()


def test_every_category_gives_a_reason_for_every_customer():
    customers = ({}, {"identified": True}, NO_PORTAL_CUSTOMER, PORTAL_CUSTOMER, {**NO_PORTAL_CUSTOMER, "accounts": []})
    for category in RULES:
        for customer in customers:
            for best_guess in (False, True):
                for action in decide([category], {}, customer, best_guess=best_guess):
                    assert explain(action), category


def test_every_rule_condition_has_a_written_reason():
    for category in RULES.values():
        for rule in category["rules"]:
            for key, value in rule.get("when", {}).items():
                assert f"{key}={str(value).lower()}" in REASONS


def test_every_code_and_template_is_named():
    for spec in RULES.values():
        assert spec.get("reply") in (None, *REPLIES["templates"])
        assert spec.get("accounts") in (None, "per_spv", "account", "spv")
        for rule in spec["rules"]:
            for code in [rule.get("open"), rule.get("closed"), *(rule.get("codes") or [])]:
                if code:
                    assert code_name(code), code
            assert rule.get("template") in (None, *REPLIES["templates"])


def test_every_configured_category_has_a_rule():
    root = Path(__file__).resolve().parents[1]
    categories = json.loads((root / "inputs" / "categories.json").read_text("utf-8"))
    assert {c["Categories"].strip() for c in categories} <= set(RULES)


def test_rules_only_use_known_flags():
    known = set(FLAGS) | {"registry_3869", "erb"}
    used = {k for c in RULES.values() for r in c["rules"] for k in r.get("when", {})}
    assert used <= known, used - known


# Email chains
def test_outlook_greek_chain_splits_into_messages():
    text = (
        "Παρακαλώ δείτε κάτω.\n\n________________\n"
        "Από: Μαρία <m@example.com>\nΑπεστάλη: Τρίτη 3 Μαρτίου\nΠρος: Εξυπηρέτηση\nΘέμα: Βεβαίωση\n\n"
        "Ζητώ βεβαίωση.\n\n"
        "From: Team [mailto:t@example.com]\nSent: Monday\nTo: Μαρία\nSubject: RE: x\n\nΑπάντηση ομάδας."
    )
    parts = split_chain(text)
    assert [p["body"] for p in parts] == [
        "Παρακαλώ δείτε κάτω.",
        "Ζητώ βεβαίωση.",
        "Απάντηση ομάδας.",
    ]
    assert parts[1]["who"] == "Μαρία <m@example.com>"
    assert parts[1]["when"] == "Τρίτη 3 Μαρτίου"
    assert parts[1]["subject"] == "Βεβαίωση"
    assert parts[2]["who"] == "Team"


def test_quoted_reply_lines_lose_their_marks():
    parts = split_chain(
        "Ευχαριστώ.\n\nOn Mon, 2 Mar, Team wrote:\n> Γεια σας\n> > παλιό"
    )
    assert [p["body"] for p in parts] == ["Ευχαριστώ.", "Γεια σας\nπαλιό"]
    assert "wrote" in parts[1]["who"]


def test_original_message_rule_merges_with_its_header():
    text = "Νέο.\n-----Original Message-----\nFrom: A\nSent: B\nΠαλιό."
    parts = split_chain(text)
    assert [p["body"] for p in parts] == ["Νέο.", "Παλιό."]
    assert parts[1]["who"] == "A"


def test_empty_forward_wrapper_keeps_only_the_forwarded_message():
    parts = split_chain(
        "---------- Forwarded message ---------\nFrom: A\nDate: B\n\nΚείμενο."
    )
    assert [(p["who"], p["body"]) for p in parts] == [("A", "Κείμενο.")]


@pytest.mark.parametrize(
    "text",
    [
        "Από: τον κύριο Παπαδόπουλο έλαβα το έγγραφο.\nΕυχαριστώ.\n\n\n\n\n\n\nΑλλη γραμμή.",
        "Απλό κείμενο χωρίς αλυσίδα.",
    ],
)
def test_plain_text_is_not_split(text):
    assert [p["body"] for p in split_chain(text)] == [text]


def test_empty_body_still_gives_one_message():
    assert split_chain("") == [{"who": "", "when": "", "subject": "", "body": ""}]
    assert split_chain(None)[0]["body"] == ""


# Candidate finder
def hints(text):
    return {c["value"]: c["hint"] for c in find_candidates(text, "body")}


def test_afm_with_separators_is_one_value():
    afm = make_afm()
    assert hints(f"ΑΦΜ {afm[:3]} {afm[3:6]} {afm[6:]}") == {afm: "afm"}


def test_labelled_afm_with_dropped_leading_zero_is_restored():
    afm = make_afm("01234567")
    assert afm_checksum_valid(afm)
    assert hints(f"Α.Φ.Μ.: {afm[1:]}") == {afm: "afm_padded"}


def test_labelled_afm_with_bad_checksum_is_kept_and_flagged():
    afm = make_afm()
    wrong = afm[:-1] + str((int(afm[-1]) + 1) % 10)
    assert hints(f"ΑΦΜ: {wrong}") == {wrong: "afm_bad_checksum"}


def test_adjacent_numbers_stay_separate():
    assert hints("τηλ 2101234567 6912345678") == {
        "2101234567": "phone_like",
        "6912345678": "phone_like",
    }


@pytest.mark.parametrize(
    "text",
    ["στις 12.05.2026", "ποσό 1.234.567,89 ευρώ", "ποσό 1.234.567", "Ν.3869/2010"],
)
def test_dates_amounts_and_laws_are_not_candidates(text):
    assert hints(text) == {}


def test_valid_iban_found_and_invalid_ignored():
    # Published example IBAN for Greece.
    valid = "GR1601101250000000012300695"
    assert mod97_valid(valid)
    assert hints(f"IBAN {valid}") == {valid: "iban"}
    assert "iban" not in hints(f"IBAN {valid[:-1]}7").values()


@pytest.mark.parametrize(
    "text, value",
    [
        ("ΑΔΤ ΑΚ 123456", "ΑΚ123456"),
        ("ΑΡΙΘΜΟΣ ΔΕΛΤΙΟΥ ΤΑΥΤΟΤΗΤΑΣ: ΑΚ123456", "ΑΚ123456"),
        ("στέλνω την ταυτότητα ΑΚ 123 456.", "ΑΚ123456"),
        ("το ΑΚ 123456 είναι το δελτίο μου", "ΑΚ123456"),  # its own format, no label
        ("Α.Δ.Τ.: Χ 123456", "Χ123456"),  # older one-letter card
        ("ΑΔΤ 123456", "123456"),
    ],
)
def test_id_card_forms(text, value):
    assert hints(text) == {value: "adt_like"}


@pytest.mark.parametrize("text", ["κωδικός Χ 123456", "ποσό 123456 ευρώ"])
def test_short_prefix_or_bare_six_digits_need_a_label(text):
    assert hints(text) == {}


def test_id_card_pass_does_not_eat_a_spaced_afm():
    afm = make_afm()
    assert hints(f"ΑΚ {afm[:3]} {afm[3:6]} {afm[6:]}") == {afm: "afm"}


@pytest.mark.parametrize(
    "text",
    ["Κωδικός πληρωμής 0412345678901", "ΚΩΔΙΚΟΣ ΠΛΗΡΩΜΗΣ: 0412345678901"],
)
def test_payment_code_is_told_apart_from_an_account_by_its_label(text):
    assert hints(text) == {"0412345678901": "payment_code_like"}


@pytest.mark.parametrize(
    "text",
    [
        "Αριθμός δανειακών λογαριασμών: 0212345678901",
        "ΑΡΙΘΜΟΣ ΛΟΓΑΡΙΑΣΜΟΥ 0212345678901",
    ],
)
def test_loan_account_keeps_its_own_hint(text):
    found = find_candidates(text, "body")
    assert [(c["value"], c["hint"], c["label"]) for c in found] == [
        ("0212345678901", "account_like", "account")
    ]


def make_rf(reference: str = "1234567890123456789") -> str:
    """A checksum-valid RF code. Synthetic, so no real payment code lives in this test."""
    digits = "".join(str(int(ch, 36)) for ch in reference + "RF00")
    return f"RF{98 - int(digits) % 97:02d}{reference}"


def test_rf_code_with_and_without_a_valid_checksum():
    rf = make_rf()
    assert mod97_valid(rf)
    assert hints(f"κωδικός πληρωμής {rf}") == {rf: "rf"}
    broken = rf[:-1] + str((int(rf[-1]) + 1) % 10)
    assert hints(f"{broken}") == {broken: "rf_bad_checksum"}


# HTML bodies
def test_html_becomes_readable_text():
    html = """<html><head><title>t</title><style>p {color:red}</style></head>
    <body><!-- note --><p>Καλημέρα <b>σας</b>,</p><div>ΑΦΜ&nbsp;123</div>
    <table><tr><td>Όνομα</td><td></td><td>Τιμή</td></tr><tr><td>Α</td><td>Β</td></tr></table>
    γραμμή<br>επόμενη<script>x()</script></body></html>"""
    text = html_to_text(html)
    assert (
        "<" not in text
        and "color" not in text
        and "note" not in text
        and "x()" not in text
    )
    lines = [line for line in text.split("\n") if line]
    assert lines == [
        "Καλημέρα σας,",
        "ΑΦΜ 123",
        "Όνομα | Τιμή",
        "Α | Β",
        "γραμμή",
        "επόμενη",
    ]


@pytest.mark.parametrize("html", ["", None, "<div></div>", "<img src='x'>"])
def test_html_without_text_is_empty(html):
    assert html_to_text(html) == ""


def test_escaped_tag_is_dropped_but_ordinary_angle_brackets_stay():
    assert html_to_text("<div>α &lt;p&gt; β</div>") == "α β"
    assert (
        html_to_text("<div>ποσό &lt; 100 και x &gt; 2</div>") == "ποσό < 100 και x > 2"
    )


def test_broken_html_keeps_its_text():
    assert html_to_text("<div>κείμενο <b>χωρίς κλείσιμο") == "κείμενο χωρίς κλείσιμο"


def test_merge_keeps_one_entry_per_value_and_drops_lowest_rank():
    afm = make_afm()
    found = find_candidates(f"ΑΦΜ {afm}", "body") + find_candidates(
        f"ΑΦΜ {afm} τηλ 2101234567", "attachment:1"
    )
    merged, dropped = merge_candidates(found, limit=1)
    assert [c["value"] for c in merged] == [afm]
    assert merged[0]["id"] == "c1"
    assert len(merged[0]["sightings"]) == 2
    assert dropped == 1
