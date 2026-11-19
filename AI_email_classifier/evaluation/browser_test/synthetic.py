"""Invented emails in the shape review_app.payload() returns. No client data.

Used by the review-server tests, its browser test, and `review_server.py demo`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]


def payload(n: int = 60) -> dict:
    config = json.loads((APP_DIR / "inputs" / "categories.json").read_text(encoding="utf-8"))
    cats = [c["Categories"].strip() for c in config] + ["No Match Found"]
    debt, copies, gdpr = "Βεβαιώσεις οφειλής", "Αντίγραφα συμβάσεων", "GDPR"
    today = datetime.now().replace(hour=9, minute=14, second=0, microsecond=0)
    why = "Το email ζητά ρητά το έγγραφο και αναφέρει τον λόγο."
    emails = []
    for i in range(n):
        # Every 7th email has not been classified yet; dates spread over 40 days, newest first.
        classified = i % 7 != 3
        p1 = 95 if i % 3 else 72
        received = today - timedelta(days=(i * 2) % 40, minutes=i)
        e = {
            "id": f"syn{i:03d}",
            "dataset": "Δοκιμή Α" if i % 2 else "Δοκιμή Β",
            "received": received.strftime("%Y-%m-%dT%H:%M"),
            "sender": f"pelatis{i}@example.com",
            "subject": f"Συνθετικό αίτημα {i} για βεβαίωση οφειλής" + (" με πολύ μεγάλο θέμα" * 4 if i % 5 == 0 else ""),
            "chain": [
                {"who": "", "when": "", "subject": "", "body": f"Καλημέρα σας,\nπαρακαλώ στείλτε μου βεβαίωση οφειλής. φράση{i} εδώ.\n"
                 + "\n".join(f"Συνθετική γραμμή {k} του μηνύματος." for k in range(12))},
                {"who": "Customer", "when": "2026-03-02T10:30", "subject": "Βεβαίωση", "body": "Το αρχικό αίτημα του πελάτη."},
            ],
            "attachments": [{"file": f"aitisi{i}.pdf", "type": "έντυπο", "relevance": "relevant", "summary": "Αίτηση για βεβαίωση οφειλής.",
                             "asks": ["βεβαίωση οφειλής"], "evidence": ["ζητώ βεβαίωση"]}] if i % 2 == 0 else [],
            "cat": None, "scores": [], "top3": [], "quotes": [], "action": None,
        }
        if classified:
            scores = [(i + k) % 9 for k in range(len(cats))]
            for name, value in ((debt, p1), (copies, 20 if i % 4 else 64), (gdpr, 6)):
                scores[cats.index(name)] = value
            e.update(
                cat=debt, scores=scores, quotes=[f"φράση{i}"],
                top3=[{"cat": debt, "p": p1, "why": why}, {"cat": copies, "p": scores[cats.index(copies)], "why": why},
                      {"cat": gdpr, "p": 6, "why": "Δεν αναφέρει προσωπικά δεδομένα."}],
                action={
                    "items": [
                        {"do": "request", "caveat": None if i % 4 else "not_identified", "cat": debt,
                         "open": "89 Βεβαίωση Οφειλής", "closed": "117 Βεβαίωση Οφειλής Cust", "codes": [], "to": [],
                         "why": ["Δεν ζητά ανάλυση της οφειλής.", "Ο πελάτης δεν έχει πρόσβαση στο Portal."]},
                        {"do": "forward", "caveat": None, "cat": copies, "open": None, "closed": None, "codes": [],
                         "to": ["tmima@example.com"], "why": []},
                    ],
                    "customer": {"identified": i % 4 != 0, "known": i % 4 != 0, "portal": i % 8 == 1, "is_3869": i % 10 == 2,
                                 "erb": False, "via": "afm"},
                    "fields": [
                        {"key": "afm", "label": "ΑΦΜ", "values": [{"value": f"0{i:08d}", "who": "Πελάτης", "case": True}] if i % 4 else None},
                        {"key": "adt", "label": "ΑΔΤ", "values": [{"value": f"ΑΚ{100000 + i}", "who": "Πελάτης", "case": False}] if i % 3 == 0 else None},
                        {"key": "email", "label": "Email", "values": [{"value": f"pelatis{i}@example.com", "who": "Αποστολέας", "case": False}]},
                        {"key": "account", "label": "Δανειακός λογαριασμός", "values": None},
                        {"key": "iban", "label": "IBAN", "values": None},
                    ],
                },
            )
        emails.append(e)
    return {"emails": emails, "categories": cats, "spec": {debt: "Κείμενο της προδιαγραφής για τη βεβαίωση."}, "high": 90, "also": 50}
