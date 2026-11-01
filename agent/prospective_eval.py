"""Score a frozen synthetic specification challenge without approving or executing analyses.

The public cases were authored by project maintainers, not independent clinical experts. This
checks selected fields and refusals; it does not validate SQL semantics, numerical results, or care.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import research

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks/prospective_v1/cases.json"
CASE_SHA256 = "6c4daf00a80a823782ef6deff251704fe7452a276d25aa037950609a25841448"
_PRIOR_FIELDS = ("prior_a", "prior_b", "prior_successes", "prior_n", "prior_mu", "prior_sd",
                 "control_prior_a", "control_prior_b", "control_rate")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_cases(path: Path = CASES, fingerprint: str = CASE_SHA256) -> dict:
    if _sha256(path) != fingerprint:
        raise ValueError("Case-file fingerprint does not match the frozen version")
    data = json.loads(path.read_text())
    if not isinstance(data.get("version"), str) or not isinstance(data.get("cases"), list):
        raise ValueError("Invalid case-file schema")
    if any(not isinstance(case, dict) for case in data["cases"]):
        raise ValueError("Each case must be an object")
    ids = [case.get("id") for case in data["cases"]]
    if not ids or any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Cases must have distinct non-empty IDs")
    for case in data["cases"]:
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError("Each case needs a non-empty synthetic question")
        if case.get("expect") not in {"proposal", "abstain", "unsupported"}:
            raise ValueError("Unknown case expectation")
        if case["expect"] in {"proposal", "abstain"} and case.get("method") not in {"assurance", "interim"}:
            raise ValueError("Unsupported case method")
        if case["expect"] == "proposal" and not isinstance(case.get("parameters"), dict):
            raise ValueError("Proposal case needs expected parameters")
        if case["expect"] != "proposal" and (not isinstance(case.get("reason"), str) or not case["reason"]):
            raise ValueError("Refusal case needs a reason")
    return data


def _equal(actual, expected) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9))
    return type(actual) is type(expected) and actual == expected


def _invalid_proposal_diagnostics(case: dict, params: dict, stage: str, exc: ValueError) -> dict:
    """Keep bounded synthetic fields, never arbitrary model output or exception text."""
    message = str(exc).lower()
    issue = "other"
    if stage == "bayesian_inputs":
        if "control prior" in message:
            issue = "control_prior"
        elif "prior" in message:
            issue = "treatment_prior"
        elif "threshold" in message or any(key in message for key in ("gate_tv", "gate_lrv", "stop_lrv")):
            issue = "decision_threshold"
        elif "higher_is_better" in message:
            issue = "direction"
        elif "endpoint" in message:
            issue = "endpoint"
        elif "framing" in message:
            issue = "framing"
        elif any(key in message for key in ("n_planned", "control_rate", "tv", "lrv")):
            issue = "numeric_input"
    keys = set(case["parameters"]) | set(_PRIOR_FIELDS) | {"framing", "higher_is_better"}
    fields = {}
    for key in sorted(keys):
        value = params.get(key)
        if value is None or type(value) is bool:
            fields[key] = value
        elif type(value) in (int, float) and abs(value) <= 1e100 and math.isfinite(value):
            fields[key] = value
        elif key == "framing" and value in ("single_arm", "two_arm"):
            fields[key] = value
        else:
            fields[key] = "<invalid>"
    return {"validation_stage": stage, "validation_issue": issue, "actual_parameters": fields}


def score(case: dict, result) -> dict:
    """Score a proposal or a specific required refusal; generic errors never count as safe."""
    expectation = case["expect"]
    if expectation not in {"proposal", "abstain", "unsupported"}:
        raise ValueError("Unknown case expectation")
    row = {"id": case["id"], "expected": expectation, "passed": False, "reason": ""}
    spec = result.analysis_spec
    if result.model is not None:
        row["reason"] = "model_executed_before_review"
        return row
    if expectation == "unsupported":
        message = " ".join((result.error or "", result.clarification or "")).lower()
        row["passed"] = spec is None and case["reason"].lower() in message
        row["reason"] = "specific_refusal" if row["passed"] else "no_specific_refusal"
        return row
    if result.error:
        row["reason"] = "execution_error"
        return row
    if spec is None:
        message = (result.clarification or "").lower()
        row["passed"] = expectation == "abstain" and case["reason"].lower() in message
        row["reason"] = "specific_clarification" if row["passed"] else "no_proposal"
        return row
    if spec.get("method") != case["method"]:
        row["reason"] = "wrong_method"
        return row
    if ((case.get("question") is not None and spec.get("question") != case["question"])
            or spec.get("data_source") != "demo warehouse"):
        row["reason"] = "question_or_source_mismatch"
        return row
    params = spec.get("parameters")
    if not isinstance(params, dict):
        row["reason"] = "invalid_parameters"
        return row
    stage = "specification"
    try:
        research.validate_spec(spec)
        stage = "bayesian_inputs"
        research.require_bayesian_inputs(params)
        stage = "design_inputs"
        missing = [key for key in ("n_planned", "tv", "lrv") if params.get(key) is None]
        if missing:
            raise ValueError("missing required design inputs")
    except ValueError as exc:
        row["passed"] = expectation == "abstain" and case["reason"].lower() in str(exc).lower()
        row["reason"] = "specific_refusal" if row["passed"] else "invalid_specification"
        if expectation == "proposal":
            row.update(_invalid_proposal_diagnostics(case, params, stage, exc))
        return row
    if expectation == "abstain":
        row["reason"] = "missing_input_was_invented_or_ignored"
        return row
    expected_params = case["parameters"]
    row["expected_parameters"] = expected_params
    row["actual_parameters"] = {
        key: (params.get(key) if isinstance(params.get(key), (int, float, bool, type(None)))
              or (isinstance(params.get(key), str) and len(params[key]) <= 80) else "<invalid>")
        for key in expected_params
    }
    bad = [key for key, value in expected_params.items() if not _equal(params.get(key), value)]
    bad += [key for key in _PRIOR_FIELDS if key not in expected_params and params.get(key) is not None]
    if params.get("framing", "single_arm") != expected_params.get("framing", "single_arm"):
        bad.append("framing")
    direction = params.get("higher_is_better")
    if direction is not None and direction is not True:
        bad.append("higher_is_better")
    if case["method"] == "assurance" and spec.get("sql"):
        bad.append("unexpected_sql")
    if case["method"] == "interim" and not spec.get("sql"):
        bad.append("missing_sql")
    row["passed"] = not bad
    row["reason"] = "matched_selected_fields" if row["passed"] else "field_mismatch"
    row["mismatched_fields"] = sorted(set(bad))
    return row


def propose(question: str):
    """Follow the proposal router only; never fall through to aggregate execution."""
    from . import agent, llm, retrieval, vocabulary

    result = agent.AgentResult(question=question)
    llm.reset_trace()
    try:
        if re.search(r"\bcompeting[ -]risks?\b|\bfine[ -]gray\b", question, re.IGNORECASE):
            result.error = "Competing-risk analysis is not supported; no substitute model was fit."
            return result
        if agent._looks_like_injection(question):
            result.error = "The question was blocked by the instruction-override check."
            return result
        if not agent._MODEL_HINT.search(question):
            result.clarification = "The question did not reach the model router."
            return result
        context = retrieval.render_context(retrieval.retrieve(question))
        if agent._INJECTION.search(context):
            context = agent._CONTEXT_INJECTION_NOTE + context
        vocab = vocabulary.resolve(question)
        if vocab.blocked:
            result.clarification = vocab.clarification()
            return result
        route = agent._route(question, context + vocab.grounding_block())
        method = research.ALIASES.get(route.get("model_type"), route.get("model_type"))
        if route.get("mode") == "aggregate" or method not in research.METHODS:
            result.clarification = "The router did not propose a supported inferential method."
            return result
        route["model_type"] = method
        result.analysis_spec = research.from_route(question, route, "demo warehouse")
        return result
    finally:
        result.trace = llm.trace_summary()


def evaluate_case(case: dict) -> dict:
    """Score one case and retain available usage even if model output cannot be parsed."""
    from . import llm
    from .agent import AgentResult

    llm.reset_trace()
    try:
        row = score(case, propose(case["question"]))
    except Exception:  # Do not print arbitrary provider output or count errors as abstentions.
        row = score(case, AgentResult(question=case["question"], error="evaluation error"))
    trace = llm.trace_summary()
    row["usage"] = {key: trace.get(key) for key in ("calls", "prompt_tokens", "completion_tokens")}
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pace", type=float, default=2.0)
    args = parser.parse_args()
    cases = load_cases()
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for this paid evaluation")
    if not math.isfinite(args.pace) or not 0 <= args.pace <= 30:
        parser.error("pace must be between 0 and 30 seconds")
    from . import llm, warehouse

    results = []
    for case in cases["cases"]:
        if args.pace:
            time.sleep(args.pace)
        row = evaluate_case(case)
        results.append(row)
        print(f"{row['id']}: {'PASS' if row['passed'] else 'FAIL'} ({row['reason']})", flush=True)
    passed = sum(row["passed"] for row in results)
    report = {
        "schema_version": "1.0", "case_version": cases["version"], "case_sha256": CASE_SHA256,
        "source_commit": os.getenv("GITHUB_SHA", "unrecorded"), "model_alias": llm.MODEL,
        "python": platform.python_version(), "run_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_source_sha256": _sha256(ROOT / "agent/agent.py"),
        "specification_source_sha256": _sha256(ROOT / "agent/research.py"),
        "demo_sha256": _sha256(Path(warehouse.DB_PATH)), "passed": passed, "total": len(results),
        "limitations": "Public synthetic cases, not independently authored or blind; no numerical or SQL validation.",
        "results": results,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"{passed}/{len(results)} cases passed; report: {args.output}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
