"""Provider resolution for TypeSafe Jev (hosted) and jevos-v4 (local).

OpenRouter is NOT a System One transport — it remains the Copilot chat LLM only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

JevProviderName = Literal["jevos", "typesafe"]

DEFAULT_JEVOS_URL = "http://jevos-v4:8017"
DEFAULT_TYPESAFE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"

# TypeSafe early-access pricing (input $/M tokens; output free). Documented assumption.
TYPESAFE_INPUT_USD_PER_M = 0.042


@dataclass(frozen=True)
class JevProviderConfig:
    name: JevProviderName
    base_url: str
    api_key: str
    model: str
    score_maturity: Literal["full", "early"]


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def resolve_provider(provider: str | None = None) -> JevProviderConfig:
    """Resolve active System One provider.

    JEV_PROVIDER: ``jevos`` (default, VPS local) | ``typesafe`` (hosted official key).
    """
    raw = (provider or _env("JEV_PROVIDER", "jevos")).lower()
    model = _env("JEV_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL

    if raw in ("jevos", "jevos-v4", "local"):
        return JevProviderConfig(
            name="jevos",
            base_url=_env("JEV_URL", DEFAULT_JEVOS_URL).rstrip("/") or DEFAULT_JEVOS_URL,
            api_key=_env("JEV_API_KEY"),
            model=model,
            score_maturity="early",
        )
    if raw in ("typesafe", "hosted", "jev"):
        # Prefer dedicated TypeSafe key; fall back to JEV_API_KEY for single-secret ops.
        key = _env("TYPESAFE_API_KEY") or _env("JEV_API_KEY")
        return JevProviderConfig(
            name="typesafe",
            base_url=_env("TYPESAFE_API_URL", DEFAULT_TYPESAFE_URL).rstrip("/")
            or DEFAULT_TYPESAFE_URL,
            api_key=key,
            model=model,
            score_maturity="full",
        )
    raise ValueError(f"unknown_jev_provider:{raw}")


def estimate_cost_usd(provider: JevProviderName, input_tokens: int | None) -> float | None:
    if input_tokens is None or input_tokens < 0:
        return None
    if provider == "jevos":
        return 0.0
    if provider == "typesafe":
        return round((input_tokens / 1_000_000.0) * TYPESAFE_INPUT_USD_PER_M, 8)
    # Exhaustive: new providers must be handled explicitly.
    raise ValueError(f"unknown_jev_provider:{provider}")
