# About page for the Streamlit app — Design

**One-line:** Add an About view as the app's default landing surface, so a first-time visitor reads what the platform is before they see a question box, with the copy held in a new `about.py` rather than in the already-large `app.py`.

**Status:** implemented and driven live; awaiting review before commit.

**Amendment (after a live drive).** The page now follows the format of the project's landing page
(`docs/index.html`) rather than the expander-based layout first specced: serif section heads with a
muted standfirst, hairline-gutter cell grids, a numbered pipeline, method chips, and an
accent-ruled note. It is rendered in **this app's own tokens** (Fraunces / IBM Plex, `#0a0e13`,
`#4fd1c5`) rather than the landing page's palette, because the two systems map almost 1:1 by role
and porting a second palette would make About look like a different product from Dashboard and
Monitoring. §4 below describes the delivered structure; the two `st.expander` sections are gone,
replaced by full sections.

## 1. Motivation

`app.py` opens directly on the Analyze view: a hero, a data-source radio, and a question box. Nothing on screen explains what the platform does, so a visitor's default reading is "another text-to-SQL chatbot" — which is precisely what this is not, and the misread costs the project its main differentiator.

A full explanation already exists at `docs/index.html`, published via GitHub Pages, but a visitor who opens the Streamlit app never sees it.

**Audience:** prospective users (clinical / HEOR analysts deciding whether to try it). The page is product onboarding, not portfolio evidence. It is deliberately *not* written for recruiters or for skeptical reviewers; those readings are served by `README.md` and the landing page respectively.

## 2. The change

Four things, no restructuring:

1. **New `about.py`** at repo root. Exports the page copy as module-level constants plus `ABOUT_MD`, the assembled markdown. Stdlib only — no Streamlit import — so it is testable without the app harness.
2. **`_render_about()` plus a `_sec()` helper in `app.py`**, sitting alongside `_render_dashboard`, `_render_reproduction`, and `_render_monitoring` and following their shape: emit markdown through the components in §4, then `st.stop()`.
3. **The nav** gains a segment and changes its default:
   ```python
   _view = st.segmented_control(
       "nav", ["ℹ️ About", "🔬 Analyze", "🧾 Reproduce", "📈 Dashboard", "📊 Monitoring"],
       default="ℹ️ About", label_visibility="collapsed")
   if _view == "ℹ️ About":
       _render_about()
       st.stop()
   ```
   placed as the first branch, above the existing Reproduce, Dashboard, and Monitoring branches.
   **Five segments, not four**: this branch was rebased onto `origin/main`, which had landed the
   🧾 Reproduce view in #43–#49 while the About work was in progress.
4. **Tests** per §6.

The hero at `app.py:646` already renders above the nav on every view, so the title, the one-paragraph summary, and the segmented control stay visible on About. "Analyze" is one visible click away, never hidden.

## 3. Why static prose, and why it is the default

**Static.** The page holds no live warehouse reads, no clickable example on-ramp, and no session state. Because About is now the *default* view, it is the surface every visitor loads first: it must render instantly and must not be able to fail. A version that read cohort counts from DuckDB would turn a bad warehouse connection into an empty landing page. Static copy cannot error.

**Default rather than a fourth tab you might click.** Landing on Analyze leaves the orientation gap exactly as it is today — a first-timer can still miss the page entirely. The cost is one extra click for repeat visitors, which is acceptable given the hero keeps the nav in view.

## 4. Page content

Six sections, all fully visible (no expanders), each introduced by a `.sec-head`: a serif `h2` with
a muted standfirst on a shared baseline. The components, all added to the CSS block in `app.py`:

| Component | Used by | Shape |
|---|---|---|
| `.sec-head` | every section | serif `h2` + muted standfirst, hairline rule above |
| `.lede` | §4.1 | 1.12rem muted paragraph, `<strong>` lifts to `--text` |
| `.chips` / `.chip` | §4.1 | mono method chips, one per fitted method |
| `.cellgrid` + `.cell` | §4.2, 4.3, 4.4, 4.6 | 1px gaps over a `--border-soft` bed, so children read as ruled cells |
| `.limits` | §4.5 | left-ruled list, bold lead-in + muted body |
| `.note` | §4.4 | 3px accent left border, mono label + prose |

`.cellgrid > div` is `display:flex; flex-direction:column` so `.tag` can take `margin-top:auto` and
bottom-align across cells whose descriptions differ in length — without it the method tags sit at
ragged heights, which a live drive caught.

`.cell .stat` uses the **display** face, not mono: IBM Plex Mono's tabular comma renders `1,139` as
`1 , 139`. Also caught on the live drive.

### 4.1 What this is — *"Statistical judgment, not text-to-SQL."*

A `.lede` paragraph, closing on the bolded **"Every number is computed, not generated."**, followed
by a `.chips` row naming all nine fitted methods (adjusted regression, survival, causal AIPW /
T-learner, A/B with FDR, non-inferiority, Bayesian go/no-go, forecasting, feature importance, power
& sample size). The chip row does the work the old bulleted list did, in one band.

### 4.2 What you can ask — *"Plain English in, a fitted model out."*

Six `.cell`s, each a **(question, what happens, method tag)** triple rather than the bare example
list first specced. The serif question carries the scan, the muted line says what the agent
actually does with it, and the mono tag names the method — which is the differentiating claim, so
it should be on screen rather than implied.

Questions are **restated** in `about.py`, not imported from `EXAMPLE_GROUPS` (`app.py:50`). This is
forced by the import direction: `app.py` imports `about.py`, so importing back would be circular.
The two lists can drift, which is acceptable because they do different jobs — About illustrates the
*range* of question types, Analyze offers *runnable* prompts.

| Question | Tag |
|---|---|
| How does patient survival differ by sex? | `survival · Cox / Kaplan-Meier` |
| What predicts 30-day readmission, adjusting for age and sex? | `logistic · covariate-adjusted` |
| How does survival differ for heart attack patients? | `cohort · vocabulary mapping` |
| Is the new antibiotic non-inferior to standard of care? | `trials · non-inferiority` |
| How many patients per arm, at 80% power? | `design · power & sample size` |
| Where does the 30-day readmission rate come from? | `lineage · dbt graph` |

### 4.3 What data sits behind it — *"Synthetic by design, so the whole project is public."*

The demo runs on Synthea synthetic EHR data: 1,139 patients, generated reproducibly from seed 12345. It is computer-generated, so there is no PHI anywhere in the system.

dbt builds **26 models** across staging, a core star schema, and analytics marts, producing the **16 tables** available to query, and **108 data tests** run against them in CI on every push.

You can also bring your own data: upload a CSV or Excel file and the agent profiles it, infers each column's structural role, and runs the same modeling suite. Uploads reach the server and the model sees your column names and query results, so use synthetic or non-sensitive data only.

### 4.4 How a question becomes an answer — *"One question runs the whole analysis."*

Six numbered `.cell`s in a 3×2 grid, mirroring the landing page's pipeline band: **01** retrieve
schema · **02** plan the approach · **03** write & fix SQL · **04** statistical guardrail · **05**
self-review · **06** report. Below it, a `.note` carrying the claim the whole page turns on:

> **Read this first** — The guardrail is the part worth reading before the headline number. It is
> **computed, not generated**: a language model may phrase a caveat, but no language model decides
> whether one applies.

### 4.5 What it will not do — *"The boundaries, stated up front."*

- **Demo numbers are illustrative, not clinical.** Synthea data is synthetic and has no ground truth. The statistical methods themselves are separately validated against published real-data results, enforced in CI.
- **It will not guess at a vague question.** A question too vague to attempt gets a clarifying question back.
- **It will not analyze a cohort that isn't there.** Name a condition absent from the warehouse and it says so, instead of fitting a model on an empty set.
- **It cannot write to anything.** The SQL engine opens the database read-only, with external file access disabled, and caps every result at 1,000 rows. Nothing typed into the question box is executed as SQL.
- **It does not give medical advice or make clinical decisions.**

### 4.6 Getting started — *"Four views. Two of them need no API key."*

Four `.cell`s in a 2×2 (`.cellgrid.c2`), one per remaining view:

- **🔬 Analyze** — ask a question. Needs `OPENAI_API_KEY`, or any OpenAI-compatible endpoint via `OPENAI_BASE_URL`; a local Ollama model works, costs nothing, and keeps the data on your machine.
- **🧾 Reproduce** — point it at a published trial design and it reproduces the paper's decision. The model only extracts the design; the exact beta-binomial engine does the arithmetic. Needs a key.
- **📈 Dashboard** — the cohort at a glance: demographics, clinical mix, utilization, distributions, correlations. No key needed.
- **📊 Monitoring** — run traces, latency, spend, warehouse health checks, and the data-quality agent. No key needed.

The Reproduce entry is not decoration: `agent/reproduction.py`'s own docstring is *"The language
model extracts an explicit statistical design. It never performs the calculation"* — the same claim
§4.4's note makes about the guardrail, so the page should state it for that view too.

## 5. Accuracy of the claims

Every factual claim in §4 was verified against the code before this spec was written:

| Claim | Source of truth |
|---|---|
| 26 models, 108 data tests | `warehouse/target/manifest.json` — exactly 26 `resource_type: model`, 108 `resource_type: test` |
| 16 queryable tables | `data/healthcare_demo.duckdb` — 11 core + 5 marts materialized; the 10 staging models are views and are not in the shipped demo |
| 1,139 patients, seed 12345 | `dim_patient` row count in the shipped demo DB; seed per `README.md:130` |
| Read-only, sandboxed, 1,000-row cap | `agent/warehouse.py:40` (`MAX_ROWS = 1000`), `:113` (outer `LIMIT`), `:119` (`read_only=True`, `enable_external_access=false`) |
| Clarifying question on vague asks | `agent/agent.py:147` — the TRIAGE gate, "deliberately conservative" |
| Absent condition reported, not analyzed | `agent/vocabulary.py:210–259` — the `absent` list and its empty-cohort guard |
| Caveats decided deterministically | `packages/caveat/src/caveat/checks.py` — no LLM import anywhere in the check logic |
| Local model via `OPENAI_BASE_URL` | `agent/llm.py:80, 88–94`; local runs report $0 (`:68`) |
| Keyless Dashboard / Monitoring | `tests/test_app_smoke.py` runs the app green with no API key |

Two precision points that the copy must respect, both from this pass:

1. **Not "26 tables."** 26 is the *model* count; only 16 are queryable in the shipped demo. §4.3 states both and conflates neither.
2. **Absence detection applies to named conditions.** `agent/vocabulary.py:340` only declares a term absent when it is clearly a condition (`is_condition=True`); free-text phrases fall through to the reactive zero-row self-heal. §4.5 therefore says "name a condition", not "anything you mention".

## 6. Testing

- **`tests/test_about.py` (new, 8 tests)** — imports `about` with no Streamlit dependency and asserts the copy still carries its load-bearing claims: the four disclosures (`synthetic`, `no PHI`, `read-only`, `1,000 rows`), the four counts against the manifest, that models and queryable tables stay stated *separately*, that the absence claim stays scoped to "name a condition", that every question cell is a complete triple, and that the pipeline stays numbered in order. This is the point of putting copy in its own module: a later edit that quietly drops the PHI disclosure fails CI.
- **`tests/test_app_smoke.py` (amend)** — the app now defaults to About, so the existing smoke test will exercise About rather than the Analyze flow. Add a second `AppTest` case that drives the nav back to `🔬 Analyze` and re-runs, restoring the coverage the default change would otherwise silently drop:
  ```python
  at.segmented_control[0].set_value("🔬 Analyze").run()
  assert not at.exception
  ```
  `AppTest.segmented_control` is available in the pinned Streamlit (1.58.0), confirmed against the installed package, so this needs no test-harness workaround.
- **`tests/test_app_render.py`** — unaffected; it calls `_render_model` directly and does not go through the nav.
- Full suite green, ruff clean. All of these are keyless.

## 7. Scope

One new module (`about.py`), one new render function plus a `_sec` helper, a CSS block for the
landing-page components, a four-line nav change, one new test file, one amended test. No change to
the agent, the warehouse, the modeling suite, or any existing view's behaviour.

Explicitly out of scope: clickable example questions that jump into Analyze; live warehouse
statistics on the page; any restructuring of `app.py` beyond the nav block and the CSS additions;
reconciling `README.md:23` (which says 291 unit tests while the root suite now collects 352).

## 8. Verification

- Full suite **352 passed**, exit 0. `ruff check .` clean.
- Driven live at `localhost:8503` in a 1280×900 viewport: all six sections render, the five-segment
  nav opens on About, the Reproduce view still renders through the rewritten nav, zero console
  errors, page height 3,460px.
- Three defects found only by a live drive and fixed: ragged `.tag` baselines across cells whose
  descriptions differ in length; `1,139` rendering as `1 , 139` under IBM Plex Mono's tabular comma;
  and, after the rebase, "Three views" in §4.6 becoming false once Reproduce landed. None of the
  three is visible to a unit test, which is why the page is driven before every commit.
- The rebase onto `origin/main` conflicted in `app.py` (nav) and `tests/test_app_smoke.py`. Both
  resolved as unions — the About branch and the Reproduce branch are independent features, and the
  smoke tests test different views. `pypdf==6.14.2` is a new upstream dependency needed to collect
  the test suite.
