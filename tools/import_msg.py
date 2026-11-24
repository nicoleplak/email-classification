"""Import Outlook .msg files into the same blob layout the Graph ingest writes, so the classifier and the
review app treat them like fetched mail.

    python tools/import_msg.py test_data/            # every .msg under that blob prefix
    python tools/import_msg.py C:/path/to/folder     # or a local folder

Writes, in container email-classification:
  messages/import/<id>/message.msg          the original, for viewing and download
  attachments/import/<id>/NN_<name>         each attachment (sha256 recorded, as the ingest does)
  bronze/import-<UTC>/emails.json           {"messages": [...], "removed": []}, Graph-shaped
The classifier always registers runs named import-*, even when REGISTER_RUNS_FROM skips older ingest runs.

Auth: STG_KEY (storage account key) if set, else your az login (needs Storage Blob Data Contributor).
Offline: set LOCAL_BLOB_DIR to write into that local folder instead of Azure (no login needed); the
.msg files must then come from a local folder.
Local tool only: needs extract-msg (requirements/requirements-tools.txt), which the image does not carry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr
from pathlib import Path

import extract_msg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "AI_email_classifier"))


def _load_env(root: Path) -> None:
    """The repo-root .env (as the classifier reads it); settings already set win. Skipped in tests (CI=1)."""
    if os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(root / ".env", override=False)


_load_env(Path(__file__).resolve().parents[1])
from utils.html_text import html_to_text  # noqa: E402

ACCOUNT = os.getenv("RESULT_STORAGE_ACCOUNT", "datallmdev")
CONTAINER = os.getenv("RESULT_CONTAINER", "email-classification")


def container_client():
    from azure.storage.blob import ContainerClient

    url = f"https://{ACCOUNT}.blob.core.windows.net"
    if os.getenv("STG_KEY"):
        return ContainerClient(url, CONTAINER, credential=os.environ["STG_KEY"])
    from azure.identity import AzureCliCredential

    return ContainerClient(url, CONTAINER, credential=AzureCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID")))


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(name).name).strip(" .")[:120] or "attachment"


def _utc(value) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _people(raw: str | None) -> list[dict]:
    return [{"emailAddress": {"name": n, "address": a}} for n, a in getaddresses([raw or ""]) if a]


def _attachment_bytes(attachment) -> bytes | None:
    data = attachment.data
    if isinstance(data, bytes):
        return data
    export = getattr(data, "exportBytes", None)  # an attached email (embedded .msg)
    return export() if callable(export) else None


def convert(raw: bytes, upload) -> dict:
    """One .msg -> a Graph-shaped message dict; ``upload(path, bytes)`` stores the files."""
    digest = hashlib.sha256(raw).hexdigest()
    email_key = f"msg-{digest[:16]}"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m.msg"
        path.write_bytes(raw)
        msg = extract_msg.openMsg(str(path))
        try:
            header = msg.header
            html = msg.htmlBody
            html = html.decode("utf-8", "replace") if isinstance(html, bytes) else (html or "")
            text = msg.body or ""
            sender_name, sender_address = parseaddr(msg.sender or (header.get("From") if header else "") or "")
            received = _utc(getattr(msg, "receivedTime", None) or msg.date)
            message_id = (msg.messageId or (header.get("Message-ID") if header else None) or f"<{email_key}@import>").strip()
            attachments, warnings = [], []
            for number, attachment in enumerate(msg.attachments, 1):
                name = attachment.getFilename() if hasattr(attachment, "getFilename") else (
                    attachment.longFilename or attachment.shortFilename or f"attachment{number}")
                data = _attachment_bytes(attachment)
                if data is None:
                    warnings.append(f"skipped attachment {number}: unsupported type")
                    continue
                if not Path(str(name)).suffix and getattr(attachment, "type", None) and "MSG" in str(attachment.type):
                    name = f"{name}.msg"
                blob_name = f"attachments/import/{email_key}/{number:02d}_{safe_name(str(name))}"
                upload(blob_name, data)
                attachments.append(
                    {
                        "id": f"{email_key}-a{number}",
                        "conversationId": email_key,
                        "messageId": email_key,
                        "name": str(name),
                        "contentType": getattr(attachment, "mimetype", None) or "application/octet-stream",
                        "size": len(data),
                        "isInline": bool(getattr(attachment, "cid", None) and getattr(attachment, "hidden", False)),
                        "contentId": getattr(attachment, "cid", None),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "decoded_size": len(data),
                        "blob_name": blob_name,
                        "status": "SAVED",
                        "warnings": [],
                    }
                )
            msg_blob = f"messages/import/{email_key}/message.msg"
            upload(msg_blob, raw)
            body_html = html or "<pre>" + text.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"
            return {
                "id": email_key,
                "internetMessageId": message_id,
                "conversationId": email_key,
                "subject": msg.subject or "",
                "from": {"emailAddress": {"name": sender_name, "address": sender_address}},
                "toRecipients": _people(msg.to),
                "ccRecipients": _people(msg.cc),
                "receivedDateTime": received,
                "sentDateTime": _utc(msg.date),
                "hasAttachments": bool(attachments),
                "body": {"contentType": "html", "content": body_html, "body_clean": html_to_text(html) if html else text},
                "body_clean": html_to_text(html) if html else text,
                "conversation_thread": [],
                "reply_to_message_id": email_key,
                "attachments": attachments,
                "attachment_fetch_attempted": bool(msg.attachments),
                "attachment_fetch_succeeded": not warnings,
                "attachment_download_errors": warnings,
                "msg_blob_path": msg_blob,
                "eml_blob_path": None,
                "source": "import",
            }
        finally:
            msg.close()


def main(target: str) -> None:
    from data import blob_output

    offline = blob_output.local_root() is not None
    client = None if offline else container_client()
    local = Path(target)
    if local.exists():
        sources = [(p.name, p.read_bytes) for p in sorted(local.rglob("*.msg"))]
    elif offline:
        sys.exit(f"{target} is not a local folder (LOCAL_BLOB_DIR is set, so Azure is not read)")
    else:
        names = sorted(b.name for b in client.list_blobs(name_starts_with=target) if b.name.lower().endswith(".msg"))
        sources = [(n.rsplit("/", 1)[-1], lambda n=n: client.download_blob(n).readall()) for n in names]
    if not sources:
        sys.exit(f"No .msg files under {target}")

    def upload(path: str, data: bytes) -> None:
        if offline:
            blob_output.upload_bytes(path, data)
        else:
            client.upload_blob(path, data, overwrite=True)

    messages = []
    for number, (_name, read) in enumerate(sources, 1):  # file names can hold customer names: not printed
        message = convert(read(), upload)
        messages.append(message)
        print(f"  email {number}: {len(message['attachments'])} attachment(s)")
    run = "import-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    upload(f"bronze/{run}/emails.json",
           json.dumps({"messages": messages, "removed": []}, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"Imported {len(messages)} email(s) as bronze/{run}/emails.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
