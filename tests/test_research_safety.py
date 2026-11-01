"""Regression tests for research-use boundaries."""
import pandas as pd

from agent import agent, modeling, research


def test_truncated_cohort_is_not_fit(monkeypatch):
    frame = pd.DataFrame({"outcome": [0, 1], "x": [1, 2]})
    frame.attrs["truncated"] = True
    monkeypatch.setattr(agent, "run_query", lambda *args, **kwargs: frame)
    monkeypatch.setattr(agent, "_fit_model", lambda *args: (_ for _ in ()).throw(AssertionError("fit")))
    result = agent._run_model("q", "", {"model_type": "logistic", "analytic_sql": "select 1"},
                              agent.AgentResult(question="q"), [])
    assert "truncated" in result.error.lower()


def test_competing_risks_are_refused_before_llm_or_database(monkeypatch):
    monkeypatch.setattr(agent.retrieval, "retrieve", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("should refuse before retrieval")))
    result = agent.run_analysis("Estimate readmission accounting for death as a competing risk")
    assert "competing" in (result.error or result.clarification).lower()


def test_interim_does_not_default_decision_thresholds():
    df = pd.DataFrame({"response": [0, 1] * 10})
    result = agent._fit_model({"model_type": "interim", "outcome": "response", "n_planned": 40,
                               "tv": .3, "lrv": .2}, df)
    assert result.error and "threshold" in result.error.lower()


def test_direct_bayesian_entry_points_require_prior_and_gates():
    result = modeling.calc_assurance(n_planned=20, tv=.4, lrv=.3, prior_a=1, prior_b=1)
    assert result.error and "threshold" in result.error.lower()
    result = modeling.fit_interim(pd.DataFrame({"response": [0, 1]}), "response",
                                  n_planned=20, tv=.4, lrv=.3,
                                  gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error and "prior" in result.error.lower()


def test_two_arm_design_requires_explicit_control_prior():
    result = modeling.calc_assurance(framing="two_arm", n_planned=20, tv=.2, lrv=0,
                                    control_rate=.3, prior_a=2, prior_b=2,
                                    gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error and "control prior" in result.error.lower()


def test_two_arm_design_records_control_prior_in_lock():
    result = modeling.calc_assurance(framing="two_arm", n_planned=20, tv=.2, lrv=0,
                                    control_rate=.3, prior_a=2, prior_b=2,
                                    control_prior_a=2, control_prior_b=3,
                                    gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error is None
    assert result.prespec["lock"]["params"]["control_prior_a"] == 2
    assert result.prespec["lock"]["params"]["control_prior_b"] == 3


def test_direct_two_arm_interim_requires_a_named_control_arm():
    frame = pd.DataFrame({"arm": ["A", "B"] * 5, "response": [0, 1] * 5})
    result = modeling.fit_interim(frame, "response", framing="two_arm", group="arm",
                                  n_planned=20, tv=.2, lrv=0, prior_a=1, prior_b=1,
                                  control_prior_a=1, control_prior_b=1,
                                  gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error and "control" in result.error.lower()


def test_two_arm_interim_uses_the_separately_specified_control_prior():
    frame = pd.DataFrame({"arm": ["treatment"] * 4 + ["control"] * 4,
                          "response": [1, 1, 0, 0, 1, 0, 0, 0]})
    result = modeling.fit_interim(frame, "response", framing="two_arm", group="arm", control="control",
                                  n_planned=20, tv=.2, lrv=0, prior_a=1, prior_b=1,
                                  control_prior_a=4, control_prior_b=2,
                                  gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error is None
    # Treatment Beta(3,3) and control Beta(5,5) both have posterior mean 0.5.
    assert abs(result.terms[0].estimate) < 1e-12


def test_unknown_bayesian_framing_is_refused():
    result = modeling.calc_assurance(framing="competing_risk", n_planned=20, tv=.4, lrv=.3,
                                    prior_a=1, prior_b=1, gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error and "framing" in result.error.lower()


def test_small_cohort_does_not_mask_invalid_interim_parameters(monkeypatch):
    frame = pd.DataFrame({"response": [0, 1] * 10})
    monkeypatch.setattr(agent, "run_query", lambda *a, **k: frame)
    spec = {"model_type": "interim", "outcome": "response", "n_planned": 40, "tv": .3, "lrv": .2,
            "analytic_sql": "select response from data"}
    result = agent._run_model("q", "", spec, agent.AgentResult(question="q"), [])
    assert "threshold" in result.interpretation.lower()


def test_two_arm_interim_does_not_ignore_previous_study_prior():
    frame = pd.DataFrame({"arm": ["treatment", "control"] * 10, "response": [0, 1, 1, 0] * 5})
    spec = {"model_type": "interim", "framing": "two_arm", "outcome": "response", "group": "arm",
            "control": "control", "n_planned": 40, "tv": .3, "lrv": .2, "gate_tv": .8,
            "gate_lrv": .9, "stop_lrv": .1, "prior_successes": 4, "prior_n": 10}
    result = agent._fit_model(spec, frame)
    assert result.error and "prior" in result.error.lower()


def test_two_arm_interim_rejects_odd_planned_total():
    frame = pd.DataFrame({"arm": ["treatment", "control"] * 10, "response": [0, 1, 1, 0] * 5})
    spec = {"model_type": "interim", "framing": "two_arm", "outcome": "response", "group": "arm",
            "control": "control", "n_planned": 41, "tv": .3, "lrv": .2, "gate_tv": .8,
            "gate_lrv": .9, "stop_lrv": .1, "prior_a": 1, "prior_b": 1,
            "control_prior_a": 1, "control_prior_b": 1}
    result = agent._fit_model(spec, frame)
    assert result.error and "even" in result.error.lower()


def test_proposed_bayesian_inputs_do_not_keep_unstated_numbers():
    question = "Assess a 50 participant study with a 30% target."
    route = {"model_type": "assurance", "n_planned": 50, "tv": .3, "lrv": "0.15",
             "gate_tv": .8, "gate_lrv": .9, "stop_lrv": .1, "prior_a": 1, "prior_b": 1}
    spec = research.from_route(question, route, "demo warehouse")
    assert spec["parameters"]["n_planned"] == 50
    assert spec["parameters"]["tv"] == .3
    assert spec["parameters"]["lrv"] is None
    assert spec["parameters"]["gate_tv"] is None
    assert spec["parameters"]["prior_a"] is None


def test_bayesian_prior_family_matches_endpoint():
    import pytest
    base = {"gate_tv": .8, "gate_lrv": .9, "stop_lrv": .1}
    with pytest.raises(ValueError, match="prior"):
        research.require_bayesian_inputs({**base, "endpoint_type": "proportion", "prior_mu": 0, "prior_sd": 1})
    with pytest.raises(ValueError, match="prior"):
        research.require_bayesian_inputs({**base, "endpoint_type": "mean", "prior_a": 1, "prior_b": 1})
    with pytest.raises(ValueError, match="prior"):
        research.require_bayesian_inputs({**base, "prior_a": 1, "prior_b": 1,
                                          "prior_successes": 3, "prior_n": 10})


def test_bayesian_thresholds_and_priors_are_valid():
    import pytest
    base = {"gate_tv": .8, "gate_lrv": .9, "stop_lrv": .1, "prior_a": 1, "prior_b": 1}
    for bad in ({"gate_tv": 1.5}, {"gate_lrv": -0.1}, {"stop_lrv": float("nan")}, {"prior_a": 0}):
        with pytest.raises(ValueError):
            research.require_bayesian_inputs({**base, **bad})
    for bad in ({"tv": float("nan")}, {"lrv": float("inf")}, {"n_planned": 20.5}):
        with pytest.raises(ValueError):
            research.require_bayesian_inputs({**base, **bad})


def test_bayesian_direct_model_rejects_invalid_threshold_and_prior_family():
    from agent import modeling
    result = modeling.calc_assurance(n_planned=20, tv=.4, lrv=.3, gate_tv=1.5, gate_lrv=.9, stop_lrv=.1,
                                    prior_a=1, prior_b=1)
    assert result.error and "gate_tv" in result.error
    result = modeling.calc_assurance(n_planned=20, tv=.4, lrv=.3, endpoint_type="proportion",
                                    prior_mu=0, prior_sd=1, gate_tv=.8, gate_lrv=.9, stop_lrv=.1)
    assert result.error and "prior" in result.error.lower()


def test_large_causal_cohort_is_not_sampled_without_approval():
    frame = pd.DataFrame({"t": [0, 1] * 10001, "y": [0, 1, 1, 0] * 5000 + [0, 1]})
    result = agent.modeling.fit_uplift(frame, "y", "t")
    assert result.error and "sampl" in result.error.lower()


def test_approved_analysis_refuses_truncated_upload(monkeypatch):
    monkeypatch.setattr(agent.retrieval, "retrieve", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("truncated upload reached retrieval")))
    result = agent.run_analysis("What predicts y?", approved_spec={"method": "logistic"}, input_truncated=True)
    assert result.error and "truncat" in result.error.lower()


def test_beta_shape_parameters_are_not_mistaken_for_study_counts():
    question = ("40 patients had 12 responses. Use a Beta(1,1) prior, with target 30% and "
                "reference 15%; gates 0.80, 0.90, 0.10.")
    route = {"model_type": "interim", "n_planned": 100, "tv": .3, "lrv": .15,
             "prior_successes": 1, "prior_n": 1, "gate_tv": .8, "gate_lrv": .9,
             "stop_lrv": .1}
    params = research.from_route(question, route, "demo warehouse")["parameters"]
    assert params["prior_successes"] is None and params["prior_n"] is None
    import pytest
    with pytest.raises(ValueError, match="prior"):
        research.require_bayesian_inputs(params)


def test_percentage_point_targets_can_be_verified_from_question():
    question = "Assess a 15-point benefit against a 0 percentage point minimum."
    route = {"model_type": "assurance", "tv": .15, "lrv": 0.0}
    params = research.from_route(question, route, "demo warehouse")["parameters"]
    assert params["tv"] == .15 and params["lrv"] == 0.0


def test_control_beta_does_not_discard_different_prior_study_counts():
    question = "Prior work had 14 responses in 20 patients. Use a Beta(1,1) control prior."
    route = {"model_type": "assurance", "framing": "two_arm", "prior_successes": 14,
             "prior_n": 20, "control_prior_a": 1, "control_prior_b": 1}
    params = research.from_route(question, route, "demo warehouse")["parameters"]
    assert (params["prior_successes"], params["prior_n"]) == (14, 20)


def test_explicit_control_beta_is_attributed_without_losing_treatment_counts():
    question = ("A treatment pilot had 8 responses in 24 patients; use Beta(3,4) as the control analysis prior. "
                "Set target, minimum and stop gates to 0.8, 0.9 and 0.1.")
    route = {"model_type": "assurance", "framing": "two_arm", "prior_successes": 8, "prior_n": 24,
             "prior_a": 3, "prior_b": 4, "control_prior_a": None, "control_prior_b": None,
             "gate_tv": .8, "gate_lrv": .9, "stop_lrv": .1}
    spec = research.from_route(question, route, "demo warehouse")
    params = spec["parameters"]
    assert (params["control_prior_a"], params["control_prior_b"]) == (3, 4)
    assert (params["prior_a"], params["prior_b"]) == (None, None)
    assert (params["prior_successes"], params["prior_n"]) == (8, 24)
    assert any("control prior" in item.lower() and "review" in item.lower() for item in spec["assumptions"])
    assert any("beta(1,1)" in item.lower() and "pilot" in item.lower() for item in spec["assumptions"])
    research.require_bayesian_inputs(params)


def test_ambiguous_or_conflicting_control_beta_is_not_automatically_reassigned():
    base = ("A treatment pilot had 8 responses in 24 patients; use Beta(3,4) as the control analysis prior.")
    route = {"model_type": "assurance", "framing": "two_arm", "prior_successes": 8, "prior_n": 24,
             "prior_a": 3, "prior_b": 4, "control_prior_a": None, "control_prior_b": None}
    examples = [
        (base.replace("use Beta", "do not use Beta"), route),
        (base.replace("A treatment pilot had", "No treatment pilot had"), route),
        (base.replace("patients;", "patients, but do not use those counts;"), route),
        (base + " Use Beta(2,2) as the treatment prior.", route),
        (base, {**route, "control_prior_a": 4, "control_prior_b": 4}),
        (base, {**route, "prior_successes": 24, "prior_n": 24}),
    ]
    for question, candidate in examples:
        spec = research.from_route(question, candidate, "demo warehouse")
        assert (spec["parameters"]["prior_a"], spec["parameters"]["prior_b"]) == (3, 4)
        assert not any("automatically attributed" in item.lower() for item in spec["assumptions"])


def test_matching_pilot_counts_and_beta_shapes_are_not_automatically_reassigned():
    question = "A treatment pilot had 3 responses in 4 patients; use Beta(3,4) as the control analysis prior."
    route = {"model_type": "assurance", "framing": "two_arm", "prior_successes": 3, "prior_n": 4,
             "prior_a": 3, "prior_b": 4, "control_prior_a": None, "control_prior_b": None}
    spec = research.from_route(question, route, "demo warehouse")
    assert (spec["parameters"]["prior_a"], spec["parameters"]["prior_b"]) == (3, 4)
    assert spec["parameters"]["control_prior_a"] is None
    assert not any("automatically attributed" in item.lower() for item in spec["assumptions"])


def test_bayesian_direction_must_be_boolean_when_supplied():
    frame = pd.DataFrame({"response": [1, 0] * 8})
    params = {"n_planned": 40, "tv": .3, "lrv": .15, "gate_tv": .8, "gate_lrv": .9,
              "stop_lrv": .1, "prior_a": 1, "prior_b": 1}
    for invalid in (None, "false", 0, 1):
        design = modeling.calc_assurance(**params, higher_is_better=invalid)
        interim = modeling.fit_interim(frame, "response", **params, higher_is_better=invalid)
        assert design.error and "higher_is_better" in design.error
        assert interim.error and "higher_is_better" in interim.error


def test_interim_spec_rejects_null_outcome_direction():
    frame = pd.DataFrame({"response": [1, 0] * 8})
    spec = {"model_type": "interim", "outcome": "response", "n_planned": 40, "tv": .3,
            "lrv": .15, "gate_tv": .8, "gate_lrv": .9, "stop_lrv": .1,
            "prior_a": 1, "prior_b": 1, "higher_is_better": None}
    result = agent._fit_model(spec, frame)
    assert result.error and "higher_is_better" in result.error
