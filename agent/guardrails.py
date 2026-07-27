"""Statistical guardrail — the biostatistics moat, now a thin adapter over `caveat`.

The checks that used to live here are domain-neutral: nothing about a small denominator or a
reversed stratified ordering is specific to healthcare. They were extracted to `caveat`
(packages/caveat) so an agent in any domain can use them, and so they can be tested and versioned
on their own. What stays here is the part that genuinely IS this project's:

  * the confounders named in the confounding message (age, sex, comorbidity burden, ...)
  * the synthetic-data caveat, which is true of this warehouse and of nothing else
  * the module-level API the rest of the agent already imports

Everything remains deterministic and computed from the data — no LLM. The model may only *phrase*
these caveats, never invent or omit them.
"""
from __future__ import annotations

import pandas as pd

# Re-exported so existing callers (agent.charts, agent.modeling, the tests) keep working unchanged.
from caveat import Config, Finding, Report, Roles, Session, render
from caveat import analyze as _analyze
from caveat.stats import (
    benjamini_hochberg,
    bootstrap_mean_ci,
    newcombe_diff_ci,
    skewness,
    two_proportion_p,
    wilson_ci,
)

__all__ = [
    "Finding", "Report", "Roles", "Config", "Session", "analyze", "render",
    "wilson_ci", "newcombe_diff_ci", "two_proportion_p", "benjamini_hochberg",
    "skewness", "bootstrap_mean_ci", "SYNTHETIC_NOTE", "CONFIG",
]

# Confounders worth naming for THIS warehouse. Generic `caveat` says "composition, exposure and
# selection"; a clinical reader wants the actual candidates.
CONFIG = Config(confounders=("age", "sex/gender", "comorbidity burden",
                             "condition severity", "payer/access"))

SYNTHETIC_NOTE = (
    "Data is synthetic (Synthea): structurally realistic but generated from care-process models, "
    "so magnitudes are illustrative, not empirical. Demonstrates method, not clinical fact.")


def analyze(df: pd.DataFrame, question: str = "", sql: str = "") -> list[Finding]:
    """Findings for a result table, always ending with the synthetic-data caveat.

    Returns a plain list rather than a caveat.Report because that is what the agent, the app and
    the report renderer already consume. Use `analyze_report` when you want the roles that were
    resolved and the checks that could not run.
    """
    return analyze_report(df, question, sql).findings


def analyze_report(df: pd.DataFrame, question: str = "", sql: str = "") -> Report:
    """The full Report — findings, resolved column roles, and every check that was skipped."""
    report = _analyze(df, question, config=CONFIG)
    if not any(f.kind == "empty_result" for f in report.findings):
        report.findings.append(Finding("synthetic_data", "info", SYNTHETIC_NOTE))
    return report


if __name__ == "__main__":
    demo = pd.DataFrame({
        "age_group": ["18-39", "40-64", "65-74", "75+"],
        "patients_with_condition": [12, 147, 62, 4],
        "total_patients_in_age_group": [309, 394, 120, 8],
        "prevalence_pct": [3.88, 37.31, 51.67, 50.0],
    })
    rep = analyze_report(demo, "Which age group has the highest prevalence of hypertension?")
    print(render(rep, icons={"info": "i", "warn": "!", "caution": "!!"}))
    print(f"\nroles: {rep.roles}")
    for s in rep.skipped:
        print(f"skipped: {s}")
