# Two-arm interim Bayesian go/no-go — Design

**One-line:** Extend `modeling.fit_interim` from a binary single-arm trial to a binary **two-arm** (treatment vs control) trial, deciding on the **risk difference** with a dual-criterion rule and reporting an **exact predictive probability of success** computed by a joint beta-binomial enumeration over both arms' remaining patients.

**Status:** design, awaiting review. Follows the shipped Bayesian go/no-go module (`agent/bayes.py`, `agent/prespec.py`, `modeling.calc_assurance`/`fit_interim`) and reuses its conventions verbatim.

---

## 1. Motivation and scope

The shipped interim analysis answers the single-arm question: given the responders seen so far against an absolute performance goal, will the trial clear its gates at full enrolment? The standard drug shape is instead **randomized**: is the *treatment* response rate enough better than a concurrent *control* to be worth a Phase III? This design adds that framing to the existing interim entry point.

**In scope:**
- Binary endpoint, two arms (treatment vs a concurrent control).
- Decision on the **absolute risk difference** `d = rate_treatment − rate_control`, dual-criterion (Target Value / Lower Reference Value).
- **Exact predictive probability of success (PPoS)** by joint enumeration of both arms' unobserved patients — the interim futility signal.
- Per-arm posteriors, the risk difference with a 95% credible interval, the pre-specification lock check, and the deterministic caveats — all reusing the existing interim scaffolding, rendering, and Word report.

**Out of scope (explicit, deferred, error-messaged):**
- Continuous two-arm interim (needs a nuisance-variance treatment; the whole interim path remains binary-only, as today).
- Unequal allocation (1:1 assumed; see §5).
- Historical/external-control **borrowing** (dynamic borrowing needs MCMC and careful discounting; out of scope per the original module spec and consistent with FDA's caution on external-data priors). Each arm gets a vague or a simply-supplied prior only.
- A two-arm **design-stage** `calc_assurance` (assurance/operating-characteristics for a randomized design). This design is interim-only; two-arm `calc_assurance` is noted as follow-on work.

## 2. Literature grounding

Every methodological choice implements a published method; nothing here is a novel construction.

- **Predictive probability of success for interim futility** — Lee & Liu (2008), *A predictive probability design for phase II cancer clinical trials*; Saville, Connor et al. (2014), *The utility of Bayesian predictive probabilities for interim monitoring of clinical trials*. A posterior threshold defines the minimum number of responders needed at the final analysis to declare success; the predictive probability of reaching that, given the interim data, is the futility signal. Low PPoS ⇒ stop.
- **Analytic beta-binomial predictive** — for a binary endpoint the number of future responders among the remaining patients follows a **beta-binomial** given the current Beta posterior, so the predictive probability is computed **analytically by enumeration**, with no simulation. (Simulation-based PPoS appears in the literature only for endpoints without a conjugate closed form, e.g. competing-risk / time-to-event; the binary case we implement is exactly tractable.)
- **Two-arm / randomized beta-binomial futility and the dual-criterion rule** — BOP2-DC, Zhao et al. (2023), *Bayesian optimal phase II designs with dual-criterion decision making*, *Pharmaceutical Statistics*: go/consider/no-go from the posterior probability that the treatment effect clears a **lower reference value** and a **clinically meaningful value**, supporting **randomized** binary trials with the effect characterized as the **posterior probability of a clinically meaningful difference** — i.e. `P(rate_t − rate_c > threshold)`.
- **Dual-criterion origin and terminology** — Lalonde et al. (2007), *Model-based drug development*, introduce the **Target Value (TV)** / **Lower Reference Value (LRV)** decision framework the module uses. BOP2-DC names the upper threshold the **Clinically Meaningful Value (CMV)**; it is the same structure. The spec and code retain TV/LRV (Lalonde) and note the CMV synonym.
- **Regulatory fit** — FDA draft guidance *Use of Bayesian Methodology in Clinical Trials of Drug and Biological Products* (2026) frames a success criterion generically as `Pr(d > a | data) ≥ c`, leaving the effect summary `d` to the clinically-justified choice of the sponsor, and explicitly endorses stopping "for futility if the predictive probability of ultimately meeting a success criterion is sufficiently low." Our risk-difference `d`, dual thresholds `a ∈ {LRV, TV}`, and gates `c ∈ {gate_lrv, gate_tv}`, with PPoS-driven futility, are a direct instance. (The dual-criterion *rule* is a decision-framework convention from the references above, layered on FDA's single-threshold primitive — not itself an FDA requirement.)

## 3. The two-arm decision rule

The effect is the risk difference `d = rate_t − rate_c` (`higher_is_better=True`; for an adverse-rate endpoint the sign flips as elsewhere in the module). The dual-criterion verdict reuses the shipped `decide(p_tv, p_lrv, rule)` unchanged, fed by the **posterior probability of the difference** rather than a one-arm tail:

```
p_tv  = prob_diff_exceeds("beta", post_t, post_c, rule.tv,  higher_is_better)   # P(d > TV)
p_lrv = prob_diff_exceeds("beta", post_t, post_c, rule.lrv, higher_is_better)   # P(d > LRV)
call, reason = decide(p_tv, p_lrv, rule)
```

`prob_diff_exceeds` already exists and is ground-truth tested (beta branch: 1-D quadrature `P(t−c>d) = ∫ f_c(v) · sf_t(v+d) dv`; normal branch closed-form). TV is the risk difference hoped for (e.g. +0.15); LRV is the minimum worth pursuing and **may be 0** (any benefit) **or slightly negative** (a non-inferiority-flavoured floor). The validation requires `TV ≥ LRV` for `higher_is_better` (reversed otherwise), both in `[-1, 1]`.

## 4. New `bayes.py` function — exact two-arm predictive probability

```
predictive_prob_success_diff(prior_t, prior_c, x_t, n_t, x_c, n_c,
                             n_planned_t, n_planned_c, rule) -> float
```

Exact PPoS that the randomized trial ends in GO, given each arm's data so far. Method:

1. **Observed posteriors:** `post_t = Beta(a_t + x_t, b_t + n_t − x_t)`, likewise `post_c`.
2. **Remaining patients:** `m_t = n_planned_t − n_t`, `m_c = n_planned_c − n_c`. If both are 0, return the final GO/no-GO decision (degenerate case).
3. **Joint predictive weights:** future responders `y_t ∈ [0, m_t]`, `y_c ∈ [0, m_c]` are independent across arms, so the joint weight is the outer product of the two beta-binomial posterior-predictive pmfs, `w_t(y_t) · w_c(y_c)`, with `w = betabinom.pmf(y; m, post_observed)`.
4. **Final decision per completion:** for the completed totals `s_t = x_t + y_t` (out of `n_planned_t`), `s_c = x_c + y_c`, form the **final** posteriors and evaluate the dual-criterion gates via `prob_diff_exceeds` → `go[y_t, y_c] ∈ {0, 1}`.
5. **PPoS** `= Σ_{y_t, y_c} w_t(y_t) · w_c(y_c) · go[y_t, y_c]`.

Exact, deterministic, bit-reproducible; no random seed.

**Cost and cap.** The go-block is `(m_t+1)(m_c+1)` evaluations of `prob_diff_exceeds` (each a fixed-grid quadrature), vectorised over the block in numpy. A module constant `MAX_ENUM_DIFF` (proposed **10,000** cells) bounds it. Above the cap the completion grid is **thinned on a fixed integer stride** in each arm — the `go` decision is evaluated on the strided sub-grid and the predictive weights are aggregated to that grid — keeping the result deterministic and closed-form (never Monte Carlo), at a controlled loss of resolution. When thinning triggers, `fit_interim` appends a caveat that the PPoS is grid-binned. This realises the original module spec's stated bound: `O((m_t+1)(m_c+1))` quadratures, capped, binned above the cap.

## 5. `fit_interim` two-arm branch (`modeling.py`)

`fit_interim` already accepts `framing` (currently ignored) and `endpoint_type`. Add a `framing == "two_arm"` branch; the single-arm path is unchanged.

- **New parameters:** `group` (the arm column) and `control` (the control arm's value; if omitted, inferred as the baseline value the way `fit_noninferiority` already does).
- **Cohorts:** clean on `[outcome, group]`; require **exactly two** arm values after filtering; identify control via `control` or inference; the other is treatment. Binarise the outcome with the existing `_to_binary`.
- **Priors:** vague `Beta(1,1)` per arm by default; a supplied per-arm prior is accepted via the existing `prior_a`/`prior_b` (applied to both arms) — no borrowing. Provenance strings state which was used.
- **Allocation:** `n_planned` is the **total** planned enrolment; **1:1 allocation assumed**, so `n_planned_t = n_planned_c = n_planned // 2`. Guard: each arm's observed n must not exceed its planned half (else "final analysis, not interim").
- **Compute:** observed posteriors → `p_tv`, `p_lrv` via `prob_diff_exceeds` → `decide`; `ppos = predictive_prob_success_diff(...)`; a low PPoS (`< stop_lrv`) forces STOP-for-futility, mirroring single-arm.
- **`ModelResult` output:**
  - `arms`: per-arm posterior summaries `{arm, value=posterior mean rate, ci_low, ci_high, n, is_baseline}` (reuses the experiment/NI `arms` shape and rendering).
  - `terms`: one risk-difference term — `Term("risk difference (t − c)", mean_diff, ci_low, ci_high, nan)`. The difference posterior's CDF `F(v) = P(d ≤ v)` is built on a fixed fine grid of `v ∈ [−1, 1]` (each point `1 − prob_diff_exceeds(post_t, post_c, v, higher_is_better=True)`, reusing the tested quadrature), then inverted for the 2.5th and 97.5th percentiles; `mean_diff` is `E[rate_t] − E[rate_c]` from the two posterior means. Deterministic, no simulation.
  - `verdict`: `{call, reason, predictive_prob, posterior_diff, diff_ci_low, diff_ci_high}`.
  - `series`: PPoS vs total enrolment, scaling both arms' observed counts proportionally (parallel to the single-arm series).
  - `prespec`: `verify(lock, params)` with `framing="two_arm"` in `params` (already a `LOCKED_FIELD`).
  - `robustness`: `{framing: "two_arm"}`.
- **Everything returns `ModelResult(..., error=…)` on any failure; never raises** (existing contract).

## 6. Agent routing (`agent.py`)

- Extend the `interim` router description: a **controlled / two-arm** interim ("treatment vs control", "vs placebo", "18/40 on the drug vs 10/38 on control") sets `framing="two_arm"`, supplies `group` (arm column) and `outcome`, and expresses `tv`/`lrv` as **risk differences** (treatment − control). `analytic_sql` returns one row per subject with the arm column + a binary outcome; when the question states per-arm counts directly, synthesise the rows with `range()` per arm (the pattern the single-arm interim already uses), e.g. two `SELECT … FROM range(k)` blocks tagged with the arm.
- `_fit_model`'s existing `interim` branch forwards `framing`, and additionally `group` and `control`.
- `_MODEL_HINT` already matches interim / go-no-go phrasing — no change.

## 7. Rendering (`app.py`, `agent/charts.py`, `agent/report.py`)

Reuse, no new chart type:
- Verdict badge + PRE-SPECIFIED/EXPLORATORY badge — unchanged.
- **Per-arm posterior table** (treatment vs control rate with credible intervals) via the existing `arms` rendering used by experiment/NI.
- The **risk difference with its credible interval** and the **predictive probability of success**, led in the interpretation as the futility signal.
- Forest plot shows the **difference term (t − c) against 0** (the existing `forest_plot` already renders a single term against the no-effect line).
- The assurance/OC curves do not apply to the interim (as today for single-arm interim).
- Word report: the interim results section gains the per-arm table and the difference row; `_METHOD_BLURB["interim"]` extended to note "single- or two-arm; two-arm decides on the risk difference via an exact joint beta-binomial predictive."
- App `_interpret_model` interim guidance extended: for a two-arm interim, state the control rate, the treatment rate, and the risk difference with its interval; lead with the verdict and PPoS; never call a DRIFTED/EXPLORATORY run confirmatory.

## 8. Error handling and edge cases (all tested)

- Arm column missing, or not exactly two arms after cleaning → clear error naming the problem.
- One arm empty → error naming the missing arm.
- Continuous endpoint in two-arm → the existing "binary only" error.
- Total observed n > n_planned, or an arm's observed n > its planned half → "final analysis, not interim."
- At full enrolment PPoS degenerates to the final decision; flagged complete.
- Enumeration above `MAX_ENUM_DIFF` → thinned grid + a caveat that the PPoS is grid-binned (not silently slow).
- TV < LRV (for `higher_is_better`) → validation error, as single-arm.

## 9. Deterministic caveats (appended to `ModelResult.issues`)

Computed in code, never invented by the LLM (existing discipline):
- The pre-specification caveat (`prespec.caveat`) first, conditioning how everything else reads.
- The prior per arm and its provenance.
- The degenerate Beta(ε,ε) warning when a near-noninformative prior meets an all-success/all-failure arm (as single-arm).
- Prior ESS vs observed n per arm when the prior is doing more work than the data.
- The grid-binned-PPoS note when thinning triggered.
- "Design-stage / interim decision support, not a regulatory submission analysis."

## 10. Test plan (TDD, keyless, exact)

New tests in `tests/test_bayes.py` and `tests/test_modeling.py`:
- **`predictive_prob_success_diff` vs Monte Carlo:** shipped code enumerates; the test draws θ_t, θ_c from the observed posteriors, simulates both arms' completions, applies the final decision, cross-checks to ≈0.005 (mirrors the single-arm PPoS test).
- **Degenerate at full enrolment:** two-arm PPoS equals the final two-arm GO/no-GO.
- **Monotone / sanity:** a strong treatment effect → high PPoS/GO; identical arms → CONSIDER or STOP, PPoS low; a large treatment deficit → STOP.
- **`fit_interim` two-arm end to end:** strong treatment → GO; no difference → not GO; futility → STOP; per-arm `arms` and the difference term populated with sane CIs.
- **Prespec stamping** for a two-arm run: EXPLORATORY without a lock; DRIFTED when a field moved.
- **Router dispatch:** a two-arm interim spec dispatches through `_fit_model` with `framing="two_arm"`, `group`, `control`.
- **Cap/thinning:** a run above `MAX_ENUM_DIFF` returns a value in [0,1], emits the grid-binned caveat, and stays close to the un-thinned value on a small check case.
- Reuses the existing ground-truth `prob_diff_exceeds` quadrature-vs-MC test.
- Full suite green, `ruff` clean, coverage ≥ 60%.

## 11. References

- Lalonde R. et al. (2007). Model-based drug development. *Clinical Pharmacology & Therapeutics.* (TV/LRV dual-criterion decision framework.)
- Lee J.J., Liu D.D. (2008). A predictive probability design for phase II cancer clinical trials. *Clinical Trials.*
- Saville B.R., Connor J.T. et al. (2014). The utility of Bayesian predictive probabilities for interim monitoring of clinical trials. *Clinical Trials.*
- Zhao Y. et al. (2023). BOP2-DC: Bayesian optimal phase II designs with dual-criterion decision making. *Pharmaceutical Statistics.* (Randomized binary dual-criterion; LRV/CMV.)
- FDA (2026, draft). Use of Bayesian Methodology in Clinical Trials of Drug and Biological Products. CDER/CBER. (`Pr(d>a)≥c` success criteria; predictive-probability futility; prior justification, prior-sensitivity, operating characteristics.)
- FDA (2016). Non-Inferiority Clinical Trials to Establish Effectiveness. (Risk-difference margins for binary endpoints.)
