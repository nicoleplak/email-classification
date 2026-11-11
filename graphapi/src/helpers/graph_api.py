import os
import requests

from dotenv import load_dotenv
from helpers.utils import paginate

load_dotenv()

GRAPH_API_ENDPOINT = os.getenv("GRAPH_API_ENDPOINT")
DOVALUEGREECE_ID = os.getenv("DOVALUEGREECE_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SCOPE = os.getenv("SCOPE")
USER_ID = os.getenv("USER_ID")


def get_access_token() -> str:
    """Obtain an OAuth2 access token via the client credentials flow."""
    url = f"https://login.microsoftonline.com/{DOVALUEGREECE_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
        "grant_type": "client_credentials",
    }
    response = requests.post(url, data=data, timeout=(10, 30))
    if not response.ok:
        print("Status:", response.status_code)
        try:
            print("Response:", response.json())
        except Exception:
            print("Response:", response.text)
    response.raise_for_status()
    return response.json()["access_token"]


def get_emails(access_token: str) -> list[dict]:
    """
    Fetch all unread, uncategorized inbox messages.

    Returns every qualifying message with the following fields:
        id, subject, from, toRecipients, receivedDateTime,
        body, categories, conversationId, hasAttachments

    Domain-based sender exclusion is applied client-side in main.py via
    EXCLUDE_DOMAINS — the Graph API OData filter does not support endswith/contains
    so per-domain filtering cannot be done server-side.

    Pagination is handled automatically — all pages are collected and returned
    as a single flat list.
    """

    # Rolling 7-day window: always looks back exactly one week from the moment the script runs.
    # e.g. script runs at 09:00 on 2026-08-05 → fetches from 2026-07-29T09:00:00Z up to 2026-08-05T09:00:00Z
    # now = datetime.now(timezone.utc)
    # week_ago = now - timedelta(days=7)
    # now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    # week_ago_str = week_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    # filter_conditions = (
    #     f"isRead eq false and not categories/any() "
    #     f"and receivedDateTime ge {week_ago_str} "
    #     f"and receivedDateTime lt {now_str}"
    # )

    filter_conditions = (
        # "isRead eq false and not categories/any() "
        "receivedDateTime ge 2026-08-03T00:00:00Z "
        "and receivedDateTime lt 2026-08-04T00:00:00Z"
    )

    # hasAttachments is a native Graph field — including it in $select costs nothing
    # extra and lets us skip a separate attachments API call in the main flow.
    email_selection = (
        "id,subject,from,toRecipients,receivedDateTime,"
        "body,categories,conversationId,hasAttachments"
    )
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    params = {"$top": 5, "$filter": filter_conditions, "$select": email_selection}
    url = f"{GRAPH_API_ENDPOINT}/users/{USER_ID}/mailFolders/inbox/messages"

    emails = []
    for page in paginate(url, headers, params):
        emails.extend(page)
    return emails


def get_conversation_thread(access_token: str, conversation_id: str) -> list[dict]:
    """
    Retrieve all messages that share the given conversationId, across ALL mail
    folders (inbox, sent, deleted items, etc.), ordered chronologically
    (oldest first).

    This gives us the complete mail chain for a conversation, regardless of
    which folder each message landed in.

    Pagination is handled automatically.
    """
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    thread_selection = (
        "id,subject,from,toRecipients,receivedDateTime,"
        "body,hasAttachments,conversationId"
    )
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$select": thread_selection,
        "$top": 50,
        # NOTE: $orderby cannot be combined with $filter on the /messages endpoint —
        # the Graph API returns a 400. We sort client-side after collecting all pages.
    }
    # /users/{id}/messages searches across all folders — intentional.
    url = f"{GRAPH_API_ENDPOINT}/users/{USER_ID}/messages"

    messages = []
    for page in paginate(url, headers, params):
        messages.extend(page)

    # Sort chronologically (oldest → newest) so conversation_thread is always
    # in the correct order and reply_to_message_id reliably points to the latest.
    messages.sort(key=lambda m: m.get("receivedDateTime", ""))
    return messages


def copy_message_to_folder(
    access_token: str, message_id: str, destination_folder_id: str
) -> dict:
    """
    Copy a message to a destination mail folder via the Graph API.

    The original message is left completely untouched — it stays unread in the
    inbox exactly as it was. The copy lands in the destination folder.

    POST /users/{userId}/messages/{messageId}/copy
    Body: { "destinationId": "<folder_id>" }

    Returns the Graph API representation of the newly created copy.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    url = f"{GRAPH_API_ENDPOINT}/users/{USER_ID}/messages/{message_id}/copy"
    payload = {"destinationId": destination_folder_id}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def get_attachments(access_token: str, message_id: str) -> list[dict]:
    """Fetch all attachment objects for one message, including file contentBytes.

    The caller persists file attachments and replaces Base64 payloads with local
    paths before exporting enriched email JSON.
    """
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    url = f"{GRAPH_API_ENDPOINT}/users/{USER_ID}/messages/{message_id}/attachments"
    attachments: list[dict] = []
    for page in paginate(url, headers, {"$top": 100}):
        attachments.extend(page)
    return attachments
