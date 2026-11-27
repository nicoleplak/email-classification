"""Run the warehouse export by hand (the job runs it after each classification when DWH_EXPORT_ENABLED=true).

    python tools/dwh_export.py                 # emails changed since the last export → gold/dwh/ (LOCAL_BLOB_DIR or Azure)
    python tools/dwh_export.py --full          # every email, e.g. the first load
    python tools/dwh_export.py --since 2026-11-20T00:00:00Z
    python tools/dwh_export.py --out exports\\dwh   # write the CSV files to a folder instead of blob storage

Reads LOCAL_STORE_DIR / CASE_STORE and LOCAL_BLOB_DIR from .env, like the classifier. An export with --out leaves
the watermark where it was, so the next real export still sends those emails.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "AI_email_classifier"))

if os.getenv("CI", "").strip().lower() not in {"1", "true", "yes"}:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true", help="every classified email, not only the changed ones")
    parser.add_argument("--since", help="emails changed since this UTC time (ISO), instead of the last export")
    parser.add_argument("--out", help="write the files to this folder; the watermark is not moved")
    args = parser.parse_args()

    from core import dwh_export
    from data.case_store import open_store

    store = open_store()
    if args.out:
        folder = Path(args.out)

        def upload(name: str, data: bytes) -> None:
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        class Keep:  # reads go to the real store; the watermark write is dropped
            def __getattr__(self, name):
                return getattr(store, name)

            def upsert(self, collection, doc):
                return doc

        summary = dwh_export.export(Keep(), upload, full=args.full, since=args.since)
    else:
        from data import blob_output

        summary = dwh_export.export(store, blob_output.upload_bytes, full=args.full, since=args.since)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
