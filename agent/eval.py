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
import os
import re
import time
from pathlib import Path

import pandas as pd

from .agent import run_analysis
from .eval_dataset import GOLD as CASES
from .warehouse import run_query

HISTORY = Path(__file__).resolve().parent / "eval_history.jsonl"

# --- throttling ------------------------------------------------------------------------------
# An eval sweep is dozens of large prompts back to back and will trip a tokens-per-minute tier.
# Deliberately NOT handled in llm.complete(): the app's per-run deadline cannot interrupt an
# in-flight call (see llm.py), so longer retries there would worsen the worst-case hang for an
# interactive user. A batch sweep can afford to wait; a person staring at Streamlit cannot.
TRANSIENT = re.compile(r"rate.?limit|429|timed? ?out|overloaded|temporarily unavailable|"
                       r"connection|50[234]", re.I)
_RETRY_HINT = re.compile(r"try again in ([\d.]+)s")
PACE_SECONDS = float(os.getenv("EVAL_PACE", "0"))


def backoff_sleep(message: str, delay: float) -> float:
    """Wait per the server's own hint when the 429 body carries one, else `delay`. Returns the
    next delay (doubled, capped) so callers can keep it in a local."""
    hint = _RETRY_HINT.search(message or "")
    time.sleep(min(float(hint.group(1)) + 1.0, 60.0) if hint else delay)
    return min(delay * 2, 60.0)


def _run_with_backoff(question: str, tries: int = 5):
    """run_analysis swallows llm.LLMError into result.error (agent.py, `except llm.LLMError`), so a
    throttled call is indistinguishable from a wrong answer and silently DEFLATES accuracy — a
    rate-limited sweep would read as an agent regression. Retry the transient ones."""
    delay = 8.0
    res = None
    for attempt in range(tries):
        if PACE_SECONDS:
            time.sleep(PACE_SECONDS)
        res = run_analysis(question)
        if res.analysis_spec:
            # The benchmark uses synthetic data and intentionally approves its generated specification
            # to measure downstream behavior. This is not a human review or a validation of the spec.
            res = run_analysis(question, approved_spec=res.analysis_spec)
        if not res.error or not TRANSIENT.search(res.error) or attempt == tries - 1:
            return res
        delay = backoff_sleep(res.error, delay)
    return res

# keywords that indicate the interpretation honored a given guardrail finding kind
_FAITHFUL_KEYS = {
    "small_sample": ("small", "sample", "n=", "unstable", "few"),
    "confounding": ("confound", "adjust", "unadjusted", "standardiz", "covariate"),
    "contrasts": ("confidence", "ci", "interval", "difference", "significant"),
    "skew": ("skew", "median", "iqr", "distribution"),
    "missing_denominator": ("denominator", "base rate", "sample size", "group size"),
    "wide_ci": ("confidence", "interval", "ci", "wide"),
    "multiple_comparisons": ("multiple", "correction", "bonferroni", "fdr", "false positive"),
    # kinds added when the guardrail moved to `caveat` — an unmapped kind can never be scored
    # faithful, so it would silently drag this metric down as new checks start firing
    "boundary_rate": ("interval", "ci", "0%", "100%", "certain", "wilson"),
    "winners_curse": ("small", "sample", "artifact", "rank", "interval", "chance"),
    "mean_contrasts": ("difference", "confidence", "ci", "interval", "mean", "significant"),
    "missing_data": ("missing", "incomplete", "null", "absent"),
    "session_multiplicity": ("multiple", "looking", "spurious", "hypothes", "confirm"),
}


def _reference(case) -> float | None:
    """The ground-truth scalar, or None when this warehouse holds no instance of what is asked.

    A zero-row or zero-valued reference cannot discriminate a correct answer from a broken one: an
    agent that computes it, one that finds nothing, one that refuses, and one that errors all
    produce the same observable. Such a case is unsupported by the warehouse under test, not failed
    by the agent, and scoring it as a failure makes accuracy a function of warehouse size.

    This is not hypothetical. CI builds a 60-patient Synthea sample in which nobody has had a
    myocardial infarction, so `heart_attack_patients` had a reference of 0. The agent did exactly
    the right thing — vocabulary.resolve blocks a condition with no records rather than fitting an
    empty cohort — and the eval marked that refusal wrong, reporting 34/35 where local reported
    35/35 with no difference in the agent at all.
    """
    df = run_query(case.reference_sql)
    if df is None or len(df) == 0:
        return None
    val = df.iloc[0, 0]
    if pd.isna(val) or float(val) == 0:
        return None
    return float(val)


def _previous_cases(path: Path | None = None) -> dict[str, bool]:
    """Per-case outcomes from the most recent run that logged them ({} if none / pre-`cases` format).

    `path` defaults to HISTORY at CALL time (not import time) so tests can redirect it, and so
    agent.route_eval can reuse this against its own history file.
    """
    path = path or HISTORY
    if not path.exists():
        return {}
    for line in reversed(path.read_text().splitlines()):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec.get("cases"), dict):
            return rec["cases"]
    return {}


def _diff_cases(cases: dict[str, bool], prev: dict[str, bool]) -> tuple[list[str], list[str]]:
    """(regressed, fixed) against the previous run. Cases absent from either run are not a change."""
    regressed = sorted(i for i, ok in cases.items() if not ok and prev.get(i) is True)
    fixed = sorted(i for i, ok in cases.items() if ok and prev.get(i) is False)
    return regressed, fixed


def _answer_cells(df, allow_multi: bool = False) -> list[float]:
    """The scalar answer as a list of candidate cells, or [] if it isn't a single-row answer.

    Every GOLD question has scalar ground truth, so a correct answer is a single row. Non-rate answers
    must be a single numeric column (scanning a multi-column/multi-row table would let a query that
    merely *contains* the value pass). Rate answers are the exception: the statistical guardrail
    REQUIRES a rate query to also select its numerator and denominator, so a correct rate result has
    three numeric columns — `allow_multi=True` returns all of them and lets `_matches` find the rate.
    """
    if df is None or len(df) != 1:
        return []
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric or (len(numeric) != 1 and not allow_multi):
        return []
    return [float(df[c].iloc[0]) for c in numeric if pd.notna(df[c].iloc[0])]


def _matches(cells, ref, is_rate, rtol=0.02) -> bool:
    if not cells:
        return False
    # A percentage answer may be reported as a percent (ref) or the equivalent fraction (ref/100);
    # never as ref*100. Non-rate answers must match the reference directly.
    targets = [ref, ref / 100.0] if is_rate else [ref]
    return any(abs(v - t) <= max(abs(t) * rtol, 0.05) for t in targets for v in cells)


def _faithful(res) -> bool | None:
    """Did the interpretation reflect the guardrail's (non-synthetic) findings? None if nothing to check."""
    kinds = [f.kind for f in res.findings if f.kind != "synthetic_data"]
    if not kinds or not res.interpretation:
        return None
    text = res.interpretation.lower()
    hit = sum(any(k in text for k in _FAITHFUL_KEYS.get(kind, ())) for kind in kinds)
    return hit >= (len(kinds) + 1) // 2   # true majority (ceil) of flagged concerns reflected


def main() -> int:
    by_cat: dict[str, list[bool]] = {}
    faithful_hits, faithful_total = 0, 0
    rows = []
    for c in CASES:
        f = None
        if c.expect_clarification:
            res = _run_with_backoff(c.question)
            ok = bool(res.clarification) and res.dataframe is None
            mark = "✅" if ok else "❌"
            print(f"  {mark} {c.id:18} [{c.category}] "
                  f"{'asked for clarification' if ok else 'did NOT clarify (guessed)'}")
        else:
            ref = _reference(c)
            if ref is None:
                # Unsupported by this warehouse — excluded from accuracy rather than counted wrong.
                print(f"  ⃠  {c.id:18} [{c.category:11}] not represented in this warehouse "
                      f"(reference is empty/zero) — skipped, not scored")
                rows.append({"id": c.id, "category": c.category, "ok": None, "faithful": None})
                continue
            res = _run_with_backoff(c.question)
            ok = res.error is None and _matches(
                _answer_cells(res.dataframe, allow_multi=c.is_rate), ref, c.is_rate)
            f = _faithful(res)
            if f is not None:
                faithful_total += 1
                faithful_hits += int(f)
            flag = "" if f is not False else "  ⚠ interpretation ignored its own caveats"
            print(f"  {'✅' if ok else '❌'} {c.id:18} [{c.category:11}] ref={ref:<11.2f} "
                  f"rows={res.n_rows:<3} tries={len(res.attempts)}{flag}")
        by_cat.setdefault(c.category, []).append(ok)
        rows.append({"id": c.id, "category": c.category, "ok": ok, "faithful": f})

    total = [ok for v in by_cat.values() for ok in v]
    if not total:
        print("\n  No case in GOLD is represented in this warehouse — nothing was scored. "
              "The warehouse is too small or too different for this eval to say anything.")
        return 1
    acc = sum(total) / len(total)
    print("\n  by category:")
    for cat, oks in sorted(by_cat.items()):
        print(f"    {cat:12} {sum(oks)}/{len(oks)}")
    faith = (faithful_hits / faithful_total) if faithful_total else 1.0
    print(f"\n  Accuracy: {sum(total)}/{len(total)} = {acc:.0%}   "
          f"Caveat-faithfulness: {faithful_hits}/{faithful_total} = {faith:.0%}")
    # Name the unfaithful cases. Faithfulness moving 7/7 -> 6/7 with no per-case record is
    # unattributable, which is the same failure the per-case accuracy log exists to prevent — and
    # this metric is the noisier of the two, since it reads generated prose rather than a number.
    if unfaithful := [r["id"] for r in rows if r["faithful"] is False]:
        print(f"    caveats ignored in: {', '.join(unfaithful)}")

    # Never let a shrinking denominator pass unremarked: 33/33 over a warehouse that can only
    # support half of GOLD is a weaker statement than 33/33 over one that supports all of it.
    unsupported = [r["id"] for r in rows if r["ok"] is None]
    if unsupported:
        share = len(unsupported) / len(rows)
        print(f"    not represented in this warehouse ({len(unsupported)}/{len(rows)}): "
              f"{', '.join(unsupported)}")
        if share > 0.25:
            print(f"    ⚠ {share:.0%} of GOLD is unsupported here — accuracy is being measured on a "
                  f"fraction of the dataset. Build a larger warehouse before trusting this number.")

    # Per-case diff against the last run. An aggregate that holds steady can still hide a case
    # flipping (one regression masked by one fix), so drift has to be attributable, not just visible.
    # Unsupported cases are omitted entirely rather than recorded as False: a case that vanishes
    # because the warehouse shrank must not read as a regression, and one that reappears because it
    # grew must not read as a fix.
    cases = {r["id"]: r["ok"] for r in rows if r["ok"] is not None}
    prev = _previous_cases()
    if prev:
        regressed, fixed = _diff_cases(cases, prev)
        print()
        if regressed:
            print(f"  ⚠ regressed since last run: {', '.join(regressed)}")
        if fixed:
            print(f"  ✓ fixed since last run:     {', '.join(fixed)}")
        if not regressed and not fixed:
            print("  no per-case change since last run")

    # regression log
    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": stamp, "accuracy": round(acc, 3),
                             "faithfulness": round(faith, 3), "n": len(total),
                             # n is what was scored; unsupported says what the warehouse could not
                             # support, so a run is comparable to another only alongside both
                             "unsupported": unsupported,
                             "cases": cases,
                             # separate from `cases` so the accuracy diff stays a clean pass/fail;
                             # null = the case had no guardrail finding to be faithful to
                             "faithful": {r["id"]: r["faithful"] for r in rows}}) + "\n")
    print(f"  logged → {HISTORY.name}")
    return 0 if acc >= 0.85 else 1


if __name__ == "__main__":
    raise SystemExit(main())
