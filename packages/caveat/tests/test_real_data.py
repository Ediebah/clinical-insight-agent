"""Validation against real published data the library was not built for.

Every other test in this suite uses frames the author invented, which proves the code does what
the author expected and nothing about whether the expectations hold outside their head. This file
uses the 1973 UC Berkeley graduate admissions table (Bickel, Hammel & O'Connell, *Science* 187:398,
1975) — real data, a documented paradox, and figures anyone can check against the paper.

It is deliberately the whole table and nothing else: no roles are passed, so role inference has to
work unaided on data that has never been near this codebase.
"""
import pandas as pd
import pytest

import caveat

# The six largest departments, as published. Men were admitted at a higher rate overall while women
# were admitted at an equal or higher rate in four of the six departments.
BERKELEY = pd.DataFrame({
    "dept":     list("AABBCCDDEEFF"),
    "gender":   ["M", "W"] * 6,
    "admitted": [512, 89, 353, 17, 120, 202, 138, 131, 53, 94, 22, 24],
    "applied":  [825, 108, 560, 25, 325, 593, 417, 375, 191, 393, 373, 341],
})


@pytest.fixture(scope="module")
def report():
    return caveat.analyze(BERKELEY, "Which gender has the higher admission rate?")


def test_ground_truth_is_what_the_paper_says():
    """Guard the fixture itself: if these numbers drift, every assertion below is meaningless."""
    m = BERKELEY[BERKELEY.gender == "M"]
    w = BERKELEY[BERKELEY.gender == "W"]
    assert m.admitted.sum() / m.applied.sum() == pytest.approx(0.445, abs=0.002)
    assert w.admitted.sum() / w.applied.sum() == pytest.approx(0.304, abs=0.002)
    higher_for_women = [
        d for d, g in BERKELEY.groupby("dept")
        if (g[g.gender == "W"].admitted.iat[0] / g[g.gender == "W"].applied.iat[0]
            > g[g.gender == "M"].admitted.iat[0] / g[g.gender == "M"].applied.iat[0])
    ]
    assert higher_for_women == ["A", "B", "D", "F"]


def test_roles_are_inferred_with_no_help_at_all():
    """No column here matches the naming regex — `admitted`/`applied` are not `cases`/`total`. The
    structural layer has to carry this entirely."""
    r = caveat.infer_roles(BERKELEY)
    assert (r.numerator, r.denominator) == ("admitted", "applied")
    assert r.source["numerator"] == "structural"
    assert (r.group, r.stratifier) == ("gender", "dept")


def test_it_finds_the_documented_paradox(report):
    """The headline claim: the canonical reversal, from raw counts, unconfigured."""
    f = report.of_kind("simpsons")
    assert f, "Simpson's paradox not detected in the dataset it is most famous for"
    assert f[0].severity == "caution"
    assert "`M` > `W`" in f[0].message
    assert "dept" in f[0].message


def test_the_pooled_contrast_matches_the_published_marginal(report):
    """44.5% - 30.4% = 14.1pp. Reported alongside the paradox warning, not instead of it."""
    f = report.of_kind("contrasts")[0]
    assert "+14.2pp" in f.message
    assert "pooled across strata" in f.message


def test_it_does_not_contrast_across_strata(report):
    """Before this was fixed, the headline was 'women in department A vs men in department F,
    +76.5pp' — arithmetically true and a comparison nobody asked for."""
    assert "/" not in report.of_kind("contrasts")[0].message.split("Largest:")[1].split(",")[0]


def test_it_flags_the_one_genuinely_small_cell(report):
    """25 women applied to department B. That is the only cell under n=30 in the table."""
    f = report.of_kind("small_sample")[0]
    assert "n=25" in f.message and "W / B" in f.message


def test_it_does_not_invent_findings_it_has_no_basis_for(report):
    """There is no continuous measure and no missingness here, so those checks must stay quiet and
    say why rather than producing something."""
    assert "skew" not in report.kinds()
    assert "missing_data" not in report.kinds()
    assert {"skew", "mean_contrasts"} <= {s.check for s in report.skipped}
