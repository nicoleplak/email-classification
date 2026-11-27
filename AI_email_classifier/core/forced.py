"""Categories added by rule, whatever the model answers (inputs/forced_categories.json).

- Board: a member of doValue's management named in the email makes it a "Διοίκηση" email.
- Documents: an attachment of a given type (e.g. an authorization) adds its category (Εξουσιοδοτήσεις).

Names are found by spelling as whole words, Greek case endings and accents ignored (core.banks).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from core.banks import _find, _phrase, _tokens

FILE = Path(__file__).resolve().parents[1] / "inputs" / "forced_categories.json"
_cache: dict[str, Any] = {}


def config() -> dict[str, Any]:
    mtime = FILE.stat().st_mtime if FILE.exists() else 0
    if _cache.get("mtime") != mtime:
        data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
        _cache.update(mtime=mtime, data=data)
    return _cache["data"]


def board_mentions(docs: Iterable[dict[str, Any]], recipients: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Where a board member (name or title) is named: {written, where, snippet}, at most one per text.

    docs: {"text", "where"} (core.understand.documents); recipients: Graph To/Cc entries.
    """
    board = config().get("board") or {}
    phrases = sorted({_phrase(x) for x in [*board.get("names", []), *board.get("titles", [])]} - {()},
                     key=len, reverse=True)
    texts = list(docs)
    for r in recipients:
        address = (r or {}).get("emailAddress") or {}
        line = f"{address.get('name') or ''} {(address.get('address') or '').split('@')[0].replace('.', ' ')}"
        texts.append({"text": line, "where": {"kind": "recipient"}})
    found = []
    for doc in texts:
        tokens = _tokens(doc.get("text") or "")
        for phrase in phrases:
            hit = _find(phrase, tokens)
            if hit:
                text = doc["text"]
                found.append({"written": text[hit[0]:hit[1]], "where": doc.get("where") or {},
                              "snippet": " ".join(text[max(0, hit[0] - 80): hit[1] + 80].split())})
                break
    return found


def board_category() -> str:
    return (config().get("board") or {}).get("category") or "Διοίκηση"


def document_categories(attachments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Categories an attachment's document type brings: {category, file, documentType}, once per category."""
    by_type = config().get("documents") or {}
    out, seen = [], set()
    for a in attachments:
        category = by_type.get(a.get("document_type") or "")
        if category and a.get("relevance") != "irrelevant" and category not in seen:
            seen.add(category)
            out.append({"category": category, "file": a.get("filename"), "documentType": a.get("document_type")})
    return out
