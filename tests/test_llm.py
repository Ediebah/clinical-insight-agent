"""Unit tests for the LLM wrapper's provider switching (no key, no network).

Covers OPENAI_BASE_URL support: running on a local / OpenAI-compatible endpoint with no key, omitting the
OpenAI-only `seed`, the JSON-mode fallback, and reporting $0 cost for a local run.
"""
import pytest

from agent import llm


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Start each test from a fresh client and a clean environment (no key, no base URL)."""
    llm._client = None
    llm.reset_trace()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    # keep a local agent/.env from injecting a real key during the keyless tests
    monkeypatch.setattr(llm, "load_dotenv", lambda *a, **k: None)
    yield
    llm._client = None


class _Resp:
    def __init__(self):
        self.usage = type("U", (), {"prompt_tokens": 3, "completion_tokens": 5})()
        self.choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]


class _FakeClient:
    """Records the kwargs each completion is called with; returns a canned response."""
    def __init__(self, reject_response_format=False):
        self.calls = []
        self._reject_rf = reject_response_format
        comp = type("Comp", (), {})()
        comp.create = self._create
        self.chat = type("Chat", (), {})()
        self.chat.completions = comp

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._reject_rf and "response_format" in kwargs:
            raise RuntimeError("this endpoint does not support response_format")
        return _Resp()


def test_no_key_and_no_base_url_raises():
    with pytest.raises(llm.LLMError):
        llm._get_client()


def test_base_url_needs_no_key(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    client = llm._get_client()                       # must not raise despite no OPENAI_API_KEY
    assert str(client.base_url).startswith("http://localhost:11434")


def test_is_local_reflects_env(monkeypatch):
    assert llm._is_local() is False
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert llm._is_local() is True


def test_hosted_sends_seed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    assert llm.complete("sys", "user") == "ok"
    assert fake.calls[0].get("seed") == 0            # hosted OpenAI → reproducible seed sent


def test_local_omits_seed(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.complete("sys", "user")
    assert "seed" not in fake.calls[0]               # local endpoint → omit the OpenAI-only field


def test_local_json_falls_back_without_response_format(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient(reject_response_format=True)  # emulate a server without JSON mode
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    assert llm.complete("sys", "user", json_mode=True) == "ok"
    assert len(fake.calls) == 2                       # first try rejected, degraded retry succeeded
    assert "response_format" not in fake.calls[1]     # retry dropped it
    assert "JSON" in fake.calls[1]["messages"][0]["content"]  # and asked for JSON in the prompt


def test_est_cost_zero_when_local(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.complete("sys", "user")
    summary = llm.trace_summary()
    assert summary["est_cost_usd"] == 0.0            # local run is free
    assert summary["est_cost_approx"] is False
