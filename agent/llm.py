"""Thin OpenAI (or any OpenAI-compatible endpoint) wrapper + lightweight cost/latency tracing.

The client is created lazily so this imports cleanly with no API key. Set OPENAI_BASE_URL to run against
a local model (Ollama, LM Studio, vLLM) or any OpenAI-compatible API with no OpenAI key. Every call
records tokens, latency, and an estimated cost into a per-run trace the agent can attach to its result.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
# Hard cap on generated tokens per completion so a runaway/looping generation can't blow up cost or
# latency. Applied to every call; override per-call via complete(max_tokens=...).
MAX_TOKENS = 1500
_client = None

# rough USD per 1K tokens (input, output) — for an order-of-magnitude cost estimate
_COST = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1": (0.002, 0.008),
    "gpt-4.1-mini": (0.0004, 0.0016),
}
# Unknown / dated model ids (e.g. a dated snapshot like "gpt-4o-2024-08-06") aren't in _COST. Rather
# than report a misleading $0, fall back to gpt-4o pricing and flag the estimate as approximate.
_FALLBACK_COST = _COST["gpt-4o"]
# Per-THREAD trace: Streamlit serves each browser session on its own thread within one process, so a
# module-global list would interleave two concurrent runs (one session's reset_trace() wiping the
# other's in-flight records, cost/latency cross-attributed).
_TRACE_LOCAL = threading.local()


def _trace() -> list[dict]:
    if not hasattr(_TRACE_LOCAL, "records"):
        _TRACE_LOCAL.records = []
    return _TRACE_LOCAL.records


class LLMError(Exception):
    pass


def reset_trace() -> None:
    _trace().clear()


def trace_summary() -> dict:
    local = _is_local()
    known = MODEL in _COST
    ci, co = _COST[MODEL] if known else _FALLBACK_COST
    records = _trace()
    pt = sum(t["prompt_tokens"] for t in records)
    ct = sum(t["completion_tokens"] for t in records)
    return {
        "calls": len(records),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "latency_ms": round(sum(t["ms"] for t in records)),
        # A local model via OPENAI_BASE_URL is free to run, so report $0 rather than a hosted estimate.
        "est_cost_usd": 0.0 if local else round(pt / 1000 * ci + ct / 1000 * co, 4),
        # True → MODEL is unknown, so est_cost_usd uses the gpt-4o fallback rate above (an
        # order-of-magnitude estimate, never a false $0). False → known priced id, or a free local run.
        "est_cost_approx": (not known) and not local,
    }


def _is_local() -> bool:
    """True when pointed at a custom OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, a free-tier
    API) via OPENAI_BASE_URL rather than hosted OpenAI. Such endpoints need no real key, can be much
    slower, and don't all accept every OpenAI-only parameter (e.g. `seed`, JSON mode)."""
    return bool(os.getenv("OPENAI_BASE_URL"))


def _get_client():
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
        base_url = os.getenv("OPENAI_BASE_URL") or None
        key = os.getenv("OPENAI_API_KEY")
        # A local / self-hosted endpoint (Ollama etc.) ignores the key, so only hosted OpenAI needs one.
        if not key and not base_url:
            raise LLMError(
                "OPENAI_API_KEY is not set. Copy agent/.env.example to agent/.env and add your key, or "
                "set OPENAI_BASE_URL to run on a local model with no key (see the README). Restart the "
                "app if it was already running."
            )
        from openai import OpenAI
        # max_retries → the SDK retries transient failures (429 rate-limit, 5xx, timeouts,
        # connection errors) with exponential backoff; timeout caps a hung request (a local model,
        # especially on CPU, can be far slower than hosted OpenAI). Keep retries×timeout modest:
        # the agent's between-step run deadline cannot interrupt a single in-flight call, so this
        # product bounds the worst-case hang of one step.
        _client = OpenAI(base_url=base_url, api_key=key or "local", max_retries=2,
                         timeout=120.0 if base_url else 40.0)
    return _client


def complete(system: str, user: str, *, json_mode: bool = False, temperature: float = 0.0,
             max_tokens: int = MAX_TOKENS) -> str:
    local = _is_local()
    kwargs = dict(
        model=MODEL,
        temperature=temperature,
        max_tokens=max_tokens,  # cost/latency guardrail: cap tokens generated per call
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    if not local:
        # reproducibility: pin sampling so identical prompts return identically. Only sent to hosted
        # OpenAI; many compatible servers reject an unknown `seed` field.
        kwargs["seed"] = 0
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    try:
        resp = _get_client().chat.completions.create(**kwargs)
    except LLMError:
        raise
    except Exception as e:   # SDK already retried transient errors; surface the final failure cleanly
        # A compatible endpoint may reject response_format; retry once without it, asking for JSON in
        # the prompt instead, so local models without a JSON mode still work.
        if local and json_mode:
            try:
                kwargs.pop("response_format", None)
                kwargs["messages"] = [
                    {"role": "system",
                     "content": system + "\n\nReturn only valid JSON, with no prose and no code fences."},
                    {"role": "user", "content": user},
                ]
                resp = _get_client().chat.completions.create(**kwargs)
            except Exception as e2:
                raise LLMError(f"LLM request failed: {type(e2).__name__}: {e2}") from e2
        else:
            raise LLMError(f"LLM request failed: {type(e).__name__}: {e}") from e
    ms = (time.perf_counter() - t0) * 1000
    u = getattr(resp, "usage", None)
    _trace().append({
        "ms": ms,
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
    })
    return resp.choices[0].message.content or ""


def _salvage_json(raw: str) -> dict | None:
    """Extract a JSON object from prose/code fences. Local models often wrap JSON in text even in
    JSON mode (many OpenAI-compatible servers accept response_format and silently ignore it)."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            out = json.loads(m.group(0))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def complete_json(system: str, user: str, temperature: float = 0.0, retries: int = 2) -> dict:
    last = ""
    for attempt in range(retries + 1):
        # After a parse failure, escalate in the PROMPT: a server that accepts-but-ignores
        # response_format returns prose without erroring, so resending the identical request
        # would just fail the same way.
        sys_msg = system if attempt == 0 else (
            system + "\n\nReturn ONLY a valid JSON object — no prose, no code fences, no explanation.")
        raw = complete(sys_msg, user, json_mode=True, temperature=temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            salvaged = _salvage_json(raw)
            if salvaged is not None:
                return salvaged
            last = raw
    raise LLMError(f"Model did not return valid JSON after {retries + 1} tries.\n---\n{last[:500]}")
