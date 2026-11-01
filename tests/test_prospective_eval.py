"""The prospective benchmark must distinguish correct proposals from safe abstentions."""
import hashlib
import importlib
import importlib.util
import json
from types import SimpleNamespace

import pytest


def evaluator():
    assert importlib.util.find_spec("agent.prospective_eval") is not None, "benchmark runner is missing"
    return importlib.import_module("agent.prospective_eval")


def _result(*, method="assurance", params=None, error=None, clarification=""):
    spec = None if method is None else {
        "method": method, "parameters": params or {}, "sql": "",
        "schema_version": "1.0", "question": "synthetic", "population": "synthetic trial",
        "outcome": "", "predictors": [], "assumptions": ["review"], "exclusions": [],
        "data_source": "demo warehouse",
    }
    return SimpleNamespace(analysis_spec=spec, error=error, clarification=clarification, model=None)


def test_correct_proposal_passes_and_wrong_parameter_fails():
    run = evaluator()
    params = {"n_planned": 84, "tv": .36, "lrv": .21, "prior_a": 2, "prior_b": 3,
              "gate_tv": .85, "gate_lrv": .9, "stop_lrv": .1}
    case = {"id": "trial", "expect": "proposal", "method": "assurance", "parameters": params}
    assert run.score(case, _result(params=params))["passed"]
    failure = run.score(case, _result(params={**params, "tv": .21}))
    assert not failure["passed"] and failure["actual_parameters"]["tv"] == .21
    assert failure["expected_parameters"]["tv"] == .36
    assert not run.score(case, _result(params={**params, "prior_a": True}))["passed"]
    assert not run.score(case, _result(params={**params, "higher_is_better": "false"}))["passed"]


def test_missing_prior_must_be_refused_not_invented():
    run = evaluator()
    case = {"id": "missing_prior", "expect": "abstain", "method": "assurance", "reason": "prior"}
    params = {"n_planned": 84, "tv": .36, "lrv": .21,
              "gate_tv": .85, "gate_lrv": .9, "stop_lrv": .1}
    assert run.score(case, _result(params=params))["passed"]
    assert not run.score(case, _result(params={**params, "prior_a": 1, "prior_b": 1}))["passed"]
    assert not run.score(case, _result(method=None, error="network error"))["passed"]


def test_unsupported_method_requires_specific_refusal():
    run = evaluator()
    case = {"id": "unsupported", "expect": "unsupported", "reason": "competing"}
    assert run.score(case, _result(method=None, error="Competing-risk analysis is unsupported"))["passed"]
    assert not run.score(case, _result(method=None, error="network error"))["passed"]
    assert not run.score(case, _result(method="survival"))["passed"]


def test_case_file_is_fingerprinted_and_unknown_expectations_are_rejected(tmp_path):
    run = evaluator()
    data = tmp_path / "cases.json"
    data.write_text('{"version":"1.0","cases": []}')
    with pytest.raises(ValueError, match="fingerprint"):
        run.load_cases(data, "0" * 64)
    with pytest.raises(ValueError, match="expect"):
        run.score({"id": "bad", "expect": "unknown"}, _result())


def test_proposal_cannot_pass_for_a_different_question_or_data_source():
    run = evaluator()
    params = {"n_planned": 84, "tv": .36, "lrv": .21, "prior_a": 2, "prior_b": 3,
              "gate_tv": .85, "gate_lrv": .9, "stop_lrv": .1}
    case = {"id": "trial", "question": "expected question", "expect": "proposal",
            "method": "assurance", "parameters": params}
    result = _result(params=params)
    assert not run.score(case, result)["passed"]
    result.analysis_spec["question"] = "expected question"
    result.analysis_spec["data_source"] = "other data"
    assert not run.score(case, result)["passed"]
    result.analysis_spec["data_source"] = "demo warehouse"
    assert run.score(case, result)["passed"]


def test_aggregate_route_never_runs_an_analysis_query(monkeypatch):
    run = evaluator()
    from agent import agent, retrieval, vocabulary, warehouse

    monkeypatch.setattr(agent, "run_analysis", lambda *_a, **_kw: pytest.fail("analysis was executed"))
    monkeypatch.setattr(agent, "run_query", lambda *_a, **_kw: pytest.fail("generated SQL was executed"))
    monkeypatch.setattr(warehouse, "run_query", lambda *_a, **_kw: pytest.fail("query was executed"))
    monkeypatch.setattr(retrieval, "retrieve", lambda *_a, **_kw: {})
    monkeypatch.setattr(retrieval, "render_context", lambda *_a, **_kw: "synthetic context")
    monkeypatch.setattr(vocabulary, "resolve", lambda *_a, **_kw: SimpleNamespace(
        blocked=False, grounding_block=lambda: ""))
    monkeypatch.setattr(agent, "_route", lambda *_a, **_kw: {"mode": "aggregate"})
    result = run.propose("Calculate Bayesian assurance for a synthetic study.")
    assert result.analysis_spec is None and result.model is None


def test_null_direction_is_not_scored_as_a_correct_interim_proposal():
    run = evaluator()
    params = {"n_planned": 96, "tv": .33, "lrv": .19, "prior_a": 3, "prior_b": 2,
              "gate_tv": .82, "gate_lrv": .92, "stop_lrv": .08}
    case = {"id": "interim", "expect": "proposal", "method": "interim", "parameters": params}
    result = _result(method="interim", params={**params, "higher_is_better": None})
    result.analysis_spec.update(outcome="response", sql="select 1 as response")
    assert not run.score(case, result)["passed"]


def test_malformed_frozen_cases_are_rejected_before_model_calls(tmp_path):
    run = evaluator()
    data = tmp_path / "cases.json"
    data.write_text(json.dumps({"version": "1.0", "cases": [
        {"id": "bad", "question": "synthetic", "expect": "unknown"}]}))
    fingerprint = hashlib.sha256(data.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="expect"):
        run.load_cases(data, fingerprint)


def test_frozen_cases_cover_proposals_and_required_refusals():
    cases = evaluator().load_cases()["cases"]
    assert len(cases) == 8
    assert {case["expect"] for case in cases} == {"proposal", "abstain", "unsupported"}
    assert all(case["question"] for case in cases)


def test_failed_proposal_keeps_usage_and_resets_trace(monkeypatch):
    run = evaluator()
    from agent import llm

    reset = []
    monkeypatch.setattr(llm, "reset_trace", lambda: reset.append(True))
    monkeypatch.setattr(llm, "trace_summary", lambda: {"calls": 1, "prompt_tokens": 101,
                                                       "completion_tokens": 12})
    monkeypatch.setattr(run, "propose", lambda _question: (_ for _ in ()).throw(ValueError("invalid JSON")))
    case = {"id": "failure", "question": "synthetic", "expect": "proposal", "method": "assurance",
            "parameters": {}}
    row = run.evaluate_case(case)
    assert reset == [True]
    assert not row["passed"] and row["reason"] == "execution_error"
    assert row["usage"] == {"calls": 1, "prompt_tokens": 101, "completion_tokens": 12}
