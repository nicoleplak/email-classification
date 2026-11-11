from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_ENDPOINT = os.getenv("GRAPH_API_ENDPOINT", "https://graph.microsoft.com/v1.0").rstrip("/")
DOVALUEGREECE_ID = os.getenv("DOVALUEGREECE_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SCOPE = os.getenv("SCOPE", "https://graph.microsoft.com/.default")
USER_ID = os.getenv("USER_ID")

# The checkpoint is kept in Blob Storage, not on the container filesystem.
DELTA_STATE_BLOB = os.getenv("DELTA_STATE_BLOB", "state/graph_delta_state.json")

# Applied only when DELTA_STATE_BLOB does not yet exist. 1 = previous 24 hours.
DELTA_BOOTSTRAP_DAYS = int(os.getenv("DELTA_BOOTSTRAP_DAYS", "1"))

REQUEST_TIMEOUT = (10, 120)

MESSAGE_SELECT = (
    "id,internetMessageId,subject,from,toRecipients,receivedDateTime,"
    "lastModifiedDateTime,body,categories,conversationId,hasAttachments"
)


@dataclass(frozen=True)
class DeltaBatch:
    messages: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    candidate_delta_link: str


class GraphApiError(RuntimeError):
    pass


def _require_settings() -> None:
    values = {
        "DOVALUEGREECE_ID": DOVALUEGREECE_ID,
        "CLIENT_ID": CLIENT_ID,
        "CLIENT_SECRET": CLIENT_SECRET,
        "SCOPE": SCOPE,
        "USER_ID": USER_ID,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment settings: {', '.join(missing)}")
    if DELTA_BOOTSTRAP_DAYS < 0:
        raise ValueError("DELTA_BOOTSTRAP_DAYS must be >= 0")


def _graph_headers(access_token: str, accept: str = "application/json") -> dict[str, str]:
    # Immutable IDs keep the storage identity stable when an Outlook item moves.
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": accept,
        "Prefer": 'IdType="ImmutableId"',
    }


def _raise_graph_error(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text
    raise GraphApiError(
        f"Microsoft Graph request failed: {response.status_code} "
        f"{response.request.method} {response.url}; response={detail}"
    )


def _get_json(
    url: str,
    headers: dict[str, str],
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    _raise_graph_error(response)
    return response.json()


def _paginate_json(
    url: str,
    headers: dict[str, str],
    params: Optional[dict[str, Any]] = None,
) -> Iterator[dict[str, Any]]:
    next_url: Optional[str] = url
    next_params = params
    while next_url:
        page = _get_json(next_url, headers, next_params)
        yield page
        # Graph's nextLink is opaque and must be reused exactly as returned.
        next_url = page.get("@odata.nextLink")
        next_params = None


def get_access_token() -> str:
    _require_settings()
    url = f"https://login.microsoftonline.com/{DOVALUEGREECE_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
        "grant_type": "client_credentials",
    }
    response = requests.post(url, data=data, timeout=(10, 30))
    _raise_graph_error(response)
    return response.json()["access_token"]


def load_delta_link() -> Optional[str]:
    """Load the last successfully committed Graph deltaLink from Blob Storage."""
    from helpers import blob_store

    raw = blob_store.download(DELTA_STATE_BLOB)
    if raw is None:
        return None

    state = json.loads(raw.decode("utf-8"))
    delta_link = state.get("delta_link")
    if not isinstance(delta_link, str) or not delta_link:
        raise ValueError(f"Invalid delta state in blob {DELTA_STATE_BLOB}")
    return delta_link


def commit_delta_link(candidate_delta_link: str) -> None:
    """Commit state only after the entire Graph -> Blob batch has succeeded."""
    if not candidate_delta_link:
        raise ValueError("candidate_delta_link must not be empty")

    from helpers import blob_store

    payload = json.dumps(
        {
            "delta_link": candidate_delta_link,
            "committed_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    if not blob_store.upload(payload, DELTA_STATE_BLOB, overwrite=True):
        raise RuntimeError(f"Failed to commit delta state to blob {DELTA_STATE_BLOB}")


def _bootstrap_from_utc() -> str:
    """Calculate the initial rolling lookback boundary, e.g. the previous 24 hours."""
    value = datetime.now(timezone.utc) - timedelta(days=DELTA_BOOTSTRAP_DAYS)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_email_delta(
    access_token: str,
    committed_delta_link: Optional[str] = None,
) -> DeltaBatch:
    """
    Complete one Inbox delta round.

    First run:
      - uses receivedDateTime >= now - DELTA_BOOTSTRAP_DAYS
      - exhausts every @odata.nextLink
      - returns the final @odata.deltaLink as an uncommitted candidate

    Later runs:
      - use the saved @odata.deltaLink exactly as Graph returned it
      - do NOT recalculate the bootstrap date

    No state is committed by this function.
    """
    _require_settings()
    headers = _graph_headers(access_token)

    if committed_delta_link:
        url = committed_delta_link
        params = None
        print(f"Delta resume: loading changes from checkpoint {DELTA_STATE_BLOB}")
    else:
        url = (
            f"{GRAPH_API_ENDPOINT}/users/{quote(USER_ID, safe='')}/"
            "mailFolders/inbox/messages/delta"
        )
        bootstrap_from = _bootstrap_from_utc()
        params = {
            "$select": MESSAGE_SELECT,
            "$filter": f"receivedDateTime ge {bootstrap_from}",
            "$orderby": "receivedDateTime desc",
            "$top": 100,
        }
        print(
            f"Delta bootstrap: no checkpoint found; retrieving Inbox changes "
            f"from {bootstrap_from} (last {DELTA_BOOTSTRAP_DAYS} day(s))."
        )

    messages: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    candidate_delta_link: Optional[str] = None

    for page in _paginate_json(url, headers, params):
        for item in page.get("value", []):
            if "@removed" in item:
                removed.append(item)
            else:
                messages.append(item)
        if page.get("@odata.deltaLink"):
            candidate_delta_link = page["@odata.deltaLink"]

    if not candidate_delta_link:
        raise GraphApiError("Delta synchronization ended without @odata.deltaLink")

    return DeltaBatch(
        messages=messages,
        removed=removed,
        candidate_delta_link=candidate_delta_link,
    )


def get_emails(access_token: str) -> DeltaBatch:
    """Load the Blob checkpoint and execute the next Inbox delta round."""
    return get_email_delta(access_token, load_delta_link())


def get_message_mime(access_token: str, message_id: str) -> bytes:
    """Retrieve raw RFC 5322 MIME bytes for storage as message.eml."""
    _require_settings()
    encoded_id = quote(message_id, safe="")
    url = (
        f"{GRAPH_API_ENDPOINT}/users/{quote(USER_ID, safe='')}/"
        f"messages/{encoded_id}/$value"
    )
    response = requests.get(
        url,
        headers=_graph_headers(access_token, accept="message/rfc822"),
        timeout=REQUEST_TIMEOUT,
    )
    _raise_graph_error(response)
    return response.content


def stable_message_key(message: dict[str, Any]) -> str:
    """Create a deterministic Blob-safe identity for idempotent retries."""
    identity = message.get("id") or message.get("internetMessageId")
    if not identity:
        raise ValueError("Message has neither id nor internetMessageId")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def message_blob_prefix(message: dict[str, Any]) -> str:
    key = stable_message_key(message)
    return f"messages/{key[:2]}/{key}"


def get_conversation_thread(access_token: str, conversation_id: str) -> list[dict]:
    """Retrieve a complete conversation across folders, oldest first."""
    _require_settings()
    headers = _graph_headers(access_token)
    selection = (
        "id,internetMessageId,subject,from,toRecipients,receivedDateTime,"
        "body,hasAttachments,conversationId"
    )
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$select": selection,
        "$top": 50,
    }
    url = f"{GRAPH_API_ENDPOINT}/users/{quote(USER_ID, safe='')}/messages"

    messages: list[dict] = []
    for page in _paginate_json(url, headers, params):
        messages.extend(page.get("value", []))

    messages.sort(key=lambda item: item.get("receivedDateTime", ""))
    return messages


def copy_message_to_folder(
    access_token: str,
    message_id: str,
    destination_folder_id: str,
) -> dict:
    """Copy a message to an Outlook folder without moving the original."""
    _require_settings()
    encoded_id = quote(message_id, safe="")
    url = (
        f"{GRAPH_API_ENDPOINT}/users/{quote(USER_ID, safe='')}/"
        f"messages/{encoded_id}/copy"
    )
    headers = _graph_headers(access_token)
    headers["Content-Type"] = "application/json"
    response = requests.post(
        url,
        headers=headers,
        json={"destinationId": destination_folder_id},
        timeout=REQUEST_TIMEOUT,
    )
    _raise_graph_error(response)
    return response.json()


def get_attachments(access_token: str, message_id: str) -> list[dict]:
    """Fetch all attachment objects for one message, preserving existing behavior."""
    _require_settings()
    encoded_id = quote(message_id, safe="")
    url = (
        f"{GRAPH_API_ENDPOINT}/users/{quote(USER_ID, safe='')}/"
        f"messages/{encoded_id}/attachments"
    )

    attachments: list[dict] = []
    for page in _paginate_json(url, _graph_headers(access_token), {"$top": 100}):
        attachments.extend(page.get("value", []))
    return attachments
