"""Unit tests for the statistical primitives + the guardrail's detection. No API key needed."""
import pandas as pd

from agent import guardrails as g


def test_wilson_ci_symmetric():
    lo, hi = g.wilson_ci(50, 100)
    assert 0.39 < lo < 0.41 and 0.59 < hi < 0.61


def test_wilson_ci_edges_and_clamp():
    assert g.wilson_ci(0, 10)[0] == 0.0
    lo, hi = g.wilson_ci(15, 10)          # k > n must not raise; stays in [0,1]
    assert 0.0 <= lo <= hi <= 1.0


def test_newcombe_diff_excludes_zero_when_clearly_different():
    d, lo, hi = g.newcombe_diff_ci(200, 1000, 50, 1000)
    assert abs(d - 0.15) < 1e-9 and lo > 0            # 20% vs 5% → CI on the difference excludes 0


def test_two_proportion_p():
    assert g.two_proportion_p(200, 1000, 50, 1000) < 0.001     # clearly different
    assert g.two_proportion_p(100, 1000, 105, 1000) > 0.3      # not different


def test_benjamini_hochberg_adjusts_upward_and_monotone():
    q = g.benjamini_hochberg([0.04, 0.03, 0.02, 0.01])
    assert all(0.0 <= x <= 1.0 for x in q)
    assert g.benjamini_hochberg([0.001]) == [0.001]
    # adjusted q is never smaller than the raw p
    ps = [0.001, 0.5, 0.02]
    assert all(a >= b - 1e-9 for a, b in zip(g.benjamini_hochberg(ps), ps))


def test_skewness_sign():
    assert abs(g.skewness([1, 2, 3, 4, 5])) < 0.1
    assert g.skewness([1, 1, 1, 1, 10]) > 0.5


def test_analyze_flags_small_sample():
    df = pd.DataFrame({"age_group": ["a", "b"],
                       "patients_with_condition": [4, 100],
                       "total_patients_in_age_group": [8, 500]})
    kinds = {f.kind for f in g.analyze(df, "prevalence by age group")}
    assert "small_sample" in kinds


def test_analyze_does_not_overflag_clean_result():
    df = pd.DataFrame({"payer": ["A", "B"], "members": [500, 510], "total_eligible": [1000, 1000]})
    findings = g.analyze(df, "members per payer")
    serious = [f for f in findings if f.severity in ("warn", "caution")]
    assert serious == []
