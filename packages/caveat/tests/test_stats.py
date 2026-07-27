"""Statistics primitives, checked against values that do not depend on this implementation."""
import math

import pytest

from caveat.stats import (
    _inv_norm,
    benjamini_hochberg,
    bootstrap_diff_ci,
    bootstrap_mean_ci,
    mde_two_proportions,
    newcombe_diff_ci,
    norm_cdf,
    skewness,
    two_proportion_p,
    wilson_ci,
)


def test_norm_cdf_matches_known_quantiles():
    assert norm_cdf(0) == pytest.approx(0.5)
    assert norm_cdf(1.959963984540054) == pytest.approx(0.975, abs=1e-6)
    assert norm_cdf(-1.959963984540054) == pytest.approx(0.025, abs=1e-6)


def test_inv_norm_inverts_norm_cdf():
    for p in (0.001, 0.01, 0.025, 0.2, 0.5, 0.8, 0.975, 0.99, 0.999):
        assert norm_cdf(_inv_norm(p)) == pytest.approx(p, abs=1e-6)


def test_wilson_ci_is_bounded_and_asymmetric_at_the_edge():
    """The reason Wilson is here: at 0/10 the Wald interval is [0, 0], which is a lie."""
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0
    assert 0.25 < hi < 0.35          # ~0.278
    lo, hi = wilson_ci(10, 10)
    assert hi == pytest.approx(1.0)  # 1.0 to machine precision, not exactly representable
    assert 0.65 < lo < 0.75


def test_wilson_ci_known_value():
    """Values computed from the Wilson definition independently of this implementation:
        p=0.25, n=20, z=1.96 -> centre 0.290276, half-width 0.178420."""
    lo, hi = wilson_ci(5, 20)
    assert lo == pytest.approx(0.111862, abs=1e-5)
    assert hi == pytest.approx(0.468701, abs=1e-5)


def test_wilson_ci_degenerate_n():
    assert wilson_ci(0, 0) == (0.0, 1.0)


def test_newcombe_diff_ci_contains_the_difference_and_stays_in_range():
    d, lo, hi = newcombe_diff_ci(8, 20, 4, 900)
    assert d == pytest.approx(0.4 - 4 / 900)
    assert lo <= d <= hi
    assert -1.0 <= lo and hi <= 1.0


def test_newcombe_handles_an_empty_arm():
    d, lo, hi = newcombe_diff_ci(0, 0, 4, 10)
    assert (lo, hi) == (-1.0, 1.0)


def test_two_proportion_p_extremes():
    assert two_proportion_p(50, 100, 50, 100) == pytest.approx(1.0)
    assert two_proportion_p(90, 100, 10, 100) < 1e-6
    assert two_proportion_p(1, 0, 1, 10) == 1.0        # empty arm -> no evidence


def test_benjamini_hochberg_is_monotone_and_bounded():
    q = benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.042, 0.9])
    assert all(0.0 <= x <= 1.0 for x in q)
    assert q[0] <= q[1] <= q[2]
    assert q[0] == pytest.approx(0.006, abs=1e-9)      # 0.001 * 6/1


def test_benjamini_hochberg_treats_nan_and_none_as_not_significant():
    """Dropping them instead would shrink the family and inflate everything else."""
    assert benjamini_hochberg([float("nan"), 5.4e-5])[0] == 1.0
    assert benjamini_hochberg([None, 0.001])[0] == 1.0
    assert len(benjamini_hochberg([None, 0.001])) == 2


def test_benjamini_hochberg_empty():
    assert benjamini_hochberg([]) == []


def test_skewness_sign_and_degenerate_cases():
    assert skewness([1, 1, 1, 1]) == 0.0
    assert skewness([1, 2]) == 0.0                     # too few points
    assert skewness([1, 1, 1, 1, 20]) > 1.0            # right tail
    assert skewness([-20, 1, 1, 1, 1]) < -1.0          # left tail


def test_bootstrap_mean_ci_brackets_the_mean_and_is_seeded():
    vals = list(range(100))
    lo, hi = bootstrap_mean_ci(vals, n_boot=500, seed=0)
    assert lo < 49.5 < hi
    assert bootstrap_mean_ci(vals, n_boot=500, seed=0) == (lo, hi)   # reproducible


def test_bootstrap_diff_ci_detects_a_real_difference_and_a_null_one():
    a = [10] * 30 + [12] * 30
    b = [50] * 30 + [52] * 30
    d, lo, hi, p = bootstrap_diff_ci(a, b, n_boot=500, seed=0)
    assert d == pytest.approx(-40, abs=0.1)
    assert hi < 0 and p < 0.05                       # interval excludes zero

    d2, lo2, hi2, p2 = bootstrap_diff_ci(a, list(a), n_boot=500, seed=0)
    assert d2 == pytest.approx(0, abs=1e-9)
    assert lo2 <= 0 <= hi2 and p2 > 0.05


def test_bootstrap_diff_p_never_reports_zero():
    """A bootstrap cannot evidence a p below its own resolution; claiming 0 would be overclaiming."""
    a = [0] * 40
    b = [1000] * 40
    *_, p = bootstrap_diff_ci(a, b, n_boot=200, seed=0)
    assert p >= 1 / 200


def test_bootstrap_diff_ci_needs_two_points_per_side():
    d, lo, hi, p = bootstrap_diff_ci([1], [1, 2, 3], n_boot=100, seed=0)
    assert math.isnan(d) and p == 1.0


def test_mde_shrinks_as_n_grows():
    small = mde_two_proportions(20, 20, 0.3)
    large = mde_two_proportions(2000, 2000, 0.3)
    assert small > large
    assert 0 < large < 0.1 < small <= 1.0


def test_mde_is_nan_for_an_empty_group():
    assert math.isnan(mde_two_proportions(0, 10, 0.3))
