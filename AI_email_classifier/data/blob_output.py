import os
from functools import lru_cache
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


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


def download(blob_name: str) -> bytes:
    return _container().download_blob(blob_name).readall()


def download_to(blob_name: str, path: str | Path) -> None:
    """Stream to disk: the registry CSV is ~170 MB, no need to hold it twice."""
    with open(path, "wb") as target:
        _container().download_blob(blob_name).readinto(target)


def list_names(prefix: str) -> list[str]:
    return sorted(blob.name for blob in _container().list_blobs(name_starts_with=prefix))


def upload_bytes(blob_name: str, data: bytes) -> None:
    # Silver is derived data and can be rebuilt, so overwriting is safe.
    _container().upload_blob(blob_name, data, overwrite=True)


def upload_result_file(local_path: str, blob_name: str) -> None:
    source = Path(local_path)

    if not source.is_file():
        raise FileNotFoundError(f"Result file not found: {source}")

    with source.open("rb") as data:
        _container().upload_blob(blob_name, data, overwrite=False)
