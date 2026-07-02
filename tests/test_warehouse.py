"""Unit tests for the read-only SQL validation (no DB / no key needed)."""
import pytest

from agent.warehouse import QueryError, validate


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
