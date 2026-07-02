"""Unit tests for the deterministic chart/KPI logic (no key needed)."""
import pandas as pd

from agent import charts


def _prevalence_df():
    return pd.DataFrame({"age_group": ["18-39", "65-74"],
                         "patients_with_condition": [12, 62],
                         "total_patients_in_age_group": [309, 120],
                         "prevalence_pct": [3.88, 51.67]})


def test_pick_measure_prefers_rate_over_denominator():
    assert charts._pick_measure(_prevalence_df()) == "prevalence_pct"


def test_build_chart_none_for_single_value():
    assert charts.build_chart(pd.DataFrame({"n": [1139]})) is None


def test_build_chart_layers_for_category_measure():
    ch = charts.build_chart(_prevalence_df())
    assert ch is not None and len(ch.to_dict().get("layer", [])) >= 2


def test_kpi_cards_shape():
    cards = charts.kpi_cards(_prevalence_df())
    assert len(cards) == 3 and cards[0]["label"].startswith("highest")


def test_add_ci_computes_bounds():
    d = _prevalence_df().copy()
    assert charts._add_ci(d, "prevalence_pct") is True
    assert "_ci_lo" in d and "_ci_hi" in d
    assert (d["_ci_lo"] <= d["prevalence_pct"]).all() and (d["prevalence_pct"] <= d["_ci_hi"]).all()
