"""Smoke test: the Streamlit app renders end-to-end without an exception (no API key needed).

app.py is the deployed surface, but nothing else imports it — without this test a syntax error or a
broken import in app.py ships green (all unit tests pass, CI import-smoke covers only agent.*).
AppTest executes the real script against the committed demo warehouse in Streamlit's test harness.
"""
from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.title or at.markdown or at.tabs        # something actually rendered


def test_reproduction_protocol_lock_runs_confirmed_design(monkeypatch):
    from agent import reproduction

    parsed = {
        "publication_title": "Chen et al. (2019)",
        "doi": "10.21037/tcr.2019.05.17",
        "endpoint_type": "single_arm_binary",
        "observed_successes": 8,
        "observed_n": 25,
        "planned_n": 50,
        "prior_a": 1,
        "prior_b": 1,
        "efficacy_reference": 0.30,
        "efficacy_gate": 0.95,
        "futility_cutoff": 0.20,
        "published_predictive_probability": 0.105,
        "published_final_boundary": 21,
        "published_decision": "STOP",
        "missing_fields": [],
    }
    monkeypatch.setattr(reproduction, "parse_published_design", lambda _text: parsed.copy())

    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.segmented_control[0].set_value("🧾 Reproduce").run()
    at.button(key="repro_load_example").click().run()
    at.button(key="repro_parse").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.text_input(key="repro_gate").value == "0.95"
    assert at.text_input(key="repro_futility").value == "0.2"

    at.checkbox(key="repro_confirm").check()
    at.button(key="FormSubmitter:repro_lock_form-Confirm protocol lock and reproduce").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("MATCH" in str(item.value) for item in at.markdown)
    assert any("Protocol lock · confirmed inputs" in str(item.value) for item in at.markdown)
    assert any("comparison-table" in str(item.value) for item in at.markdown)
