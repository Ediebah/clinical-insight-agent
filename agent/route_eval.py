"""Routing eval: does an inferential question reach the RIGHT model?

The accuracy eval (agent.eval) covers the aggregation path, where ground truth is a scalar from
reference SQL. The inferential path has no scalar to check — the ground truth is the label — and it
is where the agent's most dangerous failure lives: a misroute does not error, it returns a
confident, well-rendered model of the WRONG KIND. Fitting a logistic regression to a question about
event timing is not a crash, it is a wrong answer that looks right.

Four things are scored per case, because there are four distinct ways a question can fail to reach
its model, and only the second is what people usually mean by "routing accuracy":

  reachable  did _MODEL_HINT fire? If not, _route is never called in production and the case is
             dead no matter what the router would have said. (Also pinned deterministically, with
             no API key, in tests/test_agent.py.)
  correct    did _route pick the labelled model_type?
  keys       did the spec carry the fields agent._fit_model indexes directly? A missing one is a
             fit-time failure, not a routing failure — but it is just as fatal to the answer.
  sql        design-stage calcs (sample_size / assurance) must carry NO analytic_sql; every other
             model type MUST carry it, or agent.run_analysis (~line 700) silently drops the spec to
             the aggregate path with the correct model_type already chosen — a misroute that looks
             like a success in every other metric.

Run:  .venv/bin/python -m agent.route_eval        (needs OPENAI_API_KEY in agent/.env)
Companions: agent.eval (aggregation accuracy), agent.guardrail_eval (no key needed).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time
from collections import Counter
from pathlib import Path

from . import retrieval, vocabulary
from .agent import _MODEL_HINT, _route
from .eval import TRANSIENT, _diff_cases, _previous_cases, backoff_sleep
from .eval_dataset import ROUTE_NO_SQL, ROUTE_REQUIRED_KEYS, ROUTES
from .llm import LLMError

HISTORY = Path(__file__).resolve().parent / "route_eval_history.jsonl"

# A full sweep is ~40 large prompts (the router's system prompt + the catalog context) sent back to
# back, which trips a low tokens-per-minute tier within a handful of calls. Two defences: pace the
# calls, and back off on the 429 rather than losing the whole sweep to one throttled request.
PACE_SECONDS = float(os.getenv("ROUTE_EVAL_PACE", "0"))

# Pinned just under the measured baseline (100% end-to-end on gpt-4o, 2026-07-26), leaving about
# one case of slack for LLM nondeterminism. Set from an observed number, not a guess, and raised
# whenever the router improves — a threshold that never moves is not a gate. It was 0.90 before the
# 'association'-vs-'ols' and 'experiment'-vs-lookup prompt rules closed the last two misroutes.
# Expressed as a ratio rather than a count so it does not go stale every time ROUTES grows.
PASS_THRESHOLD = 0.95

# agent._fit_model accepts these as synonyms, so the router returning one is not a miss.
_ALIASES = {"compare": "best_model", "compare_models": "best_model", "rsf": "survival_ml"}


def _context(question: str) -> str:
    """The same context agent.run_analysis builds, so the eval measures the production prompt."""
    ctx = retrieval.render_context(retrieval.retrieve(question))
    return ctx + vocabulary.resolve(question).grounding_block()


def _route_resilient(question: str, context: str, tries: int = 5) -> tuple[dict, str | None]:
    """(spec, error). One throttled or failed call must cost that case, never the whole sweep —
    an eval that loses every completed result to the last throttled request is not a regression
    tool."""
    delay = 8.0
    for attempt in range(tries):
        try:
            return _route(question, context), None
        except LLMError as e:
            # Only throttling/transient faults are worth retrying — a malformed-JSON failure would
            # just fail again identically and burn four more calls.
            if attempt == tries - 1 or not TRANSIENT.search(str(e)):
                return {}, f"{type(e).__name__}: {e}"
            delay = backoff_sleep(str(e), delay)
    return {}, "unreachable"


def _actual(spec: dict) -> str:
    """The model_type the router effectively chose, normalised to the _fit_model vocabulary."""
    mt = (spec.get("model_type") or "").strip()
    if spec.get("mode") == "aggregate" or mt in ("", "aggregate"):
        return "aggregate"
    return _ALIASES.get(mt, mt)


def _missing_keys(expected: str, spec: dict) -> list[str]:
    """Required spec fields that are absent or empty (only meaningful when the route was correct)."""
    return [k for k in ROUTE_REQUIRED_KEYS.get(expected, ())
            if spec.get(k) in (None, "", [], {})]


def _sql_ok(expected: str, spec: dict) -> bool:
    has_sql = bool((spec.get("analytic_sql") or "").strip())
    return not has_sql if expected in ROUTE_NO_SQL else has_sql


def main() -> int:
    rows = []
    for c in ROUTES:
        reachable = bool(_MODEL_HINT.search(c.question))
        if not reachable:
            # _route is unreachable for this question in production — record it and don't spend a call.
            rows.append({"id": c.id, "expected": c.expected, "actual": "<gate-blocked>",
                         "reachable": False, "correct": False, "keys": [], "sql_ok": False})
            print(f"  🚧 {c.id:26} expected={c.expected:16} BLOCKED by _MODEL_HINT (never reaches _route)")
            continue

        if PACE_SECONDS:
            time.sleep(PACE_SECONDS)
        spec, err = _route_resilient(c.question, _context(c.question))
        if err:
            rows.append({"id": c.id, "expected": c.expected, "actual": "<error>",
                         "reachable": True, "correct": False, "keys": [], "sql_ok": False})
            print(f"  💥 {c.id:26} expected={c.expected:16} {err[:90]}")
            continue

        actual = _actual(spec)
        correct = actual == c.expected
        missing = _missing_keys(c.expected, spec) if correct else []
        sql_ok = _sql_ok(c.expected, spec) if correct else False

        mark = "✅" if (correct and not missing and sql_ok) else ("🟡" if correct else "❌")
        detail = ""
        if not correct:
            detail = f"  got={actual}   ({c.why})" if c.why else f"  got={actual}"
        elif missing:
            detail = f"  missing spec keys: {missing}"
        elif not sql_ok:
            detail = ("  analytic_sql present on a design-stage calc"
                      if c.expected in ROUTE_NO_SQL else "  NO analytic_sql → silently falls to aggregate")
        print(f"  {mark} {c.id:26} expected={c.expected:16}{detail}")

        rows.append({"id": c.id, "expected": c.expected, "actual": actual, "reachable": True,
                     "correct": correct, "keys": missing, "sql_ok": sql_ok})

    n = len(rows)
    reach = sum(r["reachable"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    keyed = sum(r["correct"] and not r["keys"] for r in rows)
    fully = sum(r["correct"] and not r["keys"] and r["sql_ok"] for r in rows)

    errors = sum(r["actual"] == "<error>" for r in rows)
    if errors:
        # Reported separately so a throttled run is never misread as a routing regression.
        print(f"\n  ⚠ {errors}/{n} cases failed to complete (LLM error, not a misroute) — "
              f"the metrics below count them as failures. Re-run, or set ROUTE_EVAL_PACE.")
    print(f"\n  Reachable (gate fired):  {reach}/{n} = {reach/n:.0%}")
    print(f"  Correct model_type:      {correct}/{n} = {correct/n:.0%}")
    print(f"  + required spec keys:    {keyed}/{n} = {keyed/n:.0%}")
    print(f"  + analytic_sql correct:  {fully}/{n} = {fully/n:.0%}   ← end-to-end routable")

    # Misroutes only. A full 18×18 matrix is unreadable; the confusions are the signal, and they
    # cluster on exactly the pairs agent._route's prompt spends its "prefer X over Y" rules on.
    confusions = Counter((r["expected"], r["actual"]) for r in rows if not r["correct"])
    if confusions:
        print("\n  misroutes (expected → actual):")
        for (exp, act), k in confusions.most_common():
            print(f"    {exp:16} → {act:16} ×{k}")

    cases = {r["id"]: bool(r["correct"] and not r["keys"] and r["sql_ok"]) for r in rows}
    prev = _previous_cases(HISTORY)
    if prev:
        regressed, fixed = _diff_cases(cases, prev)
        print()
        if regressed:
            print(f"  ⚠ regressed since last run: {', '.join(regressed)}")
        if fixed:
            print(f"  ✓ fixed since last run:     {', '.join(fixed)}")
        if not regressed and not fixed:
            print("  no per-case change since last run")

    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    with HISTORY.open("a") as fh:
        fh.write(json.dumps({"ts": stamp, "n": n,
                             "reachable": round(reach / n, 3),
                             "accuracy": round(correct / n, 3),
                             "end_to_end": round(fully / n, 3),
                             "cases": cases}) + "\n")
    print(f"  logged → {HISTORY.name}")
    return 0 if (fully / n) >= PASS_THRESHOLD else 1


if __name__ == "__main__":
    raise SystemExit(main())
