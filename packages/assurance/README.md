# assurance

**Exploratory Bayesian calculations for trial design.** Conjugate models, with deterministic numerical integration where needed.

**Research prototype:** Do not use this library for patient care, clinical decisions, trial stopping,
regulated submissions, or confidential data. Its results require independent statistical review.
The decision labels illustrate a specified rule; they are not recommendations.

```python
import assurance

d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20,
                     gate_tv=0.80, gate_lrv=0.90, stop_lrv=0.10)
print(d.summary())
```

```text
assurance 76.1%   power 28.9%   type I 0.0%   n=100
decision (prior only): GO - P(above TV 0.3) = 85.2%, P(above LRV 0.15) = 99.8%. Clears both pre-specified gates (80% at the TV and 90% at the LRV).
prior: Beta(9, 13), from a uniform prior updated with the previous study: 8 responses in 20 patients.
UNDER-POWERED: power at the TV is 29%, below the conventional 80%. Even if the true effect equals
the Target Value this design reaches GO only 29% of the time.
prior sensitivity: assurance ranges 6% to 76% across four example priors
```

That output is the argument for the library. The headline number looks good; the two lines under it
illustrate how results change when the prior changes. A single assurance figure hides that sensitivity.

## Why assurance rather than power

Classical power asks *"what is the chance of success **if** the true effect is exactly X?"* — a
question nobody can answer, because if you knew X you would not run the trial. **Assurance**
integrates power over a specified prior for X. It is conditional on that prior and the design
assumptions; it can be higher or lower than power at a selected effect size.

## No Monte Carlo, and why that matters

Every model is conjugate, so every quantity is closed-form or deterministic quadrature on a fixed
grid. There is no seed to manage. Results are deterministic for fixed inputs and environment;
floating-point results can differ across library versions and platforms.

When a programme decision turns on whether assurance is 0.78 or 0.82, a number that moves with the
seed is not enough evidence. Record the software environment and independently check decisions near
a threshold.

## What it does

| | |
|---|---|
| **Endpoints** | binary (Beta-Binomial), continuous mean with known SD (Normal-Normal) |
| **Framings** | single-arm against a performance goal; two-arm against a concurrent control |
| **Design stage** | assurance, power, type I error, operating-characteristic curve, prior-sensitivity panel |
| **Interim** | predictive probability of success (the futility signal), posterior, decision |

Decisions use the dual-criterion (Lalonde) rule: **GO** needs both P(effect > TV) >= `gate_tv` and
P(effect > LRV) >= `gate_lrv`; **STOP** when P(effect > LRV) < `stop_lrv`; **CONSIDER** in between.
A device performance goal is the degenerate case TV == LRV.

## Interim analysis, and the one subtlety

```python
i = assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15,
                      prior_a=1, prior_b=1, gate_tv=0.80, gate_lrv=0.90, stop_lrv=0.10)
i.predictive_probability   # 0.2896 — P(the trial ENDS in GO), not P(the effect is real)
i.decision                 # 'CONSIDER'
```

Two different questions live in an interim and they can disagree. The dual-criterion rule asks
where the posterior sits **today**. The predictive probability asks whether the trial can still
reach GO if it runs to **full enrolment**.

3 responses in the first 30 of a planned 120 leaves P(effect > LRV) at 30% — not a STOP by the
posterior — while the chance of ever clearing the gates is 0.05%. Reporting *"promising but short of
the gates"* there would be actively misleading, so **futility wins**: below `stop_lrv` the decision
becomes STOP and `.futile` is True.

## Two-arm designs

`tv` and `lrv` are **risk differences** (treatment minus control), not response rates, and `n` is
the total across both arms:

```python
control_prior = assurance.Prior("Control", "beta", (1., 1.), "Example uniform prior")
assurance.design(n=200, tv=0.15, lrv=0.0, control_rate=0.35,
                 prior_successes=14, prior_n=20, control_prior=control_prior,
                 gate_tv=0.80, gate_lrv=0.90, stop_lrv=0.10)  # assurance 0.8875

assurance.interim(successes=18, n=40, control_successes=10, control_n=38,
                  n_planned=200, tv=0.15, lrv=0.0, prior_a=1, prior_b=1,
                  control_prior=control_prior, gate_tv=0.80, gate_lrv=0.90,
                  stop_lrv=0.10)                       # PPoS 0.3783
```

## Priors, stated rather than assumed

Assurance is only as defensible as its prior, so every prior records where it came from:

```python
d.prior.provenance
# 'Beta(9, 13), from a uniform prior updated with the previous study: 8 responses in 20 patients.'
d.prior_ess          # 22.0 — if this exceeds n, the prior is doing more work than the trial will
```

`d.sensitivity` reports assurance under four example priors — informed, vague, skeptical,
enthusiastic — with each one's verdict. A design whose assurance is 0.8 under your prior and 0.2
under a skeptic centred at the LRV is a statement about the prior, not about the drug.

## The primitives

The high-level API requires explicit treatment priors and decision gates. Two-arm calls also require
an explicit control prior. The design calculation treats `control_rate` as a fixed generating rate;
the control prior is used in the analysis. Two-arm results use fixed-grid numerical integration, and
their precision is not guaranteed near a decision threshold. The control density's approximate grid
mass must be within 0.5% of one; this is a diagnostic, not an error bound on the result. Control Beta
parameters below one and interim completion grids above 10,000 cells are refused. Low-level primitives have their own defaults
and require expert review of every assumption. No set of example priors is universally defensible.

`assurance.core` exposes everything the convenience layer is built from — `Prior`, `DecisionRule`,
`beta_posterior`, `prob_exceeds`, `prob_diff_exceeds`, `decide`, `assurance`, `assurance_diff`,
`predictive_prob_success`, `predictive_prob_success_diff`, `operating_characteristics`,
`type_i_and_power`, `prior_panel`, `prior_ess` — because trial statisticians reasonably want to
compose them themselves.

## Install

```bash
python -m pip install ./packages/assurance
```

Run from the repository root. Requires numpy and scipy. The candidate distribution is named
`clinical-insight-assurance`, while the Python import remains `assurance`. It has not been published,
and its name is not confirmed or reserved. PyPI's `assurance` is an unrelated project; do not install
that project expecting this library. Python distributions can expose the same import name, so avoid
installing another package that provides `assurance` in the same environment.

## License

MIT
