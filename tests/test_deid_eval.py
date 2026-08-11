"""Benchmark harness tests. agent.deid is mocked: CI must never download a model."""
import json

import pytest

from agent import deid, deid_eval

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


def test_load_rows_does_not_misreport_bad_limit_as_missing_table(tmp_path):
    """Invalid limit must raise ValueError, not misreport as raw.patients not found."""
    import duckdb
    p = tmp_path / "test.duckdb"
    duckdb.connect(str(p)).close()
    with pytest.raises(ValueError):
        deid_eval.load_rows(p, limit="not-a-number")


def _identities(n=3):
    rows = [dict(_ROW, Id=f"id-{i}", FIRST=f"Ashely{i}", LAST=f"Brekke{i}") for i in range(n)]
    return deid_eval.normalise(rows)


def test_build_frame_labels_identifier_columns_and_includes_clean_ones():
    df, truth = deid_eval.build_frame(_identities())
    assert {"first", "last", "ssn", "address", "zip", "mrn", "birthdate"} <= truth
    assert {"systolic_bp", "cured", "encounter_count", "cost_usd"} <= set(df.columns)
    assert not ({"systolic_bp", "cured", "encounter_count", "cost_usd"} & truth)
    assert len(df) == 3


def test_score_columns_is_perfect_when_every_identifier_column_is_flagged(monkeypatch):
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        return [deid.ColumnFinding(column=c, entity_types=["x"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct")
                for c in truth]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    out = deid_eval.score_columns(df, truth)
    assert out["recall"] == 1.0
    assert out["precision"] == 1.0
    assert out["missed"] == []


def test_score_columns_reports_misses_and_false_positives(monkeypatch):
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        # flags one real identifier, misses the rest, and flags one clean column
        return [deid.ColumnFinding(column="first", entity_types=["first_name"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct"),
                deid.ColumnFinding(column="cured", entity_types=["age"], hit_rate=1.0,
                                   examples=[], suggested="keep", severity="quasi")]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    out = deid_eval.score_columns(df, truth)
    assert out["recall"] == 1 / len(truth)
    assert out["precision"] == 0.5
    assert "cured" in out["false_positives"]
    assert "ssn" in out["missed"]


def test_score_columns_checks_that_age_and_sex_stay_quasi(monkeypatch):
    """A regression here silently destroys the covariates the modeling suite depends on."""
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        return [deid.ColumnFinding(column="age", entity_types=["age"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct")]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    assert deid_eval.score_columns(df, truth)["quasi_ok"] is False


def test_build_notes_pairs_each_note_with_what_was_inserted():
    notes = deid_eval.build_notes(_identities(2))
    assert len(notes) == 2
    text, truth = notes[0]
    for kind in ("first_name", "last_name", "ssn", "address", "zip", "mrn", "date"):
        assert kind in truth
        assert truth[kind] in text          # ground truth by construction


def test_score_spans_is_perfect_when_everything_is_masked(monkeypatch):
    notes = deid_eval.build_notes(_identities(2))
    monkeypatch.setattr(deid, "scrub_values",
                        lambda vals: ["[REDACTED]" for _ in vals])
    out = deid_eval.score_spans(notes)
    assert out["overall"] == 1.0
    assert all(v == 1.0 for v in out["recall"].values())
    assert all(not v for v in out["leaks"].values())


def test_score_spans_is_zero_when_nothing_is_masked(monkeypatch):
    notes = deid_eval.build_notes(_identities(2))
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    out = deid_eval.score_spans(notes)
    assert out["overall"] == 0.0
    assert all(v == 0.0 for v in out["recall"].values())


def test_score_spans_reports_recall_per_type_not_aggregated(monkeypatch):
    """An aggregate would have averaged away the MRN failure that motivated this benchmark."""
    notes = deid_eval.build_notes(_identities(2))

    def masks_names_only(vals):
        out = []
        for v in vals:
            for _text, truth in notes:
                v = v.replace(truth["first_name"], "[REDACTED]")
                v = v.replace(truth["last_name"], "[REDACTED]")
            out.append(v)
        return out
    monkeypatch.setattr(deid, "scrub_values", masks_names_only)
    out = deid_eval.score_spans(notes)
    assert out["recall"]["first_name"] == 1.0
    assert out["recall"]["last_name"] == 1.0
    assert out["recall"]["ssn"] == 0.0
    assert out["leaks"]["ssn"]          # the surviving value is reported as evidence


def test_score_spans_catches_partial_masking_of_name_components(monkeypatch):
    """Masking only last name must not yield full success; first_name should be exposed."""
    notes = deid_eval.build_notes(_identities(2))

    def masks_last_name_only(vals):
        out = []
        for v in vals:
            for _text, truth in notes:
                v = v.replace(truth["last_name"], "[REDACTED]")
            out.append(v)
        return out
    monkeypatch.setattr(deid, "scrub_values", masks_last_name_only)
    out = deid_eval.score_spans(notes)
    assert out["recall"]["last_name"] == 1.0
    assert out["recall"]["first_name"] == 0.0  # not masked — failure
    assert out["leaks"]["first_name"]  # evidence captured


def test_score_spans_raises_on_wrong_output_length(monkeypatch):
    """Silent truncation reporting perfect scores is worse than any other failure mode."""
    notes = deid_eval.build_notes(_identities(2))

    def returns_fewer_items(vals):
        return ["[REDACTED]"]  # wrong: expected 2, returned 1
    monkeypatch.setattr(deid, "scrub_values", returns_fewer_items)
    with pytest.raises(ValueError, match="scrub_values returned .* expected"):
        deid_eval.score_spans(notes)


def test_run_scores_both_variants_and_records_the_gap(monkeypatch):
    monkeypatch.setattr(deid_eval, "load_rows",
                        lambda db_path=None, limit=200: [dict(_ROW, Id=f"id-{i}")
                                                         for i in range(3)])
    monkeypatch.setattr(deid, "available", lambda: True)
    monkeypatch.setattr(deid, "scan_columns", lambda frame, sample=20: [])
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    rec = deid_eval.run(limit=3)
    assert set(rec) >= {"ts", "model", "threshold", "n_patients", "normalised", "raw"}
    assert rec["n_patients"] == 3
    for variant in ("normalised", "raw"):
        assert "column_recall" in rec[variant]
        assert "span_recall" in rec[variant]
        assert set(rec[variant]["span_recall"]) == set(deid_eval.ENTITY_TYPES)


def test_run_records_the_threshold_and_model_it_measured_at(monkeypatch):
    """A score without its threshold and model id cannot be compared against a later run."""
    monkeypatch.setattr(deid_eval, "load_rows",
                        lambda db_path=None, limit=200: [dict(_ROW, Id="id-0")])
    monkeypatch.setattr(deid, "scan_columns", lambda frame, sample=20: [])
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    monkeypatch.setattr(deid, "SCORE_THRESHOLD", 0.42)
    rec = deid_eval.run(limit=1)
    assert rec["threshold"] == 0.42
    assert rec["model"] == deid.MODEL_ID


def test_main_exits_nonzero_and_says_so_when_the_model_is_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(deid, "available", lambda: False)
    assert deid_eval.main([]) == 1
    assert "unavailable" in capsys.readouterr().out.lower()


def test_history_record_is_one_json_object_per_line(tmp_path, monkeypatch):
    hist = tmp_path / "h.jsonl"
    monkeypatch.setattr(deid_eval, "HISTORY", hist)
    deid_eval.append_history({"ts": "x", "overall": 1.0})
    deid_eval.append_history({"ts": "y", "overall": 0.5})
    lines = hist.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[1])["ts"] == "y"
