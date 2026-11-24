"""Copy a sample of real emails from the Azure container to a local folder, for testing on a laptop.

    python tools/fetch_sample.py                      # newest ingest run, all its emails
    python tools/fetch_sample.py --runs 3 --limit 20  # the 3 newest runs, at most 20 emails each
    python tools/fetch_sample.py --run 20261120T080000Z
    python tools/fetch_sample.py --registry           # also the newest in/qualco_output_*.csv (~170 MB)

Copies, with the same names, into LOCAL_BLOB_DIR (default local_data/blob):
  bronze/<run>/emails.json        the run's emails (only the ones kept, with --limit)
  messages/..., attachments/...   the original email and the attachments each kept email points to
  in/qualco_output_<date>.csv     the customer registry, with --registry (else use the invented one or REGISTRY_CSV)
Then the classifier and the review app run on that folder with LOCAL_BLOB_DIR set, and Azure is not touched.

Read-only on Azure: it only lists and downloads. Connection, first that is set:
  AZURE_STORAGE_CONNECTION_STRING, or STG_KEY (account key) with RESULT_STORAGE_ACCOUNT, or your az login.
The copy is client data: keep it on your machine (local_data/ is git-ignored) and delete it when done.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_FILE = re.compile(r"^bronze/([^/]+)/emails\.json$")


def container_client():
    from azure.storage.blob import ContainerClient

    name = os.getenv("RESULT_CONTAINER", "email-classification")
    if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        return ContainerClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"], name)
    url = f"https://{os.getenv('RESULT_STORAGE_ACCOUNT', 'datallmdev')}.blob.core.windows.net"
    if os.getenv("STG_KEY"):
        return ContainerClient(url, name, credential=os.environ["STG_KEY"])
    from azure.identity import AzureCliCredential

    return ContainerClient(url, name, credential=AzureCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID")))


def referenced(message: dict) -> list[str]:
    """Every blob one email points to: its original (.eml/.msg) and its attachments."""
    names = [message.get("eml_blob_path"), message.get("msg_blob_path")]
    names += [a.get("blob_name") for a in message.get("attachments") or []]
    return [n for n in names if n]


def fetch(client, dest: Path, runs: list[str] | None = None, newest: int = 1, limit: int = 0,
          registry: bool = False, requests: bool = False, log=print) -> dict:
    """Copy runs (named, or the newest ones) and what their emails point to into dest. Returns counts."""
    def save(name: str, data: bytes) -> None:
        path = (dest / name).resolve()
        if dest.resolve() not in path.parents:
            raise ValueError(f"blob name outside the folder: {name!r}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def download(name: str) -> bytes:
        return client.download_blob(name).readall()

    if not runs:
        found = sorted({m.group(1) for b in client.list_blobs(name_starts_with="bronze/") if (m := RUN_FILE.match(b.name))})
        runs = found[-newest:] if newest else found
    totals = {"runs": 0, "emails": 0, "files": 0, "missing": 0}
    for run in runs:
        raw = json.loads(download(f"bronze/{run}/emails.json"))
        messages = raw.get("messages", []) if isinstance(raw, dict) else raw
        kept = messages[:limit] if limit else messages
        for message in kept:
            for name in referenced(message):
                try:
                    save(name, download(name))
                    totals["files"] += 1
                except Exception as exc:  # noqa: BLE001 - a missing attachment must not stop the copy
                    totals["missing"] += 1
                    log(f"  not copied: {name} ({type(exc).__name__})")
        body = {"messages": kept, "removed": raw.get("removed", []) if isinstance(raw, dict) else []}
        save(f"bronze/{run}/emails.json", json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8"))
        totals["runs"] += 1
        totals["emails"] += len(kept)
        log(f"bronze/{run}: {len(kept)} of {len(messages)} emails")
    for prefix, wanted in (("in/qualco_output_", registry), ("in/request_output_", requests)):
        if not wanted:
            continue
        names = sorted(b.name for b in client.list_blobs(name_starts_with=prefix) if b.name.endswith(".csv"))
        if names:
            log(f"{names[-1]}: downloading (large file)")
            save(names[-1], download(names[-1]))
            totals["files"] += 1
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", action="append", help="a run to copy (bronze/<run>/); repeat for several")
    parser.add_argument("--runs", type=int, default=1, help="how many of the newest runs (default 1; 0 = all)")
    parser.add_argument("--limit", type=int, default=0, help="at most this many emails per run (0 = all)")
    parser.add_argument("--registry", action="store_true", help="also the newest customer registry CSV")
    parser.add_argument("--requests", action="store_true", help="also the newest request_output CSV (~570 MB)")
    args = parser.parse_args()
    dest = Path(os.getenv("LOCAL_BLOB_DIR") or ROOT / "local_data" / "blob")
    totals = fetch(container_client(), dest, args.run, args.runs, args.limit, args.registry, args.requests)
    print(f"\nCopied {totals['emails']} emails from {totals['runs']} run(s), {totals['files']} files"
          f"{', ' + str(totals['missing']) + ' missing' if totals['missing'] else ''} into {dest}")
    print("Classify them (keys in your .env), then open the review app; see docs/LOCAL_TESTING.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
