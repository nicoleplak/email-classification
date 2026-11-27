"""Find every identifier-like value in a text, with checksum and shape hints.

Candidates are found here and never by the model: the model can only say what a
found value is, so it cannot invent or mistype a number. No I/O, no LLM.
"""

from __future__ import annotations

import re
import unicodedata

from utils.afm_utils import afm_checksum_valid

# Matched on text without accents: scanned documents are often in capitals, which
# Greek writes unaccented, so an accented pattern misses ΤΑΥΤΟΤΗΤΑΣ.
LABELS = {
    "afm": r"α\.?\s*φ\.?\s*μ\.?|\bafm\b|\btin\b|\bvat\b",
    "cid": r"\bcid\b|κωδ\w*\.?\s*πελ\w*|customer (code|id)|\bcif\b|αρ\w*\.?\s*πελ\w*",
    "case": r"υποθεσ\w*|φακελ\w*|\bcase\b",
    "account": r"λογαριασμ\w*|\bλογ\b|account",
    "contract": r"συμβασ\w*|συμβολαι\w*|δανε\w*|contract|loan",
    "payment": r"κωδ\w*\.?\s*πληρωμ\w*|πληρωμ\w*|payment\s*code",
    "adt": r"α\.?\s*δ\.?\s*τ\.?\b|ταυτοτητ\w*",
    "phone": r"τηλ\w*|κιν\b|κινητ\w*|\bmob\w*|\btel\w*|\bfax\b",
}

_IBAN = re.compile(r"\bGR(?:[ ]?\d){25}\b")
_RF = re.compile(r"\bRF[ ]?\d{2}(?:[ ]?[0-9A-Z]){1,21}\b")
_ADT = re.compile(r"(?<![\w])([Α-ΩA-Z]{1,2}[ \-]?)?\d{3}[ ]?\d{3}(?![ ]?\d)")
_DIGITS = re.compile(r"(?<![\d,.])\d(?:[ .\-]?\d){6,24}(?![\d])(?!,\d)")
_DATE = re.compile(r"^\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}$")
_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
_WINDOW = 160
# A contract or account number written right after its label, in any shape the 7+ digit search misses:
# short (512345), with a slash or letters (1234/2008, LN-778899). Matched on text without accents.
_LABEL_WORD = re.compile(r"συμβασ\w*|συμβολαι\w*|contract|δανει\w*|loan|λογαριασμ\w*|account", re.IGNORECASE)
_LABEL_REACH = 40
_TOKEN = re.compile(r"(?<![\w/])((?:[A-Z]{1,4}[\- ]?)?(\d[\d/\-.]{2,24}\d))(?![\w/])")
# Most useful first, so an over-long document loses phone numbers before tax IDs.
_RANK = (
    "afm",
    "afm_padded",
    "afm_bad_checksum",
    "afm_wrong_length",
    "iban",
    "rf",
    "rf_bad_checksum",
    "payment_code_like",
    "account_like",
    "contract_like",
    "adt_like",
    "cid_or_number",
    "number",
    "phone_like",
)


def mod97_valid(value: str) -> bool:
    """ISO 7064 check shared by IBAN and RF payment codes."""
    text = value.replace(" ", "").upper()
    text = text[4:] + text[:4]
    digits = "".join(str(int(ch, 36)) for ch in text)
    return int(digits) % 97 == 1


def _label_before(text: str, start: int) -> str | None:
    window = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text[max(0, start - 40) : start])
        if not unicodedata.combining(ch)
    )
    best, position = None, -1
    for name, pattern in LABELS.items():
        for match in re.finditer(pattern, window, flags=re.IGNORECASE):
            if match.start() > position:
                best, position = name, match.start()
    return best


def _hint(digits: str, label: str | None) -> tuple[str, str]:
    """(value, hint). Only an AFM label can change the value: dropped leading zero."""
    size = len(digits)
    if label == "afm":
        if size == 9:
            return digits, "afm" if afm_checksum_valid(digits) else "afm_bad_checksum"
        if size == 8 and afm_checksum_valid("0" + digits):
            return "0" + digits, "afm_padded"
        return digits, "afm_wrong_length"
    if (
        label == "payment"
    ):  # shaped like an account number, so only the label tells them apart
        return digits, "payment_code_like"
    if size == 9 and afm_checksum_valid(digits):
        return digits, "afm"
    if size == 10 and digits[0] in "26":
        return digits, "phone_like"
    if size == 12 and digits.startswith("30"):
        return digits, "phone_like"
    if size in (7, 8):
        return digits, "cid_or_number"
    if size == 13:
        return digits, "account_like"
    return digits, "number"


def _digit_runs(match: re.Match) -> list[tuple[str, int]]:
    """Split runs that are really separate numbers ('2101234567 6912345678')."""
    raw = match.group(0)
    parts = [(p.group(0), p.start()) for p in re.finditer(r"[^ ]+", raw)]
    if any(len(re.sub(r"\D", "", part)) >= 7 for part, _ in parts) and len(parts) > 1:
        return [
            (part, match.start() + offset)
            for part, offset in parts
            if len(re.sub(r"\D", "", part)) >= 7
        ]
    return [(raw, match.start())]


def find_candidates(text: str, source: str) -> list[dict]:
    """Every identifier-like value in one text, with where it was found."""
    if not text:
        return []
    found, taken = [], []

    def add(value: str, hint: str, start: int, end: int, label: str | None) -> None:
        context = " ".join(text[max(0, start - _WINDOW) : end + _WINDOW].split())
        found.append(
            {
                "value": value,
                "hint": hint,
                "label": label,
                "source": source,
                "context": context,
            }
        )
        taken.append((start, end))

    for match in _IBAN.finditer(text):
        value = match.group(0).replace(" ", "")
        if mod97_valid(value):
            add(value, "iban", match.start(), match.end(), "iban")
    for match in _RF.finditer(text):
        value = match.group(0).replace(" ", "")
        hint = "rf" if mod97_valid(value) else "rf_bad_checksum"
        add(value, hint, match.start(), match.end(), "payment")
    plain = "".join(unicodedata.normalize("NFD", ch)[0] for ch in text)  # same length, no accents
    for label in _LABEL_WORD.finditer(plain):
        reach = plain[label.end(): label.end() + _LABEL_REACH].split("\n")[0]
        for token in _TOKEN.finditer(reach):  # the first number after the label that is not a date or an amount
            start, end = label.end() + token.start(1), label.end() + token.end(1)
            raw, core = text[start:end], token.group(2)
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 4 or _DATE.match(core) or _THOUSANDS.match(core):
                continue
            if any(a < end and start < b for a, b in taken) or (len(digits) >= 7 and raw.isdigit()):
                break  # already found, or a plain long number the digit search below gives its own hint
            hint = "account_like" if label.group(0).lower().startswith(("λογαρ", "acc")) else "contract_like"
            # Account numbers are compared digit by digit with the registry; contract numbers keep their slash.
            value = digits if hint == "account_like" and not re.search(r"[A-Za-z]", raw) else re.sub(r"\s", "", raw)
            add(value, hint, start, end, "account" if hint == "account_like" else "contract")
            break
    for match in _ADT.finditer(text):
        start, end = match.span()
        if any(a < end and start < b for a, b in taken):
            continue
        letters = re.sub(r"[ \-]", "", match.group(1) or "")
        label = _label_before(text, start)
        # Two letters + six digits is the ID card's own format; anything shorter is
        # just a number unless a label says otherwise.
        if len(letters) == 2 or label == "adt":
            add(re.sub(r"[ \-]", "", match.group(0)), "adt_like", start, end, label)
    for match in _DIGITS.finditer(text):
        for raw, start in _digit_runs(match):
            end = start + len(raw)
            if any(a < end and start < b for a, b in taken):
                continue
            digits = re.sub(r"\D", "", raw)
            if _DATE.match(raw) or len(digits) > 20:
                continue
            if _THOUSANDS.match(raw) and not (
                len(digits) == 9 and afm_checksum_valid(digits)
            ):
                continue
            label = _label_before(text, start)
            value, hint = _hint(digits, label)
            add(value, hint, start, end, label)
    return found


def merge_candidates(found: list[dict], limit: int = 60) -> tuple[list[dict], int]:
    """One entry per value, keeping up to two sightings; returns (kept, dropped)."""
    by_value: dict[str, dict] = {}
    for item in found:
        entry = by_value.get(item["value"])
        if entry is None:
            by_value[item["value"]] = {
                "value": item["value"],
                "hint": item["hint"],
                "label": item["label"],
                "sightings": [{"source": item["source"], "context": item["context"]}],
            }
            continue
        if entry["label"] is None:
            entry["label"] = item["label"]
        if len(entry["sightings"]) < 2 and item["source"] not in {
            s["source"] for s in entry["sightings"]
        }:
            entry["sightings"].append(
                {"source": item["source"], "context": item["context"]}
            )
    ordered = sorted(
        by_value.values(),
        key=lambda c: (_RANK.index(c["hint"]), c["label"] is None),
    )
    kept = ordered[:limit]
    for index, item in enumerate(kept, 1):
        item["id"] = f"c{index}"
    return kept, len(ordered) - len(kept)
