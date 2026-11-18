"""Excel of the test-set emails and their attachments, each linked to the email in Outlook.

One row per attachment (or one row for an email with none), keyed by `id`, the same id as
in the review export business_review_<name>.csv. The link opens the email, with its
attachments, in Outlook on the web for anyone with access to the mailbox, so the Excel
can be shared on its own.

Outlook links come from Microsoft Graph (read-only, credentials in graphapi/.env) and are
cached in runs/attachments_share/outlook_links.json, so reruns don't query the mailbox.
Our saved Graph ids are per folder, so an email moved since is found by date + subject.

Run:  python evaluation/attachment_links.py   (from AI_email_classifier/)
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import dotenv_values
from openpyxl import Workbook
from openpyxl.styles import Font

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "runs"
OUT = RUNS / "attachments_share"
CACHE = OUT / "outlook_links.json"
ENV = dotenv_values(REPO / "graphapi" / ".env")
API = f"{ENV['GRAPH_API_ENDPOINT'].rstrip('/')}/users/{ENV['USER_ID']}/messages"


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))


def token():
    r = requests.post(
        f"https://login.microsoftonline.com/{ENV['DOVALUEGREECE_ID']}/oauth2/v2.0/token",
        data={"client_id": ENV["CLIENT_ID"], "client_secret": ENV["CLIENT_SECRET"],
              "scope": ENV["SCOPE"], "grant_type": "client_credentials"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get(session, url, params=None):
    for _ in range(5):
        r = session.get(url, params=params, timeout=30)
        if r.status_code not in (429, 503):
            return r
        time.sleep(int(r.headers.get("Retry-After", 5)))
    return r


def outlook_link(session, email):
    """webLink by id; if the email moved folder (new id), by received time + subject."""
    r = get(session, f"{API}/{email['id']}", {"$select": "webLink"})
    if r.ok:
        return r.json()["webLink"], "by id"
    if r.status_code != 404:
        return "", f"error {r.status_code}"
    # Some copies carry a received time a few minutes off the one we saved; take the closest.
    t = datetime.fromisoformat(email["receivedDateTime"].replace("Z", "+00:00"))
    lo, hi = ((t + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ") for m in (-3, 3))
    r = get(session, API, {"$filter": f"receivedDateTime ge {lo} and receivedDateTime le {hi}",
                           "$select": "webLink,subject,receivedDateTime", "$top": 100})
    if not r.ok:
        return "", f"error {r.status_code}"
    hits = [m for m in r.json().get("value", []) if m.get("subject") == email.get("subject")]
    hits.sort(key=lambda m: abs(datetime.fromisoformat(m["receivedDateTime"].replace("Z", "+00:00")) - t))
    return (hits[0]["webLink"], "by date+subject") if hits else ("", "not found in mailbox")


def main():
    emails = load(RUNS / "combined" / "emails.json")
    OUT.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [e for e in emails if not cache.get(e["id"], {}).get("link")]
    if todo:
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {token()}"
        with ThreadPoolExecutor(6) as pool:
            for email, (link, how) in zip(todo, pool.map(lambda e: outlook_link(session, e), todo)):
                cache[email["id"]] = {"link": link, "how": how}
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    wb = Workbook()
    ws = wb.active
    ws.title = "attachments"
    ws.append(["received", "sender", "subject", "attachments", "email in Outlook", "id"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for email in emails:  # one row per email
        sender = ((email.get("from") or {}).get("emailAddress") or {}).get("address", "")
        found = cache[email["id"]]
        names = [a.get("name") or "attachment" for a in email.get("attachments") or []
                 if not a.get("isInline")]  # inline = signatures, logos
        ws.append([email.get("receivedDateTime", "").replace("T", " ").rstrip("Z"), sender,
                   email.get("subject", ""), "\n".join(names) or "—",
                   "Άνοιγμα" if found["link"] else "not found in mailbox", email["id"]])
        for cell in ws[ws.max_row]:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.data_type = "s"  # a name like "=?utf-8?..." is text, not a formula
        if found["link"]:
            ws.cell(ws.max_row, 5).hyperlink = found["link"]
            ws.cell(ws.max_row, 5).style = "Hyperlink"

    for col, width in zip("ABCDEF", (17, 30, 50, 40, 18, 20)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(OUT / "emails_with_links.xlsx")

    counts = {}
    for email in emails:
        how = cache[email["id"]]["how"]
        counts[how] = counts.get(how, 0) + 1
    print(OUT / "emails_with_links.xlsx", "emails:", counts)
    assert not any(c.data_type == "f" for r in ws.iter_rows() for c in r)
    assert ws.max_row - 1 == len(emails)
    assert all(c.hyperlink.target.startswith("https://") for c in ws["E"][1:] if c.hyperlink)


if __name__ == "__main__":
    main()
