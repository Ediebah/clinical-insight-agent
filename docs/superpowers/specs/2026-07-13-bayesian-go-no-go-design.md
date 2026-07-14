# Bayesian go/no-go decision module — design

**Date:** 2026-07-13
**Status:** approved, ready for implementation planning
**Scope:** one feature. Dose-finding (BOIN/CRM), group-sequential designs, and Bayesian borrowing
from external controls are explicitly OUT of scope and are separate future modules.

## 1. Why

The platform today answers observational and descriptive questions (readmissions, cost, prevalence)
plus a solid inference layer (regression, survival, causal, A/B, non-inferiority). Early clinical
development asks a different question: *should we invest in the next study, and should we keep going
once it starts?* That is the go/no-go decision, and in early development it is usually Bayesian.

This module adds that capability for both drug and medical-device trials, and it is built to the
three pillars of [FDA's January 2026 draft guidance on Bayesian methodology](https://www.berryconsultants.com/resource/guide-to-the-draft-fda-bayesian-guidance-2026)
(CDER/CBER) and the [2010 CDRH device guidance](https://www.fda.gov/media/71512/download):

| FDA pillar | How this module satisfies it |
|---|---|
| Pre-specified decision criteria and thresholds | Dual-criterion TV/LRV gates, fixed before the calculation and echoed in every output |
| Operating characteristics evaluated by simulation | The OC simulator: type I error, power, and GO-rate across a grid of true effects |
| Justified priors with sensitivity analysis | The prior panel: four defensible priors, with the verdict flagged FRAGILE if it flips; plus prior effective-sample-size reporting |

FDA mandates no particular software, only that it be "reliable and adequately tested." Every model in
scope here is conjugate, so the engine is closed-form and deterministic rather than sampled (see §4).
That is a deliberate rigor claim, in the same family as "the statistical guardrail is deterministic;
the LLM may phrase a caveat but never invent or drop one."

## 2. Scope

Two modes, two framings, two endpoint types. All combinations are supported.

**Modes**

- **Design-stage** (no data). "Phase I showed 8/20 responses. What is the probability a 100-patient
  Phase II succeeds?" Produces assurance / probability of success.
- **Interim** (queries the warehouse or uploaded data). "We are 40 patients into the trial with 12
  responses. Continue or stop?" Produces the posterior and the predictive probability of eventual
  success.

**Framings**

- **Single-arm vs a performance goal.** The standard medical-device shape (an objective performance
  criterion): is the success rate above a fixed threshold?
- **Two-arm vs a control.** The standard drug shape: is the treatment effect above a threshold?

**Endpoints**

- **Binary** (response rate, procedural success, freedom from complication).
- **Continuous mean** (change from baseline).

Time-to-event endpoints are out of scope: they need a different likelihood and would not be conjugate.

## 3. The decision rule (dual-criterion TV/LRV)

The industry-standard early-development framework. Two thresholds are pre-specified:

- **LRV** (Lower Reference Value): the minimum effect worth pursuing.
- **TV** (Target Value): the effect we hope for.

Given the posterior of the effect `θ`:

```
GO        P(θ > TV) >= gate_tv   AND  P(θ > LRV) >= gate_lrv     (defaults 0.80 / 0.90)
STOP      P(θ > LRV) < stop_lrv                                  (default 0.10)
CONSIDER  anything else
```

A **device performance goal is the degenerate case**: set `TV == LRV == the performance goal` and the
three-way verdict collapses to GO / NO-GO against that single threshold. No separate code path.

`higher_is_better=false` (an adverse-event or mortality endpoint, where lower is better) mirrors the
comparisons, following the convention `fit_noninferiority` already uses.

## 4. Architecture

### New module: `agent/bayes.py`

The decision engine as pure functions. No LLM, no I/O, no `ModelResult`. Depends only on numpy and
scipy (both already pinned). Independently testable against textbook values. Kept out of
`modeling.py`, which is already ~1,300 lines.

```python
@dataclass(frozen=True)
class Prior:
    name: str                    # "Phase-I informed" | "Vague" | "Skeptical" | "Enthusiastic"
    kind: str                    # "beta" (binary endpoint) | "normal" (continuous endpoint)
    params: tuple[float, float]  # beta: (a, b).  normal: (mu, sd).
    provenance: str              # human-readable: where this prior came from

@dataclass(frozen=True)
class DecisionRule:
    tv: float                    # Target Value
    lrv: float                   # Lower Reference Value (== tv for a device performance goal)
    gate_tv: float = 0.80        # required P(theta > tv)
    gate_lrv: float = 0.90       # required P(theta > lrv)
    stop_lrv: float = 0.10       # P(theta > lrv) below this -> STOP
    higher_is_better: bool = True

beta_posterior(a, b, x, n) -> (a', b')                  # conjugate, exact
normal_posterior(mu0, sd0, xbar, sd, n) -> (mu', sd')   # conjugate, exact
prob_exceeds(post, threshold) -> float                  # single-arm, closed form (scipy sf)
prob_diff_exceeds(post_t, post_c, threshold) -> float   # two-arm.
                                                        #   normal: closed form (a difference of
                                                        #     normals is normal).
                                                        #   beta: no closed form, so 1-D quadrature
                                                        #     P(t - c > d) = INT f_c(v) * sf_t(v + d) dv
                                                        #     on a fixed grid. Deterministic, fast,
                                                        #     vectorizable. NOT Monte Carlo.
decide(p_tv, p_lrv, rule) -> (call, reason)             # the truth table above
predictive_prob_success(post, observed, n_planned, rule) -> float
                                                        # EXACT for a binary endpoint: enumerate every
                                                        # possible count of successes among the
                                                        # not-yet-observed patients (a double sum over
                                                        # both arms in the two-arm framing), weight
                                                        # each by the beta-binomial predictive pmf,
                                                        # apply the final decision rule to each.
                                                        # Continuous endpoint: the normal posterior-
                                                        # predictive, integrated on a grid.
                                                        # No simulation error either way.
assurance(prior, n_planned, rule) -> float              # integrate P(GO | theta) over the prior on a
                                                        # fine grid.
operating_characteristics(prior, n_planned, rule, grid) -> list[dict]
                                                        # for each true theta in the grid: the GO rate.
                                                        # GO rate at the null = type I error;
                                                        # at the TV = power.
prior_panel(informed, endpoint) -> list[Prior]          # the four defensible priors
prior_ess(prior) -> float                               # effective sample size (beta: a + b)
```

**No Monte Carlo anywhere in the module.** Every quantity is either closed-form or deterministic
numeric integration on a fixed grid. There is no random seed to manage, results are bit-reproducible
across runs and platforms, and the tests can assert exact values rather than tolerances. This also
means the module cannot silently produce a different verdict on re-run, which matters for a tool whose
whole purpose is to support a decision.

**Cost bound.** The binary two-arm predictive enumeration is `O((m_t + 1) * (m_c + 1))` quadratures,
where `m` is the number of patients not yet observed in each arm. It is vectorized in numpy and is
well under a second for trials of a few hundred per arm. `bayes.py` enforces a documented cap on the
enumeration size and, above it, bins the predictive distribution rather than silently getting slow.

### `agent/modeling.py` — two thin entry points

They call into `bayes.py` and package results into the existing `ModelResult` contract, exactly like
every other model family.

- `calc_assurance(**params) -> ModelResult` — design-stage, takes no data. Mirrors `calc_sample_size`.
- `fit_interim(df, **params) -> ModelResult` — interim, takes a DataFrame of subjects observed so far.
  Mirrors every other `fit_*`.

Two functions rather than one because the *routing* genuinely differs (one needs SQL, one does not),
while the Bayesian core underneath is shared.

`ModelResult` fields used:

- `verdict = {"call": "GO"|"CONSIDER"|"STOP", "reason": str, ...}` — renders in the existing verdict card.
- `series` — the curve. Design-stage: assurance vs planned n. Interim: predictive probability vs enrollment.
- `terms` — the posterior summary (estimate + 95% credible interval).
- `issues` — the deterministic caveats (§6).
- `arms` — per-arm posterior summaries in the two-arm framing.

### `agent/agent.py` — routing

Two new `model_type` values in the router prompt:

- `'assurance'` — design-stage. **No data, no `analytic_sql`.** Routed through a new `_run_assurance`,
  which mirrors the existing no-data `_run_sample_size` path (special-cased in `run_analysis`
  alongside `sample_size`). Extracted params: `endpoint_type` ("proportion"|"mean"), `framing`
  ("single_arm"|"two_arm"), `n_planned`, `tv`, `lrv`, `higher_is_better`, and the prior source
  (`prior_successes` + `prior_n` from a previous study, or explicit `prior_a`/`prior_b`, or none for
  a vague default).
- `'interim'` — data-driven. `analytic_sql` returns one row per subject observed so far, with the
  outcome column and, in the two-arm framing, the arm column. `_fit_model` gains an `interim` branch.
  Also needs `n_planned` (the full planned enrollment) to compute the predictive probability.

`_interpret_model` gains guidance to LEAD with the verdict, as it already does for non-inferiority.

### `app.py` — rendering

Reuses the existing verdict card and series chart. One new element: the prior-sensitivity table.

### `agent/report.py` — export

A new section rendering the decision, the pre-specified criteria, the priors and their provenance,
the sensitivity panel, and the operating characteristics.

## 5. Data flow

**Design-stage**

```
question -> _triage -> _route(model_type='assurance', params)   [no SQL]
         -> _run_assurance -> modeling.calc_assurance -> bayes core
         -> ModelResult(verdict, series, issues) -> _interpret_model -> UI + report
```

**Interim**

```
question -> _triage -> _route(model_type='interim', analytic_sql)
         -> run_query (+ existing self-heal) -> _fit_model -> modeling.fit_interim -> bayes core
         -> guardrails.analyze(df) also runs (this path HAS data)
         -> ModelResult(verdict, series, issues) -> _interpret_model -> UI + report
```

On the guardrail: the interim path gets the full deterministic guardrail for free, because it has a
DataFrame. The design-stage path has no DataFrame, so its caveats live in `ModelResult.issues`,
computed in code and un-droppable by the LLM. That is the same philosophy applied where no data
exists, and it matches how `calc_sample_size` already behaves.

## 6. Deterministic caveats (always emitted)

Computed in code. The LLM may phrase them but may never invent or drop one.

1. **The prior, stated explicitly**, with its parameters and provenance ("Beta(9,13), from Phase I: 8
   responses in 20 patients").
2. **Prior sensitivity**: the verdict under each of the four priors, and whether the call HOLDS or is
   FRAGILE. A verdict that flips across defensible priors is reported as fragile, never as an answer.
3. **Prior effective sample size vs observed n.** If `prior_ess > n_observed`, flag that the prior is
   doing more work than the evidence. (This is FDA's ESS-quantification requirement.)
4. **Assurance vs classical power**, when they diverge: power assumes the effect is exactly one value;
   assurance averages over the uncertainty about it, and is usually the lower, more honest number.
5. **Operating characteristics**: the type I error and power implied by the pre-specified rule.
6. **Beta(ε,ε) degeneracy guard** (§7).
7. The standing **synthetic-data** note and the **not a pre-specified SAP / not regulatory-grade**
   statement, consistent with the existing ICH-E9 language in the report.

## 7. Error handling and edge cases

Every entry point wraps its body in `try/except` and returns `ModelResult(error=...)`. Nothing raises
into the app. This is the existing convention across `modeling.py`.

Fail-closed validation with actionable messages:

- `LRV > TV` (with `higher_is_better=true`) is contradictory: error explaining the ordering.
- Proportions outside [0, 1]; `n_planned <= 0`; non-positive prior parameters.
- **Interim with `n_observed > n_planned`**: not an interim. Error saying so, and pointing at the
  final-analysis framing.
- **Interim with `n_observed == n_planned`**: the trial is complete. The predictive probability is
  degenerate (it is just the posterior decision). Report the final decision and say so, rather than
  pretending to predict.
- **Zero or perfect responses with a near-noninformative prior.** FDA's 2026 draft guidance
  specifically warns that a Beta(ε,ε) prior becomes *unexpectedly informative* at 0 or 100% response.
  Guard: when the observed data is all-success or all-failure AND the prior is near-degenerate
  (`a + b < 1`), emit a loud caveat and report the verdict as unreliable. **This is a real trap for an
  early interim look and is a required test case.**
- Empty cohort: already caught upstream by the existing empty-cohort guard before `_fit_model` runs.

## 8. Testing

The project's culture is to assert ground truth, not the absence of a crash. This module is unusually
well suited to that, because closed-form Bayesian quantities have exact known values.

**`tests/test_bayes.py` (pure engine)**

- **Conjugacy**: Beta(1,1) updated with 8 successes in 20 gives exactly Beta(9,13); posterior mean is
  exactly 9/22.
- **`prob_exceeds`** agrees with `scipy.stats.beta.sf` to machine precision.
- **Predictive probability is exact**: cross-check the enumeration against a brute-force Monte Carlo
  simulation written *in the test only*. They must agree within MC error. This validates the exactness
  claim without putting a sampler in the shipped code.
- **`prob_diff_exceeds` quadrature is right**: cross-check the beta-difference quadrature against a
  large Monte Carlo draw (again, in the test only), and against the closed form in the normal case.
- **Assurance collapses to power** (the key invariant): as the prior tightens onto a point mass at
  θ₀, assurance converges to the classical power at θ₀. Textbook-checkable and a strong test that the
  integration is right.
- **Assurance < power** when the prior has genuine spread. This is the whole reason assurance exists.
- **`decide` truth table**, including the boundary values of every gate.
- **Prior panel**: the skeptical prior is centred at or below the null; the enthusiastic one above.
- **`prior_ess`**: Beta(9,13) has an effective sample size of 22.

**`tests/test_modeling.py` (additions)**

- `calc_assurance` recovers a planted answer; the verdict flips GO → STOP as the LRV is raised.
- `fit_interim` with data well below the LRV yields STOP FOR FUTILITY.
- **Prior sensitivity**: construct a case where the skeptical prior flips the call, and assert the
  FRAGILE flag appears in `issues`. This tests the headline feature.
- **Device single-arm performance goal**: TV == LRV collapses cleanly to GO/NO-GO.
- **Beta(ε,ε) degeneracy**: all-success data with a near-degenerate prior emits the unreliability
  caveat.
- Error cases: LRV > TV, `n_observed > n_planned`, out-of-range proportions.

**`tests/test_agent.py` (additions)**

- A routed `assurance` spec reaches `_run_assurance` without touching SQL (monkeypatched LLM,
  following the existing `test_quality_agent` style).
- A routed `interim` spec dispatches correctly through `_fit_model`.

The existing `tests/test_app_smoke.py` already covers rendering end-to-end.

## 9. Out of scope (deliberately)

- Bayesian dose-finding (BOIN, CRM, mTPI). The natural *next* module.
- Group-sequential designs and alpha spending. A later module.
- Hierarchical borrowing from historical or external control arms. This one genuinely needs MCMC and
  will bring its own engine; the 2026 guidance devotes substantial attention to it (static vs dynamic
  discounting, drift, prior-data conflict), so it deserves its own spec.
- Time-to-event endpoints (non-conjugate).
- Any claim of being a regulatory submission tool. The module demonstrates method, on synthetic data.
