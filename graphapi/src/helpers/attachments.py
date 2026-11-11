from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from azure.core.exceptions import AzureError

from helpers import blob_store
from helpers.utils import sanitize_filename


FILE_ATTACHMENT_TYPE = "#microsoft.graph.fileAttachment"
ITEM_ATTACHMENT_TYPE = "#microsoft.graph.itemAttachment"
REFERENCE_ATTACHMENT_TYPE = "#microsoft.graph.referenceAttachment"


def short_storage_id(value: str, length: int = 16) -> str:
    """Return a stable, short, filesystem-safe identifier."""
    normalized = str(value or "").strip()
    if not normalized:
        return "missing-id"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]


def safe_attachment_filename(filename: str, max_length: int = 120) -> str:
    """Sanitize a filename and bound its length while preserving the extension."""
    sanitized = sanitize_filename(str(filename or "attachment")) or "attachment"
    if len(sanitized) <= max_length:
        return sanitized

    path = Path(sanitized)
    suffix = path.suffix[:20]
    available_stem_length = max(1, max_length - len(suffix))
    return f"{path.stem[:available_stem_length]}{suffix}"


def ensure_path_within_root(candidate_path: Path, storage_root: Path) -> Path:
    """Ensure a generated path cannot escape the configured attachment root."""
    resolved_root = storage_root.resolve()
    resolved_candidate = candidate_path.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "Generated attachment path is outside ATTACHMENT_DIR."
        ) from exc
    return resolved_candidate


def save_attachments(
    email: dict[str, Any],
    attachment_dir: str,
) -> list[dict[str, Any]]:
    """Persist Graph file attachments and return lightweight descriptors.

    Full Graph IDs are retained in metadata. Short deterministic hashes are used
    for local folders and file prefixes to avoid Windows path-length failures.
    Raw contentBytes is not returned, keeping the exported JSON compact.
    """
    to_blob = blob_store.enabled()
    if not attachment_dir and not to_blob:
        raise ValueError(
            "ATTACHMENT_DIR is required when attachment downloading is enabled."
        )

    graph_attachments = email.get("attachments") or []
    if not isinstance(graph_attachments, list):
        raise TypeError("email['attachments'] must be a list.")

    conversation_id = str(email.get("conversationId") or "no-conversation-id")
    message_id = str(email.get("id") or "no-message-id")
    folders = (
        short_storage_id(conversation_id, length=16),
        short_storage_id(message_id, length=16),
    )

    # Blob mode writes nothing locally; the hashed folders name the blob instead.
    storage_root = message_storage_path = None
    if not to_blob:
        storage_root = Path(attachment_dir).expanduser()
        storage_root.mkdir(parents=True, exist_ok=True)
        message_storage_path = ensure_path_within_root(
            storage_root.joinpath(*folders),
            storage_root,
        )
        message_storage_path.mkdir(parents=True, exist_ok=True)

    stored: list[dict[str, Any]] = []
    for attachment in graph_attachments:
        if not isinstance(attachment, dict):
            stored.append(
                {
                    "status": "INVALID_ATTACHMENT_OBJECT",
                    "warnings": [
                        "Microsoft Graph returned a non-object attachment entry."
                    ],
                }
            )
            continue

        stored.append(
            _save_single_attachment(
                attachment=attachment,
                conversation_id=conversation_id,
                message_id=message_id,
                folders=folders,
                message_storage_path=message_storage_path,
                storage_root=storage_root,
            )
        )

    return stored


def _save_single_attachment(
    attachment: dict[str, Any],
    conversation_id: str,
    message_id: str,
    folders: tuple[str, str],
    message_storage_path: Path | None,
    storage_root: Path | None,
) -> dict[str, Any]:
    """Persist one Graph attachment to Blob, or locally when given a storage path."""
    attachment_id = str(attachment.get("id") or "no-attachment-id")
    original_name = str(attachment.get("name") or "attachment")
    attachment_type = str(attachment.get("@odata.type") or "")
    content_type = str(attachment.get("contentType") or "application/octet-stream")

    descriptor: dict[str, Any] = {
        "id": attachment_id,
        "conversationId": conversation_id,
        "messageId": message_id,
        "name": original_name,
        "contentType": content_type,
        "size": attachment.get("size"),
        "isInline": bool(attachment.get("isInline", False)),
        "contentId": attachment.get("contentId"),
        "@odata.type": attachment_type,
    }

    if attachment_type == ITEM_ATTACHMENT_TYPE:
        return {
            **descriptor,
            "status": "ITEM_ATTACHMENT_UNSUPPORTED",
            "warnings": [
                "Attached Outlook items are not processed in the current phase."
            ],
        }

    if attachment_type == REFERENCE_ATTACHMENT_TYPE:
        return {
            **descriptor,
            "status": "REFERENCE_ATTACHMENT_UNSUPPORTED",
            "sourceUrl": attachment.get("sourceUrl"),
            "providerType": attachment.get("providerType"),
            "warnings": [
                "Cloud reference attachments require a separate authorized "
                "retrieval path."
            ],
        }

    if attachment_type != FILE_ATTACHMENT_TYPE:
        return {
            **descriptor,
            "status": "UNKNOWN_ATTACHMENT_TYPE",
            "warnings": [
                "Unsupported Microsoft Graph attachment type: "
                f"{attachment_type or '<missing>'}."
            ],
        }

    content_base64 = attachment.get("contentBytes")
    if not isinstance(content_base64, str) or not content_base64:
        return {
            **descriptor,
            "status": "DOWNLOAD_MISSING",
            "warnings": [
                "Microsoft Graph file attachment did not contain contentBytes."
            ],
        }

    try:
        decoded = base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        return {
            **descriptor,
            "status": "INVALID_BASE64",
            "warnings": [
                f"Attachment Base64 decoding failed: {type(exc).__name__}: {exc}"
            ],
        }

    warnings: list[str] = []
    declared_size = attachment.get("size")
    if declared_size is not None:
        try:
            if int(declared_size) != len(decoded):
                warnings.append(
                    "Microsoft Graph declared size differs from the decoded "
                    "attachment size."
                )
        except (TypeError, ValueError):
            warnings.append("Microsoft Graph attachment size was not numeric.")

    attachment_prefix = short_storage_id(attachment_id, length=12)
    safe_name = safe_attachment_filename(original_name, max_length=120)
    local_filename = f"{attachment_prefix}_{safe_name}"

    if message_storage_path is None:
        location = {"blob_name": "/".join(("attachments", *folders, local_filename))}
    else:
        file_path = ensure_path_within_root(
            message_storage_path / local_filename,
            storage_root,
        )
        location = {"local_path": str(file_path)}

    try:
        if "blob_name" in location:
            # Names derive from Graph ids, so an existing blob is the same file.
            blob_store.upload(decoded, location["blob_name"])
        else:
            file_path.write_bytes(decoded)
    except (OSError, AzureError) as exc:
        return {
            **descriptor,
            "status": "STORAGE_FAILED",
            "warnings": [
                f"Attachment could not be stored: {type(exc).__name__}: {exc}"
            ],
        }

    return {
        **descriptor,
        "status": "SAVED",
        **location,
        "decoded_size": len(decoded),
        "sha256": hashlib.sha256(decoded).hexdigest(),
        "storage": {
            "conversation_folder": folders[0],
            "message_folder": folders[1],
            "local_filename": local_filename,
        },
        "warnings": warnings,
    }
