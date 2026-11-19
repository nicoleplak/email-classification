import os
import struct

import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential


SQL_COPT_SS_ACCESS_TOKEN = 1256

COLUMNS = [
    "BUSINESSPR",
    "CST_ID",
    "CST_UNQ_CD",
    "PRTFL_CD",
    "PRTFL_NM",
    "NAME",
    "TAX_ID_NO",
    "ACC_ID",
    "ACC_UNQ_CD",
    "ASST_CLS",
    "ACC_TP_NM",
    "SRV_ACC_UNQ_CD",
    "CST_STS_NM",
    "ASSIGNED",
    "SETL_STS_NM",
    "PORTAL_FLAG",
    "SOURCE",
]

REQUIRED = {
    "TAX_ID_NO",
    "SOURCE",
    "CST_STS_NM",
    "CST_UNQ_CD",
    "PRTFL_CD",
    "ACC_UNQ_CD",
}


def load_registry_from_synapse() -> pd.DataFrame:
    server = os.getenv("SYNAPSE_SERVER", "dwhgruatsyn.sql.azuresynapse.net")
    driver = os.getenv("SYNAPSE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    database = os.getenv("SYNAPSE_DATABASE", "dwhuat")

    token = (
        DefaultAzureCredential()
        .get_token("https://database.windows.net/.default")
        .token
    )
    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack("<I", len(token_bytes)) + token_bytes

    connection_string = (
        f"Driver={{{driver}}};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

    query = f"""
        SELECT {", ".join(f"[{column}]" for column in COLUMNS)}
        FROM [LLM].[EMCLF_ACC_OUTPUT]
    """

    with pyodbc.connect(
        connection_string,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        timeout=30,
    ) as connection:
        cursor = connection.cursor()
        cursor.execute(query)

        # Preserve the CSV loader's string-based DataFrame contract.
        rows = []
        while batch := cursor.fetchmany(10_000):
            rows.extend(
                tuple("" if value is None else str(value) for value in row)
                for row in batch
            )

    df = pd.DataFrame(rows, columns=COLUMNS)

    missing = sorted(REQUIRED.difference(df.columns))
    if missing:
        raise ValueError("Registry is missing required columns: " + ", ".join(missing))

    df["TAX_ID_NO"] = df["TAX_ID_NO"].str.strip().str.replace("\ufeff", "", regex=False)
    return df
