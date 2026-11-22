"""Blob uploads for the Graph step; same settings as the classifier's blob_output.

``LOCAL_BLOB_DIR`` set: everything is written to and read from that folder instead of Azure, in the same
layout, so an ingest run can be tried without touching the shared storage account.
"""

import os
from functools import lru_cache
from pathlib import Path


def enabled() -> bool:
    return os.getenv("UPLOAD_RESULTS_TO_BLOB", "false").lower() == "true"


def _local_root() -> Path | None:
    root = os.getenv("LOCAL_BLOB_DIR", "").strip()
    return Path(root).resolve() if root else None


def _local_path(root: Path, blob_name: str) -> Path:
    path = (root / blob_name).resolve()
    if root not in path.parents:
        raise ValueError(f"blob name outside the local container: {blob_name!r}")
    return path


@lru_cache(maxsize=1)
def _container():
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

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
    root = _local_root()
    if root:
        path = _local_path(root, blob_name)
        if path.exists() and not overwrite:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return True

    from azure.core.exceptions import ResourceExistsError

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
    root = _local_root()
    if root:
        path = _local_path(root, blob_name)
        return path.read_bytes() if path.is_file() else None

    from azure.core.exceptions import ResourceNotFoundError

    try:
        return (
            _container()
            .download_blob(blob_name)
            .readall()
        )
    except ResourceNotFoundError:
        return None
