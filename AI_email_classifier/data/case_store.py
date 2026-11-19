"""Where cases, the audit log and processed-run markers live.

Cosmos DB in Azure; a folder of JSON files for local runs and tests.
Both stores give every document an ``_etag``. ``replace`` only succeeds when the
caller's etag is still current, so a slow writer (the classifier) can never
overwrite a save that happened while it was working (a reviewer).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

COLLECTIONS = ("cases", "audit", "runs")


class Conflict(Exception):
    """The document changed (or already exists) since the caller read it."""


class LocalStore:
    # ponytail: one JSON file per document, full scan for find(); fine for dev data.
    def __init__(self, root: str | Path):
        self.root = Path(root)
        for name in COLLECTIONS:
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def _path(self, collection: str, doc_id: str) -> Path:
        return self.root / collection / f"{doc_id}.json"

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        path = self._path(collection, doc_id)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def _write(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        doc = {**doc, "_etag": uuid.uuid4().hex}
        path = self._path(collection, doc["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return doc

    def create(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        if self._path(collection, doc["id"]).exists():
            raise Conflict(f"{collection}/{doc['id']} already exists")
        return self._write(collection, doc)

    def replace(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        current = self.get(collection, doc["id"])
        if current is None or current.get("_etag") != doc.get("_etag"):
            raise Conflict(f"{collection}/{doc['id']} changed since it was read")
        return self._write(collection, doc)

    def find(self, collection: str, field: str, value: Any) -> list[dict[str, Any]]:
        docs = (
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((self.root / collection).glob("*.json"))
        )
        return [d for d in docs if d.get(field) == value]


class CosmosStore:
    """Containers ``cases``, ``audit``, ``runs``, each partitioned on ``/id``."""

    def __init__(self, endpoint: str, database: str):
        # Imported here so local runs and tests need no Cosmos SDK.
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        # Keys are disabled on the account: Entra (managed identity) only.
        db = CosmosClient(endpoint, credential=DefaultAzureCredential()).get_database_client(database)
        self._containers = {name: db.get_container_client(name) for name in COLLECTIONS}

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            return self._containers[collection].read_item(doc_id, partition_key=doc_id)
        except CosmosResourceNotFoundError:
            return None

    def create(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        from azure.cosmos.exceptions import CosmosResourceExistsError

        try:
            return self._containers[collection].create_item(doc)
        except CosmosResourceExistsError as exc:
            raise Conflict(f"{collection}/{doc['id']} already exists") from exc

    def replace(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        from azure.core import MatchConditions
        from azure.cosmos.exceptions import CosmosAccessConditionFailedError

        try:
            return self._containers[collection].replace_item(
                doc["id"], doc, etag=doc["_etag"], match_condition=MatchConditions.IfNotModified
            )
        except CosmosAccessConditionFailedError as exc:
            raise Conflict(f"{collection}/{doc['id']} changed since it was read") from exc

    def find(self, collection: str, field: str, value: Any) -> list[dict[str, Any]]:
        if not field.isidentifier():
            raise ValueError(f"Unsafe field name: {field!r}")
        return list(
            self._containers[collection].query_items(
                f"SELECT * FROM c WHERE c.{field} = @value",
                parameters=[{"name": "@value", "value": value}],
                enable_cross_partition_query=True,
            )
        )


def open_store() -> LocalStore | CosmosStore:
    """``CASE_STORE=cosmos`` in Azure; anything else is a local folder (``LOCAL_STORE_DIR``)."""
    if os.getenv("CASE_STORE", "local").strip().lower() == "cosmos":
        return CosmosStore(
            os.environ["COSMOS_ENDPOINT"],
            os.getenv("COSMOS_DATABASE", "EmailClassification"),
        )
    return LocalStore(os.getenv("LOCAL_STORE_DIR", "case_store"))
