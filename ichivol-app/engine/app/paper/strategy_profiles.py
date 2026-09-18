"""Frozen strategy profiles for paper portfolios.

ICHIVOL_BASELINE_V1 freezes current pipeline entry/exit rules and MUST NOT
gain Market Structure or Context gates. Experimental portfolios run in
parallel (docs/ARCHITECTURE-CONSOLIDEE-V2.md).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

BASELINE_CODE = "ICHIVOL_BASELINE_V1"

BASELINE_PROFILE: dict[str, Any] = {
    "code": BASELINE_CODE,
    "label": "IchiVol baseline V1 (paper broker)",
    "entry": "pipeline_buy_sell",
    "exit": ["pipeline_flipped", "pipeline_downgraded", "stop_hit", "take_profit_hit", "manual_close"],
    "risk_pct": 0.01,
    "take_profit_r": 2.0,
    "max_open_positions": 5,
    "max_notional_pct": 0.25,
    "commission_bps": 5.0,
    "slippage_bps": 3.0,
    "spread_bps": 2.0,
    "require_atr_stop": True,
    "valuation_mode": "USDT_AS_EUR_PROXY",
    "initial_cash_eur": 5000.0,
    # Phase 2 — baseline ignores Market Structure filters
    "structure_filter": None,
    "structure_detectors": [],
    "structure_include_pytrendline": False,
    "structure_block_atr_mult": 1.0,
    "shadow_on_block": False,
    # Phase 3 — baseline ignores Context filters
    "context_rsi": False,
    "context_cmf": False,
    "context_obv": False,
    "context_regime_hard": False,
    "rsi_require_alignment": False,
    "rsi_overbought": 70.0,
    "rsi_oversold": 30.0,
    "rsi_mid": 50.0,
    "sync_auto": True,
}


def _with(**overrides: Any) -> dict[str, Any]:
    profile = deepcopy(BASELINE_PROFILE)
    profile.update(overrides)
    return profile


# --- Phase 2 structure experiments ---
STRUCTURE_MVPP = _with(
    code="STRUCTURE_MVPP",
    label="Structure experiment — MVPP zones only",
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp"],
    shadow_on_block=True,
)

STRUCTURE_TRENDLN = _with(
    code="STRUCTURE_TRENDLN",
    label="Structure experiment — trendln zones only",
    structure_filter="block_near_opposing",
    structure_detectors=["trendln"],
    shadow_on_block=True,
)

STRUCTURE_PYTRENDLINE = _with(
    code="STRUCTURE_PYTRENDLINE",
    label="Structure experiment — pytrendline (capped, candidates only)",
    structure_filter="block_near_opposing",
    structure_detectors=["pytrendline"],
    structure_include_pytrendline=True,
    shadow_on_block=True,
)

STRUCTURE_CONSENSUS = _with(
    code="STRUCTURE_CONSENSUS",
    label="Structure experiment — MVPP + trendln consensus",
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp", "trendln"],
    shadow_on_block=True,
)

ICHIVOL_MS_V1 = _with(
    code="ICHIVOL_MS_V1",
    label="IchiVol + Market Structure (consensus filter)",
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp", "trendln"],
    shadow_on_block=True,
)

# --- Phase 3 context experiments ---
ICHIVOL_CTX_RSI = _with(
    code="ICHIVOL_CTX_RSI",
    label="IchiVol + RSI exhaustion gate",
    context_rsi=True,
    rsi_require_alignment=False,
    shadow_on_block=True,
)

ICHIVOL_CTX_FLOW = _with(
    code="ICHIVOL_CTX_FLOW",
    label="IchiVol + CMF/OBV flow gate",
    context_cmf=True,
    context_obv=True,
    shadow_on_block=True,
)

ICHIVOL_CTX_REGIME = _with(
    code="ICHIVOL_CTX_REGIME",
    label="IchiVol + hard ATR regime gate (dead/extreme)",
    context_regime_hard=True,
    shadow_on_block=True,
)

# Portfolio E: Market Structure + Regime
ICHIVOL_MS_REGIME = _with(
    code="ICHIVOL_MS_REGIME",
    label="IchiVol + Market Structure + hard regime",
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp", "trendln"],
    context_regime_hard=True,
    shadow_on_block=True,
)

# Context stack without structure
ICHIVOL_CTX_FULL = _with(
    code="ICHIVOL_CTX_FULL",
    label="IchiVol + RSI + flow + hard regime",
    context_rsi=True,
    context_cmf=True,
    context_obv=True,
    context_regime_hard=True,
    rsi_require_alignment=True,
    shadow_on_block=True,
)

EXPERIMENTAL_PROFILES: dict[str, dict[str, Any]] = {
    STRUCTURE_MVPP["code"]: STRUCTURE_MVPP,
    STRUCTURE_TRENDLN["code"]: STRUCTURE_TRENDLN,
    STRUCTURE_PYTRENDLINE["code"]: STRUCTURE_PYTRENDLINE,
    STRUCTURE_CONSENSUS["code"]: STRUCTURE_CONSENSUS,
    ICHIVOL_MS_V1["code"]: ICHIVOL_MS_V1,
    ICHIVOL_CTX_RSI["code"]: ICHIVOL_CTX_RSI,
    ICHIVOL_CTX_FLOW["code"]: ICHIVOL_CTX_FLOW,
    ICHIVOL_CTX_REGIME["code"]: ICHIVOL_CTX_REGIME,
    ICHIVOL_MS_REGIME["code"]: ICHIVOL_MS_REGIME,
    ICHIVOL_CTX_FULL["code"]: ICHIVOL_CTX_FULL,
}

ALL_PROFILES: dict[str, dict[str, Any]] = {
    BASELINE_CODE: BASELINE_PROFILE,
    **EXPERIMENTAL_PROFILES,
}


def profile_for(code: str) -> dict[str, Any]:
    if code in ALL_PROFILES:
        return deepcopy(ALL_PROFILES[code])
    return deepcopy(BASELINE_PROFILE) | {"code": code}


def syncable_profile_codes() -> list[str]:
    """Codes that receive auto_watchlist sync (baseline + experiments)."""
    return [
        code
        for code, profile in ALL_PROFILES.items()
        if profile.get("sync_auto", True)
    ]
