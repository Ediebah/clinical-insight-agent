"""Unit tests for the accuracy eval's regression-tracking helpers (no key, no warehouse needed).

An aggregate accuracy that holds steady can still hide a case flipping — one regression masked by
one fix — so the per-case history is what makes drift attributable. These pin its parsing and diff.
"""
import json

import pandas as pd

from agent import eval as ev


def _write(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_previous_cases_returns_empty_when_no_history(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "HISTORY", tmp_path / "absent.jsonl")
    assert ev._previous_cases() == {}


def test_previous_cases_ignores_pre_cases_records(tmp_path, monkeypatch):
    """History written before per-case logging existed carries only aggregates — not a regression."""
    h = tmp_path / "h.jsonl"
    _write(h, [{"ts": "t1", "accuracy": 0.9, "faithfulness": 1.0, "n": 33}])
    monkeypatch.setattr(ev, "HISTORY", h)
    assert ev._previous_cases() == {}


def test_previous_cases_takes_the_most_recent_run_that_logged_cases(tmp_path, monkeypatch):
    h = tmp_path / "h.jsonl"
    _write(h, [
        {"ts": "t1", "accuracy": 0.9, "cases": {"a": True, "b": True}},
        {"ts": "t2", "accuracy": 0.9, "cases": {"a": True, "b": False}},
    ])
    monkeypatch.setattr(ev, "HISTORY", h)
    assert ev._previous_cases() == {"a": True, "b": False}


def test_previous_cases_skips_malformed_and_blank_lines(tmp_path, monkeypatch):
    """A truncated append (interrupted run) must not blind the next run's diff."""
    h = tmp_path / "h.jsonl"
    h.write_text(
        json.dumps({"ts": "t1", "cases": {"a": True}}) + "\n"
        + "\n"
        + '{"ts": "t2", "cases": {"a": fal\n'          # truncated write
    )
    monkeypatch.setattr(ev, "HISTORY", h)
    assert ev._previous_cases() == {"a": True}


def test_diff_cases_reports_both_directions():
    prev = {"a": True, "b": False, "c": True}
    now = {"a": False, "b": True, "c": True}
    assert ev._diff_cases(now, prev) == (["a"], ["b"])


def test_diff_cases_treats_new_and_dropped_cases_as_no_change():
    """Adding a case to GOLD (or removing one) is an authored change, not agent drift."""
    assert ev._diff_cases({"new": False}, {"old": True}) == ([], [])
    assert ev._diff_cases({"new": True}, {"old": False}) == ([], [])


# --- unsupported cases ---
# A zero or empty reference cannot discriminate a correct answer from a broken one: computing it,
# finding nothing, refusing, and erroring all produce the same observable. Such a case is
# unsupported by the warehouse under test, not failed by the agent.

class _Case:
    reference_sql = "select 1"


def test_reference_is_none_when_the_query_returns_no_rows(monkeypatch):
    monkeypatch.setattr(ev, "run_query", lambda sql: pd.DataFrame({"n": []}))
    assert ev._reference(_Case()) is None


def test_reference_is_none_for_a_zero_count(monkeypatch):
    """The heart_attack_patients case: CI's 60-patient warehouse has nobody with an MI, so the
    agent's correct refusal was being scored as a wrong answer."""
    monkeypatch.setattr(ev, "run_query", lambda sql: pd.DataFrame({"n": [0]}))
    assert ev._reference(_Case()) is None


def test_reference_is_none_for_a_null_value(monkeypatch):
    monkeypatch.setattr(ev, "run_query", lambda sql: pd.DataFrame({"n": [None]}))
    assert ev._reference(_Case()) is None


def test_reference_returns_a_real_value_unchanged(monkeypatch):
    monkeypatch.setattr(ev, "run_query", lambda sql: pd.DataFrame({"n": [52]}))
    assert ev._reference(_Case()) == 52.0


def test_an_unsupported_case_is_neither_a_regression_nor_a_fix():
    """The property that makes omitting unsupported cases safe: a case that disappears because the
    warehouse shrank must not read as a regression, nor reappear as a fix when it grows."""
    assert ev._diff_cases({"a": True}, {"a": True, "gone": True}) == ([], [])
    assert ev._diff_cases({"a": True, "back": True}, {"a": True}) == ([], [])


# --- throttling ------------------------------------------------------------------------------
# run_analysis swallows llm.LLMError into result.error, so a throttled call is indistinguishable
# from a wrong answer: a rate-limited sweep silently deflates accuracy and reads as an agent
# regression. These pin the detection that stops that.

def test_transient_matches_throttling_and_transport_faults():
    for msg in [
        "LLM request failed: RateLimitError: Error code: 429 - rate limit reached for gpt-4o",
        "LLM request failed: APITimeoutError: Request timed out",
        "Error code: 503 - service temporarily unavailable",
        "LLM request failed: APIConnectionError: Connection error",
        "The engine is currently overloaded, please try again later",
    ]:
        assert ev.TRANSIENT.search(msg), msg


def test_transient_does_not_match_real_agent_failures():
    """A genuine wrong answer must never be retried away — that would mask the very regression the
    eval exists to catch."""
    for msg in [
        "SQL failed after 3 attempts: Binder Error: column \"foo\" not found",
        "Model did not return valid JSON after 3 tries.",
        "The analysis could not be completed: KeyError: 'outcome'",
        "This request looks like an attempt to override the agent's instructions and was blocked.",
    ]:
        assert ev.TRANSIENT.search(msg) is None, msg


def test_backoff_sleep_honours_the_servers_own_hint(monkeypatch):
    """The 429 body carries the exact wait; guessing longer wastes the sweep's wall-clock."""
    slept = []
    monkeypatch.setattr(ev.time, "sleep", slept.append)
    nxt = ev.backoff_sleep("Please try again in 2.75s. Visit ...", 30.0)
    assert slept == [3.75]          # hint + 1s margin, not the 30s default
    assert nxt == 60.0              # delay still doubles (capped) for the next attempt


def test_previous_cases_ignores_the_faithful_map(tmp_path, monkeypatch):
    """`faithful` is logged beside `cases` but is three-valued (true/false/null-not-applicable), so
    it must never be mistaken for the pass/fail record the accuracy diff runs on."""
    h = tmp_path / "h.jsonl"
    _write(h, [{"ts": "t1", "cases": {"a": True}, "faithful": {"a": False, "b": None}}])
    monkeypatch.setattr(ev, "HISTORY", h)
    assert ev._previous_cases() == {"a": True}


def test_backoff_sleep_falls_back_to_exponential_and_caps(monkeypatch):
    slept = []
    monkeypatch.setattr(ev.time, "sleep", slept.append)
    assert ev.backoff_sleep("Connection error", 8.0) == 16.0
    assert ev.backoff_sleep("Connection error", 45.0) == 60.0   # cap
    assert slept == [8.0, 45.0]
