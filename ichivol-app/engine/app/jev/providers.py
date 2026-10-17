"""Provider resolution for TypeSafe Jev (hosted) and jevos-v4 (local).

Policy (Samir): **JEV API (typesafe) calcule** ; **jevos = fallback** quand plus de
crédit / quota API. OpenRouter n’est PAS un transport System One.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

JevProviderName = Literal["jevos", "typesafe"]

DEFAULT_JEVOS_URL = "http://jevos-v4:8017"
DEFAULT_TYPESAFE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
# Primary = hosted JEV API; local jevos only as credit/quota fallback.
DEFAULT_PROVIDER = "typesafe"
DEFAULT_FALLBACK = "jevos"

# TypeSafe early-access pricing (input $/M tokens; output free). Documented assumption.
TYPESAFE_INPUT_USD_PER_M = 0.042

# HTTP / body hints that mean "no more API credit → try jevos".
_CREDIT_HTTP = frozenset({402, 429, 403})
_CREDIT_BODY_MARKERS = (
    "credit",
    "credits",
    "quota",
    "billing",
    "payment",
    "insufficient",
    "balance",
    "rate_limit",
    "rate limit",
    "too many requests",
    "out of credits",
    "no credits",
)


@dataclass(frozen=True)
class JevProviderConfig:
    name: JevProviderName
    base_url: str
    api_key: str
    model: str
    score_maturity: Literal["full", "early"]


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _config_for(name: JevProviderName, model: str) -> JevProviderConfig:
    if name == "jevos":
        return JevProviderConfig(
            name="jevos",
            base_url=_env("JEV_URL", DEFAULT_JEVOS_URL).rstrip("/") or DEFAULT_JEVOS_URL,
            api_key=_env("JEV_API_KEY"),
            model=model,
            score_maturity="early",
        )
    # typesafe / hosted JEV API
    key = _env("TYPESAFE_API_KEY") or _env("JEV_API_KEY")
    return JevProviderConfig(
        name="typesafe",
        base_url=_env("TYPESAFE_API_URL", DEFAULT_TYPESAFE_URL).rstrip("/")
        or DEFAULT_TYPESAFE_URL,
        api_key=key,
        model=model,
        score_maturity="full",
    )


def _normalize_name(raw: str) -> JevProviderName:
    r = raw.lower().strip()
    if r in ("jevos", "jevos-v4", "local"):
        return "jevos"
    if r in ("typesafe", "hosted", "jev", "jev-api", "api"):
        return "typesafe"
    raise ValueError(f"unknown_jev_provider:{raw}")


def resolve_provider(provider: str | None = None) -> JevProviderConfig:
    """Resolve primary System One provider.

    ``JEV_PROVIDER`` default ``typesafe`` (JEV API). Use ``jevos`` only to force local.
    """
    raw = provider or _env("JEV_PROVIDER", DEFAULT_PROVIDER)
    model = _env("JEV_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
    return _config_for(_normalize_name(raw), model)


def resolve_fallback_provider() -> JevProviderConfig | None:
    """Local jevos fallback when primary (JEV API) is out of credits.

    ``JEV_FALLBACK`` default ``jevos``. Set empty / ``none`` / ``off`` to disable.
    """
    raw = _env("JEV_FALLBACK", DEFAULT_FALLBACK)
    if not raw or raw.lower() in ("none", "off", "false", "0"):
        return None
    model = _env("JEV_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
    try:
        name = _normalize_name(raw)
    except ValueError:
        return None
    return _config_for(name, model)


def is_credit_exhausted(
    *,
    error: str | None,
    http_status: int | None = None,
    raw: Any = None,
) -> bool:
    """True when the hosted JEV API refuses for billing / quota / rate-limit."""
    if http_status is not None and http_status in _CREDIT_HTTP:
        return True
    blob = f"{error or ''}"
    if isinstance(raw, dict):
        for k in ("error", "message", "detail", "code", "type"):
            v = raw.get(k)
            if v is not None:
                blob += f" {v}"
        err_obj = raw.get("error")
        if isinstance(err_obj, dict):
            for k in ("message", "code", "type"):
                v = err_obj.get(k)
                if v is not None:
                    blob += f" {v}"
    elif raw is not None:
        blob += f" {raw}"
    low = blob.lower()
    return any(m in low for m in _CREDIT_BODY_MARKERS)


def estimate_cost_usd(provider: JevProviderName, input_tokens: int | None) -> float | None:
    if input_tokens is None or input_tokens < 0:
        return None
    if provider == "jevos":
        return 0.0
    if provider == "typesafe":
        return round((input_tokens / 1_000_000.0) * TYPESAFE_INPUT_USD_PER_M, 8)
    raise ValueError(f"unknown_jev_provider:{provider}")
