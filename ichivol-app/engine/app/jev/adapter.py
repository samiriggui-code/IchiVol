"""System One adapter — jevos-v4 local and TypeSafe hosted.

Validates NOUL / CHOICE / SCORE. Invalid responses never become fake evaluations.
Does not authorize risk or place orders.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.jev.normalize import normalize_answers
from app.jev.providers import (
    JevProviderName,
    estimate_cost_usd,
    resolve_provider,
)

DEFAULT_TIMEOUT_S = 5.0


def _configured_timeout_s() -> float:
    try:
        from app.eve.settings_schema import jev_timeout_seconds

        return float(jev_timeout_seconds())
    except Exception:
        return DEFAULT_TIMEOUT_S


def _state_to_payload(state: Any) -> Any:
    """System One accepts a string or JSON-serializable object/array."""
    if isinstance(state, (dict, list)):
        return state
    if isinstance(state, str):
        return state
    return str(state)


def _parse_usage(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens"):
        val = raw.get(key)
        if val is None:
            continue
        try:
            out[key] = int(val)
        except (TypeError, ValueError):
            return None
    return out or None


def _failure(
    *,
    provider: JevProviderName | str,
    error: str,
    latency_ms: float,
    request_model: str | None = None,
    score_maturity: str | None = None,
    raw: Any = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "provider": provider,
        "request_model": request_model,
        "response_model": None,
        "score_maturity": score_maturity,
        "latency_ms": latency_ms,
        "answers": None,
        "usage": None,
        "cost_usd": None,
        "error": error,
        "raw": raw,
    }


def evaluate(
    state: Any,
    questions: dict[str, Any],
    *,
    provider: str | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Call System One and return a traced, validated envelope."""
    started = time.monotonic()
    if timeout_s is None:
        timeout_s = _configured_timeout_s()
    try:
        cfg = resolve_provider(provider)
    except ValueError as exc:
        return _failure(provider=str(provider or "unknown"), error=str(exc), latency_ms=0.0)

    if not questions or not isinstance(questions, dict):
        return _failure(
            provider=cfg.name,
            error="questions_empty",
            latency_ms=0.0,
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
        )
    if not cfg.api_key:
        return _failure(
            provider=cfg.name,
            error="jev_key_missing",
            latency_ms=0.0,
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
        )

    payload = {
        "model": cfg.model,
        "state": _state_to_payload(state),
        "questions": questions,
    }
    url = cfg.base_url.rstrip("/") + "/v1/systemone"
    headers = {
        "Authorization": "Bearer " + cfg.api_key,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.post(url, json=payload, headers=headers)
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            if response.status_code >= 400:
                return _failure(
                    provider=cfg.name,
                    error=f"http_{response.status_code}",
                    latency_ms=latency_ms,
                    request_model=cfg.model,
                    score_maturity=cfg.score_maturity,
                    raw=_safe_json(response),
                )
            body = response.json()
    except httpx.TimeoutException:
        fail = _failure(
            provider=cfg.name,
            error="timeout",
            latency_ms=round((time.monotonic() - started) * 1000, 2),
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
        )
        fail["late"] = True
        return fail
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        return _failure(
            provider=cfg.name,
            error=type(exc).__name__,
            latency_ms=round((time.monotonic() - started) * 1000, 2),
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
        )

    if not isinstance(body, dict):
        return _failure(
            provider=cfg.name,
            error="response_not_object",
            latency_ms=latency_ms,
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
            raw=body,
        )

    answers_raw = body.get("answers")
    normalized, err = normalize_answers(questions, answers_raw)
    if err or normalized is None:
        return _failure(
            provider=cfg.name,
            error=err or "answers_invalid",
            latency_ms=latency_ms,
            request_model=cfg.model,
            score_maturity=cfg.score_maturity,
            raw=body,
        )

    usage = _parse_usage(body.get("usage"))
    input_tokens = usage.get("input_tokens") if usage else None
    response_model = body.get("model")
    if response_model is not None and not isinstance(response_model, str):
        response_model = str(response_model)

    model_mismatch = False
    if (
        isinstance(response_model, str)
        and response_model
        and response_model not in (cfg.model, "jev-latest")
        and cfg.model not in ("jev-latest",)
        and response_model != cfg.model
    ):
        # Pin guard: silent upgrades must surface on the dossier.
        model_mismatch = True

    return {
        "ok": True,
        "provider": cfg.name,
        "request_model": cfg.model,
        "response_model": response_model,
        "model_mismatch": model_mismatch,
        "score_maturity": cfg.score_maturity,
        "latency_ms": latency_ms,
        "late": False,
        "answers": normalized,
        "usage": usage,
        "cost_usd": estimate_cost_usd(cfg.name, input_tokens),
        "error": None,
        "raw": body,
    }


def health(
    *,
    provider: str | None = None,
    timeout_s: float = 3.0,
) -> dict[str, Any]:
    """Probe provider readiness. jevos exposes /health; TypeSafe uses a key presence check + URL."""
    started = time.monotonic()
    try:
        cfg = resolve_provider(provider)
    except ValueError as exc:
        return {
            "ok": False,
            "provider": str(provider or "unknown"),
            "error": str(exc),
            "latency_ms": 0.0,
        }

    if not cfg.api_key:
        return {
            "ok": False,
            "provider": cfg.name,
            "base_url": cfg.base_url,
            "error": "jev_key_missing",
            "latency_ms": 0.0,
            "score_maturity": cfg.score_maturity,
        }

    # Prefer /health when available (jevos). Hosted may 404 — fall back to configured OK.
    health_url = cfg.base_url.rstrip("/") + "/health"
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.get(
                health_url,
                headers={"Authorization": "Bearer " + cfg.api_key},
            )
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            if response.status_code == 200:
                body = _safe_json(response)
                fingerprint = None
                model_files = None
                if isinstance(body, dict):
                    fingerprint = body.get("fingerprint") or body.get("sha256")
                    model_files = body.get("model_files") or body.get("files")
                return {
                    "ok": True,
                    "provider": cfg.name,
                    "base_url": cfg.base_url,
                    "probe": "health",
                    "latency_ms": latency_ms,
                    "score_maturity": cfg.score_maturity,
                    "fingerprint": fingerprint,
                    "model_files": model_files,
                    "raw": body if isinstance(body, dict) else None,
                }
            if cfg.name == "typesafe" and response.status_code in (404, 405):
                return {
                    "ok": True,
                    "provider": cfg.name,
                    "base_url": cfg.base_url,
                    "probe": "config_only",
                    "latency_ms": latency_ms,
                    "score_maturity": cfg.score_maturity,
                    "note": "health_endpoint_unavailable",
                }
            return {
                "ok": False,
                "provider": cfg.name,
                "base_url": cfg.base_url,
                "error": f"http_{response.status_code}",
                "latency_ms": latency_ms,
                "score_maturity": cfg.score_maturity,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "provider": cfg.name,
            "base_url": cfg.base_url,
            "error": type(exc).__name__,
            "latency_ms": round((time.monotonic() - started) * 1000, 2),
            "score_maturity": cfg.score_maturity,
        }


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        text = response.text
        return text[:500] if text else None


__all__ = ["evaluate", "health", "resolve_provider"]
