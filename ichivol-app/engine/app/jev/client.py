"""Backward-compatible JEV client.

Prefer ``app.jev.adapter.evaluate`` for new code (provider tracing + validation).
This module keeps the historical ``evaluate(state, questions)`` shape used by Eve Shadow.
"""

from __future__ import annotations

from typing import Any

from app.jev.adapter import evaluate as adapter_evaluate


def evaluate(state: str, questions: dict) -> dict:
    """Call System One via the multi-provider adapter.

    Legacy shape: ``{ok, result?, error?}`` where ``result`` is the raw provider body
    when successful (EveShadowPanel reads ``result.answers.*.noul``).
    """
    envelope = adapter_evaluate(state, questions)
    if not envelope.get("ok"):
        return {
            "ok": False,
            "error": envelope.get("error") or "jev_error",
            "provider": envelope.get("provider"),
            "latency_ms": envelope.get("latency_ms"),
        }
    raw = envelope.get("raw")
    result: Any = raw if isinstance(raw, dict) else {"answers": envelope.get("answers")}
    return {
        "ok": True,
        "result": result,
        "provider": envelope.get("provider"),
        "response_model": envelope.get("response_model"),
        "request_model": envelope.get("request_model"),
        "latency_ms": envelope.get("latency_ms"),
        "usage": envelope.get("usage"),
        "cost_usd": envelope.get("cost_usd"),
        "score_maturity": envelope.get("score_maturity"),
    }
