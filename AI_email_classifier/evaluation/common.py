"""Shared helpers for offline classifier evaluation.

Rebuilds, for every email of a past run, the exact inputs the production
classifier receives (thread context + attachment context), so variants can be
compared on identical evidence without re-downloading or re-OCRing attachments.
"""

from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent
load_dotenv(os.getenv("ENV_FILE", REPO_DIR / ".env"))
sys.path.insert(0, str(APP_DIR))

import pandas as pd  # noqa: E402

from core.processor import EmailProcessor  # noqa: E402
from utils.html_text import html_to_text  # noqa: E402

RUN_DIR = Path(
    os.getenv("EVAL_RUN_DIR", REPO_DIR / "runs" / "30_09_run_src" / "30_09_run")
)
OUT_DIR = Path(os.getenv("EVAL_OUT_DIR", REPO_DIR / "runs" / "eval"))
REGISTRY_COLUMNS = [
    "TAX_ID_NO",
    "SOURCE",
    "CST_STS_NM",
    "CST_UNQ_CD",
    "PRTFL_CD",
    "ACC_UNQ_CD",
]


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_categories() -> list[dict[str, Any]]:
    return load_json(APP_DIR / "inputs" / "categories.json")


# The e-wizard is being discontinued: its routing field and the spec's one sentence
# about it must not reach the model or the reviewers.
_WIZARD_SENTENCE = re.compile(
    r"\d\.\s*Αν στο mail δηλώνει αδυναμία καταχώρησης στο wiz[^:]*:\s*"
)


def categories_without_wizard() -> list[dict[str, Any]]:
    return [
        {
            key: _WIZARD_SENTENCE.sub("", value) if isinstance(value, str) else value
            for key, value in item.items()
            if key != "Παραπομπές wizard/portal"
        }
        for item in load_categories()
    ]


def spec_path() -> Path:
    """The business spec: SPEC_XLSX, else the newest copy in the repo root (git-ignored)."""
    if os.getenv("SPEC_XLSX"):
        return Path(os.environ["SPEC_XLSX"])
    return max(REPO_DIR.glob("*IDS comments*.xlsx"), key=lambda f: f.stat().st_mtime)


NO_MATCH = "No Match Found"
# Business-spec names that differ from the production names in categories.json.
SPEC_RENAMES = {
    "αιτήματα ν3869": "Αιτήματα Ν.3869",
    "aρση προσημείωσης": "Βεβαίωση άρσης προσημείωσης",
    "βεβαίωση_καταβολών/βεβαίωση_τόκων": "Βεβαίωση_Καταβολών_Βεβαίωση_Τόκων",
    "ρύθμιση με επισύναψη δικαιολογητικών": "Ρύθμιση",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def spec_rows() -> dict[str, dict[str, Any]]:
    """Spec rows by production category name, read by header so added columns can't shift them."""
    import openpyxl

    sheet = openpyxl.load_workbook(spec_path(), read_only=True, data_only=True)[
        "Record_Creation_Criteria"
    ]
    rows = sheet.iter_rows(values_only=True)
    headers = [_clean(h) for h in next(rows)]
    spec = {}
    for values in rows:
        row = dict(zip(headers, values))
        if not row.get("Categories"):
            continue
        key = _clean(row["Categories"]).lower().split(":")[0].strip()
        spec[_clean(SPEC_RENAMES.get(key, row["Categories"])).lower()] = row
    return spec


def spec_catalogue() -> list[dict[str, str]]:
    """Production category names, described with the business spec's newest text.

    Categories the spec does not cover (Marketing-SPAM) keep their config text.
    """
    spec = spec_rows()
    catalogue = []
    for item in load_categories():
        name = item["Categories"].strip()
        row = spec.get(_clean(name).lower(), item)
        catalogue.append(
            {
                "category": name,
                "keywords_rules": _clean(row.get("Rules/Λέξεις κλειδιά")),
                "comments": _clean(row.get("comments")),
                "actions": _clean(row.get("Actions")),
                "priority": _clean(row.get("Priority")),
            }
        )
    return catalogue


def render_case(case: dict[str, Any], body_limit: int = 15_000) -> dict[str, Any]:
    """Compact, model-readable view of one case (newest message + history + attachments)."""
    thread = case["thread_context"]
    attachments = (case["attachment_context"] or {}).get("records") or []
    return {
        "sender_address": case["sender"],
        "subject": case["subject"],
        "body": case["body"][:body_limit],
        "previous_messages": [
            {
                "sender_type": m.get("Sender_Type"),
                "subject": m.get("Subject"),
                "body": (m.get("Body") or "")[:4000],
            }
            for m in thread.get("Previous_Messages") or []
        ],
        "attachments": [
            {
                "filename": a.get("filename"),
                "document_type": a.get("document_type"),
                "relevance": a.get("relevance"),
                "summary": a.get("summary"),
                "requested_actions": a.get("requested_actions"),
            }
            for a in attachments
            if a.get("status") == "ANALYZED"
        ],
    }


class _CachedAttachments:
    """Replays the attachment bundle the original run produced for each email."""

    def __init__(self, summary_rows: list[dict[str, Any]]):
        self.bundles = {}
        for row in summary_rows:
            self.bundles.setdefault(
                row["id"],
                {
                    "total": row.get("attachment_count", 0),
                    "processed": row.get("attachment_processed_count", 0),
                    "relevant": row.get("attachment_relevant_count", 0),
                    "failed_or_unsupported": row.get("attachment_failed_count", 0),
                    "requires_review": row.get("attachment_requires_review", False),
                    "warnings": row.get("attachment_warnings", []),
                    "extracted_afms": row.get("attachment_extracted_afms", []),
                    "evidence_text": row.get("attachment_evidence_text", ""),
                    "records": row.get("attachment_records", []),
                },
            )

    def process_email_attachments(self, email, _categories):
        return self.bundles.get(email["id"], {})


class _Recorder:
    """Stands in for the classifier and records the arguments it is given."""

    def __init__(self):
        self.cases: list[dict[str, Any]] = []

    def classify(
        self,
        subject,
        body,
        categories_json,
        thread_context=None,
        attachment_context=None,
    ):
        self.cases.append(
            {
                "id": thread_context["Current_Message"]["Message_ID"],
                "subject": subject,
                "body": body,
                "thread_context": thread_context,
                "attachment_context": attachment_context,
            }
        )
        return {"Category": "No Match Found", "Confidence": 0.0}


def build_cases() -> list[dict[str, Any]]:
    """One case per classified email, in production order, with sender added."""
    emails = load_json(RUN_DIR / "emails.json")
    # Some runs have HTML and no body.body_clean, so the raw tags would reach everything
    # downstream. Production's fetch step fills body_clean before classifying.
    for email in emails:
        for message in [email, *(email.get("conversation_thread") or [])]:
            body = message.get("body")
            if (
                isinstance(body, dict)
                and body.get("contentType") == "html"
                and not body.get("body_clean")
            ):
                body["content"] = body["body_clean"] = html_to_text(body.get("content"))
    recorder = _Recorder()
    processor = EmailProcessor(
        registry_df=pd.DataFrame(columns=REGISTRY_COLUMNS),
        classifier=recorder,
        categories_data=load_categories(),
        reply_templates={},
        forward_rules={},
        default_reply="",
        attachment_processor=_CachedAttachments(load_json(RUN_DIR / "summary.json")),
    )
    processor.process_batch(emails, export=False, use_thread_context=True)
    senders, datasets = {}, {}
    for email in emails:
        for message in [email, *(email.get("conversation_thread") or [])]:
            senders[message["id"]] = EmailProcessor._get_sender_address(message)
            datasets[message["id"]] = email.get("_dataset", "30/09")
    for case in recorder.cases:
        case["sender"] = senders.get(case["id"], "")
        case["dataset"] = datasets.get(case["id"], "")
    return recorder.cases


def run_cached(
    name: str, cases: list[dict[str, Any]], fn: Callable[[dict], dict], workers: int = 8
) -> dict[str, dict]:
    """Run fn over cases, appending each result to OUT_DIR/<name>.jsonl; resumes on rerun."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["id"]] = row
    todo = [case for case in cases if case["id"] not in done]

    def work(case):
        try:
            return {"id": case["id"], **fn(case)}
        except Exception as exc:  # keep going; failed ids are retried on rerun
            print(
                f"  failed {case['id'][-12:]}: {type(exc).__name__}: {str(exc)[:120]}",
                flush=True,
            )
            return None

    with path.open("a", encoding="utf-8") as sink, ThreadPoolExecutor(workers) as pool:
        for count, row in enumerate(pool.map(work, todo), 1):
            if row is None:
                continue
            done[row["id"]] = row
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
            sink.flush()
            if count % 25 == 0:
                print(f"  {name}: {count}/{len(todo)}", flush=True)
    return done
