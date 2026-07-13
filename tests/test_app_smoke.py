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
