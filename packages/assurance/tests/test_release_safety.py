"""Release-blocking cases for the standalone Bayesian interface."""
import pytest
from scipy import integrate, stats

import assurance
from assurance import core
from assurance.core import Prior


def test_design_requires_an_explicit_prior():
    with pytest.raises(ValueError, match="prior"):
        assurance.design(n=20, tv=.4, lrv=.3, gate_tv=.8, gate_lrv=.9, stop_lrv=.1, full=False)


def test_design_requires_explicit_decision_gates():
    with pytest.raises((ValueError, TypeError), match="gate_tv|gate_lrv|stop_lrv"):
        assurance.design(n=20, tv=.4, lrv=.3, prior_a=1, prior_b=1, full=False)


def test_incomplete_control_data_are_not_treated_as_single_arm():
    with pytest.raises(ValueError, match="control"):
        assurance.interim(successes=5, n=10, n_planned=20, tv=.2, lrv=0,
                          control_successes=1, prior_a=1, prior_b=1,
                          gate_tv=.8, gate_lrv=.9, stop_lrv=.1)


def test_two_arm_prior_decision_uses_difference_from_control_rate():
    # For Beta(2,2), P(treatment > 0.5) = 0.5; hence P(diff > 0) < 0.6.
    result = assurance.design(n=10, tv=.2, lrv=0, control_rate=.5, prior_a=2, prior_b=2,
                              control_prior=Prior("control", "beta", (1., 1.), "specified"),
                              gate_tv=.8, gate_lrv=.9, stop_lrv=.6, full=False)
    assert result.decision == "STOP"
    assert "50.0%" in result.reason


def test_two_arm_interim_requires_control_prior():
    with pytest.raises(ValueError, match="control prior"):
        assurance.interim(successes=2, n=5, control_successes=1, control_n=5,
                          n_planned=20, tv=.2, lrv=0, prior_a=1, prior_b=1,
                          gate_tv=.8, gate_lrv=.9, stop_lrv=.1)


def test_two_arm_control_prior_with_endpoint_singularity_is_refused():
    with pytest.raises(ValueError, match="control prior"):
        assurance.interim(successes=2, n=5, control_successes=1, control_n=5,
                          n_planned=20, tv=.2, lrv=0, prior_a=1, prior_b=1,
                          control_prior=Prior("control", "beta", (.5, .5), "specified"),
                          gate_tv=.8, gate_lrv=.9, stop_lrv=.1)


def test_low_level_beta_difference_refuses_endpoint_singularity():
    with pytest.raises(ValueError, match="control"):
        core.prob_diff_exceeds("beta", (2., 2.), (.5, .5), 0.)


def test_beta_difference_does_not_require_numpy_2_trapezoid(monkeypatch):
    monkeypatch.delattr(core.np, "trapezoid", raising=False)
    assert core.prob_diff_exceeds("beta", (2., 2.), (2., 2.), 0.) == pytest.approx(.5, abs=1e-5)


@pytest.mark.parametrize("successes,n", [(6, 5), (-1, 5), (0, -1)])
def test_invalid_control_counts_are_refused(successes, n):
    with pytest.raises(ValueError, match="control"):
        assurance.interim(successes=2, n=5, control_successes=successes, control_n=n,
                          n_planned=20, tv=.2, lrv=0, prior_a=1, prior_b=1,
                          control_prior=Prior("control", "beta", (1., 1.), "specified"),
                          gate_tv=.8, gate_lrv=.9, stop_lrv=.1)


def test_fractional_sample_size_is_not_silently_rounded():
    with pytest.raises(ValueError, match="integer"):
        assurance.design(n=20.5, tv=.4, lrv=.3, prior_a=1, prior_b=1,
                         gate_tv=.8, gate_lrv=.9, stop_lrv=.1, full=False)


def test_small_two_arm_assurance_matches_independent_quadrature():
    """Enumerate outcomes with adaptive quadrature, independent of the fixed-grid engine."""
    treatment = (2., 2.)
    control = (2., 2.)
    expected = 0.0
    for x_t in range(5):
        for x_c in range(5):
            t_post = (treatment[0] + x_t, treatment[1] + 4 - x_t)
            c_post = (control[0] + x_c, control[1] + 4 - x_c)

            def probability(threshold, t_post=t_post, c_post=c_post):
                return integrate.quad(
                    lambda p: stats.beta.pdf(p, *c_post)
                    * stats.beta.sf(min(p + threshold, 1), *t_post),
                    0, 1, epsabs=1e-10,
                )[0]

            goes = probability(.1) >= .55 and probability(0) >= .65
            expected += (stats.betabinom.pmf(x_t, 4, *treatment)
                         * stats.binom.pmf(x_c, 4, .3) * goes)
    result = assurance.design(
        n=8, tv=.1, lrv=0, control_rate=.3, prior_a=2, prior_b=2,
        control_prior=Prior("control", "beta", control, "specified"),
        gate_tv=.55, gate_lrv=.65, stop_lrv=.1, full=False,
    )
    assert result.assurance == pytest.approx(expected, abs=1e-4)
    assert result.control_rate == .3
    assert result.control_prior.params == control


def test_two_arm_interim_does_not_silently_thin_outcomes(monkeypatch):
    monkeypatch.setattr(core, "MAX_ENUM_DIFF", 5)
    prior = Prior("specified", "beta", (1., 1.), "specified")
    with pytest.raises(ValueError, match="enumeration cap"):
        core.predictive_prob_success_diff(
            prior, prior, 1, 2, 1, 2, 5, 5, core.DecisionRule(.2, 0)
        )


def test_low_level_two_arm_prediction_rejects_invalid_control_counts():
    prior = Prior("specified", "beta", (1., 1.), "specified")
    with pytest.raises(ValueError, match="control"):
        core.predictive_prob_success_diff(
            prior, prior, 1, 2, 3, 2, 5, 5, core.DecisionRule(.2, 0)
        )


def test_two_arm_control_prior_can_be_specified_as_json_numbers():
    result = assurance.design(n=10, tv=.2, lrv=0, control_rate=.5, prior_a=2, prior_b=2,
                              control_prior_a=1, control_prior_b=1,
                              gate_tv=.8, gate_lrv=.9, stop_lrv=.1, full=False)
    assert result.control_prior.params == (1., 1.)
    assert result.under_powered is None
