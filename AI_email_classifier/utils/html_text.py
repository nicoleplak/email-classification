"""Readable plain text from an HTML email, keeping paragraphs and table rows."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP = {"head", "title", "style", "script"}
_BLOCK = {
    "address",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "table",
    "tr",
    "ul",
}
_CELL = {"td", "th"}
_ESCAPED_TAG = re.compile(
    r"<\s*/?\s*(?:html|head|body|div|p|br|table|tr|td|th|span|font|style|meta)\b[^<>]*>",
    re.IGNORECASE,
)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag in _SKIP:
            self.skipping += 1
        elif tag in _BLOCK:
            self.parts.append("\n")
        elif tag in _CELL:
            self.parts.append(" | ")

    def handle_endtag(self, tag) -> None:
        if tag in _SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if not self.skipping:
            # Decoding &lt;p&gt; yields a literal tag; it means nothing to a reader.
            self.parts.append(re.sub(r"\s+", " ", _ESCAPED_TAG.sub(" ", data)))


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html or "")
    parser.close()
    lines = []
    for line in "".join(parser.parts).split("\n"):
        line = re.sub(r"(?:\s*\|\s*)+", " | ", line).strip(" |")
        lines.append(re.sub(r" +", " ", line))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
