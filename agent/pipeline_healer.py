"""Self-healing pipeline demo.

Extends "self-healing" from a single query to the data pipeline:

    1. INJECT   a data defect into a mart (duplicate a primary key in dim_patient)
    2. DETECT   run `dbt test` — the `unique` test catches it
    3. DIAGNOSE the agent reads the failure + failing rows and proposes a root-cause fix   [LLM]
    4. REPAIR   rebuild the model (`dbt run`) — the fix restores the grain
    5. VERIFY   `dbt test` is green again

Uses the FULL warehouse (needs the `raw` schema to rebuild). Restore runs in a `finally`, so the
warehouse is left clean even if a step fails.

Run:  .venv/bin/python -m agent.pipeline_healer     (needs OPENAI_API_KEY in agent/.env)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import duckdb

from . import llm

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / ".venv" / "bin" / "dbt"
WAREHOUSE = ROOT / "warehouse"
DB = ROOT / "data" / "healthcare.duckdb"
RUN_RESULTS = WAREHOUSE / "target" / "run_results.json"

MODEL = "dim_patient"
PK = "patient_id"


def _dbt(*args) -> subprocess.CompletedProcess:
    return subprocess.run([str(DBT), *args, "--profiles-dir", "."],
                          cwd=WAREHOUSE, capture_output=True, text=True)


def _test_failures(model: str) -> list[dict]:
    """Run `dbt test` for a model; return the failing tests from run_results.json."""
    _dbt("test", "--select", model)
    if not RUN_RESULTS.exists():
        return []
    data = json.loads(RUN_RESULTS.read_text())
    return [{"name": r["unique_id"].split(".")[-1], "status": r["status"],
             "failures": r.get("failures"), "message": r.get("message")}
            for r in data.get("results", []) if r["status"] in ("fail", "error")]


def _preflight() -> str | None:
    if not DB.exists():
        return f"Full warehouse not found at {DB}. Build it first (loader + `dbt build`)."
    con = duckdb.connect(str(DB), read_only=True)
    try:
        schemas = {r[0] for r in con.execute(
            "select schema_name from information_schema.schemata").fetchall()}
    finally:
        con.close()
    if "raw" not in schemas or "main" not in schemas:
        return "This demo needs the FULL warehouse (raw + main). The slim demo DB can't be rebuilt."
    return None


def _diagnose(test_name: str, dup_pk: str, dup_count: int) -> dict:
    return llm.complete_json(
        "You are a data-reliability engineer. A dbt test failed on a modeled warehouse table. "
        "Diagnose the most likely root cause and propose a concrete, minimal fix.",
        f"dbt test FAILED:\n"
        f"  test: {test_name} — a `unique` test on column `{PK}`\n"
        f"  model: {MODEL} (grain: one row per patient; primary key `{PK}`)\n"
        f"  failing data: `{PK}` = {dup_pk} appears {dup_count} times (grain violated).\n\n"
        "Diagnose the root cause and propose a concrete fix (SQL or dbt-model change) plus a "
        'prevention step. Return JSON: {"root_cause": "...", "fix": "...", "prevention": "..."}.',
    )


def main() -> int:
    err = _preflight()
    if err:
        print("✗", err)
        return 1

    print(f"▶ SELF-HEALING PIPELINE DEMO — model `{MODEL}`\n")
    injected = False
    try:
        # 1. INJECT — duplicate one row so the PK is no longer unique
        con = duckdb.connect(str(DB))
        try:
            con.execute(f"insert into main.{MODEL} select * from main.{MODEL} limit 1")
            injected = True
            dup_pk, dup_count = con.execute(
                f"select {PK}, count(*) from main.{MODEL} group by 1 having count(*) > 1 limit 1"
            ).fetchone()
        finally:
            con.close()
        print(f"1. INJECT   duplicated a row → {PK}={dup_pk} now appears {dup_count}×")

        # 2. DETECT
        fails = _test_failures(MODEL)
        if not fails:
            print("   (unexpected: dbt test did not fail) — aborting")
            return 1
        t = fails[0]
        print(f"2. DETECT   `dbt test` FAILED → unique({PK}) caught {t['failures']} duplicate value/s")

        # 3. DIAGNOSE
        dx = _diagnose(t["name"], dup_pk, dup_count)
        print("3. DIAGNOSE (agent):")
        print(f"     root cause : {dx.get('root_cause', '')}")
        print(f"     fix        : {dx.get('fix', '')}")
        print(f"     prevention : {dx.get('prevention', '')}")

        # 4. REPAIR — rebuild the model from staging (the defect was only in the materialized table)
        r = _dbt("run", "--select", MODEL)
        print(f"4. REPAIR   `dbt run --select {MODEL}` → "
              f"{'ok' if r.returncode == 0 else 'FAILED'} (rebuilt from staging)")

        # 5. VERIFY
        after = _test_failures(MODEL)
        print(f"5. VERIFY   `dbt test` → {'✅ all green again' if not after else '❌ still failing'}")
        return 0 if not after else 1
    finally:
        if injected:
            _dbt("run", "--select", MODEL)   # guarantee a clean warehouse even on error


if __name__ == "__main__":
    raise SystemExit(main())
