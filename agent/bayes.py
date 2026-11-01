"""Bayesian decision engine for early-development go/no-go — now an adapter over `assurance`.

None of this maths is specific to this warehouse, this agent, or even to healthcare data
engineering: it is trial statistics. It was extracted to the `assurance` package
(packages/assurance) so it can be installed, versioned and cited on its own, and so the closed-form
guarantee it makes is testable outside this repo.

Nothing about the numbers changed. This module re-exports the same names so `agent.modeling`, the
tests and the examples keep importing exactly what they always did.

For new code prefer the high-level API, which builds the Prior and DecisionRule for you:

    import assurance
    assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20,
                     gate_tv=0.8, gate_lrv=0.9, stop_lrv=0.1)
    assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15,
                      prior_a=1, prior_b=1, gate_tv=0.8, gate_lrv=0.9, stop_lrv=0.1)

The supported conjugate calculations use closed forms or deterministic quadrature rather than Monte
Carlo. Floating-point libraries and platforms can differ, especially near a decision threshold.
"""
from __future__ import annotations

from assurance.core import (
    MAX_ENUM,
    MAX_ENUM_DIFF,
    DecisionRule,
    Prior,
    assurance,
    assurance_diff,
    beta_posterior,
    decide,
    go_grid_binary,
    go_grid_diff,
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

__all__ = [
    "Prior", "DecisionRule", "MAX_ENUM", "MAX_ENUM_DIFF",
    "beta_posterior", "normal_posterior", "prob_exceeds", "prob_diff_exceeds", "decide",
    "prior_ess", "prior_panel", "go_grid_binary", "go_grid_diff",
    "assurance", "operating_characteristics", "type_i_and_power", "predictive_prob_success",
    "assurance_diff", "operating_characteristics_diff", "predictive_prob_success_diff",
]
