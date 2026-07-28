"""The high-level API: design() and interim().

test_core.py covers the maths. These cover the ergonomics — that the convenience layer builds the
right Prior and DecisionRule, validates what it should, and returns the same numbers the primitives
do. A convenience wrapper that quietly disagrees with the engine underneath it is worse than none.
"""
import pytest

import assurance
from assurance.core import DecisionRule, Prior
from assurance.core import assurance as assurance_fn


# ── single-arm design ──────────────────────────────────────────────────────────────────────────
def test_design_matches_the_primitive_it_wraps():
    """The wrapper must not drift from the engine: same prior, same rule, same number."""
    d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    prior = Prior("x", "beta", (9.0, 13.0), "")          # Beta(1,1) updated with 8/20
    rule = DecisionRule(tv=0.30, lrv=0.15)
    assert d.assurance == pytest.approx(assurance_fn(prior, 100, rule), abs=1e-4)


def test_design_is_bit_reproducible():
    """The whole reason to be conjugate rather than simulated: no seed, no drift, same digits."""
    a = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    b = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    assert a.assurance == b.assurance
    assert a.power == b.power and a.type_i_error == b.type_i_error


def test_design_reports_power_type_i_and_a_prior_only_verdict():
    d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    assert 0.0 <= d.type_i_error <= d.power <= 1.0
    assert d.decision in ("GO", "CONSIDER", "STOP")
    assert "TV" in d.reason


def test_design_flags_under_power_even_when_assurance_looks_good():
    """The trap this exists to catch: assurance 76% and power 29% is a design that succeeds mostly
    because the prior is optimistic, not because the trial can detect anything."""
    d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    assert d.assurance > 0.70 and d.power < 0.40
    assert d.under_powered
    assert "UNDER-POWERED" in d.summary()


def test_design_records_where_the_prior_came_from():
    d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    assert "8 responses in 20 patients" in d.prior.provenance
    assert d.prior_ess == pytest.approx(22.0)


def test_design_sensitivity_panel_shows_the_skeptic():
    """A design whose assurance collapses under a skeptical prior is a statement about the prior."""
    d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    names = {r["prior"] for r in d.sensitivity}
    assert "Skeptical" in names
    vals = [r["assurance"] for r in d.sensitivity]
    assert min(vals) < d.assurance          # the skeptic is less optimistic than the informed prior


def test_full_false_skips_the_expensive_parts():
    fast = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20, full=False)
    slow = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    assert fast.assurance == slow.assurance          # the headline number is unaffected
    assert fast.operating_characteristics == [] and fast.sensitivity == []


def test_device_performance_goal_is_the_degenerate_tv_equals_lrv_case():
    d = assurance.design(n=120, tv=0.85, lrv=0.85, prior_successes=44, prior_n=50)
    assert d.assurance == pytest.approx(0.3811, abs=1e-3)
    assert d.decision in ("GO", "CONSIDER", "STOP")


# ── two-arm design ─────────────────────────────────────────────────────────────────────────────
def test_two_arm_design_treats_tv_lrv_as_risk_differences():
    d = assurance.design(n=200, tv=0.15, lrv=0.0, control_rate=0.35,
                         prior_successes=14, prior_n=20)
    assert d.assurance == pytest.approx(0.8875, abs=1e-3)
    assert 0.0 <= d.type_i_error < d.power <= 1.0


def test_two_arm_reads_power_off_the_oc_curve_not_nan():
    """The OC grid need not land exactly on the TV; nearest-point lookup keeps these real numbers
    instead of silently returning NaN for the two figures a reviewer checks first."""
    d = assurance.design(n=200, tv=0.15, lrv=0.0, control_rate=0.35,
                         prior_successes=14, prior_n=20)
    assert d.power == d.power and d.type_i_error == d.type_i_error     # not NaN


# ── interim ────────────────────────────────────────────────────────────────────────────────────
def test_interim_predictive_probability_and_decision():
    i = assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15)
    assert i.predictive_probability == pytest.approx(0.2896, abs=1e-3)
    assert i.decision == "CONSIDER"
    assert i.observed == 40 and i.n_planned == 100


def test_interim_futility_overrides_a_posterior_that_is_merely_unconvincing():
    """The two questions disagree here, and futility has to win.

    3 responses in the first 30 of a planned 120 leaves P(effect > LRV) at ~30% — not a STOP by the
    dual-criterion rule, which only looks at where the posterior sits today. But the chance of ever
    clearing the gates is 0.05%. Reporting "promising but short of the gates" would be misleading.
    """
    i = assurance.interim(successes=3, n=30, n_planned=120, tv=0.30, lrv=0.15)
    assert i.predictive_probability < 0.01
    assert i.futile
    assert i.decision == "STOP"
    assert "futility" in i.reason


def test_a_healthy_interim_is_not_marked_futile():
    i = assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15)
    assert not i.futile and i.decision == "CONSIDER"


def test_interim_saturates_at_the_go_end():
    i = assurance.interim(successes=28, n=40, n_planned=100, tv=0.30, lrv=0.15)
    assert i.predictive_probability == pytest.approx(1.0)
    assert i.decision == "GO"


def test_two_arm_interim_uses_the_difference_posterior():
    i = assurance.interim(successes=18, n=40, control_successes=10, control_n=38,
                          n_planned=200, tv=0.15, lrv=0.0)
    assert i.predictive_probability == pytest.approx(0.3783, abs=1e-3)
    assert i.posterior_mean == pytest.approx(0.1774, abs=1e-3)   # a risk DIFFERENCE, not a rate


# ── validation ─────────────────────────────────────────────────────────────────────────────────
def test_lrv_above_tv_is_rejected():
    """The minimum worth pursuing cannot be more ambitious than the value you hope for."""
    with pytest.raises(ValueError, match="LRV must not exceed the TV"):
        assurance.design(n=100, tv=0.20, lrv=0.40)


def test_lower_is_better_reverses_that_check():
    with pytest.raises(ValueError, match="TV must not exceed the LRV"):
        assurance.design(n=100, tv=0.40, lrv=0.20, higher_is_better=False)
    assurance.design(n=100, tv=0.10, lrv=0.30, higher_is_better=False, full=False)   # fine


def test_a_proportion_outside_zero_to_one_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 1"):
        assurance.design(n=100, tv=30, lrv=15)          # percentages, not proportions


def test_missing_tv_or_lrv_is_rejected():
    with pytest.raises(ValueError, match="target value"):
        assurance.design(n=100, tv=None, lrv=0.15)


def test_non_positive_n_is_rejected():
    with pytest.raises(ValueError, match="must be positive"):
        assurance.design(n=0, tv=0.30, lrv=0.15)


def test_interim_rejects_observing_more_than_planned():
    with pytest.raises(ValueError, match="exceeds the planned"):
        assurance.interim(successes=5, n=150, n_planned=100, tv=0.30, lrv=0.15)


def test_interim_rejects_more_successes_than_patients():
    with pytest.raises(ValueError, match="between 0 and n"):
        assurance.interim(successes=50, n=40, n_planned=100, tv=0.30, lrv=0.15)
