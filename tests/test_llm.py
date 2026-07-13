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
    def __init__(self, content="ok"):
        self.usage = type("U", (), {"prompt_tokens": 3, "completion_tokens": 5})()
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class _FakeClient:
    """Records the kwargs each completion is called with; returns canned responses (one per call,
    the last one repeating)."""
    def __init__(self, reject_response_format=False, contents=("ok",)):
        self.calls = []
        self._reject_rf = reject_response_format
        self._contents = list(contents)
        comp = type("Comp", (), {})()
        comp.create = self._create
        self.chat = type("Chat", (), {})()
        self.chat.completions = comp

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._reject_rf and "response_format" in kwargs:
            raise RuntimeError("this endpoint does not support response_format")
        i = min(len(self.calls) - 1, len(self._contents) - 1)
        return _Resp(self._contents[i])


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


def test_complete_json_salvages_fenced_json(monkeypatch):
    # some local models wrap the JSON in prose/code fences even when asked not to — salvage it
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient(contents=['Sure! Here it is:\n```json\n{"a": 1}\n```\nHope that helps.'])
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    assert llm.complete_json("sys", "user") == {"a": 1}
    assert len(fake.calls) == 1                       # salvaged, no retry burned


def test_complete_json_retries_with_prompt_instruction(monkeypatch):
    # a server that ACCEPTS response_format but ignores it returns prose without erroring;
    # the retry must demand raw JSON in the prompt instead of resending the identical request
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient(contents=["The answer is forty-two.", '{"a": 42}'])
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    assert llm.complete_json("sys", "user") == {"a": 42}
    assert len(fake.calls) == 2
    assert "JSON" in fake.calls[1]["messages"][0]["content"]  # retry escalated the instruction


def test_trace_is_per_thread(monkeypatch):
    # Streamlit serves each session on its own thread in one process: one session's reset_trace()
    # must not wipe another session's in-flight trace
    import threading
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.complete("sys", "user")                       # main thread: 1 traced call
    seen = {}

    def worker():
        seen["before"] = llm.trace_summary()["calls"]   # a fresh thread starts with an empty trace
        llm.reset_trace()
        llm.complete("sys", "user")
        seen["after"] = llm.trace_summary()["calls"]

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert seen == {"before": 0, "after": 1}
    assert llm.trace_summary()["calls"] == 1          # the worker's reset didn't wipe this thread


def test_est_cost_zero_when_local(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    fake = _FakeClient()
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    llm.complete("sys", "user")
    summary = llm.trace_summary()
    assert summary["est_cost_usd"] == 0.0            # local run is free
    assert summary["est_cost_approx"] is False
