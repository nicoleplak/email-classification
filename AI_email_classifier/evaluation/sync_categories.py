"""Sync inputs/categories.json with the business spec (Record_Creation_Criteria).

    python evaluation/sync_categories.py

Updates each category's rules, priority, outgoing emails, actions and comments,
and appends categories that are new in the spec. It leaves routing fields alone
and keeps config-only categories (it lists them). Re-run after each spec update,
then re-run the evaluation: changed definitions change the results.
"""

from __future__ import annotations

import json
from typing import Any

from common import APP_DIR, _clean, spec_rows

PATH = APP_DIR / "inputs" / "categories.json"
TEXT_FIELDS = ("Rules/Λέξεις κλειδιά", "Outgoing Emails", "Actions", "comments")


def _raw(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def main() -> None:
    config = json.loads(PATH.read_text(encoding="utf-8"))
    spec = spec_rows()
    seen, changed = set(), []
    for index, item in enumerate(config):
        key = _clean(item["Categories"]).lower()
        record = spec.get(key)
        if record is None:
            continue
        seen.add(key)
        new = {**item, **{f: _raw(record.get(f)) for f in TEXT_FIELDS}}
        if record.get("Priority") not in (None, ""):
            new["Priority"] = float(record["Priority"])
        if new != item:
            changed.append(item["Categories"].strip())
        config[index] = new
    added = []
    for key, record in spec.items():
        if key in seen:
            continue
        name = _clean(record["Categories"])
        added.append(name)
        config.append(
            {
                "Categories": name,
                "Priority": float(record["Priority"])
                if record.get("Priority")
                else None,
                **{f: _raw(record.get(f)) for f in TEXT_FIELDS},
                "Παραπομπές wizard/portal": None,
            }
        )
    PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"updated {len(changed)}, added {len(added)}, total {len(config)}")
    print("added:", added)
    print(
        "config-only:",
        [
            c["Categories"]
            for c in config
            if _clean(c["Categories"]).lower() not in spec
        ],
    )


if __name__ == "__main__":
    main()
