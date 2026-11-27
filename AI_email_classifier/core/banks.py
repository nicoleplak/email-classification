"""Banks and SPVs named in an email or its attachments (inputs/spvmapping.json, optionally spvmapping.csv).

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

FILE = Path(__file__).resolve().parents[1] / "inputs" / "spvmapping.json"
CSV_FILE = FILE.with_suffix(".csv")
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


def _load() -> dict[str, Any]:
    """spvmapping.json (+ spvmapping.csv), re-read when either file changes."""
    stamp = tuple(f.stat().st_mtime if f.exists() else 0 for f in (FILE, CSV_FILE))
    if _cache.get("stamp") != stamp:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        banks = {}
        for name, spec in (data.get("banks") or {}).items():
            aliases = {_phrase(a) for a in [name, *spec.get("aliases", [])]} - {()}
            banks[name] = {"aliases": sorted(aliases, key=len, reverse=True), "spvs": list(spec.get("spvs", [])),
                           "flag": spec.get("flag")}
        rows = list(data.get("spvs") or [])
        if CSV_FILE.exists():
            import csv

            text = CSV_FILE.read_text(encoding="utf-8-sig")
            dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=";,\t") if text.strip() else csv.excel
            rows += [{k.strip().upper(): (v or "").strip() for k, v in r.items() if k}
                     for r in csv.DictReader(text.splitlines(), dialect=dialect)]
        spvs = []
        for row in rows:
            name, code = str(row.get("SPVNAME") or "").strip(), str(row.get("SPVCODE") or "").strip()
            if not name and not code:
                continue
            aliases = row.get("ALIASES") or []
            aliases = [a.strip() for a in (aliases.split("|") if isinstance(aliases, str) else aliases) if a.strip()]
            # A code is looked for in the text only when it has a letter: bare numbers are everywhere in emails.
            written = [_name_phrase(name), *(_phrase(a) for a in aliases),
                       *([_phrase(code)] if re.search(r"[^\W\d_]", code) and len(code) >= 3 else [])]
            spvs.append({"name": name, "code": code, "bank": str(row.get("BANK") or "").strip(),
                         "phrases": sorted({p for p in written if p and len("".join(p)) >= 3}, key=len, reverse=True)})
        _cache.update(stamp=stamp, banks=banks, spvs=spvs)
    return _cache


def config() -> dict[str, Any]:
    """The banks: {name: {aliases, spvs, flag}}."""
    return _load()["banks"]


def spv_rows() -> list[dict[str, Any]]:
    """The SPV mapping rows: {name, code, bank, phrases}."""
    return _load()["spvs"]


def _name_phrase(name: str) -> tuple[str, ...]:
    """An SPV name as words that say which one it is (no SPV, DAC, roman numerals...)."""
    return tuple(w for w in _phrase(name) if w not in NOT_A_NAME and not ROMAN.fullmatch(w) and not w.isdigit())


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
    """The customer's SPVs the email points at: {spv as in the accounts: why}. Why is what was written.

    Through the SPV mapping: the text writes an SPV's name, code or alias, or names its bank; that SPV is the
    customer's when its SPVCODE is the account's PRTFL_CD or its SPVNAME the account's PRTFL_NM. Without a
    mapping row, an SPV whose own registry name is written in the text also counts.
    """
    banks = config()
    texts = list(texts)
    owned = [a for a in accounts if a.get("spv") and a.get("spv") != "—"]
    all_tokens = [_tokens(t) for t in texts]
    out: dict[str, str] = {}

    def written(phrases: list[tuple[str, ...]]) -> tuple[int, int, int] | None:
        for i, tokens in enumerate(all_tokens):
            for phrase in phrases:
                hit = _find(phrase, tokens)
                if hit:
                    return i, *hit
        return None

    def same(row: dict, account: dict) -> bool:
        code = str(account.get("spvCode") or "").strip().upper()
        return (bool(row["code"]) and row["code"].upper() == code) or (
            bool(row["name"]) and _phrase(row["name"]) == _phrase(account["spv"]))

    named_banks = {m["bank"]: m["written"] for m in found}
    for row in spv_rows():
        hit = written(row["phrases"])
        why = (" ".join(texts[hit[0]][hit[1]:hit[2]].split()) if hit
               else named_banks.get(row["bank"]) if row["bank"] else None)
        if why:
            for account in owned:
                if same(row, account):
                    out.setdefault(account["spv"], why)
    for m in found:  # older form: SPV names listed under the bank
        listed = {_phrase(s) for s in banks.get(m["bank"], {}).get("spvs", [])}
        for account in owned:
            if _phrase(account["spv"]) in listed:
                out.setdefault(account["spv"], m["written"])
    for account in owned:
        phrase = _name_phrase(account["spv"])
        if phrase and len("".join(phrase)) >= 4 and written([phrase]):
            out.setdefault(account["spv"], account["spv"])
    return out
