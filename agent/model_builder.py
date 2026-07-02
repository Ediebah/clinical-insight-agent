"""Automated dbt model generation + validation (self-healing).

Turns a natural-language data need into a *validated* dbt model:

    1. SPEC     a plain-English need (e.g. "avg medication cost + order count per patient")
    2. DRAFT    the agent writes a dbt model (SELECT over existing ref()s) + schema tests   [LLM]
    3. WRITE    the .sql model + a schema.yml with not_null/unique/… tests
    4. BUILD    `dbt build --select <model>` — compiles, materializes, AND runs the tests
    5. SELF-HEAL if compile/run/test fails, the agent reads the error and rewrites the SQL,   [LLM]
                then rebuilds — up to N attempts
    6. REPORT   the created model, its tests, row count, and green status

Generated files + the table are removed in a `finally` (pass --keep to keep them). Uses the FULL
warehouse (needs the ref-able upstream models).

Run:  .venv/bin/python -m agent.model_builder ["your data need"] [--keep]   (needs OPENAI_API_KEY)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

from . import llm

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / ".venv" / "bin" / "dbt"
WAREHOUSE = ROOT / "warehouse"
DB = ROOT / "data" / "healthcare.duckdb"
MART_DIR = WAREHOUSE / "models" / "marts" / "analytics"
RUN_RESULTS = WAREHOUSE / "target" / "run_results.json"
MAX_TRIES = 3

DEFAULT_NEED = ("A per-patient summary of medication spend: one row per patient with the number of "
                "medication orders and their total and average cost. Test that patient_id is unique "
                "and not null and that total cost is never negative.")


def _dbt(*args) -> subprocess.CompletedProcess:
    return subprocess.run([str(DBT), *args, "--profiles-dir", "."],
                          cwd=WAREHOUSE, capture_output=True, text=True)


def _schema_context() -> str:
    """Compact list of ref-able models + columns so the agent writes valid SQL."""
    con = duckdb.connect(str(DB), read_only=True)
    try:
        rows = con.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='main' and table_name not like 'stg_%' order by table_name").fetchall()
    finally:
        con.close()
    tables: dict[str, list[str]] = {}
    for t, c in rows:
        tables.setdefault(t, []).append(c)
    return "\n".join(f"  {t}({', '.join(cols)})" for t, cols in tables.items())


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    return s if s.startswith("mart_") else f"mart_gen_{s}"


def _draft(need: str, schema: str, prev_sql: str = "", error: str = "") -> dict:
    fix = ""
    if error:
        fix = (f"\nYour previous model FAILED `dbt build`. Fix it.\nPREVIOUS SQL:\n{prev_sql}\n\n"
               f"ERROR / FAILING TEST:\n{error[:1500]}\n")
    return llm.complete_json(
        "You are an analytics engineer writing a dbt model for a DuckDB warehouse. Reference upstream "
        "models ONLY via {{ ref('model_name') }} (never raw table names). Write standard DuckDB SQL. "
        "Choose tests that actually hold for the data.",
        f"DATA NEED: {need}\n\nRef-able models and their columns:\n{schema}\n{fix}\n"
        'Return JSON: {"model_name":"mart_...", "description":"one line", '
        '"sql":"SELECT ... FROM {{ ref(\'...\') }} ...", "pk":"the primary-key column", '
        '"tests":[{"column":"patient_id","checks":["not_null","unique"]},'
        '{"column":"total_cost","checks":["not_null"],"min_value":0}]}. '
        "Test rules: not_null / unique go in `checks`. For a 'never negative' or range constraint use "
        "min_value / max_value (renders as dbt_utils.accepted_range) — do NOT use accepted_values for "
        "numbers. Use accepted_values only for a small fixed set of categories, via \"values\":[...]. "
        "The SQL must return one row per the pk grain.",
    )


def _count_tests(spec: dict) -> int:
    n = 0
    for c in spec.get("tests", []):
        n += len(c.get("checks", []))
        n += 1 if c.get("values") else 0
        n += 1 if ("min_value" in c or "max_value" in c) else 0
    return n


def _schema_yaml(name: str, spec: dict) -> str:
    """Render a dbt schema.yml (model + column tests) from a draft spec. Pure — unit-tested."""
    col_blocks = []
    for c in spec.get("tests", []):
        lines = [f"      - name: {c['column']}", "        data_tests:"]
        for chk in c.get("checks", []):
            if chk in ("not_null", "unique"):
                lines.append(f"          - {chk}")
        if c.get("values"):
            vals = ", ".join(json.dumps(v) for v in c["values"])
            lines += ["          - accepted_values:", "              arguments:",
                      f"                values: [{vals}]"]
        if "min_value" in c or "max_value" in c:
            lines += ["          - dbt_utils.accepted_range:", "              arguments:"]
            if "min_value" in c:
                lines.append(f"                min_value: {c['min_value']}")
            if "max_value" in c:
                lines.append(f"                max_value: {c['max_value']}")
        col_blocks.append("\n".join(lines))
    return (f"version: 2\n\nmodels:\n  - name: {name}\n"
            f"    description: \"{spec.get('description', 'Generated model.')}\"\n"
            f"    columns:\n" + "\n".join(col_blocks) + "\n")


def _write(spec: dict) -> tuple[Path, Path, str]:
    name = _slug(spec["model_name"])
    sql_path = MART_DIR / f"{name}.sql"
    yml_path = MART_DIR / f"_{name}.yml"
    sql_path.write_text(spec["sql"].strip() + "\n")
    yml_path.write_text(_schema_yaml(name, spec))
    return sql_path, yml_path, name


def _failure_text(name: str, build: subprocess.CompletedProcess) -> str | None:
    """Return a human-readable failure (compile error or failing test), or None if all green."""
    if RUN_RESULTS.exists():
        data = json.loads(RUN_RESULTS.read_text())
        bad = [r for r in data.get("results", []) if r["status"] in ("fail", "error")]
        if bad:
            b = bad[0]
            return f"{b['unique_id'].split('.')[-1]}: {b['status']} — {b.get('message') or b.get('failures')}"
    if build.returncode != 0:
        tail = (build.stdout or "") + (build.stderr or "")
        return tail[-1500:].strip() or "dbt build failed"
    return None


def build_model(need: str, keep: bool = False) -> int:
    if not DB.exists():
        print(f"✗ Full warehouse not found at {DB}. Build it first (loader + dbt build).")
        return 1

    print(f"▶ AUTOMATED dbt MODEL BUILDER\n  need: {need}\n")
    schema = _schema_context()
    written: list[Path] = []
    table_name = ""
    try:
        spec, error, prev_sql = None, "", ""
        for attempt in range(1, MAX_TRIES + 1):
            spec = _draft(need, schema, prev_sql, error)
            for p in written:                        # clear any prior attempt's files
                p.unlink(missing_ok=True)
            sql_path, yml_path, table_name = _write(spec)
            written = [sql_path, yml_path]
            label = "DRAFT" if attempt == 1 else f"SELF-HEAL #{attempt - 1}"
            print(f"{attempt}. {label:11} → {table_name}  (pk: {spec.get('pk')}, "
                  f"tests: {_count_tests(spec)})")

            build = _dbt("build", "--select", table_name)
            error = _failure_text(table_name, build) or ""
            prev_sql = spec["sql"]
            if not error:
                break
            print(f"   ✗ {error.splitlines()[0][:120]}")

        if error:
            print(f"\n✗ Could not produce a passing model after {MAX_TRIES} attempts.")
            return 1

        con = duckdb.connect(str(DB), read_only=True)
        try:
            n = con.execute(f"select count(*) from main.{table_name}").fetchone()[0]
        finally:
            con.close()
        n_tests = _count_tests(spec)
        print(f"\n✅ BUILT + VALIDATED  `{table_name}`  ({n:,} rows, {n_tests} passing tests)")
        print(f"   {spec.get('description', '')}")
        print("\n   SQL:")
        for line in spec["sql"].strip().splitlines():
            print(f"     {line}")
        if keep:
            print(f"\n   kept: {written[0].relative_to(ROOT)} (+ schema yml)")
        return 0
    finally:
        if not keep:
            for p in written:
                p.unlink(missing_ok=True)
            if table_name:
                con = duckdb.connect(str(DB))
                try:
                    con.execute(f"drop table if exists main.{table_name}")
                finally:
                    con.close()


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--keep"]
    keep = "--keep" in sys.argv
    need = " ".join(args) if args else DEFAULT_NEED
    return build_model(need, keep=keep)


if __name__ == "__main__":
    raise SystemExit(main())
