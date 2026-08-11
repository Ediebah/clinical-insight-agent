"""Benchmark harness tests. agent.deid is mocked: CI must never download a model."""
import pytest

from agent import deid_eval

_ROW = {
    "Id": "d545798e-09a4-ef89-abc5-9f62dc5a5095",
    "FIRST": "Ashely524", "LAST": "Brekke496",
    "SSN": "999-28-1649", "ADDRESS": "873 Mayer Avenue",
    "CITY": "Shrewsbury", "ZIP": "00000", "BIRTHDATE": "1997-10-25",
}


def test_raw_identities_keep_synthea_markers():
    ident = deid_eval.raw_identities([_ROW])[0]
    assert ident.first == "Ashely524"          # suffix retained
    assert ident.ssn == "999-28-1649"
    assert ident.zip == "00000"


def test_normalise_strips_name_suffixes():
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.first == "Ashely"
    assert ident.last == "Brekke"


def test_normalise_replaces_the_placeholder_zip_and_reserved_ssn():
    """00000 is not a postcode and 999- is a never-issued SSN range. Both are Synthea markers
    that would make the measurement describe Synthea rather than clinical text."""
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.zip != "00000" and len(ident.zip) == 5 and ident.zip.isdigit()
    assert not ident.ssn.startswith("999-")
    assert len(ident.ssn) == 11 and ident.ssn[3] == "-" and ident.ssn[6] == "-"


def test_normalise_is_deterministic():
    """A benchmark that moves between runs cannot show a regression."""
    a = deid_eval.normalise([_ROW])[0]
    b = deid_eval.normalise([_ROW])[0]
    assert (a.ssn, a.zip) == (b.ssn, b.zip)


def test_mrn_is_derived_from_the_patient_id():
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.mrn.startswith("MRN ")
    assert ident.mrn != "MRN "


def test_load_rows_names_the_rebuild_step_when_raw_is_missing(tmp_path):
    import duckdb
    p = tmp_path / "empty.duckdb"
    duckdb.connect(str(p)).close()
    with pytest.raises(SystemExit) as e:
        deid_eval.load_rows(p, limit=10)
    assert "load_raw.py" in str(e.value)
