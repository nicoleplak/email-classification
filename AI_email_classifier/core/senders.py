"""Who sent an email: a customer or other outside party, doValue staff, or retail support forwarding one.

Rules: inputs/sender_flags.json (internal domains, the category internal emails get) and the plain list
inputs/retail_support_emails.txt. Both are re-read when they change, so an edited list applies to the next
email classified or shown, without a restart.

- internal: a sender at an internal domain. Its email gets the internal category by address: the classifier
  makes no model call for it (core.run_classifier).
- retail_support: a listed address (at an internal domain or not). Classified as usual, flagged in the app.
- external: everyone else.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

INPUTS = Path(__file__).resolve().parents[1] / "inputs"
RULES_FILE = INPUTS / "sender_flags.json"
EXTERNAL, INTERNAL, RETAIL = "external", "internal", "retail_support"


def _retail_file() -> Path:
    name = json.loads(RULES_FILE.read_text(encoding="utf-8")).get("retail_support_file") or "retail_support_emails.txt"
    return RULES_FILE.parent / name


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@lru_cache(maxsize=4)
def _rules(rules_mtime: float, retail_mtime: float) -> tuple[tuple[str, ...], frozenset[str], str]:
    data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    domains = tuple(d.strip().lower().lstrip("@") for d in data.get("internal_domains") or [] if d.strip())
    listed = set(a.strip().lower() for a in data.get("retail_support") or [] if a.strip())  # older files kept it here
    retail_file = _retail_file()
    if retail_file.exists():
        for line in retail_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip().lower()
            if line:
                listed.add(line)
    return domains, frozenset(listed), str(data.get("internal_category") or "")


def rules() -> tuple[tuple[str, ...], frozenset[str]]:
    domains, retail, _ = _rules(_mtime(RULES_FILE), _mtime(_retail_file()))
    return domains, retail


def internal_category() -> str:
    return _rules(_mtime(RULES_FILE), _mtime(_retail_file()))[2]


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
