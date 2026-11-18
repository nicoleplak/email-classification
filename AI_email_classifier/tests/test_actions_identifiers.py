"""Rule table against the spec's own worked examples, and the candidate finder on tricky text."""

import json
from pathlib import Path

import pytest

from evaluation.action_rules import FLAGS, REASONS, RULES, decide, explain
from evaluation.email_chain import split_chain
from evaluation.identifiers import find_candidates, merge_candidates, mod97_valid
from utils.afm_utils import afm_checksum_valid
from utils.html_text import html_to_text

PORTAL_CUSTOMER = {"identified": True, "known": True, "portal": True}
NO_PORTAL_CUSTOMER = {"identified": True, "known": True, "portal": False}
DEBT = "Βεβαιώσεις οφειλής"
AUTH = "Εξουσιοδοτήσεις"
SCHEDULE = "Δοσολόγιο"


def make_afm(prefix: str = "12345678") -> str:
    """A checksum-valid AFM. Synthetic, so no real tax ID lives in this test."""
    total = sum(int(d) * 2 ** (8 - i) for i, d in enumerate(prefix))
    return prefix + str((total % 11) % 10)


def only(actions):
    assert len(actions) == 1, actions
    return actions[0]


# The six outcomes the spec lists for one category (Notes.md, step 2).
def test_debt_certificate_portal_customer_is_referred():
    assert only(decide([DEBT], {}, PORTAL_CUSTOMER))["do"] == "portal_referral"


def test_debt_certificate_cannot_login_opens_a_request():
    action = only(decide([DEBT], {"cannot_use_online": True}, PORTAL_CUSTOMER))
    assert (action["do"], action["open"], action["closed"]) == ("request", "89", "117")


def test_debt_certificate_heir_opens_111_even_with_portal():
    action = only(decide([DEBT], {"is_heir": True}, PORTAL_CUSTOMER))
    assert (action["do"], action["codes"]) == ("request", ["111"])


def test_debt_certificate_breakdown_without_portal():
    action = only(decide([DEBT], {"wants_breakdown": True}, NO_PORTAL_CUSTOMER))
    assert (action["open"], action["closed"]) == ("91", "118")


def test_debt_certificate_ordinary_without_portal():
    action = only(decide([DEBT], {}, NO_PORTAL_CUSTOMER))
    assert (action["open"], action["closed"]) == ("89", "117")


def test_debt_certificate_3869_customer_gets_105():
    customer = {**NO_PORTAL_CUSTOMER, "is_3869": True}
    assert only(decide([DEBT], {}, customer))["codes"] == ["105"]


def test_one_non_online_request_cancels_every_referral():
    actions = decide([DEBT, "Αντίγραφα συμβάσεων"], {}, PORTAL_CUSTOMER)
    assert [a["do"] for a in actions] == ["request", "request"]
    assert "other_request_offline" in actions[0]["because"]


def test_all_online_requests_are_referred():
    actions = decide([DEBT, SCHEDULE], {}, PORTAL_CUSTOMER)
    assert {a["do"] for a in actions} == {"portal_referral"}


def test_unidentified_online_request_goes_to_the_website():
    assert only(decide([DEBT], {}, {}))["do"] == "portal_referral"


def test_unidentified_offline_request_asks_for_identification():
    assert only(decide(["Αντίγραφα συμβάσεων"], {}, {}))["do"] == "ask_identification"


def test_former_wizard_requests_are_registered_or_need_identification():
    assert only(decide([AUTH], {}, NO_PORTAL_CUSTOMER))["do"] == "request"
    assert only(decide([AUTH], {}, {}))["do"] == "ask_identification"


def test_no_wizard_anywhere_in_the_rules():
    assert "wizard" not in json.dumps(RULES).lower()
    assert "wizard" not in json.dumps(FLAGS).lower()


@pytest.mark.parametrize(
    "category, flags, customer, expected",
    [
        (DEBT, {"cannot_use_online": True}, PORTAL_CUSTOMER, "cannot_use_online"),
        (DEBT, {"is_heir": True}, PORTAL_CUSTOMER, "is_heir=true"),
        (DEBT, {}, NO_PORTAL_CUSTOMER, "no_portal"),
        (DEBT, {}, PORTAL_CUSTOMER, "has_portal"),
        (DEBT, {}, NO_PORTAL_CUSTOMER, "open_or_closed"),
        ("Αντίγραφα συμβάσεων", {}, {}, "not_identified"),
        ("Αντίγραφα συμβάσεων", {}, {"identified": True}, "not_in_registry"),
        ("Βεβαιώσεις εξόφλησης", {}, NO_PORTAL_CUSTOMER, "missing_contract"),
        ("Εξουσιοδοτήσεις", {}, NO_PORTAL_CUSTOMER, "open_or_closed"),
        ("Βεβαίωση άρσης προσημείωσης", {}, NO_PORTAL_CUSTOMER, "else"),
    ],
)
def test_every_action_says_why(category, flags, customer, expected):
    action = only(decide([category], flags, customer))
    assert expected in action["because"]
    assert all(explain(action))


def test_every_category_gives_a_reason_for_every_customer():
    customers = ({}, {"identified": True}, NO_PORTAL_CUSTOMER, PORTAL_CUSTOMER)
    for category in RULES:
        for customer in customers:
            for action in decide([category], {}, customer):
                assert explain(action), category


def test_every_rule_condition_has_a_written_reason():
    for category in RULES.values():
        for rule in category["rules"]:
            for key, value in rule.get("when", {}).items():
                assert f"{key}={str(value).lower()}" in REASONS


def test_identified_but_not_in_registry_is_an_exception():
    action = only(decide(["Αντίγραφα συμβάσεων"], {}, {"identified": True}))
    assert (action["do"], action["note"]) == ("manual", "not in registry")


def test_3869_decision_is_registered_despite_the_portal_flag():
    action = only(
        decide(["Αιτήματα Ν.3869"], {"decision_3869_attached": True}, PORTAL_CUSTOMER)
    )
    assert (action["do"], action["codes"]) == ("request", ["161"])


def test_imminent_auction_request_and_forward_both_fire():
    actions = decide(
        ["Πλειστηριασμοί"],
        {"asks_negotiation": True, "auction_imminent": True},
        NO_PORTAL_CUSTOMER,
    )
    assert {a["do"] for a in actions} == {"request", "forward"}


def test_forward_and_manual_need_no_identification():
    assert only(decide(["Αγωγές"], {}, {}))["do"] == "forward"
    assert only(decide(["Φορείς"], {}, {}))["do"] == "manual"


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


def test_best_guess_keeps_the_request_codes_with_a_caveat():
    unknown = {"identified": True, "known": False}
    guess = only(decide(["Αντίγραφα συμβάσεων"], {}, {}, best_guess=True))
    assert (guess["do"], guess["open"], guess["caveat"]) == (
        "request",
        "154",
        "not_identified",
    )
    guess = only(decide(["Αντίγραφα συμβάσεων"], {}, unknown, best_guess=True))
    assert (guess["do"], guess["caveat"]) == ("request", "not_in_registry")
    assert (
        only(decide(["Αντίγραφα συμβάσεων"], {}, unknown))["do"] == "manual"
    )  # production unchanged
