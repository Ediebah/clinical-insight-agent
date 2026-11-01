"""Copy for the app's About view — the default landing surface.

Kept out of app.py deliberately. app.py is ~1,250 lines and this is a page of prose that changes
for editorial reasons, not code reasons; holding it here means a typo fix never touches the
smoke-tested render path. Stdlib only, no Streamlit import, so tests/test_about.py can assert the
load-bearing claims (synthetic demo, non-sensitive input, read-only, the counts) without the app harness.

Structure follows the project's landing page (docs/index.html): a serif section head with a muted
standfirst, then hairline-gutter cell grids, numbered pipeline steps, and an accent-bordered note.
Rendered in the app's own tokens rather than the landing page's palette, so About does not look
like a different product from Dashboard and Monitoring.

Every number here is verified against the code — see
docs/superpowers/specs/2026-08-07-about-page-design.md §5 for each claim and its source of truth.
"""
from __future__ import annotations

# ── 1 · what this is ────────────────────────────────────────────────────────────────────────────
LEAD_TITLE = "An AI data scientist over a clinical warehouse."
LEAD_STANDFIRST = "Statistical judgment, not text-to-SQL."
LEAD = (
    "Ask a clinical question in plain English and it picks the model the question actually needs "
    "— adjusted regression, survival, causal effects, non-inferiority, forecasting, or a Bayesian "
    "go/no-go — prepares the data, checks the assumptions, and reports the caveats a text-to-SQL "
    "tool skips."
)
LEAD_STRONG = "Every number is computed, not generated."

# The method suite. `here` marks what the current view is about; None means no chip is highlighted.
METHOD_CHIPS: list[str] = [
    "Adjusted regression",
    "Survival · Cox / Kaplan-Meier",
    "Causal effect · AIPW / T-learner",
    "A/B ship-decision · FDR",
    "Non-inferiority",
    "Bayesian go/no-go",
    "Forecasting",
    "Feature importance",
    "Power & sample size",
]

# ── 2 · what you can ask ────────────────────────────────────────────────────────────────────────
# (question, what happens, method tag). Questions are restated rather than imported from
# app.EXAMPLE_GROUPS: app.py imports this module, so importing back would be circular.
QUESTION_CELLS: list[tuple[str, str, str]] = [
    ("How does patient survival differ by sex?",
     "Kaplan-Meier curves and a Cox model, with the proportional-hazards assumption checked before "
     "any hazard ratio is reported.",
     "survival · Cox / Kaplan-Meier"),
    ("What predicts 30-day readmission, adjusting for age and sex?",
     "A covariate-adjusted logistic model returning odds ratios with confidence intervals, screened "
     "for separation and collinearity.",
     "logistic · covariate-adjusted"),
    ("How does survival differ for heart attack patients?",
     "Name a disease the way people say it and the agent maps the term to the SNOMED descriptions "
     "actually in the warehouse before it builds the cohort.",
     "cohort · vocabulary mapping"),
    ("Is the new antibiotic non-inferior to standard of care?",
     "A one-sided test against a pre-set margin, reported as a risk difference with its confidence "
     "interval rather than a bare p-value.",
     "trials · non-inferiority"),
    ("How many patients per arm, at 80% power?",
     "Sample size and power for a trial you have not run yet, including the non-inferiority case "
     "with an explicit margin.",
     "design · power & sample size"),
    ("Where does the 30-day readmission rate come from?",
     "Traces the number back through the dbt graph to the raw source table, so any figure on screen "
     "can be audited to its origin.",
     "lineage · dbt graph"),
]

# ── 3 · what data sits behind it ────────────────────────────────────────────────────────────────
# 26 models produce 16 queryable tables; the 10 staging models are views and are not materialized
# in the shipped demo warehouse. Stating only one of those numbers misleads.
DATA_FACTS: list[tuple[str, str, str]] = [
    ("Patients", "1,334", "seed 12345"),
    ("dbt models", "26", "staging · core · marts"),
    ("Queryable tables", "16", "in the demo warehouse"),
    ("Data tests", "108", "green in CI on every push"),
]
DATA_NOTE = (
    "The demo uses **Synthea synthetic EHR data**, generated with documented settings. Use only "
    "synthetic or non-sensitive data; an upload can contain sensitive information despite these "
    "instructions. dbt builds the models above across "
    "staging, a core star schema, and analytics marts, and the data tests run against them on "
    "every push."
)
BYOD_LABEL = "Your own data"
BYOD_NOTE = (
    "Upload a CSV or Excel file and the agent profiles it, infers each column's structural role, "
    "and runs the same modeling suite against it. A local model first scans the columns for "
    "identifiers and asks you what to drop, mask, or keep — that scan runs on this machine and "
    "sends nothing anywhere. Measured against 200 Synthea-derived patients (`agent/deid_eval.py`), "
    "it caught 99.9% of the identifier text spans it was asked to mask — a **ceiling**, not a "
    "real-world figure: those notes label every identifier explicitly (MRN, DOB, SSN, resides "
    "at), which ordinary clinical text does not, and would likely score worse. It reduces what "
    "reaches the language model; it does **not** make the data de-identified or safe to share, "
    "and on this hosted demo the file has already reached the server. Use **synthetic or "
    "non-sensitive data only** here."
)

# ── 4 · how a question becomes an answer ────────────────────────────────────────────────────────
PIPELINE: list[tuple[str, str, str]] = [
    ("01", "Retrieve schema",
     "Pulls the right tables and metric definitions from the semantic catalog."),
    ("02", "Plan the approach",
     "Proposes an exploratory method and specification for the user to review."),
    ("03", "Review & run SQL",
     "Runs the approved read-only SQL without rewriting it after approval."),
    ("04", "Statistical guardrail",
     "Confidence intervals, FDR correction, and checks for confounding and Simpson's paradox."),
    ("05", "Self-review",
     "Critiques its own answer and the assumptions behind the model it chose."),
    ("06", "Report",
     "The result, its caveats, and the tables it used — exportable to a Word report."),
]
GUARDRAIL_NOTE_LABEL = "Read this first"
GUARDRAIL_NOTE = (
    "The guardrail is the part worth reading before the headline number. It is **computed, not "
    "generated**: a language model may phrase a caveat, but no language model decides whether one "
    "applies."
)

# ── 5 · what it will not do ─────────────────────────────────────────────────────────────────────
# "Name a condition" is deliberate, not loose phrasing: agent/vocabulary.py only declares a term
# absent when it is recognized as a condition. Free text falls through to the zero-row self-heal.
LIMITS: list[tuple[str, str]] = [
    ("Demo numbers are illustrative, not clinical.",
     "Synthea data is synthetic. Public-data comparisons and automated tests are limited checks; "
     "they do not establish clinical validity."),
    ("It will not guess at a vague question.",
     "A question too vague to attempt gets a clarifying question back instead of a confident "
     "answer."),
    ("It will not analyze a cohort that isn't there.",
     "Name a condition absent from the warehouse and it says so, rather than fitting a model on an "
     "empty set."),
    ("It cannot write to anything.",
     "The SQL engine opens the database read-only, with external file access disabled, and caps "
     "every result at 1,000 rows. Nothing typed into the question box is executed as SQL."),
    ("It does not give medical advice.",
     "Nothing here makes a clinical decision or substitutes for one."),
]

# ── 6 · getting started ─────────────────────────────────────────────────────────────────────────
GETTING_STARTED: list[tuple[str, str, str]] = [
    ("🔬", "Analyze",
     "Ask a question in plain English. Needs an OPENAI_API_KEY, or any OpenAI-compatible endpoint "
     "via OPENAI_BASE_URL — a local Ollama model works, costs nothing, and keeps the data on your "
     "machine."),
    ("🧾", "Reproduce",
     "Point it at a published trial design — the bundled worked example, or your own PDF — and it "
     "reproduces the paper's decision. The model only extracts the design; the exact "
     "beta-binomial engine does the arithmetic. Needs a key."),
    ("📈", "Dashboard",
     "The cohort at a glance: demographics, clinical mix, utilization, distributions, and how the "
     "measures correlate. No key needed."),
    ("📊", "Monitoring",
     "Run traces, latency, spend, warehouse health checks, and the data-quality agent. "
     "No key needed."),
]


ABOUT_MD = f"""\
# {LEAD_TITLE}

{LEAD_STANDFIRST} {LEAD} {LEAD_STRONG}

## What you can ask

{chr(10).join(f"- *{q}* — {d} ({t})" for q, d, t in QUESTION_CELLS)}

## What data sits behind it

{" · ".join(f"**{v}** {label.lower()}" for label, v, _ in DATA_FACTS)}

{DATA_NOTE}

**{BYOD_LABEL}.** {BYOD_NOTE}

## How a question becomes an answer

{chr(10).join(f"{n}. **{title}** — {desc}" for n, title, desc in PIPELINE)}

**{GUARDRAIL_NOTE_LABEL}.** {GUARDRAIL_NOTE}

## What it will not do

{chr(10).join(f"- **{head}** {body}" for head, body in LIMITS)}

## Getting started

{chr(10).join(f"- **{name}** — {desc}" for _icon, name, desc in GETTING_STARTED)}
"""
