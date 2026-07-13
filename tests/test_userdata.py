"""Unit tests for bring-your-own-data prep (no API key; DuckDB round-trip)."""
import io

import duckdb
import pandas as pd
import pytest

from agent import userdata


def test_read_upload_caps_csv_rows(monkeypatch):
    monkeypatch.setattr(userdata, "MAX_ROWS", 10)
    buf = io.StringIO("a,b\n" + "\n".join(f"{i},{i}" for i in range(100)))
    df, notes = userdata.read_upload(buf, "big.csv")
    assert len(df) == 11                             # MAX_ROWS + 1 → truncation stays detectable
    assert notes == []


def test_read_upload_rejects_oversized_excel_sheet(tmp_path, monkeypatch):
    # the 50 MB upload cap measures the COMPRESSED xlsx; a small crafted workbook can inflate to
    # GBs when parsed — the declared sheet dimensions must be checked BEFORE parsing
    openpyxl = pytest.importorskip("openpyxl")
    monkeypatch.setattr(userdata, "MAX_SHEET_CELLS", 10)
    p = tmp_path / "bomb.xlsx"
    wb = openpyxl.Workbook()
    for _ in range(6):
        wb.active.append(list(range(5)))             # declares 6×5 = 30 cells > patched cap of 10
    wb.save(p)
    with p.open("rb") as f, pytest.raises(ValueError, match="cell"):
        userdata.read_upload(f, "bomb.xlsx")


def test_read_upload_notes_extra_sheets(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "two.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    wb.active.append([1, 2])
    ws2 = wb.create_sheet("second")
    ws2.append(["x"])
    wb.save(p)
    with p.open("rb") as f:
        df, notes = userdata.read_upload(f, "two.xlsx")
    assert list(df.columns) == ["a", "b"] and len(df) == 1
    assert any("sheet" in n.lower() for n in notes)  # extra sheets are disclosed, first is analyzed


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
    # 'group' is a SQL reserved word → suffixed to 'group_' so the agent's unquoted SELECT parses
    assert table == "my_file" and list(clean.columns) == ["group_", "val"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
    finally:
        con.close()
    assert n == 3
