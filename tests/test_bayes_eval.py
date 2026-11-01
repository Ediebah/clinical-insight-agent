"""Label integrity for the Bayesian numeric oracle (no API key needed).

These tests check that the reference runs and remains consistent with the case labels. Because
the reference calls the same modeling implementation, label consistency does not independently
validate the calculations. Comparing the agent with the reference needs an API key.
"""
import pandas as pd
import pytest

from agent import bayes_eval
from agent.agent import _MODEL_HINT
from agent.eval_dataset import BAYES


@pytest.mark.parametrize("case", BAYES, ids=lambda c: c.id)
def test_reference_computes_without_error(case):
    assert bayes_eval.reference(case).error is None


@pytest.mark.parametrize("case", BAYES, ids=lambda c: c.id)
def test_reference_reproduces_the_labelled_verdict(case):
    """The expected_call in the dataset must be what bayes.py actually returns for those params.
    Guards against a label drifting away from the maths it claims to describe."""
    assert bayes_eval.reference(case).as_dict()["verdict"]["call"] == case.expected_call


@pytest.mark.parametrize("case", BAYES, ids=lambda c: c.id)
def test_reference_carries_the_metric_being_compared(case):
    """A missing metric key would make the numeric comparison silently vacuous."""
    v = bayes_eval.reference(case).as_dict()["verdict"]
    assert case.metric in v and isinstance(v[case.metric], (int, float))


@pytest.mark.parametrize("case", BAYES, ids=lambda c: c.id)
def test_every_bayes_question_reaches_the_router(case):
    """Same gate contract as ROUTES: a question _MODEL_HINT blocks never reaches _route, so the
    oracle would be scoring a path the app cannot take."""
    assert _MODEL_HINT.search(case.question), case.question


def test_the_dataset_spans_all_three_calls():
    """A suite that only ever expects GO cannot detect a router stuck on GO. STOP matters most —
    it is the futility signal that actually stops a trial."""
    assert {c.expected_call for c in BAYES} == {"GO", "CONSIDER", "STOP"}


def test_the_dataset_covers_design_and_interim_in_both_framings():
    assert {c.fn for c in BAYES} == {"assurance", "interim"}
    framings = {c.params.get("framing", "single_arm") for c in BAYES}
    assert framings == {"single_arm", "two_arm"}


def test_interim_df_single_arm_matches_the_stated_counts():
    df = bayes_eval._interim_df({"successes": 12, "n_observed": 40})
    assert len(df) == 40 and int(df["responded"].sum()) == 12


def test_interim_df_two_arm_matches_both_arms():
    df = bayes_eval._interim_df({"t_successes": 18, "t_n": 40, "c_successes": 10, "c_n": 38})
    assert len(df) == 78
    by_arm = df.groupby("arm")["responded"].agg(["sum", "count"])
    assert (by_arm.loc["treatment", "sum"], by_arm.loc["treatment", "count"]) == (18, 40)
    assert (by_arm.loc["control", "sum"], by_arm.loc["control", "count"]) == (10, 38)


def test_interim_df_is_the_shape_fit_interim_expects():
    """One row per subject, never an aggregate — the router prompt is explicit about this, and an
    aggregate row would silently change the posterior."""
    df = bayes_eval._interim_df({"successes": 3, "n_observed": 30})
    assert list(df.columns) == ["responded"]
    assert set(df["responded"].unique()) <= {0, 1}
    assert pd.api.types.is_integer_dtype(df["responded"])


def test_failed_case_diagnostic_reports_only_relevant_extracted_parameters():
    from types import SimpleNamespace

    case = next(c for c in BAYES if c.id == "bo_interim_consider")
    result = SimpleNamespace(analysis_spec={"parameters": {
        "n_planned": 100, "tv": 0.30, "lrv": 0.15, "prior_a": 12, "prior_b": 1,
        "unrelated_model_text": "do not include this",
    }})
    info = bayes_eval.extraction_diagnostics(case, result)
    assert info["expected"]["prior_a"] == 1.0
    assert info["extracted"]["prior_a"] == 12
    assert "unrelated_model_text" not in info["extracted"]
