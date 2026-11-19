"""Where cases, the audit log, locks, users and processed-run markers live.

Cosmos DB in Azure (database EmailClassification in cosmos-db-data-llm-dev); a folder of JSON files for
local runs and tests. Both give every document an ``_etag``: ``replace`` only succeeds when the caller's
etag is still current, so a slow writer (the classifier) never overwrites a reviewer's save.

Containers and partition keys: cases, runs, users, locks on /id; audit on /caseId (it is only ever read
per case). Lock documents carry ``ttl`` (seconds) and expire on their own in Cosmos.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

COLLECTIONS = ("cases", "audit", "runs", "locks", "users")
PARTITION = {"audit": "caseId"}  # everything else: /id


class Conflict(Exception):
    """The document changed (or already exists) since the caller read it."""


def _pick(doc: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    return {k: doc.get(k) for k in fields} if fields else doc


class LocalStore:
    # ponytail: one JSON file per document, full scan for find()/all(); fine for dev data.
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
        tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
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

    def upsert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self._write(collection, doc)

    def delete(self, collection: str, doc_id: str) -> None:
        self._path(collection, doc_id).unlink(missing_ok=True)

    def all(self, collection: str, fields: list[str] | None = None) -> list[dict[str, Any]]:
        return [
            _pick(json.loads(p.read_text(encoding="utf-8")), fields)
            for p in sorted((self.root / collection).glob("*.json"))
        ]

    def find(self, collection: str, field: str, value: Any) -> list[dict[str, Any]]:
        return [d for d in self.all(collection) if d.get(field) == value]


class CosmosStore:
    def __init__(self, endpoint: str, database: str, credential=None):
        # Imported here so local runs and tests need no Cosmos SDK.
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        # Entra (managed identity in Azure, your az login locally); no account keys.
        client = CosmosClient(endpoint, credential=credential or DefaultAzureCredential())
        db = client.get_database_client(database)
        self._containers = {name: db.get_container_client(name) for name in COLLECTIONS}

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        if collection in PARTITION:
            raise ValueError(f"{collection} is partitioned by {PARTITION[collection]}; use find()")
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
        from azure.cosmos.exceptions import CosmosAccessConditionFailedError, CosmosResourceNotFoundError

        try:
            return self._containers[collection].replace_item(
                doc["id"], doc, etag=doc["_etag"], match_condition=MatchConditions.IfNotModified
            )
        except (CosmosAccessConditionFailedError, CosmosResourceNotFoundError) as exc:
            raise Conflict(f"{collection}/{doc['id']} changed since it was read") from exc

    def upsert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        return self._containers[collection].upsert_item(doc)

    def delete(self, collection: str, doc_id: str) -> None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            self._containers[collection].delete_item(doc_id, partition_key=doc_id)
        except CosmosResourceNotFoundError:
            pass

    def all(self, collection: str, fields: list[str] | None = None) -> list[dict[str, Any]]:
        for name in fields or []:
            if not name.isidentifier():
                raise ValueError(f"Unsafe field name: {name!r}")
        select = ", ".join(f"c.{name}" for name in fields) if fields else "*"
        return list(
            self._containers[collection].query_items(
                f"SELECT {select} FROM c", enable_cross_partition_query=True
            )
        )

    def find(self, collection: str, field: str, value: Any) -> list[dict[str, Any]]:
        if not field.isidentifier():
            raise ValueError(f"Unsafe field name: {field!r}")
        on_partition = PARTITION.get(collection, "id") == field
        return list(
            self._containers[collection].query_items(
                f"SELECT * FROM c WHERE c.{field} = @value",
                parameters=[{"name": "@value", "value": value}],
                **({"partition_key": value} if on_partition else {"enable_cross_partition_query": True}),
            )
        )


def open_store() -> LocalStore | CosmosStore:
    """``CASE_STORE=cosmos`` in Azure; anything else is a local folder (``LOCAL_STORE_DIR``)."""
    if os.getenv("CASE_STORE", "local").strip().lower() == "cosmos":
        credential = None
        if os.getenv("AZURE_CLI_SUBSCRIPTION"):  # local runs: your az login, pinned to the right subscription
            from azure.identity import AzureCliCredential

            credential = AzureCliCredential(subscription=os.environ["AZURE_CLI_SUBSCRIPTION"])
        return CosmosStore(
            os.environ["COSMOS_ENDPOINT"],
            os.getenv("COSMOS_DATABASE", "EmailClassification"),
            credential,
        )
    return LocalStore(os.getenv("LOCAL_STORE_DIR", "case_store"))
