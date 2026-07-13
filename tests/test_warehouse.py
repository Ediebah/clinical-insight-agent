"""Unit tests for the read-only SQL validation (no DB / no key needed)."""
import duckdb
import pytest

from agent.warehouse import QueryError, run_query, validate


def test_validate_accepts_select_and_with():
    assert "select 1" in validate("select 1").lower()
    assert validate("with t as (select 1) select * from t").lower().startswith("with")


@pytest.mark.parametrize("bad", [
    "drop table dim_patient",
    "delete from dim_patient",
    "update dim_patient set age = 0",
    "insert into dim_patient values (1)",
    "create table x as select 1",
    "alter table x add column y int",
    "attach 'evil.db' as e",
    "copy dim_patient to 'out.csv'",
    "pragma database_list",
    "select 1; delete from dim_patient",   # multiple statements
    "",                                     # empty
])
def test_validate_rejects_writes_and_multistatement(bad):
    with pytest.raises(QueryError):
        validate(bad)


def test_validate_strips_trailing_semicolon():
    assert not validate("select 1;").endswith(";")


def test_run_query_flags_truncation(tmp_path):
    # a result that hits the row cap must say so — the agent reports len(df) as the TOTAL,
    # so a silent cap turns "1,000" into a confidently wrong count
    db = tmp_path / "t.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table t as select * from range(10)")
    con.close()
    df = run_query("select * from t", max_rows=5, db_path=db)
    assert len(df) == 5 and df.attrs.get("truncated") is True
    full = run_query("select * from t", max_rows=50, db_path=db)
    assert len(full) == 10 and not full.attrs.get("truncated")
