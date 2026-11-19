"""Mark evidence in an email body (HTML) or an attachment's OCR text, colour-coded by what it supports.

kind: "class"  why the email is in its category (blue)
      "action" why an action applies (purple)
      "id"     customer details found and looked up in the registry / past Qualco requests (green)

Only text is wrapped: tags and attributes pass through untouched, and everything inserted is escaped, so
neither the (untrusted) mail nor the model's quotes can add markup. Terms are search strings, nothing more.
"""

from __future__ import annotations

import html
import re

STYLE = (
    "mark.hl{border-radius:3px;padding:0 2px;color:inherit}"
    "mark.hl-class{background:#d6e9f8;box-shadow:inset 0 -2px #007cba}"
    "mark.hl-action{background:#ece4fb;box-shadow:inset 0 -2px #6941c6}"
    "mark.hl-id{background:#d9f2e3;box-shadow:inset 0 -2px #1e7b4b}"
)
PRIORITY = {"id": 0, "action": 1, "class": 2}  # where marks overlap: a customer detail beats a quote
TAG = re.compile(r"(<!--.*?-->|<[^>]*>)", re.S)
SKIP_OPEN = ("<script", "<style", "<title", "<head")
SKIP_CLOSE = ("</script", "</style", "</title", "</head")


def _pattern(term: str) -> re.Pattern | None:
    term = " ".join(str(term or "").split())
    if re.fullmatch(r"[\d\s.\-/]+", term):
        digits = re.sub(r"\D", "", term)
        if len(digits) < 5:  # short numbers would light up everywhere
            return None
        # "094014298" also matches "094 014 298" and "094.014.298"
        return re.compile(r"(?<!\d)" + r"[\s.\-/]?".join(map(re.escape, digits)) + r"(?!\d)")
    if len(term) < 4:
        return None
    return re.compile(r"\s+".join(map(re.escape, term.split())), re.IGNORECASE)


def mark_text(text: str, terms: list[tuple[str, str, str]]) -> str:
    """``text`` escaped for HTML, with every term wrapped in a <mark>.

    Overlaps are settled per character (customer detail > action > category), so a quote stays marked
    around a tax ID inside it rather than one of them vanishing.
    """
    best: list[tuple[str, str] | None] = [None] * len(text)
    for term, kind, title in terms:
        pattern = _pattern(term)
        if not pattern:
            continue
        for match in pattern.finditer(text):
            for i in range(match.start(), match.end()):
                if best[i] is None or PRIORITY.get(kind, 9) < PRIORITY.get(best[i][0], 9):
                    best[i] = (kind, title)
    out, start = [], 0
    for i in range(1, len(text) + 1):
        if i < len(text) and best[i] == best[start]:
            continue
        piece = html.escape(text[start:i], quote=False)
        if best[start] is None:
            out.append(piece)
        else:
            kind, title = best[start]
            out.append(f'<mark class="hl hl-{kind}" title="{html.escape(title)}">{piece}</mark>')
        start = i
    return "".join(out)


def mark_html(markup: str, terms: list[tuple[str, str, str]]) -> str:
    """Mark terms in the text between tags of an HTML document; script/style/title/head are left alone."""
    out, skip = [], False
    for part in TAG.split(markup or ""):
        if part.startswith("<"):
            low = part[:8].lower()
            if low.startswith(SKIP_OPEN):
                skip = True
            elif low.startswith(SKIP_CLOSE):
                skip = False
            out.append(part)
        elif skip or not part.strip():
            out.append(part)
        else:
            out.append(mark_text(html.unescape(part), terms))
    return "".join(out)


PAGE_BREAK = "<!-- PageBreak -->"


def _plain(markdown: str) -> str:
    """Document Intelligence markdown -> readable text: tables as rows, comments and tags dropped."""
    text = re.sub(r"<!--.*?-->", "", markdown, flags=re.S)
    text = re.sub(r"</t[dh]>", " | ", text, flags=re.I)
    text = re.sub(r"</tr>|<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()


def text_page(markdown: str, terms: list[tuple[str, str, str]], title: str, page_label: str) -> str:
    """The attachment's text, one section per page (anchors #p1, #p2 …), with the evidence marked."""
    pages = markdown.split(PAGE_BREAK)
    body = "".join(
        f'<section id="p{n}"><h2>{html.escape(page_label.format(n=n))}</h2><pre>{mark_text(_plain(page), terms)}</pre></section>'
        for n, page in enumerate(pages, 1)
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{STYLE}"
        "body{font:14px/1.6 'Segoe UI',Arial,sans-serif;color:#1d2733;margin:0;background:#f0f3f7}"
        "section{background:#fff;margin:12px;padding:12px 16px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.08)}"
        "h2{font-size:12px;color:#6b7785;margin:0 0 6px;text-transform:uppercase;letter-spacing:.05em}"
        "pre{white-space:pre-wrap;font:inherit;margin:0}</style></head>"
        f"<body>{body}</body></html>"
    )
