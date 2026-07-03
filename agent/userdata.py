"""Bring-your-own-data: register an uploaded table so the SAME agent can query + model it.

Given a pandas DataFrame we (1) sanitize identifiers, (2) materialize it as a table in a fresh,
session-scoped DuckDB file, and (3) build a semantic-catalog dict of the same shape the RAG layer
expects. `run_analysis(question, catalog=..., db_path=...)` then runs the full pipeline — SQL,
guardrail, and every model (A/B, non-inferiority, regression, survival, …) — over the user's data.

The catalog carries no PHI to disk; only column names + a few example values reach the LLM at
query time, so the UI must warn users to upload non-sensitive data only on the public deploy.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

MAX_ROWS = 200_000
MAX_COLS = 60


def _sanitize(name: str, fallback: str = "col") -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()
    if not s:
        s = fallback
    if s[0].isdigit():
        s = f"c_{s}"
    return s[:40]


def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to safe snake_case identifiers (dedup collisions) so generated SQL needs no quoting."""
    df = df.iloc[:, :MAX_COLS].copy()
    seen: dict[str, int] = {}
    out = []
    for c in df.columns:
        base = _sanitize(c)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(base if n == 0 else f"{base}_{n}")
    df.columns = out
    return df


def build_catalog(df: pd.DataFrame, table: str) -> dict:
    """A one-table catalog dict shaped exactly like the RAG layer's semantic_catalog.json."""
    columns = []
    for c in df.columns:
        s = df[c]
        examples = [str(v)[:28] for v in pd.unique(s.dropna())[:3]]
        columns.append({"name": c, "type": str(s.dtype), "description": "", "example_values": examples})
    table_doc = {
        "name": table,
        "description": f"User-uploaded dataset — {len(df):,} rows, {len(df.columns)} columns.",
        "primary_key": [],
        "foreign_keys": [],
        "columns": columns,
    }
    return {"tables": [table_doc], "metrics": []}


def prepare_upload(df: pd.DataFrame, filename: str = "user_data") -> tuple[Path, dict, str, pd.DataFrame]:
    """Materialize the DataFrame as a DuckDB table and return (db_path, catalog, table_name, cleaned_df)."""
    df = sanitize_columns(df).head(MAX_ROWS)
    table = _sanitize(Path(str(filename)).stem, fallback="user_data")
    db_path = Path(tempfile.mkdtemp(prefix="byod_")) / "data.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.register("_uploaded", df)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM _uploaded")
        con.unregister("_uploaded")
    finally:
        con.close()
    return db_path, build_catalog(df, table), table, df
