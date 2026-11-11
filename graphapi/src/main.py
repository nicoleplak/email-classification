from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from helpers import blob_store
from helpers.attachments import save_attachments
from helpers.graph_api import (
    get_access_token,
    get_attachments,
    get_conversation_thread,
    get_emails,
)
from helpers.utils import clean_body


load_dotenv()

ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR")
OUTPUT_EMAIL = os.getenv("OUTPUT_EMAIL")
FETCH_ATTACHMENTS = os.getenv("FETCH_ATTACHMENTS", "false").strip().lower() == "true"
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "0"))
EXCLUDE_DOMAINS = [
    value.strip().lower()
    for value in os.getenv(
        "EXCLUDE_DOMAINS",
        "dovaluegreece,eurobank",
    ).split(",")
    if value.strip()
]


def validate_configuration() -> None:
    required = {}
    if not blob_store.enabled():  # Blob mode needs no local paths.
        required["OUTPUT_EMAIL"] = OUTPUT_EMAIL
        if FETCH_ATTACHMENTS:
            required["ATTACHMENT_DIR"] = ATTACHMENT_DIR

    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Missing required configuration: " + ", ".join(missing))


def is_excluded_sender(email: dict[str, Any]) -> bool:
    address = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()
    return any(domain in address for domain in EXCLUDE_DOMAINS)


def deduplicate_by_conversation(
    emails: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep the latest fetched message for each conversationId."""
    latest_by_conversation: dict[str, dict[str, Any]] = {}

    for email in emails:
        conversation_id = str(email.get("conversationId") or email.get("id") or "")
        existing = latest_by_conversation.get(conversation_id)

        if existing is None:
            latest_by_conversation[conversation_id] = email
            continue

        if str(email.get("receivedDateTime") or "") > str(
            existing.get("receivedDateTime") or ""
        ):
            latest_by_conversation[conversation_id] = email

    return sorted(
        latest_by_conversation.values(),
        key=lambda item: str(item.get("receivedDateTime") or ""),
    )


def _copy_attachment_state(
    source: dict[str, Any],
    target: dict[str, Any],
) -> None:
    """Reuse attachment state and avoid a duplicate Graph download."""
    target["attachments"] = list(source.get("attachments", []))
    target["attachment_fetch_attempted"] = bool(
        source.get("attachment_fetch_attempted", False)
    )
    target["attachment_fetch_succeeded"] = bool(
        source.get("attachment_fetch_succeeded", False)
    )
    target["attachment_fetch_partially_succeeded"] = bool(
        source.get("attachment_fetch_partially_succeeded", False)
    )
    target["attachment_download_errors"] = list(
        source.get("attachment_download_errors", [])
    )


def _enrich_message_attachments(
    message: dict[str, Any],
    token: str,
) -> None:
    """Fetch and persist attachments for one specific Graph message."""
    message["attachments"] = []
    message["attachment_fetch_attempted"] = False
    message["attachment_fetch_succeeded"] = False
    message["attachment_fetch_partially_succeeded"] = False
    message["attachment_download_errors"] = []

    if not message.get("hasAttachments"):
        return

    if not FETCH_ATTACHMENTS:
        return

    message["attachment_fetch_attempted"] = True

    try:
        graph_attachments = get_attachments(token, message["id"])

        stored_attachments = save_attachments(
            email={**message, "attachments": graph_attachments},
            attachment_dir=ATTACHMENT_DIR,
        )
        message["attachments"] = stored_attachments

        successful_statuses = {"SAVED", "IGNORED_INLINE"}
        failures = [
            attachment
            for attachment in stored_attachments
            if attachment.get("status") not in successful_statuses
        ]
        saved_count = sum(
            attachment.get("status") == "SAVED" for attachment in stored_attachments
        )

        message["attachment_fetch_succeeded"] = not failures
        message["attachment_fetch_partially_succeeded"] = bool(failures and saved_count)

        message["attachment_download_errors"].extend(
            {
                "attachment_id": attachment.get("id"),
                "filename": attachment.get("name"),
                "status": attachment.get("status"),
                "warnings": attachment.get("warnings", []),
            }
            for attachment in failures
        )

    except Exception as exc:
        message["attachment_fetch_succeeded"] = False
        message["attachment_download_errors"].append(
            {
                "message_id": message.get("id", ""),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )


def enrich_email(
    email: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Enrich the target email and all retrieved conversation messages."""
    email["body_clean"] = clean_body(email)
    if isinstance(email.get("body"), dict):
        email["body"]["body_clean"] = email["body_clean"]

    thread = get_conversation_thread(token, email["conversationId"])
    attachment_cache: dict[str, dict[str, Any]] = {}

    for message in thread:
        message["body_clean"] = clean_body(message)
        if isinstance(message.get("body"), dict):
            message["body"]["body_clean"] = message["body_clean"]

        message_id = str(message.get("id") or "")
        if message_id in attachment_cache:
            _copy_attachment_state(
                source=attachment_cache[message_id],
                target=message,
            )
            continue

        _enrich_message_attachments(message, token)
        attachment_cache[message_id] = {
            "attachments": message.get("attachments", []),
            "attachment_fetch_attempted": message.get(
                "attachment_fetch_attempted", False
            ),
            "attachment_fetch_succeeded": message.get(
                "attachment_fetch_succeeded", False
            ),
            "attachment_fetch_partially_succeeded": message.get(
                "attachment_fetch_partially_succeeded", False
            ),
            "attachment_download_errors": message.get("attachment_download_errors", []),
        }

    email["conversation_thread"] = thread
    email["reply_to_message_id"] = thread[-1]["id"] if thread else email["id"]

    target_message_id = str(email.get("id") or "")
    if target_message_id in attachment_cache:
        _copy_attachment_state(
            source=attachment_cache[target_message_id],
            target=email,
        )
    else:
        _enrich_message_attachments(email, token)

    return email


def main() -> None:
    validate_configuration()

    token = get_access_token()
    emails = get_emails(token)
    print(f"Fetched {len(emails)} email(s) from inbox.")

    before = len(emails)
    emails = [email for email in emails if not is_excluded_sender(email)]
    print(
        f"Excluded {before - len(emails)} email(s) matching domains: {EXCLUDE_DOMAINS}"
    )
    print(f"{len(emails)} email(s) remaining after domain filter.")

    before = len(emails)
    emails = deduplicate_by_conversation(emails)
    print(
        f"Deduplicated {before - len(emails)} email(s), kept latest per conversationId."
    )
    print(f"{len(emails)} unique conversation(s) to process.")

    if MAX_EMAILS > 0:
        available = len(emails)
        emails = emails[:MAX_EMAILS]
        print(
            f"UAT mode: configured maximum={MAX_EMAILS}; "
            f"available={available}; selected={len(emails)}"
        )

    enriched: list[dict[str, Any]] = []
    total = len(emails)

    for index, email in enumerate(emails, start=1):
        subject = email.get("subject", "(no subject)")
        conversation_id = email.get("conversationId", "")
        print(f"[{index}/{total}] Processing: {subject}")

        try:
            enriched.append(enrich_email(email, token))
        except Exception as exc:
            print(
                "  ERROR - conversationId: "
                f"{conversation_id} | {type(exc).__name__}: {exc}"
            )
            email.setdefault("body_clean", "")
            email.setdefault("conversation_thread", [])
            email.setdefault("reply_to_message_id", email.get("id", ""))
            email.setdefault("attachments", [])
            email.setdefault("attachment_fetch_attempted", False)
            email.setdefault("attachment_fetch_succeeded", False)
            email.setdefault("attachment_fetch_partially_succeeded", False)
            email.setdefault(
                "attachment_download_errors",
                [
                    {
                        "message_id": email.get("id", ""),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                ],
            )
            enriched.append(email)

    payload = json.dumps(enriched, ensure_ascii=False, indent=2)

    if blob_store.enabled():
        run_id = os.getenv("RUN_ID") or datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        output_path = f"bronze/{run_id}/emails.json"
        if not blob_store.upload(payload.encode("utf-8"), output_path):
            raise FileExistsError(f"Blob already exists: {output_path}")
    else:
        output_path = os.path.abspath(OUTPUT_EMAIL)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(payload)

    print(f"\nDone. {len(enriched)} email(s) saved to {output_path}")


if __name__ == "__main__":
    main()
