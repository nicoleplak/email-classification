"""Numbers for the Metrics view: daily intake and routing, why emails needed review, how reviews went, and
what happened to the actions the system proposed.

Pure functions over case documents (no I/O), so they are tested on invented cases. Days are Athens
calendar days, like the rest of the page; the Greek DST rule is coded here so no tz database is needed
(Windows Python ships without one).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any, Iterable

# What the metrics read from each case (the store returns only these).
FIELDS = ["id", "receivedAt", "status", "route", "routeReasons", "modelCategory", "finalCategory", "noMatch",
          "confidence", "reviewedAt", "reviewedBy", "finalActions", "understanding", "reviewOutcome", "actionsOutcome"]

# routeReasons are English sentences written by core/run_classifier; the page shows them by key.
REASON_KEYS = [
    ("low_confidence", r"^confidence \d+% is below"),
    ("no_tax_id", r"^no tax ID \(AFM\) found"),
    ("tax_id_unknown", r"^tax ID not found in the customer registry"),
    ("split_categories", r"^its tax IDs lead to different categories"),
    ("no_category", r"^no category fits"),
    ("attachment_unread", r"^an attachment could not be read"),
    ("failed", r"^classification failed"),
    ("no_result", r"^the classifier returned no result"),
    ("name_mismatch", r"^the name in the email differs"),
    ("possible_customer", r"^the customer is only a possible match"),
    ("no_customer", r"^no customer found in the registry"),
    ("details_unread", r"^the customer details could not be read"),
    ("email_missing", r"^email not found in"),
    ("reset", r"^review reset by"),
    ("account_unknown", r"^the account or portfolio \(SPV\) the request concerns is not identified"),
    ("complaint_secondary", r"^the complaint is not the main request"),
    ("distress", r"^the email mentions self-harm"),
    ("heir_only", r"^the customer was identified only by an heir"),
]
REASON_RES = [(key, re.compile(pattern)) for key, pattern in REASON_KEYS]
# Certainty bands for threshold tuning: [low, high) in percent; the last one includes 100.
BANDS = [(0, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 95), (95, 101)]
ROUTES = ("AUTO", "REVIEW", "EXCEPTION")


def _last_sunday(year: int, month: int) -> date:
    d = date(year, month, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def athens_time(iso: str | None) -> datetime | None:
    """A UTC timestamp in Athens local time: UTC+3 from the last Sunday of March 01:00 UTC to the last
    Sunday of October 01:00 UTC, UTC+2 otherwise (EU rule). Naive datetime, for display and Excel."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    t = t.astimezone(timezone.utc)
    summer_from = datetime.combine(_last_sunday(t.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    summer_to = datetime.combine(_last_sunday(t.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    offset = 3 if summer_from <= t < summer_to else 2
    return (t + timedelta(hours=offset)).replace(tzinfo=None)


def athens_day(iso: str | None) -> str | None:
    """The Athens calendar day (YYYY-MM-DD) of a UTC timestamp."""
    local = athens_time(iso)
    return local.date().isoformat() if local else None


def reason_key(reason: str) -> str:
    for key, pattern in REASON_RES:
        if pattern.search(reason or ""):
            return key
    return "other"


def route_of(case: dict) -> str:
    """How the system routed the email: AUTO, REVIEW, EXCEPTION, or WAITING (not classified yet)."""
    if case.get("route") in ROUTES:
        return case["route"]
    return "WAITING"


NO_MATCH = "No Match Found"  # a category of its own: manual handling


def outcome(case: dict) -> str | None:
    """For a reviewed email: did the reviewer keep the system's category? accepted / changed / none_fits.

    "No Match Found" is a category (manual handling): kept when the system also proposed it.
    """
    if case.get("status") != "REVIEWED":
        return None
    if case.get("reviewOutcome") in ("accepted", "changed", "none_fits"):
        return case["reviewOutcome"]  # stored when the review was saved
    model = case.get("modelCategory")
    final = NO_MATCH if case.get("noMatch") else case.get("finalCategory")
    if model and final == model:
        return "accepted"
    return "none_fits" if final == NO_MATCH else "changed"


def _action_key(action: dict) -> tuple:
    return (action.get("do"), action.get("code") or ((action.get("codes") or [None])[0]), action.get("account"))


def actions_outcome(case: dict) -> str | None:
    """For a reviewed email: did the reviewer keep the proposed actions as they were? same / changed.

    Same = every proposal kept and nothing added (a changed account or code counts as a change).
    """
    if case.get("status") != "REVIEWED":
        return None
    if case.get("actionsOutcome") in ("same", "changed"):
        return case["actionsOutcome"]
    proposed = Counter(_action_key(a) for a in (case.get("understanding") or {}).get("actions") or [])
    final = case.get("finalActions") or []
    if any(a.get("source") != "suggested" for a in final):
        return "changed"
    return "same" if Counter(_action_key(a) for a in final) == proposed else "changed"


def case_facts(case: dict) -> dict:
    """What the email list filters on, for one case (cheap fields only once computed)."""
    return {"outcome": outcome(case), "actionsOutcome": actions_outcome(case),
            "reasonKeys": sorted({reason_key(r) for r in case.get("routeReasons") or []})}


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _hours(start: str | None, end: str | None) -> float | None:
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max((b - a).total_seconds() / 3600, 0.0)


def _days_between(first: str, last: str) -> list[str]:
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    return [(a + timedelta(days=n)).isoformat() for n in range((b - a).days + 1)]


def compute(cases: Iterable[dict], days: int, today: str) -> dict[str, Any]:
    """Metrics for emails received in the last ``days`` Athens days up to ``today`` (0 = everything)."""
    cases = [c for c in cases if athens_day(c.get("receivedAt"))]
    if days > 0:
        first = (date.fromisoformat(today) - timedelta(days=days - 1)).isoformat()
    else:
        first = min((athens_day(c["receivedAt"]) for c in cases), default=today)
    cases = [c for c in cases if first <= athens_day(c["receivedAt"]) <= today]

    # -- daily intake and routing
    daily = {d: {"day": d, "received": 0, "AUTO": 0, "REVIEW": 0, "EXCEPTION": 0, "WAITING": 0,
                 "reviewed": 0, "open": 0} for d in _days_between(first, today)}
    for c in cases:
        row = daily[athens_day(c["receivedAt"])]
        route = route_of(c)
        row["received"] += 1
        row[route] += 1
        if c.get("status") == "REVIEWED":
            row["reviewed"] += 1
        elif route in ("REVIEW", "EXCEPTION"):
            row["open"] += 1

    routes = Counter(route_of(c) for c in cases)
    reviewed = [c for c in cases if c.get("status") == "REVIEWED"]
    turnaround = [h for c in reviewed if (h := _hours(c.get("receivedAt"), c.get("reviewedAt"))) is not None]
    classified = routes["AUTO"] + routes["REVIEW"] + routes["EXCEPTION"]
    totals = {
        "received": len(cases),
        "classified": classified,
        "auto": routes["AUTO"],
        "review": routes["REVIEW"],
        "exception": routes["EXCEPTION"],
        "waiting": routes["WAITING"],
        "reviewed": len(reviewed),
        "open": sum(r["open"] for r in daily.values()),
        "autoPct": _pct(routes["AUTO"], classified),
        "reviewPct": _pct(routes["REVIEW"] + routes["EXCEPTION"], classified),
        "medianHoursToReview": round(median(turnaround), 1) if turnaround else None,
    }

    # -- routing: why review, how reviews went per route, certainty bands, categories
    reasons = Counter()
    for c in cases:
        if route_of(c) in ("REVIEW", "EXCEPTION"):
            reasons.update({reason_key(r) for r in c.get("routeReasons") or []})
    by_route = {}
    for route in ROUTES:
        group = [outcome(c) for c in reviewed if route_of(c) == route]
        counts = Counter(group)
        by_route[route] = {"emails": routes[route], "reviewed": len(group), "accepted": counts["accepted"],
                           "changed": counts["changed"], "noneFits": counts["none_fits"],
                           "acceptedPct": _pct(counts["accepted"], len(group))}
    bands = []
    for low, high in BANDS:
        inside = [c for c in cases if c.get("confidence") is not None
                  and low <= round(100 * float(c["confidence"])) < high]
        done = [outcome(c) for c in inside if c.get("status") == "REVIEWED"]
        bands.append({"from": low, "to": min(high, 100), "emails": len(inside), "reviewed": len(done),
                      "accepted": done.count("accepted"), "acceptedPct": _pct(done.count("accepted"), len(done))})
    categories: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        if not c.get("modelCategory"):
            continue
        row = categories[c["modelCategory"]]
        row["emails"] += 1
        row[route_of(c)] += 1
        result = outcome(c)
        if result:
            row["reviewed"] += 1
            row[result] += 1
    category_rows = sorted(
        ({"category": name, "emails": r["emails"], "auto": r["AUTO"], "review": r["REVIEW"] + r["EXCEPTION"],
          "autoPct": _pct(r["AUTO"], r["emails"]), "reviewed": r["reviewed"],
          "acceptedPct": _pct(r["accepted"], r["reviewed"])} for name, r in categories.items()),
        key=lambda r: (-r["emails"], r["category"]))

    # -- actions: proposed by the rules, then kept, removed or added in review
    kinds: dict[str, Counter] = defaultdict(Counter)
    codes = Counter()
    review_totals = Counter()
    for c in cases:
        proposed = Counter(a.get("do") for a in (c.get("understanding") or {}).get("actions") or [] if a.get("do"))
        for kind, n in proposed.items():
            kinds[kind]["proposed"] += n
        if c.get("status") != "REVIEWED":
            continue
        final = c.get("finalActions") or []
        kept = Counter(a.get("do") for a in final if a.get("source") == "suggested")
        added = Counter(a.get("do") for a in final if a.get("source") != "suggested")
        for kind in set(proposed) | set(kept) | set(added):
            k = min(kept[kind], proposed[kind]) if proposed[kind] else kept[kind]
            kinds[kind]["proposedReviewed"] += proposed[kind]
            kinds[kind]["kept"] += k
            kinds[kind]["removed"] += max(proposed[kind] - k, 0)
            kinds[kind]["added"] += added[kind]
            kinds[kind]["final"] += kept[kind] + added[kind]
        review_totals["casesWithProposals"] += bool(proposed)
        review_totals["unchanged"] += bool(proposed) and not added and kept == proposed
        for a in final:
            codes.update(str(code) for code in [a.get("open"), a.get("closed"), *(a.get("codes") or [])] if code)
    action_rows = sorted(
        ({"do": kind, "proposed": r["proposed"], "proposedReviewed": r["proposedReviewed"], "kept": r["kept"],
          "removed": r["removed"], "added": r["added"], "final": r["final"],
          "keptPct": _pct(r["kept"], r["proposedReviewed"])} for kind, r in kinds.items()),
        key=lambda r: (-(r["proposed"] + r["added"]), r["do"]))
    proposed_reviewed = sum(r["proposedReviewed"] for r in action_rows)
    action_totals = {
        "proposed": sum(r["proposed"] for r in action_rows),
        "proposedReviewed": proposed_reviewed,
        "kept": sum(r["kept"] for r in action_rows),
        "removed": sum(r["removed"] for r in action_rows),
        "added": sum(r["added"] for r in action_rows),
        "keptPct": _pct(sum(r["kept"] for r in action_rows), proposed_reviewed),
        "casesWithProposals": review_totals["casesWithProposals"],
        "unchangedPct": _pct(review_totals["unchanged"], review_totals["casesWithProposals"]),
    }

    # -- reviewers and category x actions
    people: dict[str, dict] = {}
    for c in reviewed:
        who = c.get("reviewedBy") or {}
        key = who.get("id") or who.get("name") or "?"
        row = people.setdefault(key, {"id": key, "name": who.get("name") or key, "reviewed": 0, "accepted": 0,
                                      "changed": 0, "noneFits": 0, "actionsChanged": 0, "hours": [], "last": ""})
        row["reviewed"] += 1
        row[{"accepted": "accepted", "changed": "changed", "none_fits": "noneFits"}[outcome(c)]] += 1
        row["actionsChanged"] += actions_outcome(c) == "changed"
        hours = _hours(c.get("receivedAt"), c.get("reviewedAt"))
        if hours is not None:
            row["hours"].append(hours)
        row["last"] = max(row["last"], c.get("reviewedAt") or "")
    reviewers = sorted(
        ({**{k: v for k, v in r.items() if k != "hours"}, "acceptedPct": _pct(r["accepted"], r["reviewed"]),
          "actionsChangedPct": _pct(r["actionsChanged"], r["reviewed"]),
          "medianHours": round(median(r["hours"]), 1) if r["hours"] else None} for r in people.values()),
        key=lambda r: (-r["reviewed"], r["name"]))
    matrix = Counter((outcome(c) == "accepted", actions_outcome(c) == "same") for c in reviewed)
    combined = {
        "rightRight": matrix[(True, True)], "rightWrong": matrix[(True, False)],
        "wrongRight": matrix[(False, True)], "wrongWrong": matrix[(False, False)], "reviewed": len(reviewed),
    }

    return {
        "from": first,
        "to": today,
        "totals": totals,
        "reviewers": reviewers,
        "combined": combined,
        "daily": list(daily.values()),
        "routing": {"reasons": [{"key": k, "emails": n} for k, n in reasons.most_common()],
                    "byRoute": by_route, "bands": bands, "categories": category_rows},
        "actions": {"totals": action_totals, "byKind": action_rows,
                    "codes": [{"code": k, "count": n} for k, n in codes.most_common(10)]},
    }
