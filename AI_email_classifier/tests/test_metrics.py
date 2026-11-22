"""Metrics view numbers (review_app/metrics.py), on invented cases."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "review_app"))
import metrics  # noqa: E402

TODAY = "2026-11-22"


def case(n, received, route=None, status="CLASSIFIED", model="Βεβαίωση οφειλής", final=None, reasons=(),
         confidence=0.95, proposed=(), chosen=(), reviewed_at=None, no_match=False):
    return {
        "id": f"c{n}", "receivedAt": received, "route": route, "status": "RECEIVED" if route is None else status,
        "routeReasons": list(reasons), "modelCategory": model if route else None, "finalCategory": final,
        "noMatch": no_match, "confidence": confidence if route not in (None, "EXCEPTION") else None,
        "reviewedAt": reviewed_at, "finalActions": list(chosen),
        "understanding": {"actions": [{"do": d} for d in proposed]},
    }


@pytest.mark.parametrize("iso, day", [
    ("2026-11-21T22:30:00Z", "2026-11-22"),   # winter: UTC+2, so after 22:00 UTC is the next Athens day
    ("2026-11-21T21:59:00Z", "2026-11-21"),
    ("2026-07-10T21:30:00Z", "2026-07-11"),   # summer: UTC+3
    ("2026-07-10T20:59:00Z", "2026-07-10"),
    ("2026-03-29T00:59:00Z", "2026-03-29"),   # DST starts 01:00 UTC on the last Sunday of March
    ("2026-10-24T21:30:00Z", "2026-10-25"),   # still summer until 01:00 UTC on 25 Oct
    ("not a date", None),
    (None, None),
])
def test_athens_day(iso, day):
    assert metrics.athens_day(iso) == day


def test_daily_counts_split_by_route_and_fill_empty_days():
    cases = [
        case(1, "2026-11-20T08:00:00Z", "AUTO"),
        case(2, "2026-11-20T09:00:00Z", "REVIEW", reasons=["confidence 74% is below 90%"]),
        case(3, "2026-11-20T10:00:00Z", "REVIEW", status="REVIEWED", final="Βεβαίωση οφειλής",
             reviewed_at="2026-11-20T14:00:00Z"),
        case(4, "2026-11-22T08:00:00Z", "EXCEPTION", reasons=["classification failed: boom"]),
        case(5, "2026-11-22T09:00:00Z"),  # not classified yet
        case(6, "2026-10-01T09:00:00Z", "AUTO"),  # outside the 7-day window
    ]
    out = metrics.compute(cases, 7, TODAY)
    assert out["from"] == "2026-11-16" and len(out["daily"]) == 7
    by_day = {d["day"]: d for d in out["daily"]}
    assert by_day["2026-11-20"] == {"day": "2026-11-20", "received": 3, "AUTO": 1, "REVIEW": 2, "EXCEPTION": 0,
                                    "WAITING": 0, "reviewed": 1, "open": 1}
    assert by_day["2026-11-21"]["received"] == 0
    assert by_day["2026-11-22"]["EXCEPTION"] == 1 and by_day["2026-11-22"]["WAITING"] == 1
    tot = out["totals"]
    assert (tot["received"], tot["classified"], tot["auto"], tot["review"], tot["exception"], tot["waiting"]) == (5, 4, 1, 2, 1, 1)
    assert tot["autoPct"] == 25.0 and tot["reviewPct"] == 75.0 and tot["open"] == 2
    assert tot["medianHoursToReview"] == 4.0
    assert metrics.compute(cases, 0, TODAY)["totals"]["received"] == 6  # "all" reaches back to the first email


def test_reasons_outcomes_and_bands():
    cases = [
        case(1, "2026-11-20T08:00:00Z", "AUTO", status="REVIEWED", final="Βεβαίωση οφειλής", confidence=0.97),
        case(2, "2026-11-20T08:00:00Z", "AUTO", status="REVIEWED", final="Άλλη", confidence=0.92),
        case(3, "2026-11-20T08:00:00Z", "REVIEW", status="REVIEWED", no_match=True, confidence=0.61,
             reasons=["confidence 61% is below 90%", "no customer found in the registry"]),
        case(4, "2026-11-20T08:00:00Z", "REVIEW", confidence=0.65,
             reasons=["confidence 65% is below 90%", "something new"]),
    ]
    out = metrics.compute(cases, 7, TODAY)["routing"]
    assert {r["key"]: r["emails"] for r in out["reasons"]} == {"low_confidence": 2, "no_customer": 1, "other": 1}
    assert out["byRoute"]["AUTO"] == {"emails": 2, "reviewed": 2, "accepted": 1, "changed": 1, "noneFits": 0,
                                      "acceptedPct": 50.0}
    assert out["byRoute"]["REVIEW"]["noneFits"] == 1 and out["byRoute"]["REVIEW"]["acceptedPct"] == 0.0
    bands = {b["from"]: b for b in out["bands"]}
    assert bands[95]["emails"] == 1 and bands[95]["acceptedPct"] == 100.0 and bands[95]["to"] == 100
    assert bands[90]["acceptedPct"] == 0.0 and bands[60]["emails"] == 2 and bands[60]["reviewed"] == 1
    assert out["categories"][0]["category"] == "Βεβαίωση οφειλής" and out["categories"][0]["emails"] == 4


def test_actions_kept_removed_and_added():
    cases = [
        case(1, "2026-11-20T08:00:00Z", "REVIEW", status="REVIEWED", final="Βεβαίωση οφειλής",
             proposed=["request", "forward"],
             chosen=[{"do": "request", "source": "suggested", "codes": ["124"], "open": "64"},
                     {"do": "manual", "source": "added"}]),
        case(2, "2026-11-20T08:00:00Z", "REVIEW", status="REVIEWED", final="Βεβαίωση οφειλής",
             proposed=["request"], chosen=[{"do": "request", "source": "suggested", "codes": ["124"]}]),
        case(3, "2026-11-20T08:00:00Z", "AUTO", proposed=["reply"]),  # not reviewed: proposed only
    ]
    out = metrics.compute(cases, 7, TODAY)["actions"]
    kinds = {k["do"]: k for k in out["byKind"]}
    assert kinds["request"] == {"do": "request", "proposed": 2, "proposedReviewed": 2, "kept": 2, "removed": 0,
                                "added": 0, "final": 2, "keptPct": 100.0}
    assert kinds["forward"]["removed"] == 1 and kinds["forward"]["keptPct"] == 0.0
    assert kinds["manual"]["added"] == 1 and kinds["manual"]["proposed"] == 0
    assert kinds["reply"]["proposed"] == 1 and kinds["reply"]["proposedReviewed"] == 0
    assert out["totals"] == {"proposed": 4, "proposedReviewed": 3, "kept": 2, "removed": 1, "added": 1,
                             "keptPct": 66.7, "casesWithProposals": 2, "unchangedPct": 50.0}
    assert out["codes"][0] == {"code": "124", "count": 2}


def test_no_emails():
    out = metrics.compute([], 30, TODAY)
    assert out["totals"]["received"] == 0 and out["totals"]["autoPct"] is None and len(out["daily"]) == 30
