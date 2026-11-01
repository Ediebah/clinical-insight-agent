"""A constructed stratified comparison with a known Simpson reversal.

These counts are fictional and provide a regression case, not external validation.
"""
import pandas as pd
import pytest

import caveat


@pytest.fixture(scope="module")
def table():
    return pd.DataFrame({
        "dept": list("AABBCCDD"),
        "gender": ["M", "W"] * 4,
        "admitted": [160, 18, 72, 9, 1, 20, 2, 20],
        "applied": [200, 20, 90, 10, 10, 100, 20, 100],
    })


@pytest.fixture(scope="module")
def report(table):
    return caveat.analyze(table, "Which gender has the higher admission rate?")


def test_fixture_reverses_the_pooled_order_within_each_stratum(table):
    pooled = table.groupby("gender")[["admitted", "applied"]].sum()
    rates = pooled.admitted / pooled.applied
    assert rates["M"] == pytest.approx(235 / 320)
    assert rates["W"] == pytest.approx(67 / 230)
    assert rates["M"] > rates["W"]
    for _, group in table.groupby("dept"):
        within = group.set_index("gender")
        assert (within.loc["W", "admitted"] / within.loc["W", "applied"]
                > within.loc["M", "admitted"] / within.loc["M", "applied"])


def test_roles_are_inferred_structurally(table):
    roles = caveat.infer_roles(table)
    assert (roles.numerator, roles.denominator) == ("admitted", "applied")
    assert roles.source["numerator"] == "structural"
    assert (roles.group, roles.stratifier) == ("gender", "dept")


def test_warns_about_reversal_and_reports_pooled_contrast(report):
    reversal = report.of_kind("simpsons")
    assert reversal and reversal[0].severity == "caution"
    assert "`M` > `W`" in reversal[0].message and "dept" in reversal[0].message
    contrast = report.of_kind("contrasts")[0].message
    assert "+44.3pp" in contrast and "pooled across strata" in contrast
    assert "/" not in contrast.split("Largest:")[1].split(",")[0]


def test_reports_small_cells_and_skips_unsupported_checks(report):
    small = report.of_kind("small_sample")[0].message
    assert "4 group(s)" in small and "n=10" in small
    assert "skew" not in report.kinds() and "missing_data" not in report.kinds()
    assert {"skew", "mean_contrasts"} <= {s.check for s in report.skipped}
