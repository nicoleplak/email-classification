import pandas as pd
from core.processor import EmailProcessor


class MockClassifier:
    """Mock LLM classifier returning a fixed category."""

    def classify(
        self,
        subject,
        body,
        categories_json,
        *,
        attachment_context=None,
    ):
        return {
            "Category": "Εξουσιοδοτήσεις",
            "Confidence": 0.95,
            "Matched_Rules": ["RULE_1"],
            "Reasoning": "Mocked reasoning",
        }


def build_mock_email(afm="090000045"):
    """Helper to build a fake email dict with AFM embedded in subject."""
    return {
        "id": "001",
        "conversationId": "conv-1",
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "subject": f"Mock subject with AFM {afm}",
        "body": {"content": "Mock content"},
        "receivedDateTime": "2024-05-10T10:00:00Z",
    }


def test_process_email_basic():
    """Processor should classify and return one record for valid AFM."""
    registry_df = pd.DataFrame(
        [
            {
                "TAX_ID_NO": "090000045",
                "SOURCE": "Registry",
                "CST_UNQ_CD": "C1",
                "PRTFL_CD": "SPV1",
                "CST_STS_NM": "Active",
            }
        ]
    )

    classifier = MockClassifier()
    categories_data = [{"Categories": "Εξουσιοδοτήσεις", "Παραπομπές wizar/portal": ""}]
    reply_templates = {
        "Εξουσιοδοτήσεις": "Mock reply",
        "NEEDS_IDENTIFICATION": "Need AFM",
    }
    forward_rules = {}
    default_reply = "Default reply"

    processor = EmailProcessor(
        registry_df,
        classifier,
        categories_data,
        reply_templates,
        forward_rules,
        default_reply,
    )

    email = build_mock_email()
    results = processor.process_email(email)

    assert isinstance(results, list)
    assert len(results) == 1
    result = results[0]

    assert result["afm"] == "090000045"
    assert result["category"] == "Εξουσιοδοτήσεις"
    assert result["reply_text"] == "Mock reply"
    assert result["status"] in ("verified", "needs_review")
    assert result["routing_mode"] in ("INTERNAL", "PORTAL", "WIZARD")


def test_process_email_no_afm():
    """Processor should return NEEDS_IDENTIFICATION when AFM missing."""
    registry_df = pd.DataFrame([{"TAX_ID_NO": "090000045", "SOURCE": "Registry"}])

    processor = EmailProcessor(
        registry_df,
        MockClassifier(),
        [{"Categories": "Εξουσιοδοτήσεις"}],
        {"NEEDS_IDENTIFICATION": "Need AFM"},
        {},
        "Default reply",
    )

    email = build_mock_email(afm="")  # no AFM in subject
    results = processor.process_email(email)
    assert len(results) == 1
    result = results[0]
    assert result["afm"] is None
    assert result["category"] == "Εξουσιοδοτήσεις"
    assert result["status"] == "needs_identification"
    assert result["identification_verified"] is False
    assert result["routing_mode"] == "NONE"
    assert result["routing_ready"] is False
    assert result["reply_text"] == "Need AFM"
