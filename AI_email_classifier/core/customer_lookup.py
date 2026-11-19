"""Find the customers an email is about: the registry (qualco_output) and past Qualco requests (request_output).

Evidence has two strengths:
- strong: a tax ID (ΑΦΜ) that passes its check digit, or an exact account number. Either one names a
  customer on its own.
- clue: a person's name, or an email address that earlier Qualco requests were filed under. A clue
  becomes a match only when a strong identifier, or a clue of a different kind, points at the same person.

Several people with the same name are all listed and marked "possible"; one is never picked at random.
No I/O here except the one streaming pass over request_output in ``RequestHistory.scan``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

import pandas as pd

ACCOUNT_COLUMNS = ("ACC_UNQ_CD", "SRV_ACC_UNQ_CD", "ACC_ID")
MAX_NAME_MATCHES = 8  # more than this and a name says nothing about who it is
MAX_ACCOUNTS_SHOWN = 15
HISTORY_COLUMNS = [
    "AFM",
    "EMAIL",
    "CUST_FIRST_NM",
    "CUST_LAST_NM",
    "REQUEST_TYPE_DSC",
    "REQUEST_STATUS",
    "REQUEST_CREATED",
    "CLOSED_REQUEST_FLAG",
    "ACC_ID",
]


def normalize_name(text: Any) -> str:
    """Upper case, no accents, letters and single spaces only: 'Παπαδόπουλος Γιώργος' -> 'ΠΑΠΑΔΟΠΟΥΛΟΣ ΓΙΩΡΓΟΣ'."""
    plain = "".join(
        ch for ch in unicodedata.normalize("NFD", str(text or "")) if not unicodedata.combining(ch)
    )
    return " ".join(re.sub(r"[^\w]+|[\d_]+", " ", plain.upper()).split())


def _name_tokens(text: Any) -> list[str]:
    return [t for t in normalize_name(text).split() if len(t) >= 2]


def _unique(values: Iterable[Any]) -> list[str]:
    return [v for v in dict.fromkeys(str(x).strip() for x in values) if v]


class Registry:
    """The customer registry already loaded by the classifier, with lookups by tax ID, account and name."""

    def __init__(self, df: pd.DataFrame, source: str = ""):
        self.df = df
        self.source = source
        self._names: pd.Series | None = None

    def rows_for_tax(self, tax_id: str) -> pd.DataFrame:
        return self.df[self.df["TAX_ID_NO"] == tax_id]

    def owners_of_account(self, number: str) -> list[str]:
        mask = pd.Series(False, index=self.df.index)
        for column in ACCOUNT_COLUMNS:
            if column in self.df.columns:
                mask |= self.df[column].str.strip() == number
        return _unique(self.df.loc[mask, "TAX_ID_NO"])

    def tax_ids_for_name(self, name: str) -> list[str] | int:
        """Tax IDs whose registry name holds every word of ``name``; an int when there are too many to list."""
        tokens = _name_tokens(name)
        if len(tokens) < 2 or "NAME" not in self.df.columns:
            return []  # a single word (first name only) matches thousands
        if self._names is None:
            self._names = " " + self.df["NAME"].map(normalize_name) + " "
        mask = pd.Series(True, index=self.df.index)
        for token in tokens:
            mask &= self._names.str.contains(f" {re.escape(token)} ", regex=True)
        found = _unique(self.df.loc[mask, "TAX_ID_NO"])
        return len(found) if len(found) > MAX_NAME_MATCHES else found

    def name_of(self, tax_id: str) -> str:
        rows = self.rows_for_tax(tax_id)
        return str(rows["NAME"].iloc[0]).strip() if "NAME" in rows.columns and not rows.empty else ""

    def card(self, tax_id: str) -> dict[str, Any]:
        """What a reviewer needs to know about one customer, straight from the registry rows."""
        rows = self.rows_for_tax(tax_id)

        def get(column: str) -> list[str]:
            return _unique(rows[column]) if column in rows.columns else []

        accounts = [
            {
                "account": str(row.get("ACC_UNQ_CD") or "").strip(),
                "serviceAccount": str(row.get("SRV_ACC_UNQ_CD") or "").strip(),
                "type": str(row.get("ACC_TP_NM") or "").strip(),
                "assetClass": str(row.get("ASST_CLS") or "").strip(),
                "settlement": str(row.get("SETL_STS_NM") or "").strip(),
                "portfolio": str(row.get("PRTFL_NM") or row.get("PRTFL_CD") or "").strip(),
                "assigned": str(row.get("ASSIGNED") or "").strip(),
            }
            for row in rows.head(MAX_ACCOUNTS_SHOWN).to_dict("records")
        ]
        return {
            "taxId": tax_id,
            "name": self.name_of(tax_id),
            "personOrCompany": (get("IDV_ORG_IND") or [""])[0],
            "customerCodes": get("CST_UNQ_CD"),
            "portfolios": get("PRTFL_NM") or get("PRTFL_CD"),
            "statuses": get("CST_STS_NM"),
            "sources": get("SOURCE"),
            "portal": "Y" in get("PORTAL_FLAG"),
            "accounts": accounts,
            "accountsTotal": len(rows),
        }


class RequestHistory:
    """The request_output rows for a known set of emails and tax IDs, read in one streaming pass."""

    def __init__(self, rows: pd.DataFrame, source: str = ""):
        self.rows = rows
        self.source = source

    @classmethod
    def empty(cls) -> "RequestHistory":
        return cls(pd.DataFrame(columns=HISTORY_COLUMNS))

    @classmethod
    def scan(cls, csv_path: str, emails: set[str], tax_ids: set[str], source: str = "") -> "RequestHistory":
        # ponytail: one pass per classifier run over ~570 MB; index it if runs ever get frequent.
        emails = {e.lower() for e in emails}
        keep = []
        for chunk in pd.read_csv(
            csv_path,
            sep=";",
            dtype=str,
            encoding="utf-8-sig",
            usecols=lambda c: c in HISTORY_COLUMNS,
            chunksize=250_000,
        ):
            chunk = chunk.fillna("")
            mask = chunk["AFM"].str.strip().isin(tax_ids) | chunk["EMAIL"].str.strip().str.lower().isin(emails)
            if mask.any():
                keep.append(chunk[mask])
        rows = pd.concat(keep) if keep else pd.DataFrame(columns=HISTORY_COLUMNS)
        return cls(rows.apply(lambda column: column.astype(str).str.strip()), source)

    def tax_ids_for_email(self, email: str) -> list[str]:
        rows = self.rows[self.rows["EMAIL"].str.lower() == email.lower()]
        return _unique(rows["AFM"])

    def recent(self, tax_id: str, limit: int = 5) -> list[dict[str, str]]:
        rows = self.rows[self.rows["AFM"] == tax_id].sort_values("REQUEST_CREATED", ascending=False)
        return [
            {
                "type": r["REQUEST_TYPE_DSC"],
                "status": r["REQUEST_STATUS"],
                "created": r["REQUEST_CREATED"],
                "closed": r["CLOSED_REQUEST_FLAG"],
                "account": r["ACC_ID"],
            }
            for r in rows.head(limit).to_dict("records")
        ]


def find_customers(
    registry: Registry,
    history: RequestHistory,
    tax_ids: list[dict],
    accounts: list[dict],
    emails: list[dict],
    names: list[dict],
) -> dict[str, Any]:
    """Every customer the evidence points at, how sure we are, and the facts the action rules need.

    Each evidence item is ``{"value": ..., "where": <source label>}``; names also carry
    ``principal`` (the email is about this person) and ``role``.
    """
    clues: dict[str, list[dict]] = {}
    notes: list[str] = []
    unmatched: list[dict] = []

    def add(tax_id: str, kind: str, item: dict, strong: bool) -> None:
        clues.setdefault(tax_id, []).append(
            {"kind": kind, "value": item["value"], "where": item.get("where", ""), "strong": strong}
        )

    for item in tax_ids:
        if registry.rows_for_tax(item["value"]).empty:
            unmatched.append({"kind": "afm", **item})
        else:
            add(item["value"], "afm", item, True)
    for item in accounts:
        owners = registry.owners_of_account(item["value"])
        if not owners:
            unmatched.append({"kind": "account", **item})
        for owner in owners:
            add(owner, "account", item, True)
    for item in emails:
        for owner in history.tax_ids_for_email(item["value"]):
            if not registry.rows_for_tax(owner).empty:
                add(owner, "email", item, False)
    name_groups: dict[str, list[str]] = {}
    principal_names = {n["value"] for n in names if n.get("principal")}
    for item in names:
        found = registry.tax_ids_for_name(item["value"])
        if isinstance(found, int):
            notes.append(f"too_many_name_matches:{item['value']}:{found}")
            continue
        name_groups[item["value"]] = found
        for tax_id in found:
            add(tax_id, "name", item, False)

    customers = []
    for tax_id, evidence in clues.items():
        kinds = {e["kind"] for e in evidence}
        same_name = max((len(g) for value, g in name_groups.items() if tax_id in g), default=0)
        card = registry.card(tax_id)
        card.update(
            {
                "status": "confirmed" if any(e["strong"] for e in evidence) or len(kinds) >= 2 else "possible",
                "matchedOn": evidence,
                "sameNameCount": same_name,
                "principal": any(e["kind"] == "name" and e["value"] in principal_names for e in evidence),
                "recentRequests": history.recent(tax_id),
            }
        )
        customers.append(card)

    # Double-check strong matches against the name the email gives: the owner should be that person.
    for card in customers:
        if card["status"] == "confirmed" and principal_names and not any(e["kind"] == "name" for e in card["matchedOn"]):
            registry_tokens = set(_name_tokens(card["name"]))
            if registry_tokens and not any(set(_name_tokens(n)) & registry_tokens for n in principal_names):
                card["nameMismatch"] = True

    customers.sort(key=lambda c: (c["status"] != "confirmed", not c["principal"], -len(c["matchedOn"])))
    confirmed = [c for c in customers if c["status"] == "confirmed"]
    facts_from = [c for c in confirmed if c["principal"]] or confirmed
    rows = [registry.rows_for_tax(c["taxId"]) for c in facts_from]
    return {
        "customers": customers,
        "unmatched": unmatched,
        "notes": notes,
        "facts": {
            "identified": bool(confirmed) or bool(tax_ids),
            "known": bool(confirmed),
            "portal": any(c["portal"] for c in facts_from),
            "erb": any((r["SOURCE"] == "Datamart").any() for r in rows if "SOURCE" in r.columns),
            "is_3869": any(r["CST_STS_NM"].str.contains("3869").any() for r in rows if "CST_STS_NM" in r.columns),
        },
    }
