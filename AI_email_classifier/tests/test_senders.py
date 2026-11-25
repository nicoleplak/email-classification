"""Sender flags (inputs/sender_flags.json) and the mailbox ingest keeping doValue's own senders."""

import importlib.util
import json
import sys
from pathlib import Path

from core import senders

ROOT = Path(__file__).resolve().parents[2]


def _rules(tmp_path, monkeypatch, retail_lines):
    rules = tmp_path / "sender_flags.json"
    rules.write_text(json.dumps({"internal_domains": ["dovaluegreece.gr"], "internal_category": "Cat 38",
                                 "retail_support_file": "retail.txt"}))
    (tmp_path / "retail.txt").write_text(retail_lines, encoding="utf-8")
    monkeypatch.setattr(senders, "RULES_FILE", rules)
    return tmp_path / "retail.txt"


def test_internal_retail_and_external(tmp_path, monkeypatch):
    _rules(tmp_path, monkeypatch, "# Retail Support\n  Retail.Fwd@doValueGreece.gr  # the shared box\n\n")
    assert senders.sender_type("maria@dovaluegreece.gr") == "internal"
    assert senders.sender_type("Someone@DOVALUEGREECE.GR") == "internal"
    assert senders.sender_type("ops@mail.dovaluegreece.gr") == "internal"  # a subdomain
    assert senders.sender_type("retail.fwd@dovaluegreece.gr") == "retail_support"  # listed: retail, not internal
    assert senders.sender_type("client@gmail.com") == "external"
    assert senders.sender_type("x@notdovaluegreece.gr") == "external"  # a look-alike domain is not ours
    assert senders.sender_type("") == senders.sender_type(None) == "external"
    assert senders.internal_category() == "Cat 38"


def test_a_changed_list_applies_without_a_restart(tmp_path, monkeypatch):
    import os
    import time

    retail = _rules(tmp_path, monkeypatch, "")
    assert senders.sender_type("rs@dovaluegreece.gr") == "internal"
    retail.write_text("rs@dovaluegreece.gr\n", encoding="utf-8")
    later = time.time() + 5
    os.utime(retail, (later, later))
    assert senders.sender_type("rs@dovaluegreece.gr") == "retail_support"


def test_the_shipped_rules_file_reads():
    import json as j

    domains, retail = senders.rules()
    assert "dovaluegreece.gr" in domains and isinstance(retail, frozenset)
    categories = {c["Categories"].strip() for c in j.loads((ROOT / "AI_email_classifier" / "inputs" / "categories.json").read_text("utf-8"))}
    assert senders.internal_category() in categories  # category 38 by name


def _ingest(monkeypatch):
    monkeypatch.delenv("EXCLUDE_DOMAINS", raising=False)
    monkeypatch.delenv("INTERNAL_DOMAINS", raising=False)
    monkeypatch.syspath_prepend(str(ROOT / "graphapi" / "src"))
    spec = importlib.util.spec_from_file_location("ingest_main_under_test", ROOT / "graphapi" / "src" / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mail(conv, sender, received):
    return {"id": f"{conv}-{received}", "conversationId": conv, "receivedDateTime": received,
            "from": {"emailAddress": {"address": sender}}}


def test_ingest_keeps_doValue_senders_but_the_customer_leads_a_conversation(monkeypatch):
    ingest = _ingest(monkeypatch)
    assert not ingest.is_excluded_sender(_mail("c", "staff@dovaluegreece.gr", "1"))  # kept now
    assert ingest.is_excluded_sender(_mail("c", "x@eurobank.gr", "1"))                # still dropped
    kept = ingest.deduplicate_by_conversation([
        _mail("c1", "client@example.com", "2026-11-20T08:00:00Z"),
        _mail("c1", "staff@dovaluegreece.gr", "2026-11-20T09:00:00Z"),  # newer staff reply in the same thread
        _mail("c2", "retail@dovaluegreece.gr", "2026-11-20T10:00:00Z"),  # a forward on its own
    ])
    assert [m["from"]["emailAddress"]["address"] for m in kept] == ["client@example.com", "retail@dovaluegreece.gr"]
    sys.modules.pop("ingest_main_under_test", None)


def test_ingest_asks_outlook_for_cc():
    text = (ROOT / "graphapi" / "src" / "helpers" / "graph_api.py").read_text(encoding="utf-8")
    assert text.count("toRecipients,ccRecipients") == 2
