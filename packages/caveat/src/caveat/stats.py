"""Statistics primitives.

numpy only, no scipy — the normal CDF comes from math.erf and everything else (Wilson, Newcombe,
Benjamini-Hochberg, the bootstraps) is implemented here. That keeps the install to numpy + pandas,
which matters for a library meant to sit inside someone else's agent rather than a research stack.

Comparisons of means are bootstrapped rather than t-tested. That is not only a way to avoid the t
distribution: cost, length-of-stay and duration data are strongly right-skewed, and a bootstrap
difference interval does not assume the normality that a t-test does.
"""
from __future__ import annotations

import math

import numpy as np

Z_95 = 1.959963984540054          # two-sided 95%
Z_80_POWER = 0.8416212335729143   # one-sided 80% power


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n.

    Preferred over the Wald interval, which has coverage well below nominal at small n and near 0
    or 1 — exactly the regime where a caveat library is asked to speak.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = min(max(k / n, 0.0), 1.0)
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int,
                     z: float = Z_95) -> tuple[float, float, float]:
    """(difference, lower, upper) for p1 - p2 by Newcombe's method 10, built from the two Wilson
    intervals. Behaves at the boundaries where a Wald difference interval runs outside [-1, 1]."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, -1.0, 1.0
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1, z)
    l2, u2 = wilson_ci(k2, n2, z)
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, max(-1.0, lower), min(1.0, upper)


def two_proportion_p(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided pooled two-proportion z-test p-value."""
    if n1 <= 0 or n2 <= 0:
        return 1.0
    p1, p2 = k1 / n1, k2 / n2
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    return 2 * (1 - norm_cdf(abs((p1 - p2) / se)))


def benjamini_hochberg(pvals) -> list[float]:
    """BH step-up adjusted q-values in the original order.

    A NaN or None p-value (a zero-variance contrast, an empty arm) becomes 1.0. Dropping them would
    change the family size m and quietly make everything else look more significant.
    """
    vals = list(pvals)
    m = len(vals)
    if m == 0:
        return []
    clean = [1.0 if (p is None or math.isnan(p)) else float(p) for p in vals]
    order = sorted(range(m), key=lambda i: clean[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, clean[i] * m / rank)
        q[i] = min(prev, 1.0)
    return q


def skewness(vals) -> float:
    """Population (biased) skewness. 0 for constant or near-empty input."""
    a = np.asarray(vals, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) < 3:
        return 0.0
    s = a.std(ddof=0)
    return 0.0 if s == 0 else float(((a - a.mean()) ** 3).mean() / s ** 3)


def bootstrap_mean_ci(vals, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for a mean. Seeded, so a report is reproducible."""
    a = np.asarray(vals, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n_boot, len(a)), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_diff_ci(a_vals, b_vals, n_boot: int = 2000,
                      seed: int = 0) -> tuple[float, float, float, float]:
    """(difference of means, lower, upper, two-sided p) for mean(a) - mean(b).

    The p-value is the usual bootstrap two-sided tail proportion, doubled and floored at 1/n_boot —
    never 0, because a bootstrap cannot evidence a p smaller than its own resolution.
    """
    a = np.asarray(a_vals, dtype=float)
    a = a[~np.isnan(a)]
    b = np.asarray(b_vals, dtype=float)
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return (float("nan"), float("nan"), float("nan"), 1.0)
    rng = np.random.default_rng(seed)
    da = rng.choice(a, size=(n_boot, len(a)), replace=True).mean(axis=1)
    db = rng.choice(b, size=(n_boot, len(b)), replace=True).mean(axis=1)
    diffs = da - db
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    tail = min((diffs <= 0).mean(), (diffs >= 0).mean())
    p = min(1.0, max(2 * tail, 1.0 / n_boot))
    return float(a.mean() - b.mean()), float(lo), float(hi), float(p)


def mde_two_proportions(n1: int, n2: int, p_baseline: float,
                        alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest absolute risk difference detectable at these group sizes, as a proportion.

    Answers the question behind "n is small": not "is this unstable" but "how big would an effect
    have had to be for this study to have seen it?" A non-significant contrast between two groups
    of 20 is uninformative rather than reassuring, and this is the number that says so.
    """
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    p = min(max(float(p_baseline), 1e-9), 1 - 1e-9)
    z_a = _z_two_sided(alpha)
    z_b = Z_80_POWER if abs(power - 0.80) < 1e-9 else _z_one_sided(power)
    se_unit = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return float(min(1.0, (z_a + z_b) * se_unit))


def _z_two_sided(alpha: float) -> float:
    return _inv_norm(1 - alpha / 2)


def _z_one_sided(power: float) -> float:
    return _inv_norm(min(max(power, 1e-6), 1 - 1e-6))


def _inv_norm(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation, |error| < 1.15e-9).

    Hand-rolled to keep the scipy-free promise; accurate far beyond anything a caveat needs.
    """
    if not 0.0 < p < 1.0:
        return float("nan")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
