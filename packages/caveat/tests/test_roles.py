"""Role resolution — the part that decides whether the library works on your data or does nothing.

The headline claim is that it survives meaningless column names. These tests are what hold that.
"""
import pandas as pd
import pytest

from caveat import analyze, infer_roles
from caveat.roles import UnknownColumn, resolve


def test_naming_layer_reads_disciplined_column_names():
    df = pd.DataFrame({"age_group": ["a", "b"],
                       "patients_with_condition": [12, 147],
                       "total_patients_in_age_group": [309, 394]})
    r = infer_roles(df)
    assert r.numerator == "patients_with_condition"
    assert r.denominator == "total_patients_in_age_group"
    assert r.source["numerator"] == "naming"


def test_structural_layer_survives_meaningless_column_names():
    """The whole point of the structural layer: `a`, `b`, `cnt` carry no naming signal at all, but
    a count column bounded elementwise by a larger count column is still a part inside a whole."""
    df = pd.DataFrame({"grp": ["x", "y", "z"], "a": [12, 147, 4], "b": [309, 394, 8]})
    r = infer_roles(df)
    assert (r.numerator, r.denominator) == ("a", "b")
    assert r.source["numerator"] == "structural"
    assert r.source["denominator"] == "structural"


def test_structural_layer_picks_the_largest_valid_denominator():
    """With a subtotal and a population column, the population is the denominator."""
    df = pd.DataFrame({"g": ["x", "y"], "k": [5, 9], "subtotal": [20, 30], "population": [200, 300]})
    assert infer_roles(df).denominator == "population"


def test_structural_layer_rejects_a_duplicated_column():
    """k <= n holds trivially when the two columns are equal; that is a copy, not a denominator."""
    df = pd.DataFrame({"g": ["x", "y"], "k": [5, 9], "same": [5, 9]})
    r = infer_roles(df)
    assert r.denominator is None


def test_structural_layer_rejects_negative_and_fractional_columns():
    df = pd.DataFrame({"g": ["x", "y"], "k": [-5, 9], "n": [50, 90]})
    assert infer_roles(df).numerator != "k"
    df2 = pd.DataFrame({"g": ["x", "y"], "k": [0.5, 9.25], "n": [50, 90]})
    assert infer_roles(df2).numerator != "k"


def test_structural_rate_detection_recognises_fraction_and_percent():
    df = pd.DataFrame({"g": ["x", "y"], "k": [10, 30], "n": [100, 100], "share": [0.10, 0.30]})
    assert infer_roles(df).rate == "share"
    df2 = pd.DataFrame({"g": ["x", "y"], "k": [10, 30], "n": [100, 100], "share": [10.0, 30.0]})
    assert infer_roles(df2).rate == "share"


def test_explicit_roles_win_over_inference():
    df = pd.DataFrame({"g": ["x", "y"], "cases": [1, 2], "total": [10, 20], "other": [3, 4]})
    r = resolve(df, {"numerator": "other"})
    assert r.numerator == "other"
    assert r.source["numerator"] == "explicit"
    assert r.denominator == "total"          # still inferred


def test_explicit_unknown_column_raises_rather_than_being_ignored():
    """Silently ignoring a role the caller supplied is the worst possible behaviour for a tool
    whose job is to say what you missed."""
    df = pd.DataFrame({"g": ["x"], "k": [1], "n": [10]})
    with pytest.raises(UnknownColumn, match="not in the frame"):
        resolve(df, {"denominator": "nope"})


def test_unknown_role_name_raises():
    df = pd.DataFrame({"g": ["x"], "k": [1], "n": [10]})
    with pytest.raises(UnknownColumn, match="unknown role"):
        resolve(df, {"denominatorr": "n"})


def test_role_kwargs_shorthand_reaches_the_checks():
    df = pd.DataFrame({"g": ["x", "y"], "aaa": [1, 2], "bbb": [10, 20]})
    rep = analyze(df, numerator="aaa", denominator="bbb")
    assert rep.roles.numerator == "aaa"
    assert rep.roles.source["numerator"] == "explicit"


def test_group_pick_prefers_low_cardinality_over_column_order():
    """An id-like first column must not win over a real two-level comparison axis."""
    df = pd.DataFrame({"record_id": list("abcdef"), "arm": ["t", "c"] * 3,
                       "k": [1, 2, 3, 4, 5, 6], "n": [10] * 6})
    assert infer_roles(df).group == "arm"


def test_empty_frame_infers_nothing_without_raising():
    assert infer_roles(pd.DataFrame()).identified() == []


def test_roles_str_reports_the_source_of_each_field():
    df = pd.DataFrame({"g": ["x", "y"], "a": [1, 2], "b": [10, 20]})
    s = str(infer_roles(df))
    assert "structural" in s and "numerator=" in s
