"""Accuracy eval at grade: categorized known-answer questions + clarify-gate + caveat faithfulness.

For each answerable case we compute a ground-truth scalar with a hand-written reference SQL
(deterministic, no LLM), run the agent, and check the agent's result contains that value. Clarify
cases assert the agent asks for clarification instead of guessing. We also measure "caveat
faithfulness" — whether the interpretation actually reflects the guardrail's findings — and log a
summary row to agent/eval_history.jsonl for regression tracking.

Run:  .venv/bin/python -m agent.eval        (needs OPENAI_API_KEY in agent/.env)
Companion: agent.guardrail_eval (guardrail precision/recall, no key needed).
"""
from __future__ import annotations
import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .agent import run_analysis
from .guardrails import render
from .warehouse import run_query

HISTORY = Path(__file__).resolve().parent / "eval_history.jsonl"

# keywords that indicate the interpretation honored a given guardrail finding kind
_FAITHFUL_KEYS = {
    "small_sample": ("small", "sample", "n=", "unstable", "few"),
    "confounding": ("confound", "adjust", "unadjusted", "standardiz", "covariate"),
    "contrasts": ("confidence", "ci", "interval", "difference", "significant"),
    "skew": ("skew", "median", "iqr", "distribution"),
    "missing_denominator": ("denominator", "base rate", "sample size", "group size"),
    "wide_ci": ("confidence", "interval", "ci", "wide"),
    "multiple_comparisons": ("multiple", "correction", "bonferroni", "fdr", "false positive"),
}


@dataclass
class Case:
    id: str
    question: str
    category: str
    reference_sql: str = ""          # ground-truth scalar (row 0, col 0)
    is_rate: bool = False
    expect_clarification: bool = False


CASES: list[Case] = [
    # ---- counts ----
    Case("n_patients", "How many patients are in the warehouse?", "count",
         "select count(*) from dim_patient"),
    Case("n_deceased", "How many patients are deceased?", "count",
         "select count(*) from dim_patient where is_deceased"),
    Case("n_inpatient", "How many inpatient encounters are there?", "count",
         "select count(*) from fct_encounters where encounter_class = 'inpatient'"),
    Case("n_conditions", "How many distinct conditions are recorded?", "count",
         "select count(*) from dim_condition"),
    Case("n_med_orders", "What is the total number of medication orders?", "count",
         "select count(*) from fct_medications"),
    Case("n_encounters", "How many encounters are there in total?", "count",
         "select count(*) from fct_encounters"),
    Case("n_providers", "How many providers are in the warehouse?", "count",
         "select count(*) from dim_provider"),
    Case("n_female", "How many female patients are there?", "count",
         "select count(*) from dim_patient where gender = 'F'"),
    # ---- cost ----
    Case("avg_cost", "What is the average total claim cost per encounter?", "cost",
         "select round(avg(total_claim_cost), 2) from fct_encounters"),
    Case("max_cost", "What is the most expensive encounter's total claim cost?", "cost",
         "select round(max(total_claim_cost), 2) from fct_encounters"),
    Case("avg_inpatient_cost", "What is the average claim cost of an inpatient encounter?", "cost",
         "select round(avg(total_claim_cost), 2) from fct_encounters where encounter_class = 'inpatient'"),
    Case("total_med_cost", "What is the total cost of all medication orders?", "cost",
         "select round(sum(total_cost), 0) from fct_medications"),
    # ---- rates ----
    Case("readmit_rate", "What is the overall 30-day readmission rate as a percent?", "rate",
         "select round(100 * avg(is_30d_readmission::int), 1) from mart_readmissions", is_rate=True),
    Case("htn_65_74", "What is the prevalence of hypertension in the 65-74 age group, as a percent?", "rate",
         "select round(prevalence_pct, 1) from mart_condition_prevalence "
         "where condition_description ilike '%hypertension%' and age_group = '65-74'", is_rate=True),
    Case("pct_deceased", "What percent of patients are deceased?", "rate",
         "select round(100.0 * avg(is_deceased::int), 1) from dim_patient", is_rate=True),
    # ---- filter by clinical name (grounding) ----
    Case("n_diabetes_pts", "How many patients have a diabetes diagnosis?", "filter_name",
         "select count(distinct c.patient_id) from fct_conditions c join dim_condition d "
         "using (condition_code) where d.condition_description ilike '%diabetes%'"),
    # ---- descriptive stat ----
    Case("avg_age", "What is the average patient age?", "stat",
         "select round(avg(age), 1) from dim_patient"),
    # ---- clarify gate (should NOT guess) ----
    Case("ambiguous_trends", "show me the trends", "clarify", expect_clarification=True),
    Case("out_of_scope", "which treatment is clinically best?", "clarify", expect_clarification=True),
]


def _reference(case: Case) -> float:
    return float(run_query(case.reference_sql).iloc[0, 0])


def _numeric_cells(df) -> list[float]:
    if df is None or len(df) == 0:
        return []
    out = []
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            out += [float(v) for v in df[c].dropna().tolist()]
    return out


def _matches(cells, ref, is_rate, rtol=0.02) -> bool:
    targets = [ref] + ([ref / 100.0, ref * 100.0] if is_rate else [])
    return any(abs(v - t) <= max(abs(t) * rtol, 0.5) for t in targets for v in cells)


def _faithful(res) -> bool | None:
    """Did the interpretation reflect the guardrail's (non-synthetic) findings? None if nothing to check."""
    kinds = [f.kind for f in res.findings if f.kind != "synthetic_data"]
    if not kinds or not res.interpretation:
        return None
    text = res.interpretation.lower()
    hit = sum(any(k in text for k in _FAITHFUL_KEYS.get(kind, ())) for kind in kinds)
    return hit >= max(1, len(kinds) // 2)   # majority of flagged concerns reflected


def main() -> int:
    by_cat: dict[str, list[bool]] = {}
    faithful_hits, faithful_total = 0, 0
    rows = []
    for c in CASES:
        if c.expect_clarification:
            res = run_analysis(c.question)
            ok = bool(res.clarification) and res.dataframe is None
            mark = "✅" if ok else "❌"
            print(f"  {mark} {c.id:18} [{c.category}] "
                  f"{'asked for clarification' if ok else 'did NOT clarify (guessed)'}")
        else:
            ref = _reference(c)
            res = run_analysis(c.question)
            ok = res.error is None and _matches(_numeric_cells(res.dataframe), ref, c.is_rate)
            f = _faithful(res)
            if f is not None:
                faithful_total += 1
                faithful_hits += int(f)
            print(f"  {'✅' if ok else '❌'} {c.id:18} [{c.category:11}] ref={ref:<11.2f} "
                  f"rows={res.n_rows:<3} tries={len(res.attempts)}")
        by_cat.setdefault(c.category, []).append(ok)
        rows.append({"id": c.id, "category": c.category, "ok": ok})

    total = [ok for v in by_cat.values() for ok in v]
    acc = sum(total) / len(total)
    print("\n  by category:")
    for cat, oks in sorted(by_cat.items()):
        print(f"    {cat:12} {sum(oks)}/{len(oks)}")
    faith = (faithful_hits / faithful_total) if faithful_total else 1.0
    print(f"\n  Accuracy: {sum(total)}/{len(total)} = {acc:.0%}   "
          f"Caveat-faithfulness: {faithful_hits}/{faithful_total} = {faith:.0%}")

    # regression log
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": stamp, "accuracy": round(acc, 3),
                             "faithfulness": round(faith, 3), "n": len(total)}) + "\n")
    print(f"  logged → {HISTORY.name}")
    return 0 if acc >= 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(main())
