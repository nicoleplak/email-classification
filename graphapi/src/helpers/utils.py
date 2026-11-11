import re
import requests
from bs4 import BeautifulSoup


def html_to_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def sanitize_filename(name: str) -> str:
    """Remove or replace characters not allowed in file/folder names."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def clean_body(message: dict) -> str:
    """
    Extract and return plain-text body from a Graph API message dict.
    Handles both 'html' and 'text' contentType values.
    """
    body = message.get("body", {})
    content_type = body.get("contentType", "")
    content = body.get("content", "")
    if content_type == "html":
        return html_to_text(content)
    return content


def paginate(url: str, headers: dict, params: dict = None):
    """
    Generator that handles OData pagination via @odata.nextLink.

    Yields one page of results (a list) at a time.
    The first request uses `url` + `params`; subsequent requests
    follow the @odata.nextLink URL returned by the API (which already
    encodes all query parameters, so params is not forwarded again).

    Usage:
        all_items = []
        for page in paginate(url, headers, params):
            all_items.extend(page)
    """
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    yield data.get("value", [])

    while "@odata.nextLink" in data:
        response = requests.get(data["@odata.nextLink"], headers=headers)
        response.raise_for_status()
        data = response.json()
        yield data.get("value", [])
