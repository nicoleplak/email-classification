from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from helpers import blob_store
from helpers.attachments import save_attachments
from helpers.graph_api import (
    commit_delta_link,
    get_access_token,
    get_attachments,
    get_conversation_thread,
    get_emails,
    get_message_mime,
    message_blob_prefix,
)
from helpers.utils import clean_body

load_dotenv()

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR")
OUTPUT_EMAIL = os.getenv("OUTPUT_EMAIL")
FETCH_ATTACHMENTS = os.getenv("FETCH_ATTACHMENTS", "false").strip().lower() == "true"
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "0"))
EXCLUDE_DOMAINS = [
    value.strip().lower()
    for value in os.getenv("EXCLUDE_DOMAINS", "dovaluegreece,eurobank").split(",")
    if value.strip()
]


def validate_configuration() -> None:
    required = {}
    if not blob_store.enabled():
        required["OUTPUT_EMAIL"] = OUTPUT_EMAIL
        if FETCH_ATTACHMENTS:
            required["ATTACHMENT_DIR"] = ATTACHMENT_DIR
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Missing required configuration: " + ", ".join(missing))


def is_excluded_sender(email: dict[str, Any]) -> bool:
    address = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
    return any(domain in address for domain in EXCLUDE_DOMAINS)


def deduplicate_by_conversation(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for email in emails:
        key = str(email.get("conversationId") or email.get("id") or "")
        existing = latest.get(key)
        if existing is None or str(email.get("receivedDateTime") or "") > str(existing.get("receivedDateTime") or ""):
            latest[key] = email
    return sorted(latest.values(), key=lambda x: str(x.get("receivedDateTime") or ""))


def _copy_attachment_state(source: dict[str, Any], target: dict[str, Any]) -> None:
    target["attachments"] = list(source.get("attachments", []))
    for name in (
        "attachment_fetch_attempted",
        "attachment_fetch_succeeded",
        "attachment_fetch_partially_succeeded",
    ):
        target[name] = bool(source.get(name, False))
    target["attachment_download_errors"] = list(source.get("attachment_download_errors", []))


def _enrich_message_attachments(message: dict[str, Any], token: str) -> None:
    message["attachments"] = []
    message["attachment_fetch_attempted"] = False
    message["attachment_fetch_succeeded"] = False
    message["attachment_fetch_partially_succeeded"] = False
    message["attachment_download_errors"] = []

    if not message.get("hasAttachments") or not FETCH_ATTACHMENTS:
        return

    message["attachment_fetch_attempted"] = True
    try:
        graph_attachments = get_attachments(token, message["id"])
        stored = save_attachments(
            email={**message, "attachments": graph_attachments},
            attachment_dir=ATTACHMENT_DIR,
        )
        message["attachments"] = stored
        successful = {"SAVED", "IGNORED_INLINE"}
        failures = [a for a in stored if a.get("status") not in successful]
        saved_count = sum(a.get("status") == "SAVED" for a in stored)
        message["attachment_fetch_succeeded"] = not failures
        message["attachment_fetch_partially_succeeded"] = bool(failures and saved_count)
        message["attachment_download_errors"].extend(
            {
                "attachment_id": a.get("id"),
                "filename": a.get("name"),
                "status": a.get("status"),
                "warnings": a.get("warnings", []),
            }
            for a in failures
        )
    except Exception as exc:
        message["attachment_fetch_succeeded"] = False
        message["attachment_download_errors"].append(
            {"message_id": message.get("id", ""), "error_type": type(exc).__name__, "error": str(exc)}
        )
        raise


def enrich_email(email: dict[str, Any], token: str) -> dict[str, Any]:
    email["body_clean"] = clean_body(email)
    if isinstance(email.get("body"), dict):
        email["body"]["body_clean"] = email["body_clean"]

    thread = get_conversation_thread(token, email["conversationId"])
    cache: dict[str, dict[str, Any]] = {}

    for message in thread:
        message["body_clean"] = clean_body(message)
        if isinstance(message.get("body"), dict):
            message["body"]["body_clean"] = message["body_clean"]
        mid = str(message.get("id") or "")
        if mid in cache:
            _copy_attachment_state(cache[mid], message)
            continue
        _enrich_message_attachments(message, token)
        cache[mid] = dict(message)

    email["conversation_thread"] = thread
    email["reply_to_message_id"] = thread[-1]["id"] if thread else email["id"]
    mid = str(email.get("id") or "")
    if mid in cache:
        _copy_attachment_state(cache[mid], email)
    else:
        _enrich_message_attachments(email, token)
    return email


def _upload_overwrite(data: bytes, path: str) -> None:
    """Use overwrite semantics when the helper supports them."""
    try:
        result = blob_store.upload(data, path, overwrite=True)
    except TypeError as exc:
        raise RuntimeError(
            "Idempotent delta processing requires helpers.blob_store.upload(..., overwrite=True). "
            "Update blob_store.upload to expose Azure upload_blob(overwrite=True)."
        ) from exc
    if result is False:
        raise RuntimeError(f"Blob upload failed: {path}")


def main() -> None:
    validate_configuration()
    token = get_access_token()
    batch = get_emails(token)

    print(f"Delta returned {len(batch.messages)} changed/new message(s) and {len(batch.removed)} removed message(s).")

    # Never truncate a delta batch. Doing so and committing its deltaLink would skip
    # unprocessed changes. MAX_EMAILS therefore blocks checkpoint advancement.
    if MAX_EMAILS > 0 and len(batch.messages) > MAX_EMAILS:
        raise RuntimeError(
            "MAX_EMAILS cannot truncate a delta batch safely. Set MAX_EMAILS=0 "
            "or implement a non-committing UAT run."
        )

    emails = [e for e in batch.messages if not is_excluded_sender(e)]
    print(f"{len(emails)} message(s) remain after configured sender exclusions.")
    emails = deduplicate_by_conversation(emails)
    print(f"{len(emails)} unique conversation(s) selected for enrichment.")

    enriched: list[dict[str, Any]] = []

    try:
        # Persist raw MIME first. Stable immutable-ID hashes + overwrite make retries safe.
        for index, email in enumerate(emails, start=1):
            subject = email.get("subject", "(no subject)")
            print(f"[{index}/{len(emails)}] Processing: {subject}")

            mime = get_message_mime(token, email["id"])
            prefix = message_blob_prefix(email)

            eml_blob_path = f"{prefix}/message.eml"

            if blob_store.enabled():
                _upload_overwrite(mime, eml_blob_path)

                # Explicit mapping between emails.json and the raw .eml
                email["eml_blob_path"] = eml_blob_path
            else:
                eml_dir = os.path.join(os.path.dirname(os.path.abspath(OUTPUT_EMAIL)), prefix)
                os.makedirs(eml_dir, exist_ok=True)
                with open(os.path.join(eml_dir, "message.eml"), "wb") as fh:
                    fh.write(mime)

            # A failure is fatal by design. We do not advance the delta checkpoint.
            enriched.append(enrich_email(email, token))

        # Preserve removal information instead of attempting MIME/attachment retrieval.
        payload_obj = {
            "messages": enriched,
            "removed": batch.removed,
        }
        payload = json.dumps(payload_obj, ensure_ascii=False, indent=2).encode("utf-8")

        if blob_store.enabled():
            run_id = os.getenv("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output_path = f"bronze/{run_id}/emails.json"
            _upload_overwrite(payload, output_path)
        else:
            output_path = os.path.abspath(OUTPUT_EMAIL)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as fh:
                fh.write(payload)

        # Transaction boundary: only now is the returned delta state safe to consume.
        commit_delta_link(batch.candidate_delta_link)

    except Exception:
        print("Run failed. Delta checkpoint NOT advanced; next execution will retry this batch.")
        raise

    print(f"\nDone. {len(enriched)} email(s) saved to {output_path}")
    print(f"Processed {len(batch.removed)} removed-message delta record(s).")
    print("Delta checkpoint committed successfully.")


if __name__ == "__main__":
    main()
