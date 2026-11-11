"""Blob uploads for the Graph step; same settings as the classifier's blob_output."""

import os
from functools import lru_cache

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


def enabled() -> bool:
    return os.getenv("UPLOAD_RESULTS_TO_BLOB", "false").lower() == "true"


@lru_cache(maxsize=1)
def _container():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

    if connection_string:
        # Local/VDI runs: use the configured storage connection string.
        service = BlobServiceClient.from_connection_string(
            connection_string
        )
    else:
        # Container/cloud runs: use managed identity.
        account = os.environ["RESULT_STORAGE_ACCOUNT"]

        service = BlobServiceClient(
            account_url=f"https://{account}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )

    return service.get_container_client(
        os.environ["RESULT_CONTAINER"]
    )


def upload(
    data: bytes,
    blob_name: str,
    *,
    overwrite: bool = False,
) -> bool:
    """
    Upload bytes to Blob Storage.

    overwrite=False:
        Preserve the previous behaviour. If the blob already exists,
        return False.

    overwrite=True:
        Replace the existing blob. This is required for idempotent
        Graph delta retries.
    """
    try:
        _container().upload_blob(
            name=blob_name,
            data=data,
            overwrite=overwrite,
        )
    except ResourceExistsError:
        return False

    return True


def download(blob_name: str) -> bytes | None:
    """
    Download bytes from Blob Storage.

    Returns None when the blob does not exist. This allows the Graph
    code to distinguish an initial delta bootstrap from a resumed run.
    """
    try:
        return (
            _container()
            .download_blob(blob_name)
            .readall()
        )
    except ResourceNotFoundError:
        return None