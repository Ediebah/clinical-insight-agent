"""De-identification wrapper. openmed is mocked throughout: CI must never download a model.

The mocks mirror the REAL API, verified by installing the package and calling it:
`OnnxModel.from_pretrained(...)` returns a callable, and calling it yields objects with
`label`, `score`, `start`, `end`, `text` — character offsets, lowercase snake_case labels.
`openmed.deidentify()` is deliberately not used: it requires transformers, which pulls torch.
"""
import sys
import types

import pytest

from agent import deid


@pytest.fixture(autouse=True)
def _reset_model_cache():
    """The real OnnxModel takes ~12s to load, so deid caches it module-level. Reset per test."""
    deid._MODEL = None
    deid._LOAD_FAILED = False
    yield
    deid._MODEL = None
    deid._LOAD_FAILED = False


def _fake_model(spans_by_text):
    """Stand-in for a loaded OnnxModel: callable, returning objects with the real OnnxEntity
    fields (label, score, start, end, text). spans_by_text maps text -> [(label, start, end)]."""
    def _call(text):
        return [types.SimpleNamespace(label=label, score=0.99, start=s, end=e, text=text[s:e])
                for label, s, e in spans_by_text.get(text, [])]
    return _call


def test_available_is_false_when_openmed_is_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.available() is False


def test_available_never_raises_when_the_model_fails_to_load(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("no network")
    monkeypatch.setattr(deid, "_load_model", boom)
    assert deid.available() is False


def test_a_failed_load_is_not_retried(monkeypatch):
    """A 12s load that failed must not be re-attempted on every value in a 60-column scan."""
    calls = []

    def boom(*_a, **_k):
        calls.append(1)
        raise OSError("no network")
    monkeypatch.setattr(deid, "_load_model", boom)
    deid.available()
    deid.available()
    deid.available()
    assert len(calls) == 1


def test_scrub_values_masks_detected_spans_by_offset(monkeypatch):
    monkeypatch.setattr(deid, "_load_model",
                        lambda: _fake_model({"John Doe is 42": [("first_name", 0, 4)]}))
    assert deid.scrub_values(["John Doe is 42"]) == ["[REDACTED] Doe is 42"]


def test_scrub_values_masks_multiple_spans_right_to_left(monkeypatch):
    """Offsets are applied in reverse so earlier replacements can't shift later ones."""
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"John saw Jane": [("first_name", 0, 4), ("first_name", 9, 13)]}))
    assert deid.scrub_values(["John saw Jane"]) == ["[REDACTED] saw [REDACTED]"]


def test_scrub_values_returns_input_unchanged_when_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.scrub_values(["John Doe"]) == ["John Doe"]


def test_scrub_values_ignores_low_confidence_spans(monkeypatch):
    def _low(text):
        return [types.SimpleNamespace(label="city", score=0.1, start=0, end=4, text="Mass")]
    monkeypatch.setattr(deid, "_load_model", lambda: _low)
    assert deid.scrub_values(["Mass General"]) == ["Mass General"]
