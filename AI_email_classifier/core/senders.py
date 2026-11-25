"""Who sent an email: a customer or other outside party, doValue staff, or retail support forwarding one.

Rules in inputs/sender_flags.json; read on every call through a small cache, so a changed list applies to
every email the next time it is shown (the review app and the export work this out when they show it).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parents[1] / "inputs" / "sender_flags.json"
EXTERNAL, INTERNAL, RETAIL = "external", "internal", "retail_support"


@lru_cache(maxsize=4)
def _rules(mtime: float) -> tuple[tuple[str, ...], frozenset[str]]:
    data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    domains = tuple(d.strip().lower().lstrip("@") for d in data.get("internal_domains") or [] if d.strip())
    retail = frozenset(a.strip().lower() for a in data.get("retail_support") or [] if a.strip())
    return domains, retail


def rules() -> tuple[tuple[str, ...], frozenset[str]]:
    return _rules(RULES_FILE.stat().st_mtime)


def sender_type(address: str | None) -> str:
    """'retail_support' for a listed address, 'internal' for an internal domain, else 'external'."""
    address = (address or "").strip().lower()
    domains, retail = rules()
    if address in retail:
        return RETAIL
    domain = address.rpartition("@")[2]
    if domain and any(domain == d or domain.endswith("." + d) for d in domains):
        return INTERNAL
    return EXTERNAL
