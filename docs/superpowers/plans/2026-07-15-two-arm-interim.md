# Two-arm interim Bayesian go/no-go — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `modeling.fit_interim` from a binary single-arm trial to a binary two-arm (treatment vs control) trial: decide on the risk difference with the existing dual-criterion rule, and report an exact predictive probability of success computed by a joint beta-binomial enumeration over both arms' remaining patients.

**Architecture:** One new pure function in `agent/bayes.py` (`predictive_prob_success_diff`, plus a shared block helper `_go_diff_block` and a public `go_grid_diff`). A `framing == "two_arm"` branch in the existing `modeling.fit_interim`. Router and `_fit_model` pass the arm column through. Rendering reuses the existing per-arm (`arms`) machinery. No new dependencies, no Monte Carlo in shipped code.

**Tech Stack:** Python 3.12, numpy, scipy, pandas (all pinned). pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-07-15-two-arm-interim-design.md`

## Global Constraints

- **No new dependencies.** numpy + scipy only.
- **No Monte Carlo in shipped code.** Every quantity is closed-form or deterministic grid integration. MC may appear only inside a test, as an independent cross-check.
- **Never raise into the app.** Every public entry point in `modeling.py` wraps its body in `try/except Exception` and returns `ModelResult(..., error=str(e))`.
- **Caveats are deterministic.** Computed in code and appended to `ModelResult.issues`.
- **Line length 120** (`ruff`). Run `.venv/bin/ruff check .` before every commit.
- **Tests are keyless.** No test may require `OPENAI_API_KEY` or network.
- **Commit style:** no `Co-Authored-By` trailer.
- **Coverage gate:** `fail_under = 60` in `pyproject.toml`. Do not lower it.
- Run the full suite with `.venv/bin/pytest -q -p no:warnings` before each commit.
- **Effect measure is the absolute risk difference** `d = rate_treatment − rate_control`. TV/LRV are on that scale; LRV may be 0 or slightly negative.
- **1:1 allocation assumed**; `n_planned` is the TOTAL, each arm plans `n_planned // 2`.
- **No historical-control borrowing.** Vague `Beta(1,1)` per arm by default, or a single supplied `Beta(prior_a, prior_b)` applied to both arms.

---

### Task 1: The two-arm predictive probability of success (`agent/bayes.py`)

Pure numpy/scipy. The one genuinely new piece of math. Reuses only the module-level `_GRID` and the existing `beta_posterior`.

**Files:**
- Modify: `agent/bayes.py` (append)
- Test: `tests/test_bayes.py` (append)

**Interfaces:**
- Consumes: `Prior`, `DecisionRule`, `beta_posterior` (existing), module constant `_GRID` (existing).
- Produces:
  - `_go_diff_block(t_ab, st, n_t, c_ab, sc, n_c, rule) -> np.ndarray` (private) — 2-D `{0,1}` GO grid for the given final treatment counts `st` (out of `n_t`) and control counts `sc` (out of `n_c`).
  - `go_grid_diff(prior_t, prior_c, n_t, n_c, rule) -> np.ndarray` — full `(n_t+1, n_c+1)` GO grid.
  - `predictive_prob_success_diff(prior_t, prior_c, x_t, n_t, x_c, n_c, n_planned_t, n_planned_c, rule) -> float`.
  - Module constant `MAX_ENUM_DIFF: int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bayes.py`:

```python
# ── two-arm predictive probability of success ─────────────────────────────────────────────────────
DIFF_RULE = bayes.DecisionRule(tv=0.15, lrv=0.0)      # a 15-point benefit hoped for; any benefit is the floor


def test_go_grid_diff_shape_and_monotonicity():
    vague = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    go = bayes.go_grid_diff(vague, vague, 30, 30, DIFF_RULE)
    assert go.shape == (31, 31)
    # more treatment successes can only help; more control successes can only hurt
    assert np.all(np.diff(go, axis=0) >= 0)
    assert np.all(np.diff(go, axis=1) <= 0)


def test_predictive_prob_diff_matches_a_brute_force_simulation():
    """The shipped code enumerates exactly; the TEST simulates, reusing the shipped GO grid as the
    reference decision (exactly as the single-arm predictive test does)."""
    vague = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    x_t, n_t, x_c, n_c = 14, 30, 8, 30
    npt = npc = 60
    exact = bayes.predictive_prob_success_diff(vague, vague, x_t, n_t, x_c, n_c, npt, npc, DIFF_RULE)

    go = bayes.go_grid_diff(vague, vague, npt, npc, DIFF_RULE)
    rng = np.random.default_rng(0)
    pa_t, pb_t = bayes.beta_posterior(1.0, 1.0, x_t, n_t)
    pa_c, pb_c = bayes.beta_posterior(1.0, 1.0, x_c, n_c)
    th_t = rng.beta(pa_t, pb_t, 300_000)
    th_c = rng.beta(pa_c, pb_c, 300_000)
    fut_t = rng.binomial(npt - n_t, th_t)
    fut_c = rng.binomial(npc - n_c, th_c)
    sim = float(np.mean(go[x_t + fut_t, x_c + fut_c]))
    assert exact == pytest.approx(sim, abs=0.005)


def test_predictive_prob_diff_at_full_enrolment_is_the_final_decision():
    vague = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    go = bayes.go_grid_diff(vague, vague, 50, 50, DIFF_RULE)
    for x_t, x_c in [(25, 15), (20, 20), (10, 30)]:
        got = bayes.predictive_prob_success_diff(vague, vague, x_t, 50, x_c, 50, 50, 50, DIFF_RULE)
        assert got == pytest.approx(float(go[x_t, x_c]))


def test_predictive_prob_diff_high_for_a_strong_treatment_low_for_none():
    vague = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    strong = bayes.predictive_prob_success_diff(vague, vague, 24, 30, 8, 30, 60, 60, DIFF_RULE)
    none = bayes.predictive_prob_success_diff(vague, vague, 12, 30, 12, 30, 60, 60, DIFF_RULE)
    assert strong > 0.8
    assert none < 0.3


def test_predictive_prob_diff_thins_above_the_cap_and_stays_close():
    """Above MAX_ENUM_DIFF the completion grid is thinned; the answer must stay in [0,1] and near the
    exact value on a case small enough to also compute exactly."""
    vague = bayes.Prior("Vague", "beta", (1.0, 1.0), "")
    exact = bayes.predictive_prob_success_diff(vague, vague, 20, 40, 12, 40, 120, 120, DIFF_RULE)
    saved = bayes.MAX_ENUM_DIFF
    try:
        bayes.MAX_ENUM_DIFF = 400                       # force thinning on the same problem
        thinned = bayes.predictive_prob_success_diff(vague, vague, 20, 40, 12, 40, 120, 120, DIFF_RULE)
    finally:
        bayes.MAX_ENUM_DIFF = saved
    assert 0.0 <= thinned <= 1.0
    assert thinned == pytest.approx(exact, abs=0.05)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_bayes.py -q -p no:warnings -k "diff"`
Expected: FAIL with `AttributeError: module 'agent.bayes' has no attribute 'go_grid_diff'`

- [ ] **Step 3: Write the implementation**

Append to `agent/bayes.py`:

```python
# ── two-arm predictive probability of success ─────────────────────────────────────────────────────
MAX_ENUM_DIFF = 10_000    # cap on the (reachable) completion grid; above it, thin on a fixed stride

# trapezoid weights on the fixed [0,1] quadrature grid, computed once
_WV = np.full(_GRID, 1.0 / (_GRID - 1))
_WV[0] = _WV[-1] = 0.5 / (_GRID - 1)
_VGRID = np.linspace(0.0, 1.0, _GRID)


def _go_diff_block(t_ab, st, n_t: int, c_ab, sc, n_c: int, rule: DecisionRule) -> np.ndarray:
    """GO decision for every (final treatment count st, final control count sc). Vectorized: the
    beta-difference tail P(rate_t - rate_c > threshold) is one trapezoid integral per (st, sc), but it
    factorizes into (len_st, GRID) survival rows and (len_sc, GRID) density rows combined by a single
    matrix multiply -- no per-cell Python loop, no 3-D intermediate.

        P(t - c > d) = INT f_c(v) * sf_t(v + d) dv  ==  (sf_t * wv) @ f_c.T
    """
    at, bt = t_ab
    ac, bc = c_ab
    st = np.asarray(st, dtype=float)
    sc = np.asarray(sc, dtype=float)
    a_t, b_t = at + st, bt + (n_t - st)                       # final treatment posteriors  (len_st,)
    a_c, b_c = ac + sc, bc + (n_c - sc)                       # final control posteriors    (len_sc,)
    f_c = stats.beta.pdf(_VGRID[None, :], a_c[:, None], b_c[:, None])      # (len_sc, GRID)

    def block_p(threshold):
        thr = np.clip(_VGRID + threshold, 0.0, 1.0)
        sf_t = stats.beta.sf(thr[None, :], a_t[:, None], b_t[:, None])     # (len_st, GRID)
        p = (sf_t * _WV[None, :]) @ f_c.T                                  # (len_st, len_sc)
        return p if rule.higher_is_better else 1.0 - p

    p_tv = block_p(rule.tv)
    p_lrv = block_p(rule.lrv)
    return ((p_tv >= rule.gate_tv) & (p_lrv >= rule.gate_lrv)).astype(int)


def go_grid_diff(prior_t: Prior, prior_c: Prior, n_t: int, n_c: int, rule: DecisionRule) -> np.ndarray:
    """go[st, sc] == 1 iff a trial that finishes with st/​n_t treatment and sc/​n_c control responders is a
    GO. The two-arm analog of go_grid_binary; reused by the predictive probability and by the tests."""
    return _go_diff_block(prior_t.params, np.arange(n_t + 1), n_t,
                          prior_c.params, np.arange(n_c + 1), n_c, rule)


def predictive_prob_success_diff(prior_t: Prior, prior_c: Prior, x_t: int, n_t: int, x_c: int, n_c: int,
                                 n_planned_t: int, n_planned_c: int, rule: DecisionRule) -> float:
    """P(the randomized trial ENDS in GO | both arms' data so far). Exact for a binary endpoint.

    Enumerate every joint completion (y_t future treatment responders, y_c future control responders),
    weight by the PRODUCT of each arm's beta-binomial posterior-predictive, and check whether the FINAL
    difference clears the pre-specified gates:

        PPoS = SUM_{y_t, y_c} BetaBinom(y_t; m_t, ...) * BetaBinom(y_c; m_c, ...) * go[x_t+y_t, x_c+y_c]

    No simulation error. Above MAX_ENUM_DIFF reachable cells the completion grid is thinned on a fixed
    stride (deterministic, still no Monte Carlo)."""
    if prior_t.kind != "beta" or prior_c.kind != "beta":
        raise ValueError("the two-arm predictive probability supports a binary endpoint only")
    if n_t > n_planned_t or n_c > n_planned_c:
        raise ValueError("observed n exceeds the planned n in an arm")
    post_t = beta_posterior(*prior_t.params, x_t, n_t)        # observed posterior -> predictive weights
    post_c = beta_posterior(*prior_c.params, x_c, n_c)
    m_t, m_c = n_planned_t - n_t, n_planned_c - n_c
    y_t = np.arange(m_t + 1)
    y_c = np.arange(m_c + 1)
    if (m_t + 1) * (m_c + 1) > MAX_ENUM_DIFF:                 # thin: keep <= sqrt(cap) points per arm
        side = max(1, int(MAX_ENUM_DIFF ** 0.5))
        step_t = max(1, -(-(m_t + 1) // side))                # ceil division
        step_c = max(1, -(-(m_c + 1) // side))
        y_t, y_c = y_t[::step_t], y_c[::step_c]
    w_t = stats.betabinom.pmf(y_t, m_t, post_t[0], post_t[1])
    w_c = stats.betabinom.pmf(y_c, m_c, post_c[0], post_c[1])
    w_t = w_t / w_t.sum()                                     # renormalize (exact when unthinned; bins when thinned)
    w_c = w_c / w_c.sum()
    go = _go_diff_block(prior_t.params, x_t + y_t, n_planned_t,
                        prior_c.params, x_c + y_c, n_planned_c, rule)
    return float(w_t @ go @ w_c)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_bayes.py -q -p no:warnings`
Expected: PASS (all, including the 5 new two-arm tests)

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check agent/bayes.py tests/test_bayes.py
git add agent/bayes.py tests/test_bayes.py
git commit -m "Add the two-arm predictive probability of success

Exact for a binary endpoint: enumerate every joint completion of both arms'
remaining patients, weight by the product of each arm's beta-binomial
posterior-predictive, and check whether the final risk difference clears the
pre-specified gates. The beta-difference tail factorizes into a single matrix
multiply, so the whole go-grid is computed without a per-cell loop or a 3-D
intermediate. Above a documented cap the completion grid is thinned on a fixed
stride -- deterministic, never Monte Carlo. Cross-checked against a brute-force
simulation and against the degenerate case at full enrolment."
```

---

### Task 2: The `fit_interim` two-arm branch (`agent/modeling.py`)

**Files:**
- Modify: `agent/modeling.py` (add `_diff_credible_interval`; extend `fit_interim` and `render`)
- Test: `tests/test_modeling.py` (append)

**Interfaces:**
- Consumes: `predictive_prob_success_diff`, `go_grid_diff`, `MAX_ENUM_DIFF`, `prob_diff_exceeds`, `decide`, `DecisionRule`, `Prior`, `beta_posterior` (Task 1 + existing); `_clean`, `_to_binary`, `_is_control`, `Term`, `ModelResult` (existing).
- Produces: `fit_interim(..., group=None, control=None)` handling `framing="two_arm"`; `_diff_credible_interval(post_t, post_c, higher_is_better) -> tuple[float, float, float]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_modeling.py`:

```python
# ── Bayesian go/no-go: two-arm interim ────────────────────────────────────────────────────────────
def _two_arm_df(x_t: int, n_t: int, x_c: int, n_c: int) -> pd.DataFrame:
    rows = ([("treatment", 1)] * x_t + [("treatment", 0)] * (n_t - x_t)
            + [("control", 1)] * x_c + [("control", 0)] * (n_c - x_c))
    return pd.DataFrame(rows, columns=["arm", "responded"])


def test_two_arm_interim_goes_when_treatment_clearly_beats_control():
    r = modeling.fit_interim(_two_arm_df(26, 30, 8, 30), "responded", n_planned=80, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    assert r.error is None and r.verdict["call"] == "GO"
    arms = {a["arm"]: a for a in r.arms}
    assert set(arms) == {"treatment", "control"} and arms["treatment"]["value"] > arms["control"]["value"]


def test_two_arm_interim_stops_for_futility_when_arms_are_equal():
    r = modeling.fit_interim(_two_arm_df(9, 45, 9, 45), "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    assert r.error is None and r.verdict["call"] == "STOP"
    assert r.verdict["predictive_prob"] < 0.10


def test_two_arm_interim_reports_the_risk_difference_with_a_credible_interval():
    r = modeling.fit_interim(_two_arm_df(18, 40, 10, 40), "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    t = r.terms[0]
    assert "difference" in t.name.lower()
    assert t.ci_low < t.estimate < t.ci_high
    assert t.estimate == pytest.approx(18 / 40 - 10 / 40, abs=0.02)


def test_two_arm_interim_without_a_lock_is_exploratory():
    r = modeling.fit_interim(_two_arm_df(18, 40, 10, 40), "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    assert r.prespec["status"] == "EXPLORATORY"
    assert any("not pre-specified" in i.lower() for i in r.issues)


def test_two_arm_interim_infers_control_when_not_named():
    # 'control' is recognized by name even without the control= argument
    r = modeling.fit_interim(_two_arm_df(20, 40, 12, 40), "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm")
    assert r.error is None
    assert next(a for a in r.arms if a["is_baseline"])["arm"] == "control"


def test_two_arm_interim_rejects_a_single_arm_cohort():
    df = pd.DataFrame({"arm": ["treatment"] * 20, "responded": [1] * 12 + [0] * 8})
    r = modeling.fit_interim(df, "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    assert r.error is not None and "two arms" in r.error.lower()


def test_two_arm_interim_rejects_more_observed_than_planned_per_arm():
    r = modeling.fit_interim(_two_arm_df(30, 60, 20, 60), "responded", n_planned=100, tv=0.15, lrv=0.0,
                             framing="two_arm", group="arm", control="control")
    assert r.error is not None and "planned" in r.error.lower()


def test_two_arm_interim_accepts_a_negative_lrv_non_inferiority_floor():
    # a risk-difference LRV may be negative (a non-inferiority-style floor); it must NOT be rejected as
    # out of [0,1], and a clearly-better treatment against a small negative floor should still be able to GO
    r = modeling.fit_interim(_two_arm_df(28, 30, 8, 30), "responded", n_planned=80, tv=0.15, lrv=-0.05,
                             framing="two_arm", group="arm", control="control")
    assert r.error is None and r.verdict["call"] in ("GO", "CONSIDER", "STOP")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_modeling.py -q -p no:warnings -k "two_arm"`
Expected: FAIL (the two-arm branch does not exist; `fit_interim` treats the whole cohort as one arm)

- [ ] **Step 3a: Add the credible-interval helper**

In `agent/modeling.py`, immediately BEFORE `def fit_interim(`:

```python
def _diff_credible_interval(post_t, post_c, higher_is_better: bool) -> tuple[float, float, float]:
    """Posterior mean and 95% credible interval of the risk difference rate_t - rate_c. The difference
    posterior's CDF F(v) = P(d <= v) is built on a fixed grid via the tested prob_diff_exceeds quadrature,
    then inverted for the 2.5th and 97.5th percentiles. Deterministic; no simulation."""
    grid = np.linspace(-1.0, 1.0, 801)
    cdf = np.array([1.0 - _bayes.prob_diff_exceeds("beta", post_t, post_c, float(v), True) for v in grid])
    lo = float(np.interp(0.025, cdf, grid))
    hi = float(np.interp(0.975, cdf, grid))
    mean = post_t[0] / (post_t[0] + post_t[1]) - post_c[0] / (post_c[0] + post_c[1])
    return float(mean), lo, hi
```

- [ ] **Step 3b: Extend the `fit_interim` signature**

Change the `def fit_interim(` signature to add `group` and `control` (place them with the other keyword args):

```python
def fit_interim(df: pd.DataFrame, outcome: str, n_planned=None, tv=None, lrv=None,
                gate_tv: float = 0.80, gate_lrv: float = 0.90, stop_lrv: float = 0.10,
                higher_is_better: bool = True,
                prior_successes=None, prior_n=None, prior_a=None, prior_b=None,
                lock=None, endpoint_type: str = "proportion",
                framing: str = "single_arm", group=None, control=None) -> ModelResult:
```

- [ ] **Step 3c: Add the two-arm branch**

In `fit_interim`, immediately AFTER the endpoint-type guard (the block
`if endpoint_type != "proportion":` / `return _err("the interim analysis currently supports a binary endpoint only.")`)
and BEFORE the single-arm `if higher_is_better and lrv > tv:` check, insert the dispatch. It must go here —
before the single-arm `0 <= tv,lrv <= 1` range check — because two-arm thresholds are RISK DIFFERENCES that
may be negative, and the two-arm function does its own `[-1, 1]` validation:

```python
        if framing == "two_arm":
            return _fit_interim_two_arm(df, outcome, group, control, n_planned, tv, lrv,
                                        gate_tv, gate_lrv, stop_lrv, higher_is_better,
                                        prior_a, prior_b, lock)
```

Then add the two-arm implementation as a new function immediately AFTER `fit_interim` ends:

```python
def _fit_interim_two_arm(df, outcome, group, control, n_planned, tv, lrv,
                         gate_tv, gate_lrv, stop_lrv, higher_is_better,
                         prior_a, prior_b, lock) -> ModelResult:
    """Interim go/no-go for a randomized two-arm binary trial. Decides on the risk difference
    (treatment - control) with the dual-criterion rule and the exact two-arm predictive probability."""
    def _err(msg):
        return ModelResult("interim", outcome or "go/no-go", 0,
                           "posterior risk difference (95% credible interval)", error=msg)
    try:
        if not group:
            return _err("a two-arm interim needs the arm column (group).")
        if n_planned is None or tv is None or lrv is None:
            return _err("a two-arm interim needs the planned total enrolment, a TV, and an LRV.")
        n_planned, tv, lrv = int(n_planned), float(tv), float(lrv)
        if not (-1.0 <= tv <= 1.0 and -1.0 <= lrv <= 1.0):
            return _err("the two-arm TV and LRV are risk differences and must be between -1 and 1 "
                        "(express a 15-point benefit as 0.15).")
        if higher_is_better and lrv > tv:
            return _err("the LRV must not exceed the TV.")
        if not higher_is_better and tv > lrv:
            return _err("with a lower-is-better endpoint the TV must not exceed the LRV.")
        d = _clean(df, [group, outcome])
        if group not in d.columns or outcome not in d.columns or len(d) == 0:
            return _err("no observed subjects to analyse.")
        d[group] = d[group].astype(str)
        arms = sorted(d[group].unique())
        if len(arms) != 2:
            return _err(f"a two-arm interim needs exactly two arms; found {len(arms)}.")
        base = control if control in arms else next((a for a in arms if _is_control(a)), None)
        if base is None:
            base = max(arms, key=lambda a: int((d[group] == a).sum()))   # fallback: the larger arm
        trt = next(a for a in arms if a != base)

        rule = _bayes.DecisionRule(tv=tv, lrv=lrv, gate_tv=float(gate_tv), gate_lrv=float(gate_lrv),
                                   stop_lrv=float(stop_lrv), higher_is_better=bool(higher_is_better))
        if prior_a is not None and prior_b is not None:
            pa, pb = float(prior_a), float(prior_b)
            prov = f"Supplied prior Beta({pa:g}, {pb:g}) on each arm."
        else:
            pa, pb = 1.0, 1.0
            prov = "Uniform Beta(1,1) on each arm (no prior study supplied)."
        prior_t = _bayes.Prior("arm prior", "beta", (pa, pb), prov)
        prior_c = _bayes.Prior("arm prior", "beta", (pa, pb), prov)

        n_planned_t = n_planned_c = int(n_planned) // 2
        summ = {}
        for arm in (trt, base):
            y = _to_binary(d.loc[d[group] == arm, outcome])
            summ[arm] = (int(len(y)), int(y.sum()))
        if summ[trt][0] > n_planned_t or summ[base][0] > n_planned_c:
            return _err(f"an arm's observed n exceeds its planned enrolment ({n_planned_t} per arm at "
                        "1:1 allocation): this is a final analysis, not an interim.")

        (n_t, x_t), (n_c, x_c) = summ[trt], summ[base]
        post_t = _bayes.beta_posterior(pa, pb, x_t, n_t)
        post_c = _bayes.beta_posterior(pa, pb, x_c, n_c)
        p_tv = float(_bayes.prob_diff_exceeds("beta", post_t, post_c, tv, higher_is_better))
        p_lrv = float(_bayes.prob_diff_exceeds("beta", post_t, post_c, lrv, higher_is_better))
        call, reason = _bayes.decide(p_tv, p_lrv, rule)
        ppos = _bayes.predictive_prob_success_diff(prior_t, prior_c, x_t, n_t, x_c, n_c,
                                                   n_planned_t, n_planned_c, rule)

        params = {"endpoint_type": "proportion", "framing": "two_arm", "n_planned": int(n_planned),
                  "tv": tv, "lrv": lrv, "gate_tv": gate_tv, "gate_lrv": gate_lrv,
                  "stop_lrv": stop_lrv, "higher_is_better": higher_is_better,
                  "prior_a": pa, "prior_b": pb, "prior_mu": None, "prior_sd": None}
        ps = _prespec.verify(lock, params)

        mean_d, lo_d, hi_d = _diff_credible_interval(post_t, post_c, higher_is_better)
        m_t = post_t[0] / (post_t[0] + post_t[1])
        m_c = post_c[0] / (post_c[0] + post_c[1])
        t_lo, t_hi = stats.beta.ppf([0.025, 0.975], post_t[0], post_t[1])
        c_lo, c_hi = stats.beta.ppf([0.025, 0.975], post_c[0], post_c[1])

        mr = ModelResult("interim", outcome, n_t + n_c, "posterior risk difference (95% credible interval)",
                         [Term("risk difference (treatment - control)", float(mean_d), float(lo_d),
                               float(hi_d), float("nan"))],
                         fit_stat=f"{x_t}/{n_t} treatment vs {x_c}/{n_c} control · "
                                  f"{int(n_planned) - n_t - n_c} still to enrol · PPoS={ppos:.1%}",
                         note="Interim two-arm Bayesian go/no-go on the risk difference. The predictive "
                              "probability of success is the chance the trial ends in GO at full enrolment. "
                              "Synthetic data.")
        mr.arms = [{"arm": trt, "n": n_t, "value": float(m_t), "ci_low": float(t_lo),
                    "ci_high": float(t_hi), "is_baseline": False, "is_winner": False},
                   {"arm": base, "n": n_c, "value": float(m_c), "ci_low": float(c_lo),
                    "ci_high": float(c_hi), "is_baseline": True, "is_winner": False}]
        if ppos < rule.stop_lrv:
            call = "STOP"
            reason = (f"Predictive probability of success is only {ppos:.1%}: even at full enrolment "
                      f"({int(n_planned):,}), the treatment is very unlikely to clear its pre-specified "
                      "margin over control. Stop for futility.")
        mr.verdict = {"call": call, "reason": reason, "predictive_prob": round(ppos, 4),
                      "posterior_diff": round(float(mean_d), 4),
                      "diff_ci_low": round(float(lo_d), 4), "diff_ci_high": round(float(hi_d), 4)}
        mr.prespec = {"status": ps["status"], "lock": lock, "drift": ps["drift"]}
        mr.robustness = {"framing": "two_arm"}

        issues = [_prespec.caveat(ps), f"Prior: {prov}"]
        if (n_t + n_c) >= int(n_planned):
            issues.append("Enrolment is complete, so this is the FINAL decision, not a prediction.")
        if (n_planned_t + 1) * (n_planned_c + 1) > _bayes.MAX_ENUM_DIFF:
            issues.append("The predictive probability was grid-binned: the planned enrolment exceeds the "
                          "exact-enumeration cap, so the PPoS is a close deterministic approximation, "
                          "not the exact sum.")
        issues.append("Two-arm decision support on the risk difference; not a regulatory submission analysis.")
        mr.issues = issues
        return mr
    except Exception as e:  # noqa: BLE001 — never raise into the app
        return _err(str(e))
```

- [ ] **Step 3d: Render the two-arm interim in `modeling.render`**

In `agent/modeling.py`, in `render`, find the block
`if r.model_type in ("assurance", "interim") and r.verdict:` and add, right after the `PRE-SPECIFICATION`
line inside that block, handling for the two-arm arms so the LLM interpreter sees them:

```python
        for a in r.arms:                                   # two-arm interim: per-arm posteriors
            tag = " (control)" if a.get("is_baseline") else ""
            lines.append(f"  {a['arm']:16} n={a['n']:,}  rate={a['value']:.1%}{tag}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_modeling.py -q -p no:warnings -k "two_arm or interim or render"`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check agent/modeling.py tests/test_modeling.py
git add agent/modeling.py tests/test_modeling.py
git commit -m "Add the two-arm branch to modeling.fit_interim

A randomized binary interim: split the cohort by the arm column (control named
or inferred), form a Beta posterior per arm, decide on the risk difference with
prob_diff_exceeds + the dual-criterion rule, and report the exact two-arm
predictive probability of success. A low PPoS is STOP-for-futility. Per-arm
posteriors go in arms; the risk difference with a credible interval is the
headline term. 1:1 allocation, vague-or-supplied per-arm priors, no borrowing."
```

---

### Task 3: Agent routing (`agent/agent.py`)

**Files:**
- Modify: `agent/agent.py` (the `interim` router description; the `_fit_model` interim branch)
- Test: `tests/test_agent.py` (append)

**Interfaces:**
- Consumes: `modeling.fit_interim(..., framing, group, control)` (Task 2).
- Produces: an `interim` router spec that carries `framing`, `group`, `control`; a `_fit_model` interim branch that forwards them.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent.py`:

```python
def test_fit_model_dispatches_two_arm_interim():
    import pandas as pd
    rows = ([("treatment", 1)] * 18 + [("treatment", 0)] * 22
            + [("control", 1)] * 10 + [("control", 0)] * 30)
    df = pd.DataFrame(rows, columns=["arm", "responded"])
    spec = {"model_type": "interim", "outcome": "responded", "n_planned": 100,
            "tv": 0.15, "lrv": 0.0, "framing": "two_arm", "group": "arm", "control": "control"}
    mr = agent._fit_model(spec, df)
    assert mr.model_type == "interim" and mr.error is None
    assert {a["arm"] for a in mr.arms} == {"treatment", "control"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent.py -q -p no:warnings -k two_arm`
Expected: FAIL (the interim branch does not pass `group`/`control`, so both arms collapse to one cohort and the arms set is wrong or an error is returned)

- [ ] **Step 3a: Forward `group`/`control` in `_fit_model`**

In `agent/agent.py`, replace the existing `interim` branch of `_fit_model`:

```python
    if mt == "interim":
        return modeling.fit_interim(
            df, spec["outcome"], n_planned=spec.get("n_planned"), tv=spec.get("tv"),
            lrv=spec.get("lrv"), higher_is_better=spec.get("higher_is_better", True),
            prior_successes=spec.get("prior_successes"), prior_n=spec.get("prior_n"),
            framing=spec.get("framing", "single_arm"))
```

with:

```python
    if mt == "interim":
        return modeling.fit_interim(
            df, spec["outcome"], n_planned=spec.get("n_planned"), tv=spec.get("tv"),
            lrv=spec.get("lrv"), higher_is_better=spec.get("higher_is_better", True),
            prior_successes=spec.get("prior_successes"), prior_n=spec.get("prior_n"),
            prior_a=spec.get("prior_a"), prior_b=spec.get("prior_b"),
            framing=spec.get("framing", "single_arm"),
            group=spec.get("group"), control=spec.get("control"))
```

- [ ] **Step 3b: Teach the router the two-arm framing**

In `agent/agent.py`, in the `interim` model-type description inside `_route`, find the END of the interim
block — the line `"question gives no TV/LRV, use the LRV/TV from any stated goal, else tv=0.30, lrv=0.15 for a "`
followed by `"response-rate endpoint and SAY SO in the hypothesis.\n"` — and insert a new string literal
immediately AFTER that `...SAY SO in the hypothesis.\n"` line and BEFORE the `"  'causal'      the EFFECT / IMPACT...`
line:

```python
        "For a RANDOMIZED / two-arm interim (treatment vs a concurrent control or placebo, e.g. '18/40 "
        "on the drug vs 10/38 on control') set `framing`='two_arm', `group`=the arm column, `control`=the "
        "control arm's value, and express `tv`/`lrv` as RISK DIFFERENCES treatment-minus-control (e.g. a "
        "15-point benefit hoped for -> tv 0.15; any benefit is the floor -> lrv 0). analytic_sql returns "
        "one row per subject with the arm column + a binary outcome; when counts are stated directly, "
        "synthesize each arm's rows with range() (e.g. `SELECT 'treatment' AS arm, 1 AS responded FROM "
        "range(18) UNION ALL ...`). n_planned is the TOTAL planned enrolment across both arms.\n"
```

(Note the trailing `\n"` — this is a standalone concatenated string literal in the prompt, so it must end
with a newline like its neighbors.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_agent.py -q -p no:warnings`
Expected: PASS

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check agent/agent.py tests/test_agent.py
git add agent/agent.py tests/test_agent.py
git commit -m "Route the two-arm interim through the agent

_fit_model forwards group/control/prior_a/prior_b to fit_interim; the router
description teaches the two-arm framing -- an arm column, a named control, TV/LRV
as risk differences, and per-arm row synthesis with range() when counts are
stated. n_planned is the total across both arms."
```

---

### Task 4: Rendering — app and Word report (`app.py`, `agent/report.py`)

**Files:**
- Modify: `app.py` (`_render_model` two-arm arms table + difference); `agent/report.py` (`_METHOD_BLURB["interim"]`; the per-arm table in the interim results section)
- Test: `tests/test_hardening.py` (append)

**Interfaces:**
- Consumes: `ModelResult.as_dict()` with `arms`, `verdict` (`predictive_prob`, `posterior_diff`), `terms` (Task 2).
- Produces: no new public functions.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hardening.py`:

```python
def test_report_renders_a_two_arm_interim(tmp_path):
    """The .docx must carry the per-arm rates and the risk difference for a two-arm interim run."""
    import io
    import zipfile
    from types import SimpleNamespace

    import pandas as pd

    from agent import modeling, report

    rows = ([("treatment", 1)] * 20 + [("treatment", 0)] * 20
            + [("control", 1)] * 10 + [("control", 0)] * 30)
    df = pd.DataFrame(rows, columns=["arm", "responded"])
    mr = modeling.fit_interim(df, "responded", n_planned=100, tv=0.15, lrv=0.0,
                              framing="two_arm", group="arm", control="control")
    assert mr.error is None and len(mr.arms) == 2
    res = SimpleNamespace(question="Continue the trial?", model=mr.as_dict(),
                          sql="", interpretation="**Findings**\nok", findings=[], citations=[],
                          verification={}, hypothesis="", dataframe=None, trace={}, lineage=None,
                          error=None, clarification=None, attempts=[])
    blob = report.build_docx(res)
    assert blob[:2] == b"PK" and len(blob) > 5000
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode()
    assert "treatment" in xml and "control" in xml           # the per-arm table
    assert "Predictive probability of success" in xml
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_hardening.py -q -p no:warnings -k two_arm`
Expected: FAIL (the interim report section has no per-arm table; the arm names are absent from the XML)

- [ ] **Step 3a: Per-arm table in the Word report**

In `agent/report.py`, in the results section, find the `elif mt in ("assurance", "interim"):` branch. Inside
it, after the block that writes the interim key/values (the `else:` that calls
`_kv(doc, "Predictive probability of success", ...)` and `_kv(doc, "Posterior response rate", ...)`),
replace that `else:` block with:

```python
        else:
            _kv(doc, "Predictive probability of success", f"{v.get('predictive_prob', 0):.1%}")
            if m.get("arms"):                              # two-arm: per-arm rates + the risk difference
                _kv(doc, "Posterior risk difference (t - c)", f"{v.get('posterior_diff', 0):+.1%} "
                    f"[{v.get('diff_ci_low', 0):+.1%}, {v.get('diff_ci_high', 0):+.1%}]")
                table_caption("Per-arm posterior response rates with 95% credible intervals.")
                pt = doc.add_table(rows=1, cols=4); pt.style = "Table Grid"
                for j, h in enumerate(["Arm", "Rate", "95% CrI", "n"]):
                    pt.rows[0].cells[j].text = h
                for a in m["arms"]:
                    c = pt.add_row().cells
                    tag = " (control)" if a.get("is_baseline") else ""
                    c[0].text = f"{a['arm']}{tag}"; c[1].text = f"{a['value']:.1%}"
                    c[2].text = f"[{a['ci_low']:.1%}, {a['ci_high']:.1%}]"; c[3].text = f"{a['n']:,}"
            else:
                _kv(doc, "Posterior response rate", f"{v.get('posterior_mean', 0):.1%}")
```

- [ ] **Step 3b: Extend the interim method blurb**

In `agent/report.py`, replace the `"interim"` entry of `_METHOD_BLURB` with:

```python
    "interim": "Bayesian interim go/no-go. Single-arm: posterior response rate with a 95% credible "
               "interval and the exact predictive probability the trial ends in a GO at full enrolment. "
               "Two-arm: the same decision on the risk difference (treatment - control) via an exact "
               "joint beta-binomial predictive. Conjugate Beta-Binomial; closed form (no simulation).",
```

- [ ] **Step 3c: Per-arm table in the app**

In `app.py`, in `_render_model`, inside the `if m.get("model_type") in ("assurance", "interim"):` branch,
find the `else:` that appends the predictive-probability and posterior-response-rate lines and replace it
with:

```python
        else:
            lines.append(f"- **predictive probability of success**: {v.get('predictive_prob', 0):.1%}")
            if m.get("arms"):                              # two-arm: risk difference + per-arm table
                lines.append(f"- **posterior risk difference (t − c)**: {v.get('posterior_diff', 0):+.1%} "
                             f"[{v.get('diff_ci_low', 0):+.1%}, {v.get('diff_ci_high', 0):+.1%}]")
                lines += ["", "| arm | posterior rate | 95% CrI | n |", "|---|---|---|---|"]
                for a in m["arms"]:
                    tag = " · control" if a.get("is_baseline") else ""
                    lines.append(f"| `{a['arm']}`{tag} | {a['value']:.1%} "
                                 f"| [{a['ci_low']:.1%}, {a['ci_high']:.1%}] | {a['n']:,} |")
            else:
                lines.append(f"- **posterior response rate**: {v.get('posterior_mean', 0):.1%}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_hardening.py tests/test_app_smoke.py -q -p no:warnings`
Expected: PASS

- [ ] **Step 5: Lint, run the full suite, and commit**

```bash
.venv/bin/ruff check agent/report.py app.py tests/test_hardening.py
.venv/bin/pytest -q -p no:warnings
git add agent/report.py app.py tests/test_hardening.py
git commit -m "Render the two-arm interim: per-arm posteriors and the risk difference

The app and the Word report show a per-arm posterior table (treatment vs
control with credible intervals) and the posterior risk difference with its
interval, alongside the predictive probability of success. Single-arm interim
rendering is unchanged. The interim method blurb now covers both framings."
```

---

## Final verification (after Task 4)

- [ ] **Run everything**

```bash
.venv/bin/pytest -q -p no:warnings          # expect all green
.venv/bin/ruff check .                      # expect "All checks passed!"
.venv/bin/pytest --cov=agent -q -p no:warnings | tail -3   # expect coverage >= 60%
```

- [ ] **Drive the real app**

```bash
.venv/bin/streamlit run app.py --server.headless=true --server.port=8599
```

Ask, in the app:
1. `"We randomized 80 patients, 40 per arm: 26 responses on the new drug vs 10 on control, and planned to enrol 200 total. Continue or stop?"`
   Expect: an `interim` model with `framing=two_arm`, a GO/CONSIDER/STOP badge, an EXPLORATORY badge, a per-arm posterior table (treatment vs control), the posterior risk difference with a credible interval, and a predictive probability of success.
2. `"Interim on our controlled trial: 9 of 45 responded on treatment and 9 of 45 on control, planned 200 total. Should we stop for futility?"`
   Expect: a STOP for futility with a low predictive probability of success.

- [ ] **Update the docs**

In `README.md`, update the two-arm coverage note in the Bayesian go/no-go paragraph (change "fit_interim is binary single-arm" framing to "single- and two-arm binary"), and bump the unit-test count. Commit.

Update `CONCEPTS.md` §26 to note the two-arm interim (risk difference, joint beta-binomial predictive) if that section is present locally. (CONCEPTS.md is git-ignored; edit it but do not commit it.)

---

## Self-review notes

**Spec coverage.** §3 decision rule → Task 2 (prob_diff_exceeds + decide). §4 predictive_prob_success_diff + cap/thinning → Task 1. §5 fit_interim two-arm branch, priors, 1:1 allocation, arms/terms/verdict output → Task 2. §6 routing → Task 3. §7 rendering (app, report, render) → Tasks 2 (render) + 4 (app/report). §8 error handling → Task 2 (tested: single arm, obs>planned, and the binary-only/complete cases via the shared guards). §9 deterministic caveats → Task 2. §10 test plan → distributed across every task. §11 references → in the spec.

**Type consistency.** `predictive_prob_success_diff(prior_t, prior_c, x_t, n_t, x_c, n_c, n_planned_t, n_planned_c, rule)` is defined in Task 1 and called with exactly those arguments in Task 2. `_go_diff_block(t_ab, st, n_t, c_ab, sc, n_c, rule)` takes `(a,b)` tuples for `t_ab`/`c_ab`, matching how Task 2 passes `prior_t.params`. `arms` dicts use `{arm, n, value, ci_low, ci_high, is_baseline, is_winner}` — the existing shape rendered by app/report. `verdict` adds `posterior_diff`, `diff_ci_low`, `diff_ci_high`, all read in Task 4.

**Known scope reduction, deliberate and flagged.** 1:1 allocation only; no historical-control borrowing; binary endpoint only; interim only (no two-arm `calc_assurance`). Each is stated in the spec and enforced or defaulted in code, not a silent gap.
