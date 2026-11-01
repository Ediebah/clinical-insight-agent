"""Unit tests for the deterministic chart/KPI logic (no key needed)."""
import pandas as pd
import pytest

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


def test_kpi_formats_fraction_rate_as_percent_when_explicit():
    df = pd.DataFrame({"age_group": ["0-17", "75+"], "readmission_rate": [0.0, 0.1443]})
    cards = charts.kpi_cards(df, rate_unit="fraction")
    blob = " ".join(c.get("value", "") + c.get("sub", "") for c in cards)
    assert "14.4%" in blob and "0.1%" not in blob


def test_kpi_percent_column_left_unscaled_when_explicit():
    df = pd.DataFrame({"grp": ["a", "b"], "prevalence_pct": [3.88, 51.67]})
    blob = " ".join(c.get("sub", "") for c in charts.kpi_cards(df, rate_unit="percent"))
    assert "51.7%" in blob and "3.9%" in blob


def test_add_ci_computes_bounds():
    d = _prevalence_df().copy()
    assert charts._add_ci(d, "prevalence_pct", rate_unit="percent", numerator="patients_with_condition",
                          denominator="total_patients_in_age_group") is True
    assert "_ci_lo" in d and "_ci_hi" in d
    assert (d["_ci_lo"] <= d["prevalence_pct"]).all() and (d["prevalence_pct"] <= d["_ci_hi"]).all()


def test_ambiguous_rate_displays_original_values_without_percent_or_intervals():
    df = pd.DataFrame({"grp": ["a", "b"], "mortality_rate": [0.5, 1.2],
                       "events": [1, 2], "total": [10, 10]})
    blob = " ".join(c.get("value", "") + c.get("sub", "") for c in charts.kpi_cards(df))
    assert "1.2" in blob and "120.0%" not in blob and "%" not in blob
    chart = charts.build_chart(df).to_dict()
    assert len(chart["layer"]) == 2


def test_explicit_units_make_cards_and_chart_labels_agree():
    df = pd.DataFrame({"grp": ["a", "b"], "mortality_rate": [0.5, 1.2]})
    cards = charts.kpi_cards(df, rate_unit="percent")
    assert "1.2%" in " ".join(c.get("sub", "") for c in cards)
    chart = charts.build_chart(df, rate_unit="percent").to_dict()
    data = next(iter(chart["datasets"].values()))
    assert {r["_label"] for r in data} == {"0.5%", "1.2%"}


def test_non_percentage_index_stays_in_original_units():
    cards = charts.kpi_cards(pd.DataFrame({"activity_index": [200]}))
    assert cards[0]["value"] == "200"


def test_small_percent_intervals_are_in_percent_units():
    df = pd.DataFrame({"rate": [.5, 1.2], "events": [5, 12], "total": [1000, 1000]})
    assert charts._add_ci(df, "rate", rate_unit="percent", numerator="events", denominator="total")
    assert all(df["_ci_lo"] < df["rate"]) and all(df["_ci_hi"] > df["rate"])
    assert df["_ci_lo"].iloc[0] > .1


def test_wilson_intervals_require_explicit_consistent_counts():
    df = pd.DataFrame({"grp": ["a", "b"], "rate": [.2, .4], "events": [2, 4], "total": [10, 10]})
    assert charts._add_ci(df.copy(), "rate", rate_unit="fraction") is False
    assert charts._add_ci(df.copy(), "rate", rate_unit="fraction", numerator="events", denominator="total")
    bad = df.assign(events=[2, 9])
    assert charts._add_ci(bad, "rate", rate_unit="fraction", numerator="events", denominator="total") is False
    for bad in (df.assign(events=[2, 11]), df.assign(events=[2, 4.5]), df.assign(total=[0, 10])):
        assert charts._add_ci(bad, "rate", rate_unit="fraction", numerator="events", denominator="total") is False
    nullable = df.assign(events=pd.Series([2, pd.NA], dtype="Int64"))
    assert charts._add_ci(nullable, "rate", rate_unit="fraction", numerator="events", denominator="total") is False


@pytest.mark.parametrize("rate,k,unit", [(-.0001, 0, "fraction"), (1.0001, 100, "fraction"),
                                         (-.01, 0, "percent"), (100.01, 100, "percent")])
def test_wilson_intervals_reject_out_of_range_rates_even_near_rounding(rate, k, unit):
    df = pd.DataFrame({"rate": [rate], "events": [k], "total": [100]})
    assert not charts._add_ci(df, "rate", rate_unit=unit, numerator="events", denominator="total")


def test_invalid_units_are_rejected():
    with pytest.raises(ValueError, match="rate_unit"):
        charts.kpi_cards(pd.DataFrame({"rate": [.5]}), rate_unit="guess")


def test_report_uses_the_selected_chart_units():
    from types import SimpleNamespace

    from agent.report import _figure_titles
    df = pd.DataFrame({"grp": ["a", "b"], "mortality_rate": [.5, 1.2]})
    figure, _ = _figure_titles(SimpleNamespace(dataframe=df), {}, rate_unit="percent")[0]
    data = next(iter(figure.to_dict()["datasets"].values()))
    assert {r["_label"] for r in data} == {"0.5%", "1.2%"}


def test_assurance_curve_chart_builds():
    model = {"model_type": "assurance", "error": None,
             "series": [{"n": 20, "assurance": 0.31}, {"n": 100, "assurance": 0.62}],
             "verdict": {"call": "GO"}}
    assert charts.assurance_curve_chart(model) is not None


def test_assurance_curve_chart_is_none_without_series():
    assert charts.assurance_curve_chart({"model_type": "assurance", "series": []}) is None


def test_oc_curve_chart_builds():
    model = {"model_type": "assurance", "error": None,
             "robustness": {"oc": [{"theta": 0.1, "go_rate": 0.02}, {"theta": 0.4, "go_rate": 0.9}]}}
    assert charts.oc_curve_chart(model) is not None
