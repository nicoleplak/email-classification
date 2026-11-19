"""Split an email body into the messages of its chain, for display only.

Replies and forwards carry older messages inside the body, marked by an Outlook
header block, an "On ... wrote:" line or an "Original message" rule. The classifier
keeps reading the whole body; only the review app shows the parts apart.
"""

from __future__ import annotations

import re

_LABEL = {
    "from": "who",
    "από": "who",
    "sent": "when",
    "date": "when",
    "απεστάλη": "when",
    "στάλθηκε": "when",
    "αποστολή": "when",
    "ημερομηνία": "when",
    "subject": "subject",
    "θέμα": "subject",
    "to": None,
    "προς": None,
    "cc": None,
    "κοιν": None,
    "κοιν/ση": None,
}
_HEADER = re.compile(r"^\s*[*_]*([^\W\d_/]+(?:/[^\W\d_]+)?)\s*:[*_]*\s*(.*)$")
_WROTE = re.compile(r"^\s*(?:On|Στις|Στη|Την)\s.{5,160}(?:wrote|έγραψε)\s*:?\s*$", re.I)
_RULE = re.compile(
    r"^\s*-{2,}\s*(?:Original Message|Forwarded message|Αρχικό μήνυμα|Προωθημένο μήνυμα)\s*-*\s*$",
    re.I,
)
_LINE_RULE = re.compile(r"^\s*[_-]{10,}\s*$")
_QUOTE_PREFIX = re.compile(r"^(?:\s*>)+ ?")
_MAILTO = re.compile(r"\s*[\[<]mailto:[^\]>]*[\]>]", re.I)
_HEADER_REACH = (
    6  # lines to look ahead: a lone "From:" in a customer's text is not a header
)


def _field(line: str) -> str | None:
    """The header field a line holds ('who', 'when', 'subject', 'other'), or None."""
    match = _HEADER.match(line)
    if not match or match[1].lower() not in _LABEL:
        return None
    return _LABEL[match[1].lower()] or "other"


def _value(line: str) -> str:
    return _MAILTO.sub("", _HEADER.match(line)[2]).strip()


def _starts_header(lines: list[str], index: int) -> bool:
    if _field(lines[index]) != "who":
        return False
    following = (_field(line) for line in lines[index + 1 : index + _HEADER_REACH])
    return any(field in ("when", "subject", "other") for field in following)


def split_chain(text: str | None) -> list[dict[str, str]]:
    """Messages newest first: [{who, when, subject, body}]. The first has no header of its own."""
    lines = [_QUOTE_PREFIX.sub("", line) for line in (text or "").split("\n")]
    parts = [{"who": "", "when": "", "subject": "", "lines": []}]
    index = 0
    while index < len(lines):
        line = lines[index]
        if _RULE.match(line):
            parts.append({"who": "", "when": "", "subject": "", "lines": []})
            index += 1
        elif _starts_header(lines, index):
            part = {"who": "", "when": "", "subject": "", "lines": []}
            while index < len(lines) and (
                _field(lines[index]) or not lines[index].strip()
            ):
                field = _field(lines[index])
                # A second From: starts the next message, even with no text between them.
                if field == "who" and part["who"]:
                    break
                if field and field != "other" and not part[field]:
                    part[field] = _value(lines[index])
                index += 1
            # An "Original message" rule just before the block belongs to this header.
            if parts[-1]["lines"] or parts[-1]["who"] or len(parts) == 1:
                parts.append(part)
            else:
                parts[-1] = part
        elif _WROTE.match(line):
            parts.append(
                {
                    "who": line.strip().rstrip(":").strip(),
                    "when": "",
                    "subject": "",
                    "lines": [],
                }
            )
            index += 1
        else:
            parts[-1]["lines"].append(line)
            index += 1
    messages = []
    for part in parts:
        body = part.pop("lines")
        while body and (not body[-1].strip() or _LINE_RULE.match(body[-1])):
            body.pop()
        part["body"] = "\n".join(body).strip("\n")
        if part["body"]:
            messages.append(part)
    return messages or [{"who": "", "when": "", "subject": "", "body": ""}]


def message_key(body: str) -> str:
    """Same text at the start, whitespace aside: the same message seen twice in a thread."""
    return " ".join(body.split())[:200]
