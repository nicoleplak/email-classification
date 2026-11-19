import json
import math
from types import SimpleNamespace

from llm.classifier import EmailClassifier


def _choice(category, logprob):
    """A fake completion choice whose Category value is one token with logprob."""
    head = '{"Reasoning":"r","Category":"'
    tail = '","Thread_Relation":"standalone","Matched_Rules":[]}'
    tokens = [
        SimpleNamespace(token=head, bytes=list(head.encode()), logprob=0.0),
        SimpleNamespace(token=category, bytes=list(category.encode()), logprob=logprob),
        SimpleNamespace(token=tail, bytes=list(tail.encode()), logprob=0.0),
    ]
    return SimpleNamespace(
        message=SimpleNamespace(content=head + category + tail),
        logprobs=SimpleNamespace(content=tokens),
    )


def _classifier(choices):
    classifier = EmailClassifier.__new__(EmailClassifier)
    classifier.samples = len(choices)
    classifier.model_name = "test"
    classifier.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: SimpleNamespace(choices=choices)
            )
        )
    )
    return classifier


def test_majority_category_wins_and_confidence_is_agreeing_probability_mass():
    choices = [
        _choice("Ρύθμιση", math.log(0.9)),
        _choice("Ρύθμιση", math.log(0.8)),
        _choice("GDPR", math.log(0.99)),
    ]
    result = json.loads(
        _classifier(choices)._call_llm([], ["Ρύθμιση", "GDPR", "No Match Found"])
    )
    assert result["Category"] == "Ρύθμιση"
    assert math.isclose(result["Confidence"], (0.9 + 0.8) / 3, abs_tol=1e-4)
    assert list(result["Category_Votes"]) == ["Ρύθμιση", "GDPR"]
    assert math.isclose(result["Category_Votes"]["GDPR"], 0.99 / 3, abs_tol=1e-4)


def test_low_confidence_flags_review_instead_of_failing_validation():
    classifier = _classifier([])
    classifier.confidence_threshold = 0.8
    parsed = {
        "Category": "GDPR",
        "Confidence": 0.4,
        "Matched_Rules": ["not in the email"],
        "Reasoning": "r",
        "Thread_Relation": "standalone",
    }
    normalized = classifier._normalize_result(parsed, context_used=False)
    valid, errors = classifier._validate_result(
        normalized,
        allowed_categories=["GDPR", "No Match Found"],
        context_used=False,
        thread_context={"Current_Message": {"Body": "body text"}},
    )
    assert valid, errors
    assert normalized["Needs_Review"] is True
    assert normalized["Matched_Rules"] == []
