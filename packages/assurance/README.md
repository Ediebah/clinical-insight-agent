# assurance

**Bayesian go/no-go for trial design and interim decisions.** Conjugate, closed-form, no Monte Carlo.

```python
import assurance

d = assurance.design(n=100, tv=0.30, lrv=0.15, prior_successes=8, prior_n=20)
print(d.summary())
```

```text
assurance 76.1%   power 28.9%   type I 0.0%   n=100
decision (prior only): GO - P(above TV 0.3) = 85.2%, P(above LRV 0.15) = 99.8%. Clears both gates.
prior: Beta(9, 13), from a uniform prior updated with the previous study: 8 responses in 20 patients.
UNDER-POWERED: power at the TV is 29%, below the conventional 80%. Even if the true effect equals
the Target Value this design reaches GO only 29% of the time.
prior sensitivity: assurance ranges 6% to 76% across four defensible priors
```

That output is the argument for the library. The headline number looks good; the two lines under it
say the design succeeds mostly because the prior is optimistic, and that a skeptic would put the
chance at 6%. A single assurance figure hides both.

## Why assurance rather than power

Classical power asks *"what is the chance of success **if** the true effect is exactly X?"* — a
question nobody can answer, because if you knew X you would not run the trial. **Assurance**
integrates over what you actually believe about X and answers the question a decision-maker has:
*given everything we know, what is the chance this trial succeeds?* It is usually the lower and more
honest number.

## No Monte Carlo, and why that matters

Every model is conjugate, so every quantity is closed-form or deterministic quadrature on a fixed
grid. There is no seed to manage, and re-running never changes a verdict.

When a programme decision turns on whether assurance is 0.78 or 0.82, a number that moves with the
seed is not evidence. And a regulator asking you to reproduce a design two years later should get
the same digits, not the same distribution.

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
i = assurance.interim(successes=12, n=40, n_planned=100, tv=0.30, lrv=0.15)
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
assurance.design(n=200, tv=0.15, lrv=0.0, control_rate=0.35,
                 prior_successes=14, prior_n=20)       # assurance 0.8875

assurance.interim(successes=18, n=40, control_successes=10, control_n=38,
                  n_planned=200, tv=0.15, lrv=0.0)     # PPoS 0.3783
```

## Priors, stated rather than assumed

Assurance is only as defensible as its prior, so every prior records where it came from:

```python
d.prior.provenance
# 'Beta(9, 13), from a uniform prior updated with the previous study: 8 responses in 20 patients.'
d.prior_ess          # 22.0 — if this exceeds n, the prior is doing more work than the trial will
```

`d.sensitivity` reports assurance under four defensible priors — informed, vague, skeptical,
enthusiastic — with each one's verdict. A design whose assurance is 0.8 under your prior and 0.2
under a skeptic centred at the LRV is a statement about the prior, not about the drug.

## The primitives

`assurance.core` exposes everything the convenience layer is built from — `Prior`, `DecisionRule`,
`beta_posterior`, `prob_exceeds`, `prob_diff_exceeds`, `decide`, `assurance`, `assurance_diff`,
`predictive_prob_success`, `predictive_prob_success_diff`, `operating_characteristics`,
`type_i_and_power`, `prior_panel`, `prior_ess` — because trial statisticians reasonably want to
compose them themselves.

## Install

```bash
pip install assurance
```

Requires numpy and scipy.

## License

MIT
