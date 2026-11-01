"""The demo export must not silently reuse or expose raw warehouse tables."""
import subprocess
import sys
from pathlib import Path

import duckdb

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_demo_database.py"
TABLES = (
    "dim_condition", "dim_medication", "dim_organization", "dim_patient", "dim_payer",
    "dim_provider", "fct_conditions", "fct_encounters", "fct_medications", "fct_observations",
    "fct_procedures", "mart_condition_prevalence", "mart_cost_by_condition", "mart_experiments",
    "mart_readmissions", "mart_trials",
)


def _source(path, *, omit=None):
    con = duckdb.connect(str(path))
    con.execute("create schema raw")
    con.execute("create table raw.private_source as select 1 as id")
    for table in TABLES:
        if table != omit:
            con.execute(f'create table main."{table}" as select 42 as id')
    con.close()


def _run(source, output):
    return subprocess.run([sys.executable, str(SCRIPT), "--source", str(source), "--output", str(output)],
                          capture_output=True, text=True, check=False)


def test_exports_only_named_models_and_preserves_source(tmp_path):
    source, output = tmp_path / "source.duckdb", tmp_path / "demo.duckdb"
    _source(source)
    result = _run(source, output)
    assert result.returncode == 0, result.stderr
    db = duckdb.connect(str(output), read_only=True)
    tables = db.execute("select table_name from information_schema.tables where table_schema='main'").fetchall()
    assert {x[0] for x in tables} == set(TABLES)
    assert db.execute("select id from main.dim_patient").fetchone() == (42,)
    assert not db.execute("select 1 from information_schema.schemata where schema_name='raw'").fetchall()
    db.close()
    db = duckdb.connect(str(source), read_only=True)
    assert db.execute("select id from raw.private_source").fetchone() == (1,)
    db.close()


def test_refuses_existing_output_and_missing_models(tmp_path):
    source, output = tmp_path / "source.duckdb", tmp_path / "demo.duckdb"
    _source(source, omit="mart_trials")
    result = _run(source, output)
    assert result.returncode != 0 and "missing required model" in result.stderr.lower() and not output.exists()
    output.write_bytes(b"preserve me")
    result = _run(source, output)
    assert result.returncode != 0 and "output already exists" in result.stderr.lower()
    assert output.read_bytes() == b"preserve me"
