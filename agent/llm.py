"""Thin OpenAI wrapper + lightweight cost/latency tracing.

The client is created lazily so this imports cleanly with no API key. Every call records tokens,
latency, and an estimated cost into a per-run trace the agent can attach to its result.
"""
from __future__ import annotations

import json
import os
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
_TRACE: list[dict] = []


class LLMError(Exception):
    pass


def reset_trace() -> None:
    _TRACE.clear()


def trace_summary() -> dict:
    known = MODEL in _COST
    ci, co = _COST[MODEL] if known else _FALLBACK_COST
    pt = sum(t["prompt_tokens"] for t in _TRACE)
    ct = sum(t["completion_tokens"] for t in _TRACE)
    return {
        "calls": len(_TRACE),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "latency_ms": round(sum(t["ms"] for t in _TRACE)),
        "est_cost_usd": round(pt / 1000 * ci + ct / 1000 * co, 4),
        # True → MODEL is unknown, so est_cost_usd uses the gpt-4o fallback rate above (an
        # order-of-magnitude estimate, never a false $0). False → MODEL is a known priced id.
        "est_cost_approx": not known,
    }


def _get_client():
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
        if not os.getenv("OPENAI_API_KEY"):
            raise LLMError(
                "OPENAI_API_KEY is not set. Copy agent/.env.example to agent/.env and add your key "
                "(then restart the app if it was already running)."
            )
        from openai import OpenAI
        # max_retries → the SDK retries transient failures (429 rate-limit, 5xx, timeouts,
        # connection errors) with exponential backoff; timeout caps a hung request.
        _client = OpenAI(max_retries=4, timeout=40.0)
    return _client


def complete(system: str, user: str, *, json_mode: bool = False, temperature: float = 0.0,
             max_tokens: int = MAX_TOKENS) -> str:
    kwargs = dict(
        model=MODEL,
        temperature=temperature,
        seed=0,                 # reproducibility: pin sampling so identical prompts return identically
        max_tokens=max_tokens,  # cost/latency guardrail: cap tokens generated per call
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    try:
        resp = _get_client().chat.completions.create(**kwargs)
    except LLMError:
        raise
    except Exception as e:   # SDK already retried transient errors; surface the final failure cleanly
        raise LLMError(f"LLM request failed: {type(e).__name__}: {e}") from e
    ms = (time.perf_counter() - t0) * 1000
    u = getattr(resp, "usage", None)
    _TRACE.append({
        "ms": ms,
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
    })
    return resp.choices[0].message.content or ""


def complete_json(system: str, user: str, temperature: float = 0.0, retries: int = 2) -> dict:
    last = ""
    for _ in range(retries + 1):
        raw = complete(system, user, json_mode=True, temperature=temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            last = raw            # occasionally the model returns prose in JSON mode — try again
    raise LLMError(f"Model did not return valid JSON after {retries + 1} tries.\n---\n{last[:500]}")
