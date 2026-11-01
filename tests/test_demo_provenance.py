"""Verify the checked-in demo against its build manifest without accessing raw records."""
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_demo_and_recorded_build_files_match_manifest():
    manifest = json.loads((ROOT / "docs/demo_dataset_manifest.json").read_text())
    demo = ROOT / manifest["demo"]["path"]
    assert _sha256(demo) == manifest["demo"]["sha256"]
    for name, expected in manifest["project_files_sha256"].items():
        assert _sha256(ROOT / name) == expected, name
    with duckdb.connect(str(demo), read_only=True) as con:
        actual = {r[0] for r in con.execute(
            "select table_name from information_schema.tables where table_schema='main'"
        ).fetchall()}
        assert actual == set(manifest["demo"]["tables_and_rows"])
        for table, expected in manifest["demo"]["tables_and_rows"].items():
            assert con.execute(f'SELECT count(*) FROM main."{table}"').fetchone()[0] == expected
        assert not con.execute("select 1 from information_schema.schemata where schema_name='raw'").fetchall()
