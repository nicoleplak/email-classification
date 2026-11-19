from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd
from config import settings


def _excel_safe(value: Any) -> Any:
    return (
        json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, (dict, list, tuple, set))
        else value
    )


class DataSaver:
    @staticmethod
    def save_json(data, path=None):

        target = Path(path or settings.summary_json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        print(f"JSON saved to: {target}")

    @staticmethod
    def save_excel(data, path=None):
        target = Path(path or settings.summary_excel_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        pd.DataFrame(data).map(_excel_safe).to_excel(
            target, index=False, engine="openpyxl"
        )
        print(f"Excel saved to: {target}")
