"""Numeric oracle for the Bayesian go/no-go layer: does the agent reach the right NUMBER?

agent.route_eval checks the agent reaches the right MODEL. That is not the same guarantee. Routing
correctly to `assurance` and then reading "30%" as the LRV instead of the TV yields a confident GO
on a trial that should stop, and every routing metric still scores it green.

This is the agent.eval pattern — deterministic ground truth, agent measured against it — moved to
the inferential layer. bayes.py is closed-form conjugate, so the reference is obtained by calling
the SAME modeling entry point with the CORRECT parameters. Both paths then run identical
arithmetic, and the only thing that can differ is what the agent pulled out of English. A numeric
mismatch is therefore an EXTRACTION bug, never an arithmetic one — which is what makes the failures
actionable rather than merely visible.

Being able to say "the agent's Bayesian decision is checked against a deterministic reference on
every run" is a stronger claim than most clinical-AI products can make about anything they ship.

Run:  .venv/bin/python -m agent.bayes_eval        (needs OPENAI_API_KEY in agent/.env)
Companions: agent.eval (aggregation), agent.route_eval (routing), agent.guardrail_eval (no key).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pandas as pd

from . import modeling
from .eval import _diff_cases, _previous_cases, _run_with_backoff
from .eval_dataset import BAYES

HISTORY = Path(__file__).resolve().parent / "bayes_eval_history.jsonl"

# Both paths run the same closed-form code, so a correct extraction agrees to within float noise.
# A whole percentage point of slack is already far looser than "right"; anything beyond it is a
# different parameter, not a rounding difference.
TOL = 0.01
PASS_THRESHOLD = 0.85


def _interim_df(observed: dict) -> pd.DataFrame:
    """The per-subject rows the question states, as agent._route is told to synthesize them."""
    if "t_successes" in observed:
        rows = ([("treatment", 1)] * observed["t_successes"]
                + [("treatment", 0)] * (observed["t_n"] - observed["t_successes"])
                + [("control", 1)] * observed["c_successes"]
                + [("control", 0)] * (observed["c_n"] - observed["c_successes"]))
        return pd.DataFrame(rows, columns=["arm", "responded"])
    x, n = observed["successes"], observed["n_observed"]
    return pd.DataFrame({"responded": [1] * x + [0] * (n - x)})


def reference(case) -> modeling.ModelResult:
    """Ground truth: the same entry point the agent reaches, with the parameters it should have
    extracted. Computed live rather than hardcoded — see the note on BAYES in eval_dataset."""
    if case.fn == "assurance":
        return modeling.calc_assurance(**case.params)
    return modeling.fit_interim(_interim_df(case.observed), "responded", **case.params)


def main() -> int:
    rows = []
    for c in BAYES:
        ref = reference(c)
        if ref.error:                     # a broken label, not an agent failure — say so loudly
            print(f"  ⛔ {c.id:24} REFERENCE FAILED: {ref.error}")
            rows.append({"id": c.id, "ok": False, "reason": "bad reference"})
            continue
        ref_v = ref.as_dict()["verdict"]
        ref_num, ref_call = ref_v[c.metric], ref_v["call"]

        res = _run_with_backoff(c.question)
        model = res.model or {}
        verdict = model.get("verdict") or {}
        got_type, got_num, got_call = model.get("model_type"), verdict.get(c.metric), verdict.get("call")

        type_ok = got_type == c.fn
        call_ok = got_call == ref_call == c.expected_call
        num_ok = got_num is not None and abs(float(got_num) - float(ref_num)) <= TOL
        ok = type_ok and call_ok and num_ok

        if ok:
            print(f"  ✅ {c.id:24} {c.metric}={ref_num:.4f}  call={ref_call}")
        else:
            why = (res.error or f"routed to {got_type!r}, expected {c.fn!r}" if not type_ok
                   else f"call {got_call} ≠ {ref_call}" if not call_ok
                   else f"{c.metric} {got_num} ≠ {ref_num:.4f}")
            print(f"  ❌ {c.id:24} {why}")
            # fit_stat echoes the parameters actually used ("assurance=76.1% · n=100 · TV=0.3 /
            # LRV=0.15"), which turns "the number is wrong" into "it read the LRV as the TV".
            if model.get("fit_stat"):
                print(f"       agent used: {model['fit_stat']}")
                print(f"       should be : {ref.fit_stat}")
            print(f"       ({c.why})")

        rows.append({"id": c.id, "ok": ok})

    n = len(rows)
    passed = sum(r["ok"] for r in rows)
    print(f"\n  Bayesian numeric agreement: {passed}/{n} = {passed/n:.0%}  (tolerance ±{TOL})")

    cases = {r["id"]: r["ok"] for r in rows}
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
        fh.write(json.dumps({"ts": stamp, "n": n, "accuracy": round(passed / n, 3),
                             "cases": cases}) + "\n")
    print(f"  logged → {HISTORY.name}")
    return 0 if (passed / n) >= PASS_THRESHOLD else 1


if __name__ == "__main__":
    raise SystemExit(main())
