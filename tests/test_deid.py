"""De-identification wrapper. openmed is mocked throughout: CI must never download a model.

The mocks mirror the REAL API, verified by installing the package and calling it:
`OnnxModel.from_pretrained(...)` returns a callable, and calling it yields objects with
`label`, `score`, `start`, `end`, `text` — character offsets, lowercase snake_case labels.
`openmed.deidentify()` is deliberately not used: it requires transformers, which pulls torch.
"""
import sys
import types

import pandas as pd
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


# ── column scanning and decisions ───────────────────────────────────────────────────────────────

_NAMES = {"John Doe": [("first_name", 0, 8)], "Jane Roe": [("first_name", 0, 8)]}


def test_scan_flags_an_identifying_column_and_ignores_a_numeric_one(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    df = pd.DataFrame({"patient": ["John Doe", "Jane Roe"], "age": [41, 52]})
    findings = deid.scan_columns(df)
    assert [f.column for f in findings] == ["patient"]
    assert findings[0].entity_types == ["first_name"]     # lowercase snake_case, per the real model
    assert findings[0].hit_rate == 1.0


def test_scan_suggests_drop_at_high_hit_rate_and_mask_below(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    high = pd.DataFrame({"name": ["John Doe", "Jane Roe"]})
    low = pd.DataFrame({"notes": ["John Doe", "seen in clinic", "no issues", "stable"]})
    assert deid.scan_columns(high)[0].suggested == "drop"
    assert deid.scan_columns(low)[0].suggested == "mask"


def test_scan_examples_never_contain_the_raw_identifier(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    finding = deid.scan_columns(pd.DataFrame({"patient": ["John Doe"]}))[0]
    assert all("John Doe" not in e for e in finding.examples)


def test_scan_returns_nothing_when_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.scan_columns(pd.DataFrame({"patient": ["John Doe"]})) == []


def test_apply_decisions_drops_and_masks_exactly_the_named_columns(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    df = pd.DataFrame({"a": ["John Doe"], "b": ["John Doe"], "c": [7]})
    out = deid.apply_decisions(df, drop=["a"], mask=["b"])
    assert list(out.columns) == ["b", "c"]
    assert out["b"].iloc[0] == "[REDACTED]"
    assert out["c"].iloc[0] == 7


def test_scrub_frame_touches_only_the_named_columns(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    df = pd.DataFrame({"keep": ["John Doe"], "other": ["John Doe"]})
    out = deid.scrub_frame(df, ["keep"])
    assert out["keep"].iloc[0] == "[REDACTED]"
    assert out["other"].iloc[0] == "John Doe"


def test_scrub_frame_is_a_noop_for_an_empty_column_list(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model({}))
    df = pd.DataFrame({"a": ["x"]})
    assert deid.scrub_frame(df, []) is df


# ── span merging and quasi-identifiers (found by running the real model) ────────────────────────

def test_adjacent_spans_merge_into_one_redaction(monkeypatch):
    """The real model returns first_name and last_name as separate adjacent spans, which produced
    '[REDACTED][REDACTED]' for 'John Doe'."""
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"John Doe": [("first_name", 0, 4), ("last_name", 4, 8)]}))
    assert deid.scrub_values(["John Doe"]) == ["[REDACTED]"]


def test_overlapping_spans_merge_without_leaving_fragments(monkeypatch):
    """Overlapping spans produced '[REDACTED]RN[REDACTED]' — a fragment of the identifier left
    in the clear. Merged spans must cover the whole run."""
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"MRN 123456": [("medical_record_number", 0, 3), ("biometric_identifier", 2, 10)]}))
    assert deid.scrub_values(["MRN 123456"]) == ["[REDACTED]"]


def test_separated_spans_do_not_merge(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"John saw Jane": [("first_name", 0, 4), ("first_name", 9, 13)]}))
    assert deid.scrub_values(["John saw Jane"]) == ["[REDACTED] saw [REDACTED]"]


def test_age_is_a_quasi_identifier_and_defaults_to_keep(monkeypatch):
    """age is a HIPAA identifier only above 89, and it is the most common covariate in the
    modeling suite. Defaulting it to drop would gut the analysis the feature protects."""
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"41": [("age", 0, 2)], "52": [("age", 0, 2)]}))
    finding = deid.scan_columns(pd.DataFrame({"age": ["41", "52"]}))[0]
    assert finding.severity == "quasi"
    assert finding.suggested == "keep"          # NOT "drop", despite a 100% hit rate


def test_a_direct_identifier_at_high_hit_rate_still_suggests_drop(monkeypatch):
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(_NAMES))
    finding = deid.scan_columns(pd.DataFrame({"patient": ["John Doe", "Jane Roe"]}))[0]
    assert finding.severity == "direct"
    assert finding.suggested == "drop"


def test_a_mixed_column_is_direct_when_any_label_is_direct(monkeypatch):
    """A notes column holding both an age and a name must not be softened to quasi."""
    monkeypatch.setattr(deid, "_load_model", lambda: _fake_model(
        {"aged 41, John Doe": [("age", 5, 7), ("first_name", 9, 13)]}))
    finding = deid.scan_columns(pd.DataFrame({"notes": ["aged 41, John Doe"]}))[0]
    assert finding.severity == "direct"


# ── honest claim wording ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:11434/v1", True),
    ("http://[::1]:11434/v1", True),
    ("https://api.groq.com/openai/v1", False),      # a REMOTE custom endpoint
    ("https://api.together.xyz/v1", False),
    ("", False),                                     # unset -> hosted OpenAI
])
def test_loopback_check_is_true_only_for_this_machine(monkeypatch, url, expected):
    """llm._is_local() is documented as true for remote free-tier endpoints, so it must NOT be
    used here: it would assert 'nothing left this machine' exactly when that is false."""
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    assert deid.llm_is_on_this_machine() is expected


def test_assurance_line_never_claims_compliance(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    line = deid.assurance_line(scrubbed=True)
    lowered = line.lower()
    assert "identifiers were removed" in lowered
    assert "nothing left this machine" not in lowered
    for forbidden in ("hipaa", "compliant", "de-identified", "safe to share", "anonymised",
                      "anonymized"):
        assert forbidden not in lowered


def test_assurance_line_adds_the_local_claim_only_on_loopback(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert "nothing left this machine" in deid.assurance_line(scrubbed=True).lower()
