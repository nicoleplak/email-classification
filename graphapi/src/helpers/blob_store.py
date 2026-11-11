"""Blob uploads for the Graph step; same settings as the classifier's blob_output."""

import os
from functools import lru_cache

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


def enabled() -> bool:
    return os.getenv("UPLOAD_RESULTS_TO_BLOB", "false").lower() == "true"


@lru_cache(maxsize=1)
def _container():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        # Local/VDI runs: user identities have no blob data role on the account.
        service = BlobServiceClient.from_connection_string(connection_string)
    else:
        account = os.environ["RESULT_STORAGE_ACCOUNT"]
        service = BlobServiceClient(
            account_url=f"https://{account}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )
    return service.get_container_client(os.environ["RESULT_CONTAINER"])


def upload(data: bytes, blob_name: str) -> bool:
    """Upload bytes; False if the blob already exists."""
    try:
        _container().upload_blob(blob_name, data)
    except ResourceExistsError:
        return False
    return True
