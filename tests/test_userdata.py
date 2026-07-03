"""Unit tests for bring-your-own-data prep (no API key; DuckDB round-trip)."""
import duckdb
import pandas as pd

from agent import userdata


def test_sanitize_columns_dedup_and_leading_digit():
    df = pd.DataFrame({"A B": [1], "A-B": [2], "3x": [3]})
    out = userdata.sanitize_columns(df)
    assert list(out.columns) == ["a_b", "a_b_1", "c_3x"]


def test_build_catalog_shape_matches_rag():
    df = pd.DataFrame({"arm": ["a", "b"], "converted": [0, 1]})
    cat = userdata.build_catalog(df, "t")
    assert cat["metrics"] == [] and len(cat["tables"]) == 1
    tbl = cat["tables"][0]
    assert tbl["name"] == "t" and tbl["primary_key"] == [] and tbl["foreign_keys"] == []
    assert {c["name"] for c in tbl["columns"]} == {"arm", "converted"}
    assert all("example_values" in c for c in tbl["columns"])


def test_prepare_upload_roundtrip_queryable():
    df = pd.DataFrame({"Group": ["x", "y", "x"], "Val": [1, 2, 3]})
    db_path, cat, table, clean = userdata.prepare_upload(df, "My File.csv")
    assert table == "my_file" and list(clean.columns) == ["group", "val"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
    finally:
        con.close()
    assert n == 3
