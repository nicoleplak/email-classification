"""The data of an email as a table: what was found in the email and its documents, where, and what a reviewer
added or corrected; and the decision made again from that table (customer, accounts, actions).

Stored as one document per email in the case store's "data" collection (id = case id), rows in ``rows``:

    type             afm, account, contract, payment_code (RF), iban, adt, phone, email, case_ref, name, spv
    value            as found or typed
    role             debtor, co_debtor, deceased_debtor, heir, representative, ... (whose value it is)
    identifiesCase   used to find the customer
    source           where it was found: {kind: subject|body|thread|attachment|sender|user, file, page}
    snippet          the text around it
    method           pattern + check digit, pattern + model, pattern, user, ...
    checked          passed a check digit (ΑΦΜ, IBAN, RF)
    status           found (by the classifier), added / edited / removed (by a reviewer)
    by, at           who and when, for reviewer rows; original: the value before an edit

``redecide`` runs the customer lookup and the action rules again on the rows, without the model: what the
email asks (categories, flags) stays as read; who the customer is and which account comes from the table.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from core.action_rules import decide, explain
from core.customer_lookup import HISTORY_COLUMNS, Registry, RequestHistory, find_customers
from utils.afm_utils import afm_checksum_valid

TYPES = ("afm", "account", "contract", "payment_code", "iban", "adt", "phone", "email", "case_ref", "name", "spv")
ID_TYPES = ("afm", "account", "contract", "payment_code")  # what can find the customer
PERSON_ROLES = {"debtor", "co_debtor", "deceased_debtor", "heir"}
ROLE_RANK = {"deceased_debtor": 1, "heir": 3}
REVIEWER = ("added", "edited", "removed")


def row_id(case_id: str, kind: str, value: str) -> str:
    return hashlib.sha256(f"{case_id}|{kind}|{value}".encode()).hexdigest()[:16]


def _where(source: dict | None) -> dict:
    return {k: v for k, v in (source or {}).items() if k != "snippet" and v is not None}


def rows_from_understanding(case_id: str, u: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The classifier's findings as rows (status "found")."""
    u = u or {}
    rows: list[dict[str, Any]] = []
    for e in u.get("extracted") or []:
        first = (e.get("sources") or [{}])[0] or {}
        rows.append({
            "id": row_id(case_id, e["type"], e["value"]), "type": e["type"], "value": e["value"],
            "role": e.get("role") or None, "identifiesCase": bool(e.get("identifiesCase")), "checked": bool(e.get("checked")),
            "method": e.get("method") or ("sender" if first.get("kind") == "sender" else "pattern"),
            "source": _where(first), "snippet": first.get("snippet") or "", "status": "found",
        })
    for p in u.get("people") or []:
        if p.get("principal") or p.get("role") in PERSON_ROLES:
            value = p.get("registryForm") or p.get("name") or ""
            rows.append({
                "id": row_id(case_id, "name", value), "type": "name", "value": value, "written": p.get("name"),
                "role": p.get("role"), "principal": bool(p.get("principal")), "identifiesCase": False, "checked": False,
                "method": "model", "source": _where(p.get("where")), "snippet": p.get("evidence") or "", "status": "found",
            })
    for spv, why in (u.get("spvMentioned") or {}).items():
        rows.append({"id": row_id(case_id, "spv", spv), "type": "spv", "value": spv, "role": None, "identifiesCase": False,
                     "checked": False, "method": "spvmapping", "source": {"kind": "text"}, "snippet": why, "status": "found"})
    unique: dict[str, dict] = {}
    for row in rows:
        unique.setdefault(row["id"], row)
    return list(unique.values())


def merge(found: list[dict[str, Any]], kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """New classifier rows plus the reviewer's rows, which win over a found row with the same id."""
    reviewer = {r["id"]: r for r in kept if r.get("status") in REVIEWER}
    return [reviewer.pop(r["id"], r) for r in found] + list(reviewer.values())


def to_extracted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows back in the shape the case page and the highlights read (understanding.extracted)."""
    return [{
        "type": r["type"], "value": r["value"], "role": r.get("role"), "identifiesCase": bool(r.get("identifiesCase")),
        "checked": bool(r.get("checked")), "method": r.get("method"), "status": r.get("status"),
        "sources": [{**(r.get("source") or {}), "snippet": r.get("snippet") or ""}],
    } for r in rows if r.get("status") != "removed" and r["type"] not in ("name", "spv")]


def _uses(row: dict) -> bool:
    """A row that finds the customer: the reader said so, an heir's or deceased's value, a reviewer's own value,
    or an account / contract / payment code (the registry has to have it exactly)."""
    return (row.get("identifiesCase") or row.get("role") in ("deceased_debtor", "heir")
            or row.get("status") in ("added", "edited") or row["type"] in ("account", "contract", "payment_code"))


def redecide(u: dict[str, Any], rows: list[dict[str, Any]], registry: Registry, categories: list[str]) -> dict[str, Any]:
    """The understanding again, from the table: customers, accounts, SPV and actions. categories: the email's
    requests, main first (as the reviewer has them now). Nothing is sent to the model."""
    active = [r for r in rows if r.get("status") != "removed"]

    def item(r: dict) -> dict:
        return {"value": str(r["value"]).strip(), "where": {**(r.get("source") or {}), "snippet": r.get("snippet") or ""},
                "rank": ROLE_RANK.get(r.get("role"), 2), "role": r.get("role")}

    tax_ids = [item(r) for r in active if r["type"] == "afm" and _uses(r) and afm_checksum_valid(str(r["value"]).strip())]
    accounts = [item(r) for r in active if r["type"] in ("account", "contract", "payment_code") and _uses(r)]
    emails = [{"value": r["value"], "where": r.get("source") or {}} for r in active if r["type"] == "email"]
    names = [{"value": r["value"], "where": r.get("source") or {}, "principal": bool(r.get("principal")),
              "role": r.get("role")} for r in active if r["type"] == "name"]
    # Requests already in Qualco, as read when classified (the past-requests file is not read again here).
    known = (u.get("customerFacts") or {}).get("open_requests") or []
    history = RequestHistory(pd.DataFrame(
        [{"AFM": q.get("taxId", ""), "EMAIL": "", "CUST_FIRST_NM": "", "CUST_LAST_NM": "", "REQUEST_TYPE_DSC": q.get("type", ""),
          "REQUEST_STATUS": q.get("status", ""), "REQUEST_CREATED": q.get("created", ""), "CLOSED_REQUEST_FLAG": q.get("closed", ""),
          "ACC_ID": q.get("account", "")} for q in known], columns=HISTORY_COLUMNS), "as read when classified")
    lookup = find_customers(registry, history, tax_ids=tax_ids, accounts=accounts, emails=emails, names=names)
    facts = lookup["facts"]
    wanted = {str(r["value"]).strip().upper() for r in active if r["type"] == "spv"}
    facts["spv_hint"] = sorted({a["spv"] for a in facts["accounts"]
                                if a["spv"].upper() in wanted or str(a.get("spvCode") or "").upper() in wanted})
    flags = {f: True for f in u.get("flags") or []}
    actions = decide(list(dict.fromkeys(c for c in categories if c)), flags, facts,
                     has_contract=any(r["type"] in ("contract", "account") for r in active), best_guess=True)
    for action in actions:
        action["reasons"] = explain(action)
    return {
        **u,
        "principalCategory": categories[0] if categories else u.get("principalCategory"),
        "otherRequests": [c for c in categories[1:]],
        "extracted": to_extracted(active),
        "customers": lookup["customers"],
        "unmatched": lookup["unmatched"],
        "lookupNotes": lookup["notes"],
        "customerFacts": {**facts, "open_requests": known},
        "spvMentioned": {s: (u.get("spvMentioned") or {}).get(s) or "στοιχεία email" for s in facts["spv_hint"]},
        "actions": actions,
    }
