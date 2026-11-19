"""Readable copy of a .eml for people without a mail client that opens .eml files.

A .eml is the raw message (MIME): Greek text and attachments are base64 or
quoted-printable encoded, so Notepad or a browser shows gibberish. This writes,
next to each <name>.eml:
  <name>.html            headers + the body as sent (open in any browser, print to PDF)
  <name>_files/...       the attachments, linked from the page

Stdlib only. Usage:  python tools/eml_to_html.py <file.eml or folder> [...]
"""

import base64
import html
import re
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

# The page holds untrusted mail HTML: no scripts, no remote loads (tracking pixels).
CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(name).name).strip(" .") or "attachment"


def render(raw: bytes, files_dir: str = "") -> tuple[str, list[tuple[str, bytes]]]:
    """Return (html page, [(file name, bytes)]). Links point at files_dir/<name>."""
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    inline = {}  # Content-ID -> data: URI, so cid: images show in the body
    for part in msg.walk():
        cid = (part["Content-ID"] or "").strip().strip("<>")
        if cid and part.get_content_maintype() == "image":
            data = part.get_payload(decode=True) or b""
            inline[cid] = f"data:{part.get_content_type()};base64,{base64.b64encode(data).decode()}"

    files, used = [], set()
    for part in msg.iter_attachments():
        if part.get_content_type() == "message/rfc822":  # attached email: keep it as .eml
            data = part.get_content().as_bytes(policy=policy.default)
            name = part.get_filename() or "attached email.eml"
        else:
            data = part.get_payload(decode=True) or b""
            name = part.get_filename() or "attachment"
        name = _safe_name(name)
        stem, n = name, 1
        while name.lower() in used:
            n += 1
            name = f"{Path(stem).stem} ({n}){Path(stem).suffix}"
        used.add(name.lower())
        files.append((name, data))

    body = msg.get_body(("html", "plain"))
    if body is None:
        content = "<p><i>(no body)</i></p>"
    elif body.get_content_subtype() == "html":
        content = re.sub(
            r"cid:([^\"'\s)>]+)", lambda m: inline.get(m.group(1), m.group(0)), body.get_content()
        )
    else:
        content = f"<pre style='white-space:pre-wrap;font:inherit'>{html.escape(body.get_content())}</pre>"

    rows = "".join(
        f"<tr><th>{k}</th><td>{html.escape(str(msg[k]))}</td></tr>"
        for k in ("From", "To", "Cc", "Date", "Subject")
        if msg[k]
    )
    if files:
        links = ", ".join(
            f"<a href='{html.escape(files_dir + '/' + n, quote=True)}'>{html.escape(n)}</a>"
            if files_dir else html.escape(n)
            for n, _ in files
        )
        rows += f"<tr><th>Attachments</th><td>{links}</td></tr>"

    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta http-equiv='Content-Security-Policy' content=\"{CSP}\">"
        f"<title>{html.escape(str(msg['Subject'] or 'email'))}</title>"
        "<style>.eml-h{font:14px Segoe UI,Arial,sans-serif;border-collapse:collapse;margin:0 0 16px;"
        "width:100%;background:#f3f5f7}.eml-h th{text-align:left;padding:4px 12px;width:110px;"
        "vertical-align:top}.eml-h td{padding:4px 12px}</style></head><body>"
        f"<table class='eml-h'>{rows}</table><hr>{content}</body></html>"
    )
    return page, files


def convert(eml: Path) -> Path:
    files_dir = f"{eml.stem}_files"
    page, files = render(eml.read_bytes(), files_dir)
    for name, data in files:
        out = eml.with_name(files_dir) / name
        out.parent.mkdir(exist_ok=True)
        out.write_bytes(data)
    target = eml.with_suffix(".html")
    target.write_text(page, encoding="utf-8")
    return target


def _demo() -> None:
    raw = (
        "From: a@x.gr\r\nTo: b@y.gr\r\nSubject: =?utf-8?b?zrXOu867zrfOvc65zrrOrA==?=\r\n"
        "MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n"
        "--B\r\nContent-Type: multipart/related; boundary=R\r\n\r\n"
        "--R\r\nContent-Type: text/html; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
        + base64.b64encode("<p>Καλησπέρα</p><img src='cid:logo@1'><script>x()</script>".encode()).decode()
        + "\r\n--R\r\nContent-Type: image/png\r\nContent-ID: <logo@1>\r\nContent-Transfer-Encoding: base64\r\n\r\n"
        "iVBORw0KGgo=\r\n--R--\r\n"
        "--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"../a.pdf\"\r\n"
        "Content-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n"
        "--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"a.pdf\"\r\n"
        "Content-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n--B--\r\n"
    ).encode()
    page, files = render(raw, "m_files")
    assert "Καλησπέρα" in page and "ελληνικά" in page, "Greek body and subject decoded"
    assert "data:image/png;base64," in page and "cid:" not in page, "inline image embedded"
    assert "Content-Security-Policy" in page, "scripts blocked by CSP"
    assert [n for n, _ in files] == ["a.pdf", "a (2).pdf"], files  # no path escape, no overwrite
    assert files[0][1] == b"%PDF"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] in ([], ["--test"]):
        sys.exit(_demo())
    for arg in sys.argv[1:]:
        p = Path(arg)
        for eml in sorted(p.rglob("*.eml")) if p.is_dir() else [p]:
            print(convert(eml))
