"""Safe, read-only query execution against the DuckDB warehouse.

Guardrails (the spec's "agent can't run destructive or runaway SQL"):
  1. Engine-level: the connection is opened read_only=True — DuckDB itself rejects any write.
  2. Statement-level: we validate the SQL is a single SELECT/WITH with no write keywords.
  3. Runaway-level: results are capped by wrapping the query in an outer LIMIT.

On any validation or execution error we raise QueryError with a clear message — the agent
feeds that message back to the model to self-heal.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time
from pathlib import Path

import duckdb
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _resolve_db_path() -> Path:
    """Full warehouse locally; committed slim demo DB on deploy (where the full one is absent).
    Override with the WAREHOUSE_DB env var."""
    if os.getenv("WAREHOUSE_DB"):
        return Path(os.environ["WAREHOUSE_DB"])
    full = _DATA_DIR / "healthcare.duckdb"
    return full if full.exists() else _DATA_DIR / "healthcare_demo.duckdb"


DB_PATH = _resolve_db_path()
MAX_ROWS = 1000
_AUDIT_LOG = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"


def _audit(sql: str, rows: int, ms: float) -> None:
    """Append every executed query to a read-only audit trail (logs/ is git-ignored)."""
    try:
        _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": _dt.datetime.now().isoformat(timespec="seconds"),
               "rows": rows, "ms": round(ms, 1), "sql": sql}
        with _AUDIT_LOG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass

# Whole-word write/DDL keywords that must never appear in an analytics query.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|replace|truncate|attach|detach|copy|"
    r"install|load|pragma|export|import|call|set|vacuum|checkpoint)\b",
    re.IGNORECASE,
)


class QueryError(Exception):
    """Raised on validation failure or a DuckDB execution error."""


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)          # line comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)  # block comments
    return sql


def _strip_literals(sql: str) -> str:
    """Blank out string/identifier literal CONTENTS so keyword/';' scanning ignores them
    (e.g. ILIKE '%NURSE ON CALL%' must not trip the 'call' keyword). The read-only engine is the
    real guard against writes; this scan only rejects obvious multi-statement / DDL attempts."""
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)   # single-quoted strings (with '' escape)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)   # double-quoted identifiers
    return sql


def validate(sql: str) -> str:
    """Return a cleaned, validated single-statement SELECT/WITH, or raise QueryError."""
    if not sql or not sql.strip():
        raise QueryError("Empty query.")
    cleaned = sql.strip().rstrip(";").strip()
    body = _strip_sql_comments(cleaned)
    scan = _strip_literals(body)                 # scan ignores string-literal contents
    if ";" in scan:
        raise QueryError("Only a single statement is allowed (found ';').")
    if not re.match(r"^\s*(select|with)\b", body, re.IGNORECASE):
        raise QueryError("Only read-only SELECT/WITH queries are allowed.")
    if _FORBIDDEN.search(scan):
        bad = _FORBIDDEN.search(scan).group(0)
        raise QueryError(f"Write/DDL keyword '{bad}' is not permitted.")
    return cleaned


def run_query(sql: str, max_rows: int = MAX_ROWS, db_path: Path | None = None) -> pd.DataFrame:
    """Validate + execute read-only, capped at max_rows. Returns a DataFrame or raises QueryError.
    db_path overrides the warehouse (used for user-uploaded 'bring your own data' sessions)."""
    cleaned = validate(sql)
    path = Path(db_path) if db_path else DB_PATH
    if not path.exists():
        raise QueryError(f"Warehouse not found at {path}. Run the loader + `dbt build` first.")
    wrapped = f"select * from (\n{cleaned}\n) as _agent_q limit {max_rows}"
    t0 = time.perf_counter()
    try:
        con = duckdb.connect(str(path), read_only=True)
        try:
            df = con.execute(wrapped).df()
        finally:
            con.close()
    except QueryError:
        raise
    except Exception as e:  # noqa: BLE001 — surface the DB message to the self-heal loop
        raise QueryError(str(e)) from e
    _audit(cleaned, len(df), (time.perf_counter() - t0) * 1000)
    return df


if __name__ == "__main__":
    df = run_query("select encounter_class, count(*) n from fct_encounters group by 1 order by n desc")
    print(df.to_string(index=False))
