"""The email-classification blob container: Azure Blob Storage, or a local folder for offline work.

Set ``LOCAL_BLOB_DIR`` to a folder and every read and write goes there instead of Azure, with the same
layout (``bronze/``, ``messages/``, ``attachments/``, ``silver/``, ``in/``). Nothing then needs a storage
account, a connection string or a login. Leave it unset in Azure.
"""

import os
from functools import lru_cache
from pathlib import Path


def local_root() -> Path | None:
    """The folder that stands in for the container, or None to use Azure."""
    root = os.getenv("LOCAL_BLOB_DIR", "").strip()
    return Path(root).resolve() if root else None


def local_path(root: Path, blob_name: str) -> Path:
    """Where a blob lives under ``root``; refuses names that would leave the folder."""
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
    root = local_root()
    if root:
        return local_path(root, blob_name).read_bytes()  # FileNotFoundError when missing
    return _container().download_blob(blob_name).readall()


def download_to(blob_name: str, path: str | Path) -> None:
    """Stream to disk: the registry CSV is ~170 MB, no need to hold it twice."""
    root = local_root()
    with open(path, "wb") as target:
        if root:
            with local_path(root, blob_name).open("rb") as source:
                while chunk := source.read(1 << 20):
                    target.write(chunk)
        else:
            _container().download_blob(blob_name).readinto(target)


def list_names(prefix: str) -> list[str]:
    root = local_root()
    if root:
        if not root.is_dir():
            return []
        names = (p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
        return sorted(n for n in names if n.startswith(prefix) and not n.endswith(".tmp"))
    return sorted(blob.name for blob in _container().list_blobs(name_starts_with=prefix))


def _write_local(blob_name: str, data: bytes, overwrite: bool) -> bool:
    path = local_path(local_root(), blob_name)
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return True


def upload_bytes(blob_name: str, data: bytes) -> None:
    # Silver is derived data and can be rebuilt, so overwriting is safe.
    if local_root():
        _write_local(blob_name, data, overwrite=True)
        return
    _container().upload_blob(blob_name, data, overwrite=True)


def upload_result_file(source_path: str, blob_name: str) -> None:
    source = Path(source_path)

    if not source.is_file():
        raise FileNotFoundError(f"Result file not found: {source}")

    if local_root():
        if not _write_local(blob_name, source.read_bytes(), overwrite=False):
            raise FileExistsError(f"Blob already exists: {blob_name}")
        return
    with source.open("rb") as data:
        _container().upload_blob(blob_name, data, overwrite=False)
