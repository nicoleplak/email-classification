"""Where do the details in attachments get lost? A check over emails already classified, without model calls.

For each email it answers, step by step:
  1. attachments   how many the email has (bronze run file)
  2. read          how many have OCR text saved in silver (Document Intelligence read them)
  3. in text       tax IDs / accounts / contract numbers the pattern search finds in that text today
  4. on the case   what the case shows in «Στοιχεία που βρέθηκαν», from attachments and from the email
and why, when the reading step failed. Reads LOCAL_STORE_DIR and LOCAL_BLOB_DIR from .env, like the review app.

    python tools/check_extraction.py               # every classified email, newest first, plus totals
    python tools/check_extraction.py --limit 20
    python tools/check_extraction.py --case 20261116T183529Z_c4ea6bd8   # one email in detail
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "AI_email_classifier"
sys.path.insert(0, str(APP))

if os.getenv("CI", "").strip().lower() not in {"1", "true", "yes"}:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass

KINDS = {"afm": "ΑΦΜ", "account": "Λογαριασμός", "contract": "Σύμβαση", "payment_code": "Κωδ. πληρωμής", "iban": "IBAN"}
PATTERN_KIND = {"afm": "afm", "afm_padded": "afm", "afm_bad_checksum": "afm?", "account_like": "account",
                "contract_like": "contract", "iban": "iban", "rf": "payment_code", "payment_code_like": "payment_code"}


def texts_of(blob, case: dict) -> dict[str, str]:
    silver = (case.get("sourceRefs") or {}).get("silver")
    if not silver:
        return {}
    out = {}
    names = blob.list_names(silver + "text/")
    for name in names:
        if not name.endswith(".txt"):
            continue
        sidecar = name[:-4] + ".json"
        label = json.loads(blob.download(sidecar)).get("filename") if sidecar in names else Path(name).name
        out[label] = blob.download(name).decode("utf-8", "replace")
    return out


def check(case: dict, blob, run_message) -> dict:
    from core.identifiers import find_candidates

    message = run_message(case) or {}
    attachments = [a for a in message.get("attachments") or [] if a.get("blob_name") and not a.get("isInline")]
    texts = texts_of(blob, case)
    in_text = Counter()
    for name, text in texts.items():
        for c in find_candidates(text, name):
            kind = PATTERN_KIND.get(c["hint"]) or (c["label"] if c["label"] in ("account", "contract") else None)
            if kind:
                in_text[kind] += 1
    u = case.get("understanding") or {}
    on_case = Counter()
    for e in u.get("extracted") or []:
        if e.get("type") in KINDS:
            where = "att" if any((s or {}).get("kind") == "attachment" for s in e.get("sources") or []) else "email"
            on_case[(e["type"], where)] += 1
    records = (case.get("payload") or {}).get("records") or [{}]
    failed = [f"{r.get('filename')}: {r.get('status')}" for r in records[0].get("attachment_records") or []
              if r.get("status") not in (None, "ANALYZED")]
    return {"id": case["id"], "attachments": len(attachments), "read": len(texts), "in_text": in_text, "on_case": on_case,
            "error": u.get("error"), "failed": failed, "texts": texts, "names": [a.get("name") for a in attachments],
            "extracted": u.get("extracted") or []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="only the newest N emails")
    parser.add_argument("--case", help="one email, in detail")
    args = parser.parse_args()

    from data import blob_output as blob
    from data.case_store import open_store
    from core.run_classifier import email_id, unwrap_run

    store = open_store()
    runs: dict[str, dict] = {}

    def run_message(case: dict) -> dict | None:
        name = case["sourceRefs"]["runFile"]
        if name not in runs:
            messages, _ = unwrap_run(json.loads(blob.download(name)))
            runs[name] = {email_id(m): m for m in messages}
        return runs[name].get(case["id"])

    if args.case:
        case = store.get("cases", args.case)
        if not case:
            print(f"No email {args.case} in {os.getenv('LOCAL_STORE_DIR', 'case_store')}")
            return 1
        r = check(case, blob, run_message)
        print(f"Email {r['id']}: {r['attachments']} attachment(s), OCR text for {r['read']}")
        for name in r["names"]:
            print(f"  - {name}: {'text saved' if name in r['texts'] else 'NO TEXT'}")
        for line in r["failed"]:
            print(f"  ! not read: {line}")
        if r["error"]:
            print(f"  ! the customer-details step failed: {r['error']}")
        from core.identifiers import find_candidates

        for name, text in r["texts"].items():
            found = [(c["value"], c["hint"], c["label"]) for c in find_candidates(text, name)]
            print(f"\n  Pattern search in {name} ({len(text)} characters): {len(found)} value(s)")
            for value, hint, label in found[:40]:
                print(f"    {value:<26} {hint:<18} {label or ''}")
        print(f"\n  On the case («Στοιχεία που βρέθηκαν»): {len(r['extracted'])}")
        for e in r["extracted"]:
            where = ", ".join(s.get("file") or s.get("kind") or "" for s in e.get("sources") or [])
            print(f"    {e.get('type'):<13} {e.get('value'):<26} {e.get('role') or '':<16} {e.get('method') or '':<26} {where}")
        return 0

    cases = [c for c in store.all("cases") if c.get("status") in ("CLASSIFIED", "REVIEWED")]
    cases.sort(key=lambda c: c.get("receivedAt") or "", reverse=True)
    if args.limit:
        cases = cases[: args.limit]
    totals = Counter()
    print(f"{'email':<28} {'att':>3} {'read':>4}  {'in attachment text (pattern)':<34} {'on the case, from attachments':<34} note")
    for case in cases:
        try:
            r = check(case, blob, run_message)
        except Exception as exc:  # noqa: BLE001
            print(f"{case['id']:<28} could not check: {type(exc).__name__}: {exc}")
            continue
        found = " ".join(f"{KINDS.get(k, k)} {n}" for k, n in sorted(r["in_text"].items())) or "—"
        shown = " ".join(f"{KINDS[t]} {n}" for (t, w), n in sorted(r["on_case"].items()) if w == "att") or "—"
        note = "reading step failed" if r["error"] else ("not read: " + "; ".join(r["failed"]))[:60] if r["failed"] else ""
        if r["attachments"]:
            print(f"{r['id']:<28} {r['attachments']:>3} {r['read']:>4}  {found:<34} {shown:<34} {note}")
        totals["emails"] += 1
        totals["with attachments"] += bool(r["attachments"])
        totals["attachments"] += r["attachments"]
        totals["attachments read"] += r["read"]
        totals["values in attachment text"] += sum(r["in_text"].values())
        totals["values on cases from attachments"] += sum(n for (t, w), n in r["on_case"].items() if w == "att")
        totals["reading step failed"] += bool(r["error"])
    print("\nTotals:")
    for key, value in totals.items():
        print(f"  {key:<34} {value}")
    print("\nOne email in detail: python tools/check_extraction.py --case <email id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
