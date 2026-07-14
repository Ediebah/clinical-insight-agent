"""Unit tests for the Bayesian decision engine (pure; exact values, no key, no network)."""
import numpy as np
import pytest
from scipy import stats

from agent import bayes


def test_beta_posterior_is_exact_conjugate_update():
    assert bayes.beta_posterior(1.0, 1.0, 8, 20) == (9.0, 13.0)


def test_beta_posterior_mean():
    a, b = bayes.beta_posterior(1.0, 1.0, 8, 20)
    assert a / (a + b) == pytest.approx(9 / 22)


def test_normal_posterior_shrinks_toward_the_prior():
    # a vague prior barely moves the sample mean; a tight prior pulls it hard
    mu_vague, _ = bayes.normal_posterior(0.0, 1e3, 5.0, 2.0, 25)
    mu_tight, _ = bayes.normal_posterior(0.0, 0.01, 5.0, 2.0, 25)
    assert mu_vague == pytest.approx(5.0, abs=0.01)
    assert abs(mu_tight) < 0.5


def test_prob_exceeds_matches_scipy():
    got = bayes.prob_exceeds("beta", 9.0, 13.0, 0.30)
    assert got == pytest.approx(float(stats.beta.sf(0.30, 9.0, 13.0)))


def test_prob_exceeds_flips_when_lower_is_better():
    hi = bayes.prob_exceeds("beta", 9.0, 13.0, 0.30, higher_is_better=True)
    lo = bayes.prob_exceeds("beta", 9.0, 13.0, 0.30, higher_is_better=False)
    assert hi + lo == pytest.approx(1.0)


def test_prob_exceeds_is_vectorized():
    out = bayes.prob_exceeds("beta", np.array([2.0, 9.0]), np.array([20.0, 13.0]), 0.30)
    assert out.shape == (2,) and out[1] > out[0]


def test_prob_diff_exceeds_beta_matches_monte_carlo():
    # the shipped code uses quadrature; the TEST uses MC as an independent cross-check
    t, c = (30.0, 20.0), (20.0, 30.0)
    quad = bayes.prob_diff_exceeds("beta", t, c, 0.0)
    rng = np.random.default_rng(0)
    mc = float(np.mean(rng.beta(*t, 400_000) - rng.beta(*c, 400_000) > 0.0))
    assert quad == pytest.approx(mc, abs=0.005)


def test_prob_diff_exceeds_normal_is_closed_form():
    # a difference of normals is normal: check against the analytic answer
    t, c = (5.0, 1.0), (3.0, 2.0)
    got = bayes.prob_diff_exceeds("normal", t, c, 1.0)
    want = float(stats.norm.sf(1.0, loc=5.0 - 3.0, scale=np.hypot(1.0, 2.0)))
    assert got == pytest.approx(want)


RULE = bayes.DecisionRule(tv=0.30, lrv=0.15)


def test_decide_truth_table():
    assert bayes.decide(0.85, 0.95, RULE)[0] == "GO"          # clears both gates
    assert bayes.decide(0.55, 0.94, RULE)[0] == "CONSIDER"    # clears LRV, misses TV
    assert bayes.decide(0.01, 0.05, RULE)[0] == "STOP"        # cannot even reach the LRV
    assert bayes.decide(0.85, 0.85, RULE)[0] == "CONSIDER"    # misses the LRV gate -> not a GO


def test_decide_gate_boundaries_are_inclusive():
    assert bayes.decide(0.80, 0.90, RULE)[0] == "GO"          # exactly on both gates
    assert bayes.decide(0.80, 0.10, RULE)[0] == "CONSIDER"    # exactly on stop_lrv -> not a STOP


def test_decide_reason_is_populated():
    call, reason = bayes.decide(0.85, 0.95, RULE)
    # :g is magnitude-safe but strips trailing zeros: 0.30 -> "0.3" (see test below for why
    # :.2f, which WOULD print "0.30" literally, is the wrong choice).
    assert call == "GO" and "0.3" in reason and "0.15" in reason


def test_decide_reason_renders_thresholds_without_losing_magnitude():
    # :.2f renders TV=0.001 as "0.00", telling a clinician the target is zero when it isn't.
    # :g renders every magnitude faithfully. This is the property that motivates using :g.
    rule = bayes.DecisionRule(tv=0.001, lrv=0.0005)
    _, reason = bayes.decide(0.85, 0.95, rule)
    assert "0.001" in reason
    assert "0.0005" in reason
    assert "TV 0.00)" not in reason      # the misleading :.2f zero-rendering must not appear
    assert "LRV 0.00)" not in reason

    big_rule = bayes.DecisionRule(tv=10.0, lrv=5.0)
    _, big_reason = bayes.decide(0.85, 0.95, big_rule)
    assert "TV 10)" in big_reason


def test_decide_reason_does_not_round_probability_to_100_percent():
    # :.0% rounds 0.9979 up to "100%", falsely reporting certainty in a tool whose whole
    # point is honest reporting. :.1% must preserve the distinction.
    call, reason = bayes.decide(0.9979, 0.95, RULE)
    assert call == "GO"
    assert "100%" not in reason
    assert "99.8%" in reason


def test_prior_ess_is_a_plus_b():
    assert bayes.prior_ess(bayes.Prior("x", "beta", (9.0, 13.0), "")) == 22.0


def test_prior_panel_spans_skeptical_to_enthusiastic():
    informed = bayes.Prior("Phase-I informed", "beta", (9.0, 13.0), "Phase I: 8/20")
    panel = bayes.prior_panel(informed, RULE)
    names = [p.name for p in panel]
    assert names == ["Phase-I informed", "Vague", "Skeptical", "Enthusiastic"]
    mean = lambda p: p.params[0] / (p.params[0] + p.params[1])   # noqa: E731
    skeptical = next(p for p in panel if p.name == "Skeptical")
    enthusiastic = next(p for p in panel if p.name == "Enthusiastic")
    assert mean(skeptical) <= RULE.lrv            # centred at or below the "not worth pursuing" value
    assert mean(enthusiastic) >= RULE.tv          # centred at or above the target


# ── assurance + operating characteristics ─────────────────────────────────────────────────────────
def _point_prior(theta: float, k: float = 1e6) -> bayes.Prior:
    """A Beta prior collapsed onto a point mass at theta (huge effective sample size)."""
    return bayes.Prior("point", "beta", (theta * k, (1 - theta) * k), "point mass")


def test_go_grid_is_monotone_in_successes():
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    go = bayes.go_grid_binary(prior, 60, RULE)
    assert go.shape == (61,)
    assert go[0] == 0 and go[-1] == 1                 # 0 successes -> never GO; all successes -> GO
    assert np.all(np.diff(go) >= 0)                   # more successes can only help


def test_assurance_collapses_to_power_under_a_point_prior():
    """THE key invariant: as the prior tightens onto theta0, assurance -> classical power at theta0."""
    rule, n, theta0 = bayes.DecisionRule(tv=0.30, lrv=0.15), 80, 0.35
    a = bayes.assurance(_point_prior(theta0), n, rule)
    oc = bayes.operating_characteristics(_point_prior(theta0), n, rule, grid=np.array([theta0]))
    power_at_theta0 = oc[0]["go_rate"]
    assert a == pytest.approx(power_at_theta0, abs=1e-6)


def test_assurance_is_below_power_when_the_prior_has_spread():
    """The whole point of assurance: averaging over uncertainty is more honest, and lower, than
    assuming the effect is exactly the value you hope for."""
    rule, n, theta0 = bayes.DecisionRule(tv=0.30, lrv=0.15), 80, 0.35
    spread = bayes.Prior("informed", "beta", (7.0, 13.0), "Phase I: 6/18")   # mean 0.35, real spread
    power = bayes.operating_characteristics(_point_prior(theta0), n, rule,
                                            grid=np.array([theta0]))[0]["go_rate"]
    assert bayes.assurance(spread, n, rule) < power


def test_operating_characteristics_go_rate_rises_with_the_true_effect():
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    oc = bayes.operating_characteristics(prior, 80, RULE, grid=np.array([0.05, 0.15, 0.30, 0.60]))
    rates = [row["go_rate"] for row in oc]
    assert rates == sorted(rates)
    assert rates[0] < 0.05 and rates[-1] > 0.90


def test_type_i_and_power_are_read_off_the_oc_curve():
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    oc = bayes.operating_characteristics(prior, 80, RULE)
    t1, power = bayes.type_i_and_power(oc, RULE)
    assert 0.0 <= t1 <= 0.20            # GO rate when the effect is only at the LRV
    assert power > t1                   # GO rate at the TV must exceed it
