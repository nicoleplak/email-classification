"""Banks and funds named in an email or its attachments (inputs/banks.json).

Two uses:
- the customer's portfolio (SPV): a bank or SPV name in the text points at the accounts that came from it,
  so the action rules can open the request on the right SPV (``spvs_for``);
- flags: Eurobank named anywhere in the email text or an attachment flags the email ERB (``flags``).

Names are found by spelling, never by the model, as whole words with Greek case endings ignored
(Τράπεζα Πειραιώς = της Τράπεζας Πειραιώς), without accents or case. No I/O except reading the file.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

FILE = Path(__file__).resolve().parents[1] / "inputs" / "banks.json"
WORD = re.compile(r"\w+")
GREEK_ENDINGS = ("ΟΥΣ", "ΑΣ", "ΗΣ", "ΟΣ", "ΟΥ", "ΩΝ", "ΕΣ", "ΩΣ", "ΑΙ", "Α", "Η", "Ο", "Ε", "Σ", "Υ", "Ι")
# Words in portfolio names that say nothing about which one it is.
NOT_A_NAME = {"SPV", "DAC", "LTD", "LIMITED", "SA", "AE", "DESIGNATED", "ACTIVITY", "COMPANY", "PORTFOLIO", "FUND"}
ROMAN = re.compile(r"[IVX]+")
_cache: dict[str, Any] = {}


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)).upper()


def stem(word: str) -> str:
    """Accent-free upper case; Greek words longer than four letters lose their case ending."""
    word = _plain(word)
    if len(word) > 4 and re.match(r"[Α-Ω]", word):
        for ending in GREEK_ENDINGS:
            if word.endswith(ending) and len(word) - len(ending) >= 4:
                return word[: -len(ending)]
    return word


def _phrase(text: str) -> tuple[str, ...]:
    return tuple(stem(w) for w in WORD.findall(text))


def config() -> dict[str, Any]:
    """banks.json, re-read when the file changes."""
    mtime = FILE.stat().st_mtime if FILE.exists() else 0
    if _cache.get("mtime") != mtime:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"banks": {}}
        banks = {}
        for name, spec in (data.get("banks") or {}).items():
            aliases = {_phrase(a) for a in [name, *spec.get("aliases", [])]} - {()}
            banks[name] = {"aliases": sorted(aliases, key=len, reverse=True), "spvs": list(spec.get("spvs", [])),
                           "flag": spec.get("flag")}
        _cache.update(mtime=mtime, banks=banks)
    return _cache["banks"]


def _find(phrase: tuple[str, ...], tokens: list[tuple[str, int, int]]) -> tuple[int, int] | None:
    stems = [t[0] for t in tokens]
    n = len(phrase)
    for i in range(len(stems) - n + 1):
        if tuple(stems[i : i + n]) == phrase:
            return tokens[i][1], tokens[i + n - 1][2]
    return None


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(stem(m.group(0)), m.start(), m.end()) for m in WORD.finditer(text or "")]


def mentions(docs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every bank named in the texts: {bank, written, flag, where, snippet}, once per bank and text.

    docs: {"text": ..., "where": {...}} as from core.understand.documents.
    """
    banks = config()
    found, seen = [], set()
    for doc in docs:
        text = doc.get("text") or ""
        tokens = _tokens(text)
        for name, spec in banks.items():
            for alias in spec["aliases"]:
                hit = _find(alias, tokens)
                if not hit or (name, id(doc)) in seen:
                    continue
                seen.add((name, id(doc)))
                start, end = hit
                found.append({
                    "bank": name, "written": text[start:end], "flag": spec["flag"], "where": doc.get("where") or {},
                    "snippet": " ".join(text[max(0, start - 80) : end + 80].split()),
                })
                break
    return found


def flags(found: list[dict[str, Any]]) -> list[str]:
    """Marks for the email, e.g. ["ERB"] when Eurobank is named."""
    return sorted({m["flag"] for m in found if m.get("flag")})


def spvs_for(found: list[dict[str, Any]], texts: Iterable[str], accounts: list[dict[str, Any]]) -> dict[str, str]:
    """The customer's SPVs the email points at: {spv: why}. Why is the bank or the SPV name as written.

    An SPV matches when it is listed under a bank the email names, or when its own name is in the text.
    """
    banks = config()
    spvs = {a.get("spv") for a in accounts if a.get("spv") and a.get("spv") != "—"}
    out: dict[str, str] = {}
    for m in found:
        listed = {_phrase(s) for s in banks.get(m["bank"], {}).get("spvs", [])}
        for spv in spvs:
            if _phrase(spv) in listed:
                out.setdefault(spv, m["written"])
    all_tokens = [_tokens(t) for t in texts]
    for spv in spvs:
        phrase = tuple(w for w in _phrase(spv) if w not in NOT_A_NAME and not ROMAN.fullmatch(w) and not w.isdigit())
        if not phrase or len("".join(phrase)) < 4:
            continue
        for tokens in all_tokens:
            if _find(phrase, tokens):
                out.setdefault(spv, spv)
                break
    return out
