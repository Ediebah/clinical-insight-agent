#!/usr/bin/env python3
"""Export the documented demo models from a built warehouse without copying raw tables.

Both paths are explicit. The output must not exist; build a new file before replacing a demo.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import duckdb

DEMO_TABLES = (
    "dim_condition", "dim_medication", "dim_organization", "dim_patient", "dim_payer",
    "dim_provider", "fct_conditions", "fct_encounters", "fct_medications", "fct_observations",
    "fct_procedures", "mart_condition_prevalence", "mart_cost_by_condition", "mart_experiments",
    "mart_readmissions", "mart_trials",
)


def export_demo(source: Path, output: Path) -> None:
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"Source warehouse does not exist: {source}")
    if output.exists() or output.is_symlink():
        raise ValueError(f"Output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {output.parent}")

    con = duckdb.connect(str(source), read_only=True)
    try:
        available = {row[0] for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()}
    finally:
        con.close()
    missing = sorted(set(DEMO_TABLES) - available)
    if missing:
        raise ValueError(f"Missing required model(s): {', '.join(missing)}")

    # Create in the destination filesystem; a hard link publishes without overwriting an existing file.
    with tempfile.TemporaryDirectory(prefix="demo-export-", dir=output.parent) as tmp:
        candidate = Path(tmp) / "demo.duckdb"
        con = duckdb.connect(str(candidate))
        try:
            escaped = str(source).replace("'", "''")
            con.execute(f"ATTACH '{escaped}' AS source_db (READ_ONLY)")
            for table in DEMO_TABLES:
                con.execute(f'CREATE TABLE main."{table}" AS SELECT * FROM source_db.main."{table}"')
            con.execute("DETACH source_db")
            con.execute("CHECKPOINT")
        finally:
            con.close()
        os.link(candidate, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        export_demo(args.source, args.output)
    except (ValueError, OSError, duckdb.Error) as exc:
        parser.exit(1, f"Demo export failed: {exc}\n")


if __name__ == "__main__":
    main()
