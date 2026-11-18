from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd


class DataLoader:
    @staticmethod
    def load_text(path: str) -> str:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"Text file not found: {source}")
        return source.read_text(encoding="utf-8")

    @staticmethod
    def load_json(path: str) -> Any:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(f"JSON file not found: {source}")
        try:
            return json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {source}: {exc}") from exc

    @staticmethod
    def load_registry_df(csv_path: str) -> pd.DataFrame:
        source = Path(csv_path)
        if not source.is_file():
            raise FileNotFoundError(f"Registry CSV not found: {source}")

        df = pd.read_csv(
            source, sep=";", dtype=str, encoding="utf-8-sig", engine="python"
        ).fillna("")
        required = {
            "TAX_ID_NO",
            "SOURCE",
            "CST_STS_NM",
            "CST_UNQ_CD",
            "PRTFL_CD",
            "ACC_UNQ_CD",
        }
        missing = sorted(required.difference(df.columns))

        if missing:
            raise ValueError(
                "Registry is missing required columns: " + ", ".join(missing)
            )
        df["TAX_ID_NO"] = (
            df["TAX_ID_NO"].str.strip().str.replace("\ufeff", "", regex=False)
        )
        return df
