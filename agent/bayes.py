"""Bayesian decision engine for early-development go/no-go.

Every model here is CONJUGATE, so every quantity is closed-form or deterministic numeric integration
on a fixed grid. There is NO Monte Carlo in this module: no seed to manage, results are
bit-reproducible across runs and platforms, and the tests assert exact values rather than tolerances.
A tool whose only job is to support a decision must not return a different verdict on re-run.

Endpoints:  binary (Beta-Binomial)  |  continuous mean, known SD (Normal-Normal)
Framings:   single-arm vs a performance goal (device)  |  two-arm vs a control (drug)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

_GRID = 2001          # quadrature points for the Beta-difference integral


@dataclass(frozen=True)
class Prior:
    name: str                       # "Phase-I informed" | "Vague" | "Skeptical" | "Enthusiastic"
    kind: str                       # "beta" (binary endpoint) | "normal" (continuous endpoint)
    params: tuple[float, float]     # beta: (a, b).  normal: (mu, sd).
    provenance: str                 # human-readable: where this prior came from


@dataclass(frozen=True)
class DecisionRule:
    """Dual-criterion (Lalonde) go/no-go. A device performance goal is the degenerate case tv == lrv."""
    tv: float                       # Target Value: the effect we hope for
    lrv: float                      # Lower Reference Value: the minimum worth pursuing
    gate_tv: float = 0.80           # required P(theta beyond tv)
    gate_lrv: float = 0.90          # required P(theta beyond lrv)
    stop_lrv: float = 0.10          # P(theta beyond lrv) below this -> STOP
    higher_is_better: bool = True


# ── conjugate updates ─────────────────────────────────────────────────────────────────────────────
def beta_posterior(a: float, b: float, x: int, n: int) -> tuple[float, float]:
    """Beta(a,b) prior + x successes in n trials -> Beta(a+x, b+n-x). Exact."""
    return float(a + x), float(b + n - x)


def normal_posterior(mu0: float, sd0: float, xbar: float, sd: float, n: int) -> tuple[float, float]:
    """Normal(mu0, sd0) prior + n observations with mean xbar and KNOWN sd -> normal posterior. Exact."""
    if n <= 0:
        return float(mu0), float(sd0)
    prec0, prec_d = 1.0 / sd0 ** 2, n / sd ** 2
    var = 1.0 / (prec0 + prec_d)
    return float(var * (prec0 * mu0 + prec_d * xbar)), float(np.sqrt(var))


# ── tail probabilities ────────────────────────────────────────────────────────────────────────────
def prob_exceeds(kind: str, p1, p2, threshold: float, higher_is_better: bool = True):
    """P(theta is BEYOND threshold on the good side). Vectorized over p1/p2 (numpy arrays welcome)."""
    if kind == "beta":
        sf = stats.beta.sf(threshold, p1, p2)
    else:
        sf = stats.norm.sf(threshold, loc=p1, scale=p2)
    return sf if higher_is_better else 1.0 - sf


def prob_diff_exceeds(kind: str, t: tuple[float, float], c: tuple[float, float],
                      threshold: float, higher_is_better: bool = True) -> float:
    """P(theta_treatment - theta_control is beyond threshold).

    normal: a difference of normals is normal -> closed form.
    beta:   no closed form, so 1-D quadrature on a fixed grid:
                P(T - C > d) = INT f_C(v) * sf_T(v + d) dv
            Deterministic and fast. NOT Monte Carlo.
    """
    if kind == "normal":
        mu = t[0] - c[0]
        sd = float(np.hypot(t[1], c[1]))
        sf = float(stats.norm.sf(threshold, loc=mu, scale=sd))
    else:
        v = np.linspace(0.0, 1.0, _GRID)
        f_c = stats.beta.pdf(v, c[0], c[1])
        sf_t = stats.beta.sf(np.clip(v + threshold, 0.0, 1.0), t[0], t[1])
        sf = float(np.trapezoid(f_c * sf_t, v))
    return sf if higher_is_better else 1.0 - sf


# ── the decision rule ─────────────────────────────────────────────────────────────────────────────
def decide(p_tv: float, p_lrv: float, rule: DecisionRule) -> tuple[str, str]:
    """Dual-criterion verdict. p_tv / p_lrv are probabilities of being on the GOOD side of each value."""
    side = "above" if rule.higher_is_better else "below"
    ev = (f"P({side} TV {rule.tv:g}) = {p_tv:.1%}, P({side} LRV {rule.lrv:g}) = {p_lrv:.1%}")
    if p_tv >= rule.gate_tv and p_lrv >= rule.gate_lrv:
        return "GO", (f"{ev}. Clears both pre-specified gates "
                      f"({rule.gate_tv:.0%} at the TV and {rule.gate_lrv:.0%} at the LRV).")
    if p_lrv < rule.stop_lrv:
        return "STOP", (f"{ev}. The effect is very unlikely to reach even the LRV "
                        f"({rule.lrv:g}), the minimum worth pursuing.")
    return "CONSIDER", (f"{ev}. Promising but short of the pre-specified GO gates "
                        f"({rule.gate_tv:.0%} at the TV, {rule.gate_lrv:.0%} at the LRV) -- "
                        "the evidence does not yet justify a commitment.")


# ── priors ────────────────────────────────────────────────────────────────────────────────────────
def prior_ess(prior: Prior) -> float:
    """Effective sample size. Beta(a,b) carries as much information as a+b observations."""
    return float(prior.params[0] + prior.params[1]) if prior.kind == "beta" else float("nan")


def prior_panel(informed: Prior, rule: DecisionRule) -> list[Prior]:
    """Four defensible priors. If the verdict flips across them it is FRAGILE, not an answer.

    This is FDA's prior-sensitivity requirement (Jan 2026 draft guidance): show that the trial's
    conclusion is robust across plausible alternative priors, not an artefact of one choice.
    """
    if informed.kind != "beta":
        _, sd = informed.params
        span = abs(rule.tv - rule.lrv) or 1.0
        return [
            informed,
            Prior("Vague", "normal", (rule.lrv, 10.0 * span), "Weakly informative, centred at the LRV."),
            Prior("Skeptical", "normal", (rule.lrv, span / 2), "Centred at the minimum worth pursuing."),
            Prior("Enthusiastic", "normal", (rule.tv, span / 2), "Centred at the target value."),
        ]
    ess = 10.0                                       # the reference priors carry ~10 observations
    skeptical = (rule.lrv * ess, (1 - rule.lrv) * ess)
    enthusiastic = (rule.tv * ess, (1 - rule.tv) * ess)
    return [
        informed,
        Prior("Vague", "beta", (1.0, 1.0), "Uniform on [0,1]: every response rate equally likely."),
        Prior("Skeptical", "beta", skeptical,
              f"Centred on the LRV ({rule.lrv:g}), the minimum worth pursuing; ESS {ess:g}."),
        Prior("Enthusiastic", "beta", enthusiastic,
              f"Centred on the TV ({rule.tv:g}), the hoped-for effect; ESS {ess:g}."),
    ]


# ── assurance + operating characteristics ─────────────────────────────────────────────────────────
def go_grid_binary(prior: Prior, n: int, rule: DecisionRule) -> np.ndarray:
    """go[x] == 1 iff observing x successes in n trials yields a GO. Computed ONCE, then reused by
    assurance, the operating characteristics, and the predictive probability -- all three are just
    different weightings of this same vector."""
    a, b = prior.params
    xs = np.arange(n + 1)
    post_a, post_b = a + xs, b + (n - xs)
    p_tv = prob_exceeds("beta", post_a, post_b, rule.tv, rule.higher_is_better)
    p_lrv = prob_exceeds("beta", post_a, post_b, rule.lrv, rule.higher_is_better)
    return ((p_tv >= rule.gate_tv) & (p_lrv >= rule.gate_lrv)).astype(int)


def _go_threshold_normal(prior: Prior, n: int, rule: DecisionRule, sd: float) -> float:
    """The observed sample mean at which the decision tips to GO. The posterior tail probability is
    monotone in the sample mean, so a single threshold exists; find it by bisection on a fine grid."""
    mu0, sd0 = prior.params
    lo, hi = mu0 - 10 * sd, mu0 + 10 * sd
    xbars = np.linspace(lo, hi, 4001)
    pm, ps = np.vectorize(lambda xb: normal_posterior(mu0, sd0, xb, sd, n))(xbars)
    p_tv = prob_exceeds("normal", pm, ps, rule.tv, rule.higher_is_better)
    p_lrv = prob_exceeds("normal", pm, ps, rule.lrv, rule.higher_is_better)
    go = (p_tv >= rule.gate_tv) & (p_lrv >= rule.gate_lrv)
    if not go.any():
        return float("inf") if rule.higher_is_better else float("-inf")
    idx = int(np.argmax(go)) if rule.higher_is_better else int(len(go) - 1 - np.argmax(go[::-1]))
    return float(xbars[idx])


def assurance(prior: Prior, n_planned: int, rule: DecisionRule, sd: float | None = None) -> float:
    """P(the trial reaches GO), averaging over the prior uncertainty about the true effect.

    This is Bayesian power, and it is the honest number: classical power asks "what is the chance of
    success IF the effect is exactly X", which is a question nobody can answer. Assurance integrates
    over what you actually believe about X, and is usually lower.

    Binary: EXACT. assurance = SUM_x go[x] * BetaBinomial(x; n, a, b), because the prior-predictive
    distribution of the success count under a Beta prior IS the beta-binomial. No integration error.
    """
    if prior.kind == "beta":
        a, b = prior.params
        go = go_grid_binary(prior, n_planned, rule)
        xs = np.arange(n_planned + 1)
        return float(np.sum(stats.betabinom.pmf(xs, n_planned, a, b) * go))
    if sd is None or sd <= 0:
        raise ValueError("a continuous endpoint needs a positive known SD")
    mu0, sd0 = prior.params
    crit = _go_threshold_normal(prior, n_planned, rule, sd)
    se = sd / np.sqrt(n_planned)
    # theta ~ prior; xbar | theta ~ N(theta, se) -> xbar ~ N(mu0, sqrt(sd0^2 + se^2)) marginally
    marg = float(np.hypot(sd0, se))
    p = float(stats.norm.sf(crit, loc=mu0, scale=marg))
    return p if rule.higher_is_better else 1.0 - p


def operating_characteristics(prior: Prior, n_planned: int, rule: DecisionRule,
                              sd: float | None = None, grid=None) -> list[dict]:
    """The GO rate at each TRUE effect value. FDA's second pillar: show how the design behaves across
    a plausible range of truths, not just at the value you hope for.

    Read off this curve: the GO rate at the LRV is the type I error (declaring success when the effect
    is not worth pursuing); the GO rate at the TV is the power.
    """
    if grid is None:
        grid = (np.linspace(0.01, 0.99, 99) if prior.kind == "beta"
                else np.linspace(rule.lrv - 2 * abs(rule.tv - rule.lrv),
                                 rule.tv + 2 * abs(rule.tv - rule.lrv), 99))
    out = []
    if prior.kind == "beta":
        go = go_grid_binary(prior, n_planned, rule)
        xs = np.arange(n_planned + 1)
        for th in np.asarray(grid, dtype=float):
            out.append({"theta": float(th),
                        "go_rate": float(np.sum(stats.binom.pmf(xs, n_planned, th) * go))})
        return out
    if sd is None or sd <= 0:
        raise ValueError("a continuous endpoint needs a positive known SD")
    crit = _go_threshold_normal(prior, n_planned, rule, sd)
    se = sd / np.sqrt(n_planned)
    for th in np.asarray(grid, dtype=float):
        p = float(stats.norm.sf(crit, loc=th, scale=se))
        out.append({"theta": float(th), "go_rate": p if rule.higher_is_better else 1.0 - p})
    return out


def type_i_and_power(oc: list[dict], rule: DecisionRule) -> tuple[float, float]:
    """Type I error = GO rate at the LRV. Power = GO rate at the TV. Nearest grid point."""
    def _at(target):
        row = min(oc, key=lambda r: abs(r["theta"] - target))
        return float(row["go_rate"])
    return _at(rule.lrv), _at(rule.tv)
