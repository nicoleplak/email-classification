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
            "categories": [{"category": c, "applies": True, "reason": "Ζητά βεβαίωση οφειλής.",
                            "quote": "Παρακαλώ βεβαίωση οφειλής" if i == 0 else "δεν υπάρχει στο κείμενο", "source": "body"}
                           for i, c in enumerate(kwargs["response_format"]["json_schema"]["schema"]["properties"]
                                                  ["other_requests"]["items"].get("enum", [])[:2])],
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


def test_category_reasons_banks_and_the_erb_marker(registry):
    message = {
        "id": "m1", "subject": "Βεβαίωση οφειλής",
        "from": {"emailAddress": {"address": "lawyer@example.test", "name": "Δικηγόρος"}},
        "body": {"body_clean": "Παρακαλώ βεβαίωση οφειλής για δάνειο της Eurobank, ΑΦΜ 094014298."},
        "conversation_thread": [{"id": "m0", "subject": "Re", "body": {"body_clean": "Τράπεζα Πειραιώς"}}],
    }
    out = understand(client=FakeClient(), model="m", message=message, records=[{"category": "Βεβαιώσεις οφειλής"}],
                     text_dir=None, categories=["Βεβαιώσεις οφειλής", "GDPR"], registry=registry,
                     history=RequestHistory.empty())
    assert out["markers"] == ["ERB"]
    assert [b["bank"] for b in out["banks"]] == ["Eurobank"]  # earlier messages are not the sender's own text
    reasons = out["categoryReasons"]
    assert reasons[0]["reason"] == "Ζητά βεβαίωση οφειλής." and reasons[0]["quote"] == "Παρακαλώ βεβαίωση οφειλής"
    assert reasons[1]["quote"] == ""  # a quote not found in the text is dropped


# Inheritance: the deceased debtor is searched first; an heir's identifiers only when the deceased is not found.
def test_the_deceased_debtor_comes_before_the_heir(registry):
    heir = {"value": "094014298", "where": {"kind": "body"}, "rank": 3, "role": "heir"}
    deceased = {"value": "090000045", "where": {"kind": "attachment"}, "rank": 1, "role": "deceased_debtor"}
    found = find_customers(registry, RequestHistory.empty(), tax_ids=[heir, deceased], accounts=[], emails=[], names=[])
    assert [c["taxId"] for c in found["customers"]] == ["090000045", "094014298"]
    assert found["facts"]["identified_via"] == "deceased_debtor"
    assert [a["account"] for a in found["facts"]["accounts"]] == ["1000000000002"]  # the deceased's, not the heir's
    missing = {**deceased, "value": "123456783"}  # the deceased is not in the registry: the heir is the fallback
    found = find_customers(registry, RequestHistory.empty(), tax_ids=[heir, missing], accounts=[], emails=[], names=[])
    assert found["facts"]["identified_via"] == "heir" and found["facts"]["accounts"][0]["account"] == "1000000000001"
    understanding = {"customers": found["customers"], "customerFacts": found["facts"], "actions": [{"do": "request"}]}
    assert any("only by an heir" in r for r in rc.understanding_reasons(understanding))


class HeirClient(FakeClient):
    """The model calls the sender (an heir) principal and does not mark the heir's tax ID as identifying."""

    def create(self, **kwargs):
        from core.action_rules import FLAGS

        user = json.loads(kwargs["messages"][1]["content"])
        roles = {"094014298": "heir", "090000045": "deceased_debtor"}
        answer = {
            "analysis": "heirs", "other_requests": [], "categories": [], "evidence": [],
            "candidates": [{"id": c["id"], "field": "afm", "role": roles.get(c["value"], "none"),
                            "identifies_case": False, "certainty": "high"} for c in user["candidates"]],
            "people": [
                {"name": "Γιάννης Παπαδόπουλος", "registry_form": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΙΩΑΝΝΗΣ", "role": "heir",
                 "is_principal": True, "evidence": "ως κληρονόμος", "source": "body"},
                {"name": "Νικόλαος Παπαδόπουλος", "registry_form": "ΠΑΠΑΔΟΠΟΥΛΟΣ ΝΙΚΟΛΑΟΣ", "role": "deceased_debtor",
                 "is_principal": False, "evidence": "του αποβιώσαντος", "source": "body"},
            ],
            "flags": {k: k == "is_heir" for k in FLAGS},
        }
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))])


def test_understand_searches_the_deceased_and_makes_them_principal(registry):
    message = {
        "id": "m1", "subject": "Κληρονομιά",
        "from": {"emailAddress": {"address": "heir@example.test", "name": "Γιάννης Παπαδόπουλος"}},
        "body": {"body_clean": "Ως κληρονόμος (ΑΦΜ 094014298) του αποβιώσαντος πατέρα μου, ΑΦΜ 090000045, ζητώ βεβαίωση."},
    }
    out = understand(client=HeirClient(), model="m", message=message, records=[{"category": "Βεβαιώσεις οφειλής"}],
                     text_dir=None, categories=["Βεβαιώσεις οφειλής"], registry=registry, history=RequestHistory.empty())
    assert [p["role"] for p in out["people"] if p["principal"]] == ["deceased_debtor"]
    assert out["customerFacts"]["identified_via"] == "deceased_debtor"
    assert out["customers"][0]["taxId"] == "090000045" and out["customers"][0]["rank"] == 1


# Categories by rule: a board member named → Διοίκηση (main); an authorization attached → Εξουσιοδοτήσεις.
CATS = ["Βεβαιώσεις οφειλής", "Διοίκηση", "Εξουσιοδοτήσεις"]


def read(registry, body, records, to=()):
    message = {"id": "m1", "subject": "Αίτημα", "from": {"emailAddress": {"address": "c@example.test", "name": "Πελάτης"}},
               "body": {"body_clean": body}, "toRecipients": list(to)}
    return understand(client=FakeClient(), model="m", message=message, records=records, text_dir=None,
                      categories=CATS, registry=registry, history=RequestHistory.empty())


def test_a_board_member_makes_the_email_a_management_one(registry):
    out = read(registry, "Υπόψιν κ. Πανούση: παρακαλώ βεβαίωση οφειλής, ΑΦΜ 094014298.", [{"category": "Βεβαιώσεις οφειλής"}])
    assert out["principalCategory"] == "Διοίκηση" and out["principalByRule"]
    assert "Βεβαιώσεις οφειλής" in out["otherRequests"]  # what the email asks is still done
    assert any(a.get("folder") == "ΦΟΡΕΙΣ" for a in out["actions"])
    assert any(a["category"] == "Βεβαιώσεις οφειλής" for a in out["actions"])  # its Portal reply here
    assert out["categoryReasons"][0]["byRule"] and "Πανούση" in out["categoryReasons"][0]["reason"]
    to = [{"emailAddress": {"name": "Kalantonis Ioannis", "address": "i.kalantonis@example.test"}}]
    assert read(registry, "Παρακαλώ βεβαίωση οφειλής.", [{"category": "Βεβαιώσεις οφειλής"}], to)["principalCategory"] == "Διοίκηση"
    assert not read(registry, "Ο πρόεδρος του δικαστηρίου αποφάσισε.", [{"category": "Βεβαιώσεις οφειλής"}])["principalByRule"]


def test_an_authorization_attached_brings_the_authorization_request(registry):
    records = [{"category": "Βεβαιώσεις οφειλής", "attachment_summaries": [
        {"filename": "exousiodotisi.pdf", "document_type": "Εξουσιοδότηση / πληρεξούσιο", "relevance": "relevant"}]}]
    out = read(registry, "Παρακαλώ βεβαίωση οφειλής, ΑΦΜ 094014298.", records)
    assert out["principalCategory"] == "Βεβαιώσεις οφειλής" and "Εξουσιοδοτήσεις" in out["otherRequests"]
    assert any(a["category"] == "Εξουσιοδοτήσεις" and a["do"] == "request" and a["code"] == "45" for a in out["actions"])
    nothing = [{"category": "No Match Found", "attachment_summaries": records[0]["attachment_summaries"]}]
    assert read(registry, "Σας στέλνω το έγγραφο, ΑΦΜ 094014298.", nothing)["principalCategory"] == "Εξουσιοδοτήσεις"
    irrelevant = [{**records[0], "attachment_summaries": [{**records[0]["attachment_summaries"][0], "relevance": "irrelevant"}]}]
    assert "Εξουσιοδοτήσεις" not in read(registry, "Παρακαλώ βεβαίωση οφειλής.", irrelevant)["otherRequests"]


def test_the_reader_sees_whole_pages_and_the_people_further_down_long_ones():
    from core.understand import PAGE_MIN, readable

    short = {"text": "Πιστοποιητικό εγγυτέρων συγγενών " * 20, "where": {"kind": "attachment"}}
    assert readable(short, 3) == {"text": short["text"]}  # a normal page is read whole, not its first 600 characters
    filler = "Λοιπά στοιχεία της πράξης. " * 400
    long = {"text": filler + "Ο ΑΠΟΒΙΩΣΑΣ ΠΑΠΑΔΟΠΟΥΛΟΣ ΝΙΚΟΛΑΟΣ, κληρονόμοι: η σύζυγος ΜΑΡΙΑ. " + filler,
            "where": {"kind": "attachment"}}
    seen = readable(long, 60)  # many pages: each gets its share, plus the passages about people
    assert len(seen["text"]) == PAGE_MIN and any("ΑΠΟΒΙΩΣΑΣ ΠΑΠΑΔΟΠΟΥΛΟΣ" in m for m in seen["more"])
    assert len(readable({"text": "x" * 9000, "where": {"kind": "thread", "date": None}}, 1)["text"]) == 1500


def test_an_account_without_the_qualco_number_still_counts_by_its_other_numbers():
    rows = pd.DataFrame([{"TAX_ID_NO": "094014298", "NAME": "Χ", "ACC_UNQ_CD": "", "SRV_ACC_UNQ_CD": "5000000000001",
                          "ACC_ID": "", "PRTFL_NM": "P", "PRTFL_CD": "PC", "CST_STS_NM": "Active", "SOURCE": "Qualco"}])
    accounts = Registry(rows).accounts("094014298")
    assert [(a["account"], a["spv"], a["spvCode"]) for a in accounts] == [("5000000000001", "P", "PC")]


def test_values_the_model_does_not_label_are_kept_from_their_pattern(registry):
    class Silent(FakeClient):
        def create(self, **kwargs):
            answer = json.loads(super().create(**kwargs).choices[0].message.content)
            answer["candidates"] = []  # the model labelled nothing
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))])

    message = {"id": "m1", "subject": "Σύμβαση", "from": {"emailAddress": {"address": "c@example.test", "name": "Π"}},
               "body": {"body_clean": "ΑΦΜ 094014298, αριθμός σύμβασης 1234/2008, λογαριασμός 1000000000001."}}
    out = understand(client=Silent(), model="m", message=message, records=[{"category": "Βεβαιώσεις οφειλής"}],
                     text_dir=None, categories=["Βεβαιώσεις οφειλής"], registry=registry, history=RequestHistory.empty())
    got = {(e["type"], e["value"]) for e in out["extracted"] if e["type"] != "email"}
    assert got == {("afm", "094014298"), ("contract", "1234/2008"), ("account", "1000000000001")}
    assert all(not e["identifiesCase"] for e in out["extracted"] if e["type"] != "email")
    # The account number is in the registry, so it still finds the customer; the unlabelled tax ID alone would not.
    assert [c["taxId"] for c in out["customers"] if c["status"] == "confirmed"] == ["094014298"]
    assert "afm" not in [m["kind"] for m in out["customers"][0]["matchedOn"]]
