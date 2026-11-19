"""Browser test for the review app, with Playwright's bundled Chromium.

    python evaluation/browser_test/run.py          # invented emails only
    python evaluation/browser_test/run.py --real   # also walks runs/eval/review_app.html, counts only

Reports numbers and short labels, never email text. Screenshots of the invented
emails go to runs/eval/ui_test_output/ for a person to look at. Exits 1 if a check fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
OUT_DIR = APP_DIR.parent / "runs" / "eval"
REAL_APP = OUT_DIR / "review_app.html"


def synthetic_page() -> str:
    """The real template and category names, with invented emails."""
    source = (HERE.parent / "review_app.py").read_text(encoding="utf-8")
    template = source.split('TEMPLATE = r"""', 1)[1].split('"""', 1)[0]
    config = json.loads(
        (APP_DIR / "inputs" / "categories.json").read_text(encoding="utf-8")
    )
    cats = [c["Categories"].strip() for c in config] + ["No Match Found"]
    debt, copies, gdpr = "Βεβαιώσεις οφειλής", "Αντίγραφα συμβάσεων", "GDPR"
    filler = "\n".join(
        f"Συνθετική γραμμή {i} του μηνύματος, με αρκετό κείμενο." for i in range(90)
    )
    why = "Το email ζητά ρητά το έγγραφο και αναφέρει τον λόγο. " * 3

    def email(i: int, p1: int, p2: int, p3: int, batch: str) -> dict:
        scores = [i % 7 for _ in cats]
        for name, value in ((debt, p1), (copies, p2), (gdpr, p3)):
            scores[cats.index(name)] = value
        return {
            "id": f"id{i}",
            "dataset": batch,
            "received": "2026-10-26T09:14",
            "sender": f"user{i}@example.com",
            "subject": f"Συνθετικό θέμα {i} "
            + "με πολύ μεγάλο τίτλο " * (6 if i % 2 else 1),
            "chain": [
                {
                    "who": "",
                    "when": "",
                    "subject": "",
                    "body": f"Παρακαλώ στείλτε τη σύμβαση. φράση{i} εδώ.\n{filler}",
                },
                {
                    "who": "Ομάδα <team@example.com>",
                    "when": "Τρίτη 3 Μαρτίου 2026",
                    "subject": "RE: Βεβαίωση",
                    "body": "Απάντηση της ομάδας.",
                },
                {
                    "who": "Customer",
                    "when": "2026-03-02T10:30",
                    "subject": "Βεβαίωση",
                    "body": "Το αρχικό αίτημα του πελάτη.",
                },
            ],
            "attachments": [
                {
                    "file": "a.pdf",
                    "type": "έντυπο",
                    "relevance": "relevant",
                    "summary": "περίληψη " * 40,
                    "asks": ["αίτημα"],
                    "evidence": ["απόσπασμα"],
                }
            ],
            "cat": debt,
            "scores": scores,
            "top3": [
                {"cat": debt, "p": p1, "why": why},
                {"cat": copies, "p": p2, "why": why},
                {"cat": gdpr, "p": p3, "why": why},
            ],
            "quotes": [f"φράση{i}"],
            "action": {
                "items": [
                    {
                        "do": "request",
                        "cat": debt,
                        "open": "89 Βεβαίωση Οφειλής",
                        "closed": "117 Βεβαίωση Οφειλής Cust",
                        "codes": [],
                        "to": [],
                        "why": [
                            "Δεν ζητά ανάλυση της οφειλής.",
                            "Ο πελάτης δεν έχει πρόσβαση στο Portal, οπότε το αίτημα το καταχωρούμε εμείς.",
                        ],
                    },
                    {
                        "do": "forward",
                        "cat": copies,
                        "open": None,
                        "closed": None,
                        "codes": [],
                        "to": ["dept@example.com"],
                        "why": [],
                    },
                ],
                "customer": {
                    "identified": True,
                    "known": True,
                    "portal": False,
                    "is_3869": False,
                    "erb": False,
                    "via": "afm",
                },
            },
        }

    emails = [
        email(
            i,
            95 if i % 3 else 80,
            72 if i % 4 == 0 else 20,
            8,
            "30/09" if i < 20 else "26/10",
        )
        for i in range(40)
    ]
    emails[5]["action"] = None
    data = json.dumps(
        {
            "emails": emails,
            "categories": cats,
            "spec": {debt: "Κείμενο της προδιαγραφής."},
            "high": 90,
            "also": 50,
        },
        ensure_ascii=False,
    )
    return template.replace("__DATA__", data.replace("</", "<\\/"))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "synthetic.html"
        page.write_text(synthetic_page(), encoding="utf-8")
        command = [
            "node",
            str(HERE / "pw_test.cjs"),
            page.as_uri(),
            str(OUT_DIR / "ui_test_output"),
        ]
        if "--real" in sys.argv:
            command.append(REAL_APP.as_uri())
        return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
