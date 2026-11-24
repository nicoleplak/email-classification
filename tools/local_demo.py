"""Fill a local folder with invented emails, so the classifier and review app run with no Azure at all.

    python tools/local_demo.py                     # 40 invented emails over two weeks, classified, some reviewed
    python tools/local_demo.py --emails 100
    python tools/local_demo.py --no-reviews        # classified, but nobody has reviewed anything yet
    python tools/local_demo.py --unclassified      # leave them waiting, for the real classifier to classify
    python tools/local_demo.py --folder other_dir  # default: local_data/ (git-ignored)

Writes, under <folder>/blob/ (the stand-in for the blob container, LOCAL_BLOB_DIR):
  bronze/import-demo-<UTC>/emails.json        Graph-shaped emails, as the ingest writes them
  messages/demo/<id>/message.eml               each original email, for viewing and download
  attachments/demo/<id>/NN_<name>              each attachment (sha256 recorded, as the ingest does)
  in/qualco_output_<date>.csv                  an invented customer registry for those emails
and registers them as cases in <folder>/case_store/ (LOCAL_STORE_DIR). Without --unclassified, a stand-in
model (no network calls) classifies them through the real run_classifier and understand code, so every
queue and card in the review app has something in it: AUTO, REVIEW, EXCEPTION and not-yet-classified,
customer details, evidence highlights and attachment text. Older emails also get invented reviews (category
kept or changed, actions kept, removed or added), so the Metrics view has numbers in every table.

Then start the review app on the same folders (the script prints the exact command):

    LOCAL_BLOB_DIR=local_data/blob LOCAL_STORE_DIR=local_data/case_store REVIEW_AUTH=dev \\
        python review_app/server.py

Everything here is invented: no client data is read or written. Running it again adds another run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "AI_email_classifier"

SENDERS = [("Μαρία Παπαδοπούλου", "maria.p@example.com"), ("Γιώργος Νικολάου", "g.nikolaou@example.org"),
           ("Ελένη Κωνσταντίνου", "eleni.k@example.net"), ("Δημήτρης Αλεξίου", "d.alexiou@example.com")]
REQUESTS = [
    ("Βεβαίωση οφειλής", "Παρακαλώ να μου στείλετε βεβαίωση οφειλής για το δάνειό μου."),
    ("Αντίγραφο σύμβασης", "Θα ήθελα αντίγραφο της σύμβασης δανείου που έχω υπογράψει."),
    ("Αλλαγή διεύθυνσης", "Σας επισυνάπτω υπεύθυνη δήλωση για την αλλαγή της διεύθυνσής μου."),
    ("Ρύθμιση οφειλής", "Επιθυμώ να συζητήσουμε ρύθμιση της οφειλής μου σε δόσεις."),
    ("Παράπονο", "Είμαι πολύ δυσαρεστημένος με την εξυπηρέτηση που έλαβα την προηγούμενη εβδομάδα."),
    ("Ερώτηση", "Μπορείτε να μου πείτε ποιο είναι το υπόλοιπο του λογαριασμού μου;"),
]


def invented_afm(n: int) -> str:
    """A 9-digit number that passes the Greek tax ID check digit; it belongs to no real person."""
    head = f"{90000000 + n * 104729:08d}"[-8:]
    check = sum(int(head[i]) * 2 ** (8 - i) for i in range(8)) % 11 % 10
    return head + str(check)


def plain_upper(name: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", name.upper()) if not unicodedata.combining(c))


def demo_accounts(n: int) -> list[tuple[str, str]]:
    """(account, SPV) of invented customer n: every third has one account, the rest three in two SPVs."""
    count = 1 if n % 3 == 1 else 3
    return [(f"{9000000000000 + n * 10 + k}", ("SPV Alpha", "SPV Beta")[k % 2]) for k in range(count)]


def registry_csv(count: int) -> bytes:
    """Registry rows (qualco_output columns) for the invented customers; every 4th tax ID is left out, so
    some cases show "tax ID not found in the customer registry"."""
    header = ["TAX_ID_NO", "NAME", "SOURCE", "CST_STS_NM", "CST_UNQ_CD", "PRTFL_CD", "PRTFL_NM",
              "ACC_UNQ_CD", "SRV_ACC_UNQ_CD", "ACC_ID", "PORTAL_FLAG", "IDV_ORG_IND"]
    rows = [";".join(header)]
    for n in range(count):
        if n % 4 == 3:
            continue
        last, first = reversed(SENDERS[n % len(SENDERS)][0].split())
        for account, spv in demo_accounts(n):
            rows.append(";".join([invented_afm(n), plain_upper(f"{last} {first}"), "Datamart" if n % 10 == 5 else "Qualco",
                                  "Ν.3869" if n % 6 == 0 else "Active", f"DEMO{n:04d}", spv[-4:].upper(), spv,
                                  account, "", "", "Y" if n % 2 else "N", "I"]))
    return ("\n".join(rows) + "\n").encode("utf-8")


def tiny_pdf(text: str) -> bytes:
    """A valid one-page PDF with one line of (ASCII) text."""
    stream = f"BT /F1 14 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               b"/Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def invented_email(n: int, now: datetime, upload, hours_ago: float | None = None) -> dict:
    name, address = SENDERS[n % len(SENDERS)]
    subject, ask = REQUESTS[n % len(REQUESTS)]
    afm = invented_afm(n)
    received = now - timedelta(hours=n * 8.5 + 1 if hours_ago is None else hours_ago, minutes=n * 7)
    key = f"demo-{hashlib.sha256(f'{now.isoformat()}-{n}'.encode()).hexdigest()[:16]}"
    extra = ""
    if n % 5 == 2:
        extra = f"\nΛογαριασμός: {demo_accounts(n)[-1][0]}"
    elif n % 7 == 3:
        extra = "\nΤο αίτημα αφορά όλες τις οφειλές μου."
    text = f"Καλημέρα σας,\n\n{ask}\nΑΦΜ: {afm}{extra}\n\nΕυχαριστώ,\n{name}"
    html = "<p>" + "</p><p>".join(line or "&nbsp;" for line in text.split("\n")) + "</p>"

    files = []
    if n % 2 == 0:
        files.append(("aitisi.pdf", "application/pdf", tiny_pdf(f"Request {n}: invented document, tax ID {afm}")))
    if n % 3 == 0:
        files.append(("simeiosi.txt", "text/plain", f"Σημείωση πελάτη {n}: {ask}\nΑΦΜ {afm}\n".encode("utf-8")))
    attachments = []
    for number, (file_name, content_type, data) in enumerate(files, 1):
        blob_name = f"attachments/demo/{key}/{number:02d}_{file_name}"
        upload(blob_name, data)
        attachments.append({
            "id": f"{key}-a{number}", "conversationId": key, "messageId": key, "name": file_name,
            "contentType": content_type, "size": len(data), "isInline": False, "contentId": None,
            "sha256": hashlib.sha256(data).hexdigest(), "decoded_size": len(data), "blob_name": blob_name,
            "status": "SAVED", "warnings": [],
        })

    eml = EmailMessage()
    eml["From"], eml["To"], eml["Subject"] = f"{name} <{address}>", "info@example.test", subject
    eml["Date"], eml["Message-ID"] = format_datetime(received), f"<{key}@demo.example.test>"
    eml.set_content(text)
    eml.add_alternative(html, subtype="html")
    for file_name, content_type, data in files:
        main, sub = content_type.split("/")
        eml.add_attachment(data, maintype=main, subtype=sub, filename=file_name)
    eml_blob = f"messages/demo/{key}/message.eml"
    upload(eml_blob, eml.as_bytes())

    stamp = received.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": key, "internetMessageId": f"<{key}@demo.example.test>", "conversationId": key,
        "subject": subject, "from": {"emailAddress": {"name": name, "address": address}},
        "toRecipients": [{"emailAddress": {"name": "Info", "address": "info@example.test"}},
                         *([{"emailAddress": {"name": "Νομικό τμήμα", "address": "legal@example.test"}}] if n % 4 == 1 else [])],
        "ccRecipients": [{"emailAddress": {"name": "Δικηγόρος πελάτη", "address": "lawyer@example.org"}},
                         {"emailAddress": {"name": "", "address": f"family{n}@example.net"}}] if n % 3 == 0 else [],
        "receivedDateTime": stamp, "sentDateTime": stamp, "hasAttachments": bool(attachments),
        "body": {"contentType": "html", "content": html}, "body_clean": text,
        "conversation_thread": [], "reply_to_message_id": key, "attachments": attachments,
        "attachment_fetch_attempted": bool(attachments), "attachment_fetch_succeeded": True,
        "attachment_download_errors": [], "msg_blob_path": None, "eml_blob_path": eml_blob, "source": "demo",
    }


@dataclass
class TextConfig:
    """What run_classifier needs from an attachment reader to collect its text into silver."""

    save_extracted_text_debug: bool = True
    extracted_text_debug_directory: str = ""


class FakeProcessor:
    """Stands in for the classifier: a fixed category and certainty per email, never a network call.

    Like the real attachment reader, it writes each attachment's text (plus a sidecar with the file name)
    to the folder run_classifier gives it, so the review app has text views and highlights to show.
    """

    def __init__(self, categories: list[str], blob):
        self.categories = categories
        self.blob = blob
        self.seen = 0
        self.attachment_processor = SimpleNamespace(config=TextConfig())

    def _save_texts(self, email: dict) -> list[dict]:
        folder = Path(self.attachment_processor.config.extracted_text_debug_directory)
        records = []
        for number, item in enumerate(email.get("attachments") or [], 1):
            data = self.blob.download(item["blob_name"])
            if item["name"].endswith(".pdf"):  # what OCR would read off the invented page
                text = data.split(b"(", 1)[1].split(b")", 1)[0].decode("ascii")
            else:
                text = data.decode("utf-8")
            stem = f"{Path(item['name']).stem}_{number}"
            (folder / f"{stem}.txt").write_text(text, encoding="utf-8")
            (folder / f"{stem}.json").write_text(json.dumps({"filename": item["name"]}), encoding="utf-8")
            records.append({"filename": item["name"], "status": "ANALYZED", "relevance": "relevant",
                            "evidence_phrases": [text.splitlines()[0][:60]]})
        return records

    def process_batch(self, emails, export, use_thread_context):
        (email,) = emails
        n, self.seen = self.seen, self.seen + 1
        if n % 7 == 5:
            raise RuntimeError("invented model failure, to show an EXCEPTION case")
        category = self.categories[n % len(self.categories)]
        confidence = (0.97, 0.93, 0.74, 0.61)[n % 4]
        runner_up = self.categories[(n + 1) % len(self.categories)]
        return [{
            "category": category, "confidence": f"{confidence:.0%}",
            "status": "needs_identification" if n % 5 == 4 else "verified",
            "model_votes": {category: confidence, runner_up: round(1 - confidence, 2)},
            "reasoning": "Invented classification from tools/local_demo.py (no model was called).",
            "attachment_records": self._save_texts(email),
        }]


class FakeModel:
    """Answers core.understand's one structured call from the email itself: the tax IDs it found are the
    debtor's, the sender is the customer, and the request sentence is the category evidence."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        from core.action_rules import FLAGS

        user = json.loads(kwargs["messages"][1]["content"])
        lines = [line.strip() for line in user["body"].splitlines() if len(line.strip()) > 20]
        sender = user["sender"]["name"] or ""
        answer = {
            "analysis": "Invented reading from tools/local_demo.py (no model was called).",
            "candidates": [
                {"id": c["id"], "field": "afm" if c["hint"].startswith("afm") else "account" if c["hint"] == "account_like"
                 else "other", "role": "debtor", "identifies_case": c["hint"].startswith("afm") or c["hint"] == "account_like",
                 "certainty": "high"}
                for c in user["candidates"]
            ],
            "people": [{"name": sender, "registry_form": plain_upper(" ".join(reversed(sender.split()))),
                        "role": "debtor", "is_principal": True, "evidence": sender, "source": "body"}]
            if sender else [],
            "flags": {k: (k == "asks_debt_certificate" and "βεβαίωση" in user["body"].lower())
                      or (k == "all_debts" and "όλες τις οφειλές" in user["body"]) for k in FLAGS},
            "other_requests": [],
            "evidence": [{"quote": lines[0], "supports": "category", "flag": "", "source": "body"}] if lines else [],
        }
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))])


def invented_reviews(store, categories: list[str], now: datetime) -> int:
    """Review most classified emails older than two days, the way people would: the category is usually
    kept, sometimes changed or found not to fit; proposed actions are usually kept, sometimes one is
    removed or a manual one added. Written like review_app/server.py save_review, with an audit entry."""
    import uuid

    reviewers = [{"id": "dev-demo-a", "name": "Demo reviewer A", "email": "reviewer.a@example.test"},
                 {"id": "dev-demo-b", "name": "Demo reviewer B", "email": "reviewer.b@example.test"}]
    cutoff = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases = sorted((c for c in store.find("cases", "status", "CLASSIFIED") if (c.get("receivedAt") or "") < cutoff),
                   key=lambda c: c["receivedAt"])
    done = 0
    for i, case in enumerate(cases):
        if i % 10 >= 8:
            continue  # some stay in the queue
        model = case.get("modelCategory")
        no_match = bool(model) and int(case["id"][-8:], 16) % 9 == 4
        # The id ends in 8 hex digits of a hash: a fair, repeatable "coin" independent of the order above.
        coin = int(case["id"][-8:], 16)
        if not model or (case.get("route") != "AUTO" and coin % 4 == 1):
            final = categories[(i * 3) % len(categories)]  # the reviewer picked another category
        else:
            final = model
        proposed = (case.get("understanding") or {}).get("actions") or []
        kept = proposed[:-1] if proposed and i % 3 == 0 else proposed
        actions = [{"do": a["do"], "category": a.get("category"), "codes": a.get("codes") or [], "open": a.get("open"),
                    "closed": a.get("closed"), "to": [a["to"]] if isinstance(a.get("to"), str) else a.get("to") or [],
                    "source": "suggested"} for a in kept]
        if i % 5 == 2:
            actions.append({"do": "manual", "category": final, "codes": [], "open": None, "closed": None, "to": [],
                            "source": "added"})
        reviewer = reviewers[i % 2]
        received = datetime.fromisoformat(case["receivedAt"].replace("Z", "+00:00"))
        at = min(received + timedelta(hours=2 + (i * 7) % 30), now).strftime("%Y-%m-%dT%H:%M:%SZ")
        fields = ("status", "finalCategory", "otherCategories", "finalActions", "reviewComment")
        before = {k: case.get(k) for k in fields}
        saved = store.replace("cases", {**case, "status": "REVIEWED", "finalCategory": "No Match Found" if no_match else final,
                                        "noMatch": no_match, "otherCategories": [], "finalActions": actions,
                                        "reviewComment": "", "reviewedBy": reviewer, "reviewedAt": at, "updatedAt": at})
        store.create("audit", {"id": uuid.uuid4().hex, "caseId": case["id"], "at": at, "by": reviewer["id"],
                               "byName": reviewer["name"], "action": "reviewed", "before": before,
                               "after": {k: saved.get(k) for k in fields}})
        done += 1
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", default=str(ROOT / "local_data"), help="default: local_data/ in the repo")
    parser.add_argument("--emails", type=int, default=40)
    parser.add_argument("--no-reviews", action="store_true", help="classify, but add no invented reviews")
    parser.add_argument("--unclassified", action="store_true", help="register only; classify later")
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    os.environ.setdefault("LOCAL_BLOB_DIR", str(folder / "blob"))
    os.environ.setdefault("LOCAL_STORE_DIR", str(folder / "case_store"))
    os.environ["CASE_STORE"] = "local"  # never Cosmos, even if the shell has it set
    os.environ["CI"] = "1"  # settings.py: skip .env (no keys needed) and folder creation in the cwd
    sys.path.insert(0, str(APP))

    from core import run_classifier as rc
    from data import blob_output
    from data.case_store import open_store

    blob_dir, store_dir = os.environ["LOCAL_BLOB_DIR"], os.environ["LOCAL_STORE_DIR"]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    # Two extra emails go in a second run that is registered but not classified, so the "not classified
    # yet" queue has something in it too (with --unclassified, everything waits).
    waiting_count = 0 if args.unclassified else 2
    total = args.emails + waiting_count
    registry_blob = f"in/qualco_output_{now:%Y%m%d}.csv"
    blob_output.upload_bytes(registry_blob, registry_csv(total))

    def write_run(run: str, numbers: range, hours_ago: float | None = None) -> int:
        messages = [invented_email(n, now, blob_output.upload_bytes, hours_ago) for n in numbers]
        blob_output.upload_bytes(f"bronze/{run}/emails.json", json.dumps(
            {"messages": messages, "removed": []}, ensure_ascii=False, indent=1).encode("utf-8"))
        return len(messages)

    store = open_store()
    run = f"import-demo-{stamp}"
    count = write_run(run, range(args.emails))
    registered = rc.register_runs(store, blob_output, rc.utcnow())
    print(f"Wrote {count} invented emails as bronze/{run}/emails.json; {registered['new_cases']} new cases")
    if not args.unclassified:
        categories = [c["Categories"].strip() for c in json.loads(
            (APP / "inputs" / "categories.json").read_text(encoding="utf-8"))]
        from core.customer_lookup import Registry, RequestHistory
        from core.understand import understand
        from data.loader import DataLoader

        registry_file = Path(blob_dir) / registry_blob
        registry = Registry(DataLoader.load_registry_df(str(registry_file)), registry_blob)

        def understand_factory(_processor, _messages):
            def read(message, records, text_dir):
                return understand(client=FakeModel(), model="demo", message=message, records=records,
                                  text_dir=text_dir, categories=categories, registry=registry,
                                  history=RequestHistory.empty())
            return read

        processor = FakeProcessor(categories, blob_output)
        totals = rc.classify_waiting(store, blob_output, lambda: processor, rc.utcnow, threshold=0.90,
                                     understand_factory=understand_factory)
        print("Fake classification:", {k: v for k, v in totals.items() if v})
        later = f"import-demo-{stamp}-waiting"
        write_run(later, range(args.emails, total), hours_ago=0.5)
        rc.register_runs(store, blob_output, rc.utcnow())
        print(f"Wrote {waiting_count} more as bronze/{later}/emails.json, left waiting for the classifier")
        if not args.no_reviews:
            print(f"Invented reviews: {invented_reviews(store, categories, now)}")

    print("\nStart the review app on these folders (http://127.0.0.1:8765):\n")
    print(f'  LOCAL_BLOB_DIR="{blob_dir}" LOCAL_STORE_DIR="{store_dir}" REVIEW_AUTH=dev python review_app/server.py')
    print("\nPowerShell:\n")
    print(f'  $env:LOCAL_BLOB_DIR="{blob_dir}"; $env:LOCAL_STORE_DIR="{store_dir}"; $env:REVIEW_AUTH="dev"')
    print("  python review_app/server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
