"""Research workflow must be usable without an LLM and must not export source records."""
import json

import pandas as pd
import pytest

from agent import research


def _spec():
    return {"schema_version": "1.0", "question": "Association?", "population": "all rows",
            "outcome": "y", "predictors": ["x"], "method": "association",
            "assumptions": ["independent observations"], "exclusions": [],
            "data_source": "in-memory dataframe", "sql": "", "parameters": {"var_a": "x", "var_b": "y"}}


def test_direct_analysis_requires_explicit_approval():
    frame = pd.DataFrame({"x": range(20), "y": range(20)})
    with pytest.raises(ValueError, match="approv"):
        research.run_spec(_spec(), frame)
    result = research.run_spec(_spec(), frame, approved=True)
    assert result.error is None


@pytest.mark.parametrize("field,value", [("sql", "select * from t where x > 0"),
                                         ("population", "only x > 0"), ("exclusions", ["x < 0"])])
def test_direct_analysis_rejects_unapplied_cohort_restrictions(field, value):
    frame = pd.DataFrame({"x": range(20), "y": range(20)})
    spec = _spec()
    spec[field] = value
    with pytest.raises(ValueError, match="cohort|SQL|exclusion"):
        research.run_spec(spec, frame, approved=True)


def test_direct_analysis_requires_matching_source_identity():
    spec = _spec()
    spec["data_source"] = "different.csv"
    with pytest.raises(ValueError, match="source"):
        research.run_spec(spec, pd.DataFrame({"x": [1, 2], "y": [2, 3]}), approved=True)


def test_bundle_omits_dataframe_and_authentication_fields():
    frame = pd.DataFrame({"x": range(20), "y": range(20), "private_record": ["secret"] * 20})
    spec = _spec()
    result = research.run_spec(spec, frame, approved=True)
    bundle = research.make_bundle(spec, result.as_dict(), frame=frame)
    encoded = json.dumps(bundle, allow_nan=False)
    assert "private_record" not in encoded and '"secret"' not in encoded
    assert bundle["specification"] == spec
    assert bundle["data_fingerprint"]["sha256"]
    assert research.verify_bundle(bundle)
    bundle["result"]["n"] += 1
    assert not research.verify_bundle(bundle)


def test_bundle_discards_unexpected_record_and_secret_fields():
    result = {"model_type": "association", "n": 2, "rows": [{"name": "Alice"}],
              "api_key": "secret-value", "issues": []}
    bundle = research.make_bundle(_spec(), result)
    encoded = json.dumps(bundle)
    assert "Alice" not in encoded and "secret-value" not in encoded


def test_bundle_rejects_obvious_secrets_in_free_text():
    spec = _spec()
    spec["sql"] = "select * from t where api_key='supersecret'"
    with pytest.raises(ValueError, match="secret"):
        research.make_bundle(spec, {"n": 1})


def test_bundle_rejects_raw_record_fields_in_specification():
    spec = _spec()
    spec["parameters"]["records"] = [{"name": "Alice"}]
    with pytest.raises(ValueError, match="record"):
        research.make_bundle(spec, {"n": 1})


def test_bundle_excludes_time_series_history():
    result = {"model_type": "timeseries", "series": [
        {"kind": "history", "value": 123456789}, {"kind": "forecast", "value": 4}]}
    bundle = research.make_bundle(_spec(), result)
    assert "123456789" not in json.dumps(bundle)
    assert bundle["result"]["series"] == [{"kind": "forecast", "value": 4}]


def test_survival_spec_has_one_canonical_event():
    from agent import research
    spec = research.from_route("Survival?", {"model_type": "survival", "event": "death",
                                               "duration": "time", "predictors": ["age"]}, "demo")
    assert spec["outcome"] == "death" and "event" not in spec["parameters"]
    spec["parameters"]["event"] = "other"
    with pytest.raises(ValueError, match="event"):
        research.validate_spec(spec)


def test_spec_rejects_missing_details_and_unknown_method():
    spec = _spec()
    spec["method"] = "competing_risks"
    with pytest.raises(ValueError, match="unsupported"):
        research.validate_spec(spec)
    del spec["population"]
    with pytest.raises(ValueError, match="population"):
        research.validate_spec(spec)


def test_dataframe_adapter_returns_isolated_data():
    source = pd.DataFrame({"x": [1, 2]})
    adapter = research.DataFrameAdapter(source)
    result = adapter.read()
    result.loc[0, "x"] = 99
    assert source.loc[0, "x"] == 1


def test_duckdb_adapter_reads_and_refuses_truncation(tmp_path):
    import duckdb
    path = tmp_path / "source.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute("create table observations as select * from range(5)")
    conn.close()
    adapter = research.DuckDBAdapter(path, "select * from observations", max_rows=5)
    assert len(adapter.read()) == 5
    with pytest.raises(ValueError, match="truncated"):
        research.DuckDBAdapter(path, "select * from observations", max_rows=4).read()


def test_proposed_spec_must_be_approved_before_model_execution(monkeypatch):
    from agent import agent

    class Vocabulary:
        blocked = False
        def grounding_block(self):
            return ""

    route = {"model_type": "logistic", "outcome": "y", "predictors": ["x"],
             "analytic_sql": "select y, x from data", "hypothesis": "explore"}
    monkeypatch.setattr(agent.retrieval, "retrieve", lambda *a, **k: {"all_table_names": []})
    monkeypatch.setattr(agent.retrieval, "render_context", lambda *a: "")
    monkeypatch.setattr(agent.vocabulary, "resolve", lambda *a, **k: Vocabulary())
    monkeypatch.setattr(agent.lineage, "detect", lambda *a: None)
    monkeypatch.setattr(agent, "_route", lambda *a: route.copy())
    calls = []
    monkeypatch.setattr(agent, "_run_model", lambda *a, **k: calls.append(a[2]) or a[3])
    proposed = agent.run_analysis("What predicts y?", catalog={})
    assert proposed.analysis_spec and calls == []
    approved = dict(proposed.analysis_spec)
    approved["outcome"] = "edited_y"
    agent.run_analysis("What predicts y?", catalog={}, approved_spec=approved)
    assert calls and calls[0]["outcome"] == "edited_y"


@pytest.mark.parametrize("route_type", ["compare", "compare_models", "rsf", "unsupported_model"])
def test_router_alias_or_unknown_method_cannot_bypass_review(monkeypatch, route_type):
    from agent import agent
    class Vocabulary:
        blocked = False
        def grounding_block(self):
            return ""
    monkeypatch.setattr(agent.retrieval, "retrieve", lambda *a, **k: {"all_table_names": []})
    monkeypatch.setattr(agent.retrieval, "render_context", lambda *a: "")
    monkeypatch.setattr(agent.vocabulary, "resolve", lambda *a, **k: Vocabulary())
    monkeypatch.setattr(agent.lineage, "detect", lambda *a: None)
    monkeypatch.setattr(agent, "_route", lambda *a: {"model_type": route_type, "analytic_sql": "select 1"})
    monkeypatch.setattr(agent, "_run_model", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fit")))
    result = agent.run_analysis("What predicts y?", catalog={})
    assert result.analysis_spec or (result.error and "unsupported" in result.error.lower())


def test_approved_model_without_query_is_refused_instead_of_falling_back(monkeypatch):
    from agent import agent
    class Vocabulary:
        blocked = False
        def grounding_block(self):
            return ""
    monkeypatch.setattr(agent.retrieval, "retrieve", lambda *a, **k: {"all_table_names": []})
    monkeypatch.setattr(agent.retrieval, "render_context", lambda *a: "")
    monkeypatch.setattr(agent.vocabulary, "resolve", lambda *a, **k: Vocabulary())
    monkeypatch.setattr(agent.lineage, "detect", lambda *a: None)
    monkeypatch.setattr(agent, "_triage", lambda *a: (_ for _ in ()).throw(AssertionError("fallback")))
    spec = _spec()
    spec.update(question="What predicts y?", data_source="uploaded dataset", method="logistic")
    result = agent.run_analysis(spec["question"], catalog={}, approved_spec=spec)
    assert result.error and "query" in result.error.lower()


def test_reviewed_query_failure_is_not_rewritten(monkeypatch):
    from agent import agent
    def fail(*args, **kwargs):
        raise agent.QueryError("invalid query")
    monkeypatch.setattr(agent, "run_query", fail)
    monkeypatch.setattr(agent, "_fix_sql", lambda *a: (_ for _ in ()).throw(AssertionError("rewritten")))
    spec = {"model_type": "logistic", "analytic_sql": "select missing from t"}
    result = agent._run_model("q", "", spec, agent.AgentResult(question="q"), [], reviewed=True)
    assert "invalid query" in result.error
    assert result.sql == "select missing from t"


def test_app_shows_editable_spec_before_approval(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from agent import agent
    calls = []
    def fake_run(question, **kwargs):
        calls.append(kwargs.get("approved_spec"))
        return agent.AgentResult(question=question, analysis_spec=_spec())
    monkeypatch.setattr(agent, "run_analysis", fake_run)
    app = AppTest.from_file("app.py", default_timeout=120).run()
    app.segmented_control[0].set_value("🔬 Analyze").run()
    app.text_input(key="question").set_value("Association?")
    next(button for button in app.button if "Run analysis" in button.label).click().run()
    assert calls == [None]
    assert app.text_area(key="analysis_spec_editor")
    assert app.button(key="approve_analysis_spec")
    app.button(key="approve_analysis_spec").click().run()
    assert calls[1] == _spec()


def test_app_displays_clarification_after_approval(monkeypatch):
    from streamlit.testing.v1 import AppTest

    from agent import agent
    def fake_run(question, **kwargs):
        return agent.AgentResult(question=question, analysis_spec=_spec(),
                                 clarification="Explicit decision thresholds required" if kwargs.get(
                                     "approved_spec") else "")
    monkeypatch.setattr(agent, "run_analysis", fake_run)
    app = AppTest.from_file("app.py", default_timeout=120).run()
    app.segmented_control[0].set_value("🔬 Analyze").run()
    app.text_input(key="question").set_value("Association?")
    next(button for button in app.button if "Run analysis" in button.label).click().run()
    app.button(key="approve_analysis_spec").click().run()
    assert any("thresholds required" in str(item.value) for item in app.warning)
