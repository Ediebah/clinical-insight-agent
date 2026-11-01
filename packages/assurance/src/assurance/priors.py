"""Turning what you actually know into a prior, and showing how much the answer depends on it.

Assurance is only as defensible as its prior, so two things matter more than the arithmetic:
stating where the prior came from, and showing what a skeptic would conclude from the same design.
`Prior.provenance` carries the first; `sensitivity()` is the second.
"""
from __future__ import annotations

import math

from .core import Prior, assurance, beta_posterior, decide, prior_panel, prob_exceeds


def build_prior(*, endpoint: str = "proportion", tv: float, lrv: float,
                prior_successes=None, prior_n=None, prior_a=None, prior_b=None,
                prior_mu=None, prior_sd=None) -> Prior:
    """The informed prior from whatever the caller supplied, else weakly informative.

    Precedence: an explicit Beta(a, b) or Normal(mu, sd) wins; then a previous study's
    successes/n, which is turned into a posterior from a uniform prior; then a deliberately vague
    default. Every branch records its provenance, because "where did this prior come from" is the
    first question anyone competent will ask.
    """
    pairs = ((prior_a, prior_b), (prior_successes, prior_n), (prior_mu, prior_sd))
    present = [i for i, pair in enumerate(pairs) if any(v is not None for v in pair)]
    if endpoint not in ("proportion", "mean"):
        raise ValueError("unsupported prior endpoint")
    allowed = (0, 1) if endpoint == "proportion" else (2,)
    if len(present) > 1 or (present and (present[0] not in allowed or None in pairs[present[0]])):
        raise ValueError("supply one complete prior compatible with the endpoint")
    if present:
        first, second = (float(v) for v in pairs[present[0]])
        if not math.isfinite(first) or not math.isfinite(second):
            raise ValueError("prior parameters must be finite")
        if present[0] == 0 and (first <= 0 or second <= 0):
            raise ValueError("beta prior parameters must be positive")
        if present[0] == 1 and (first < 0 or second <= 0 or first > second or
                                not first.is_integer() or not second.is_integer()):
            raise ValueError("prior study counts must be valid integers")
        if present[0] == 2 and second <= 0:
            raise ValueError("normal prior standard deviation must be positive")
    if endpoint == "mean":
        if prior_mu is None:
            return Prior("Vague", "normal", (float(lrv), 10.0 * (abs(tv - lrv) or 1.0)),
                         "Weakly informative (no prior study supplied); centred at the LRV.")
        return Prior("Informed", "normal", (float(prior_mu), float(prior_sd or 1.0)),
                     f"Supplied prior: mean {prior_mu:g}, SD {prior_sd:g}.")
    if prior_a is not None and prior_b is not None:
        return Prior("Informed", "beta", (float(prior_a), float(prior_b)),
                     f"Supplied prior: Beta({prior_a:g}, {prior_b:g}).")
    if prior_successes is not None and prior_n is not None:
        a, b = beta_posterior(1.0, 1.0, int(prior_successes), int(prior_n))
        return Prior("Phase-I informed", "beta", (a, b),
                     f"Beta({a:g}, {b:g}), from a uniform prior updated with the previous study: "
                     f"{int(prior_successes)} responses in {int(prior_n)} patients.")
    return Prior("Vague", "beta", (1.0, 1.0),
                 "Uniform Beta(1,1) (no prior study supplied): every response rate equally likely.")


def sensitivity(prior: Prior, n_planned: int, rule, sd: float | None = None) -> list[dict]:
    """Assurance under each of four example priors, with each one's prior-only verdict.

    The single number is never the whole answer. A design whose assurance is 0.8 under your prior
    and 0.2 under a skeptic centred at the LRV is a design whose result is a statement about the
    prior, not about the drug. This panel makes that visible instead of leaving it implicit.
    """
    rows = []
    for p in prior_panel(prior, rule):
        x, y = p.params
        p_tv = float(prob_exceeds(p.kind, x, y, rule.tv, rule.higher_is_better))
        p_lrv = float(prob_exceeds(p.kind, x, y, rule.lrv, rule.higher_is_better))
        call, _ = decide(p_tv, p_lrv, rule)
        rows.append({"prior": p.name, "params": [round(float(v), 3) for v in p.params],
                     "assurance": round(assurance(p, n_planned, rule, sd), 4),
                     "call": call, "provenance": p.provenance})
    return rows
