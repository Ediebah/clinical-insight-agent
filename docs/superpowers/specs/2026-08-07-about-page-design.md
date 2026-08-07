# About page for the Streamlit app — Design

**One-line:** Add an About view as the app's default landing surface, so a first-time visitor reads what the platform is before they see a question box, with the copy held in a new `about.py` rather than in the already-large `app.py`.

**Status:** design, approved, awaiting spec review.

## 1. Motivation

`app.py` opens directly on the Analyze view: a hero, a data-source radio, and a question box. Nothing on screen explains what the platform does, so a visitor's default reading is "another text-to-SQL chatbot" — which is precisely what this is not, and the misread costs the project its main differentiator.

A full explanation already exists at `docs/index.html`, published via GitHub Pages, but a visitor who opens the Streamlit app never sees it.

**Audience:** prospective users (clinical / HEOR analysts deciding whether to try it). The page is product onboarding, not portfolio evidence. It is deliberately *not* written for recruiters or for skeptical reviewers; those readings are served by `README.md` and the landing page respectively.

## 2. The change

Four things, no restructuring:

1. **New `about.py`** at repo root. Exports the page copy as module-level constants plus `ABOUT_MD`, the assembled markdown. Stdlib only — no Streamlit import — so it is testable without the app harness.
2. **`_render_about()` in `app.py`**, sitting alongside `_render_dashboard` and `_render_monitoring` and following their shape exactly: emit markdown, use the existing `.eyebrow` design token for section labels, `st.expander` for the two collapsed sections.
3. **Nav at `app.py:660`** gains a fourth segment and changes its default:
   ```python
   _view = st.segmented_control("nav", ["ℹ️ About", "🔬 Analyze", "📈 Dashboard", "📊 Monitoring"],
                                default="ℹ️ About", label_visibility="collapsed")
   if _view == "ℹ️ About":
       _render_about()
       st.stop()
   ```
   placed as the first branch, above the existing Dashboard and Monitoring branches.
4. **Tests** per §6.

The hero at `app.py:646` already renders above the nav on every view, so the title, the one-paragraph summary, and the segmented control stay visible on About. "Analyze" is one visible click away, never hidden.

## 3. Why static prose, and why it is the default

**Static.** The page holds no live warehouse reads, no clickable example on-ramp, and no session state. Because About is now the *default* view, it is the surface every visitor loads first: it must render instantly and must not be able to fail. A version that read cohort counts from DuckDB would turn a bad warehouse connection into an empty landing page. Static copy cannot error.

**Default rather than a fourth tab you might click.** Landing on Analyze leaves the orientation gap exactly as it is today — a first-timer can still miss the page entirely. The cost is one extra click for repeat visitors, which is acceptable given the hero keeps the nav in view.

## 4. Page content

Six sections. Sections 4 and 5 sit inside `st.expander`, consistent with existing app usage (`app.py:607`, `app.py:741`), keeping roughly 450–550 words visible by default.

### 4.1 What this is

Clinical Insight Agent answers questions about clinical data in plain English, but it is not a text-to-SQL tool. It decides which statistical model the question actually needs — survival, adjusted regression, causal, non-inferiority, forecast, or machine learning — prepares the data, fits the model, checks its assumptions, and reports the result alongside the caveats that would stop a statistician believing it.

The language model plans and phrases. Every number is computed by `statsmodels` or `scikit-learn`, and every caveat is decided by deterministic rules.

### 4.2 What you can ask

Six question types, two examples each, drawn from the groups in `EXAMPLE_GROUPS` (`app.py:50`). The examples are **restated** in `about.py` rather than imported. This is forced by the import direction: `app.py` imports `about.py`, so `about.py` importing `EXAMPLE_GROUPS` back from `app.py` would be circular. The upside is that editing About's examples cannot affect the Analyze view's example buttons; the cost is that the two lists can drift, which is acceptable because they serve different jobs (About illustrates the *range* of question types, Analyze offers *runnable* prompts).

| Type | Examples |
|---|---|
| Clinical inference & modeling | "How does patient survival differ by sex?" · "What predicts 30-day readmission, adjusting for age and sex?" |
| A specific condition | "How does survival differ for heart attack patients?" · "What is the total encounter cost for COPD patients?" |
| Trials — non-inferiority | "Is the new antibiotic non-inferior to standard of care on cure rate (10-point margin)?" |
| Trial design — power & sample size | "How many patients per arm to detect a 10-point rise in cure rate from 70%, at 80% power?" |
| Operational analytics | "Which chronic conditions drive the highest total encounter cost?" · "Forecast monthly encounter volume for the next 12 months." |
| Lineage & trust | "Where does the 30-day readmission rate come from?" |

Closing note: name a disease the way people say it (*heart attack*, *COPD*, *diabetes*) and the agent maps the term to the SNOMED descriptions actually in the warehouse before it queries.

### 4.3 What data sits behind it

The demo runs on Synthea synthetic EHR data: 1,139 patients, generated reproducibly from seed 12345. It is computer-generated, so there is no PHI anywhere in the system.

dbt builds **26 models** across staging, a core star schema, and analytics marts, producing the **16 tables** available to query, and **108 data tests** run against them in CI on every push.

You can also bring your own data: upload a CSV or Excel file and the agent profiles it, infers each column's structural role, and runs the same modeling suite. Uploads reach the server and the model sees your column names and query results, so use synthetic or non-sensitive data only.

### 4.4 How to read an answer *(expander)*

What each part of the output is for:

- **Hypothesis** — what it is testing, stated before it looks at the data.
- **SQL** — the exact read-only query it wrote. If a query errors, returns nothing, or comes back all zeros, it rewrites and retries; the failed attempts stay visible.
- **Model** — which model it chose and why.
- **Guardrail** — confidence intervals, BH-FDR correction across pairwise contrasts, confounding and Simpson's-paradox warnings, small-sample flags.
- **Self-review** — the agent checking its own answer against the data it retrieved.
- **Lineage** — trace any number back through the dbt graph to the raw source table.

The guardrail is the part worth reading first. It is computed, not generated: an LLM may phrase a caveat, but no LLM decides whether one applies.

### 4.5 What it will not do *(expander)*

- **Demo numbers are illustrative, not clinical.** Synthea data is synthetic and has no ground truth. The statistical methods themselves are separately validated against published real-data results, enforced in CI.
- **It will not guess at a vague question.** A question too vague to attempt gets a clarifying question back.
- **It will not analyze a cohort that isn't there.** Name a condition absent from the warehouse and it says so, instead of fitting a model on an empty set.
- **It cannot write to anything.** The SQL engine opens the database read-only, with external file access disabled, and caps every result at 1,000 rows. Nothing typed into the question box is executed as SQL.
- **It does not give medical advice or make clinical decisions.**

### 4.6 Getting started

- **🔬 Analyze** — ask a question. Needs `OPENAI_API_KEY`, or any OpenAI-compatible endpoint via `OPENAI_BASE_URL`; a local Ollama model works, costs nothing, and keeps the data on your machine.
- **📈 Dashboard** — the cohort at a glance: demographics, clinical mix, utilization, distributions, correlations. No key needed.
- **📊 Monitoring** — run traces, latency, spend, warehouse health checks, and the data-quality agent. No key needed.

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

- **`tests/test_about.py` (new)** — imports `about` with no Streamlit dependency and asserts the copy still carries its load-bearing claims: that it says `synthetic`, `no PHI`, `read-only`, `1,000`, `26`, `108`, `1,139`, and that it is not empty. This is the point of putting copy in its own module: a later edit that quietly drops the PHI disclosure fails CI.
- **`tests/test_app_smoke.py` (amend)** — the app now defaults to About, so the existing smoke test will exercise About rather than the Analyze flow. Add a second `AppTest` case that drives the nav back to `🔬 Analyze` and re-runs, restoring the coverage the default change would otherwise silently drop:
  ```python
  at.segmented_control[0].set_value("🔬 Analyze").run()
  assert not at.exception
  ```
  `AppTest.segmented_control` is available in the pinned Streamlit (1.58.0), confirmed against the installed package, so this needs no test-harness workaround.
- **`tests/test_app_render.py`** — unaffected; it calls `_render_model` directly and does not go through the nav.
- Full suite green, ruff clean. All of these are keyless.

## 7. Scope

One new module, one new render function, a four-line nav change, one new test file, one amended test. No change to the agent, the warehouse, the modeling suite, or any existing view's behaviour.

Explicitly out of scope: clickable example questions that jump into Analyze; live warehouse statistics on the page; any restructuring of `app.py` beyond the nav block; reconciling `README.md:23` (which says 291 unit tests while the root suite now collects 314).
