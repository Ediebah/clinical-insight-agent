"""assurance — Bayesian go/no-go for trial design and interim decisions.

Classical power asks "what is the chance of success IF the true effect is exactly X?", which is a
question nobody can answer. **Assurance** integrates over what you actually believe about X and
answers the question a decision-maker has: *given everything we know, what is the chance this trial
succeeds?* It is usually the lower and more honest number.

    >>> import assurance
    >>> d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
    >>> d.assurance, d.power, d.decision
    (0.7612, 0.2893, 'GO')

    >>> i = assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15)
    >>> i.predictive_probability, i.decision
    (0.2896, 'CONSIDER')

Everything is conjugate and closed-form. **There is no Monte Carlo anywhere**: no seed to manage,
identical digits on every machine and every re-run. When a programme decision turns on whether
assurance is 0.78 or 0.82, a number that moves with the seed is not evidence.

Decisions use the dual-criterion (Lalonde) rule: GO needs both P(effect > TV) above `gate_tv` and
P(effect > LRV) above `gate_lrv`; STOP when P(effect > LRV) falls below `stop_lrv`; CONSIDER in
between. A device performance goal is the degenerate case TV == LRV.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import core
from .core import (
    DecisionRule,
    Prior,
    assurance,
    assurance_diff,
    beta_posterior,
    decide,
    normal_posterior,
    operating_characteristics,
    operating_characteristics_diff,
    predictive_prob_success,
    predictive_prob_success_diff,
    prior_ess,
    prior_panel,
    prob_diff_exceeds,
    prob_exceeds,
    type_i_and_power,
)
from .priors import build_prior, sensitivity

__version__ = "0.1.0"

__all__ = [
    "DecisionRule",
    "Design",
    "Interim",
    "Prior",
    "assurance",
    "assurance_diff",
    "beta_posterior",
    "build_prior",
    "core",
    "decide",
    "design",
    "interim",
    "normal_posterior",
    "operating_characteristics",
    "operating_characteristics_diff",
    "predictive_prob_success",
    "predictive_prob_success_diff",
    "prior_ess",
    "prior_panel",
    "prob_diff_exceeds",
    "prob_exceeds",
    "sensitivity",
    "type_i_and_power",
]


@dataclass(frozen=True)
class Design:
    """A design-stage go/no-go. No data has been collected yet."""
    assurance: float               # P(this trial reaches GO), averaged over the prior
    power: float                   # P(GO) if the true effect were exactly the TV
    type_i_error: float            # P(GO) if the true effect were only the LRV
    decision: str                  # GO | CONSIDER | STOP, from the prior alone
    reason: str
    prior: Prior
    rule: DecisionRule
    n_planned: int
    under_powered: bool            # power below the conventional 80%
    operating_characteristics: list = field(default_factory=list)
    sensitivity: list = field(default_factory=list)

    @property
    def prior_ess(self) -> float:
        """Effective sample size of the prior. If it exceeds n_planned, the prior is doing more
        work than the trial will."""
        return prior_ess(self.prior)

    def summary(self) -> str:
        lines = [
            (f"assurance {self.assurance:.1%}   power {self.power:.1%}   "
             f"type I {self.type_i_error:.1%}   n={self.n_planned:,}"),
            f"decision (prior only): {self.decision} - {self.reason}",
            f"prior: {self.prior.provenance}",
        ]
        if self.under_powered:
            lines.append(f"UNDER-POWERED: power at the TV is {self.power:.0%}, below the "
                         f"conventional 80%. Even if the true effect equals the Target Value this "
                         f"design reaches GO only {self.power:.0%} of the time.")
        if self.sensitivity:
            vals = [r["assurance"] for r in self.sensitivity]
            lines.append(f"prior sensitivity: assurance ranges {min(vals):.0%} to {max(vals):.0%} "
                         f"across four defensible priors")
        return "\n".join(lines)


@dataclass(frozen=True)
class Interim:
    """An interim go/no-go, conditioned on the patients observed so far.

    Two different questions live here and they can disagree. The dual-criterion rule asks where the
    posterior sits *today*; the predictive probability asks whether the trial can still reach GO if
    it runs to full enrolment. A trial can be "not yet ruled out" on the first and hopeless on the
    second — 3 responses in the first 30 of a planned 120 leaves P(effect > LRV) at 30%, which is
    not a STOP by the posterior, while the predictive probability of ever clearing the gates is
    0.05%.

    Reporting "promising but short of the gates" there would be actively misleading, so futility
    wins: when `predictive_probability` falls below the rule's `stop_lrv`, the decision is STOP and
    the reason says why.
    """
    predictive_probability: float  # P(the trial ENDS in GO | data so far)
    posterior_mean: float
    decision: str
    reason: str
    prior: Prior
    rule: DecisionRule
    observed: int
    n_planned: int

    @property
    def futile(self) -> bool:
        """The trial is very unlikely to clear its gates even if run to completion."""
        return self.predictive_probability < self.rule.stop_lrv

    def summary(self) -> str:
        return (f"predictive probability of success {self.predictive_probability:.1%}   "
                f"posterior mean {self.posterior_mean:.3f}   "
                f"{self.observed}/{self.n_planned} observed\n"
                f"decision: {self.decision} - {self.reason}")


def _at(oc: list, theta: float) -> float:
    """The GO rate on an OC curve at a given true effect, by nearest grid point.

    Exact equality would be fragile: the curve is evaluated on a grid that need not land precisely
    on the TV or the LRV, and silently returning NaN there would quietly hide the two numbers a
    reviewer looks at first.
    """
    if not oc:
        return float("nan")
    best = min(oc, key=lambda r: abs(r["theta"] - theta))
    return float(best["go_rate"])


def _rule(tv, lrv, gate_tv, gate_lrv, stop_lrv, higher_is_better) -> DecisionRule:
    if tv is None or lrv is None:
        raise ValueError("a go/no-go needs a target value (tv) and a lower reference value (lrv)")
    tv, lrv = float(tv), float(lrv)
    if higher_is_better and lrv > tv:
        raise ValueError("the LRV must not exceed the TV: the minimum worth pursuing cannot be "
                         "more ambitious than the value you hope for")
    if not higher_is_better and tv > lrv:
        raise ValueError("with a lower-is-better endpoint the TV must not exceed the LRV")
    return DecisionRule(tv=tv, lrv=lrv, gate_tv=float(gate_tv), gate_lrv=float(gate_lrv),
                        stop_lrv=float(stop_lrv), higher_is_better=bool(higher_is_better))


def design(*, n: int, tv: float, lrv: float, endpoint: str = "proportion",
           control_rate: float | None = None, sd: float | None = None,
           prior_successes=None, prior_n=None, prior_a=None, prior_b=None,
           prior_mu=None, prior_sd=None, prior: Prior | None = None,
           gate_tv: float = 0.80, gate_lrv: float = 0.90, stop_lrv: float = 0.10,
           higher_is_better: bool = True, full: bool = True) -> Design:
    """Design-stage go/no-go: the probability this trial ends in GO, before it runs.

    n              planned enrolment (TOTAL across both arms when `control_rate` is given)
    tv, lrv        Target Value and Lower Reference Value. For a two-arm design these are RISK
                   DIFFERENCES (treatment minus control), not response rates.
    control_rate   supply this for a two-arm design against a concurrent control; omit it for a
                   single-arm design against a performance goal
    endpoint       'proportion' (Beta-Binomial) or 'mean' (Normal-Normal, needs `sd`)
    prior_*        a previous study as successes/n, or an explicit Beta(a,b) / Normal(mu,sd)
    full           also compute the OC curve and the prior-sensitivity panel (the slow parts)

    A device performance goal is the degenerate case tv == lrv: set both to the goal.
    """
    rule = _rule(tv, lrv, gate_tv, gate_lrv, stop_lrv, higher_is_better)
    n = int(n)
    if n <= 0:
        raise ValueError("the planned sample size must be positive")
    if endpoint == "proportion" and control_rate is None and not (0 <= rule.tv <= 1 and 0 <= rule.lrv <= 1):
        raise ValueError("for a single-arm proportion endpoint the TV and LRV must be between 0 "
                         "and 1 (express 30% as 0.30)")
    p = prior or build_prior(endpoint=endpoint, tv=rule.tv, lrv=rule.lrv,
                             prior_successes=prior_successes, prior_n=prior_n,
                             prior_a=prior_a, prior_b=prior_b,
                             prior_mu=prior_mu, prior_sd=prior_sd)

    if control_rate is not None:                       # two-arm, against a concurrent control
        n_t = n // 2
        n_c = n - n_t
        assur = assurance_diff(p, float(control_rate), n_t, n_c, rule)
        # The two-arm OC curve is indexed by `theta` = the risk difference, so type I error and
        # power are read off it at the LRV and the TV. There is no type_i_and_power_diff helper;
        # the curve is computed anyway when full=True, so read it rather than recompute.
        oc = (operating_characteristics_diff(p, float(control_rate), n_t, n_c, rule)
              if full else [])
        t1 = _at(oc, rule.lrv)
        power = _at(oc, rule.tv)
    else:
        assur = assurance(p, n, rule, sd)
        oc = operating_characteristics(p, n, rule, sd) if full else []
        t1, power = type_i_and_power(p, n, rule, sd)

    x, y = p.params
    p_tv = float(prob_exceeds(p.kind, x, y, rule.tv, rule.higher_is_better))
    p_lrv = float(prob_exceeds(p.kind, x, y, rule.lrv, rule.higher_is_better))
    call, reason = decide(p_tv, p_lrv, rule)

    return Design(
        assurance=round(float(assur), 4), power=round(float(power), 4),
        type_i_error=round(float(t1), 4), decision=call, reason=reason,
        prior=p, rule=rule, n_planned=n,
        under_powered=bool(not math.isnan(power) and power < 0.80),
        operating_characteristics=oc,
        sensitivity=sensitivity(p, n, rule, sd) if (full and control_rate is None) else [])


def interim(*, successes: int, n: int, n_planned: int, tv: float, lrv: float,
            control_successes: int | None = None, control_n: int | None = None,
            prior_successes=None, prior_n=None, prior_a=None, prior_b=None,
            prior: Prior | None = None, control_prior: Prior | None = None,
            gate_tv: float = 0.80, gate_lrv: float = 0.90, stop_lrv: float = 0.10,
            higher_is_better: bool = True) -> Interim:
    """Interim go/no-go on the patients seen so far: will this trial end in GO?

    The predictive probability of success is the futility signal that stops a trial early. Supply
    `control_successes` / `control_n` for a two-arm interim, in which case tv/lrv are again RISK
    DIFFERENCES.
    """
    rule = _rule(tv, lrv, gate_tv, gate_lrv, stop_lrv, higher_is_better)
    successes, n, n_planned = int(successes), int(n), int(n_planned)
    if n > n_planned:
        raise ValueError(f"observed n ({n}) exceeds the planned n ({n_planned})")
    if not 0 <= successes <= n:
        raise ValueError(f"successes ({successes}) must be between 0 and n ({n})")
    p = prior or build_prior(endpoint="proportion", tv=rule.tv, lrv=rule.lrv,
                             prior_successes=prior_successes, prior_n=prior_n,
                             prior_a=prior_a, prior_b=prior_b)

    if control_successes is not None and control_n is not None:
        pc = control_prior or Prior("Vague", "beta", (1.0, 1.0), "Uniform Beta(1,1) control prior.")
        n_t = n_planned // 2
        n_c = n_planned - n_t
        ppos = predictive_prob_success_diff(p, pc, successes, n, int(control_successes),
                                            int(control_n), n_t, n_c, rule)
        at, bt = beta_posterior(*p.params, successes, n)
        ac, bc = beta_posterior(*pc.params, int(control_successes), int(control_n))
        post_mean = at / (at + bt) - ac / (ac + bc)
        p_tv = float(prob_diff_exceeds("beta", (at, bt), (ac, bc), rule.tv, rule.higher_is_better))
        p_lrv = float(prob_diff_exceeds("beta", (at, bt), (ac, bc), rule.lrv, rule.higher_is_better))
    else:
        ppos = predictive_prob_success(p, successes, n, n_planned, rule)
        a, b = beta_posterior(*p.params, successes, n)
        post_mean = a / (a + b)
        p_tv = float(prob_exceeds("beta", a, b, rule.tv, rule.higher_is_better))
        p_lrv = float(prob_exceeds("beta", a, b, rule.lrv, rule.higher_is_better))

    call, reason = decide(p_tv, p_lrv, rule)
    # Futility overrides the posterior call. See the note on Interim: a trial whose predictive
    # probability of ever clearing the gates is 0.05% must not be reported as "promising".
    if float(ppos) < rule.stop_lrv:
        call = "STOP"
        reason = (f"Predictive probability of success is only {float(ppos):.1%}: even running to "
                  f"full enrolment ({n_planned:,}), this trial is very unlikely to clear its "
                  f"pre-specified gates. Stop for futility.")
    return Interim(predictive_probability=round(float(ppos), 4),
                   posterior_mean=round(float(post_mean), 4),
                   decision=call, reason=reason, prior=p, rule=rule,
                   observed=n, n_planned=n_planned)
