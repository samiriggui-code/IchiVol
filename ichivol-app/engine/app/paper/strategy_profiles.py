"""Frozen strategy profiles for paper portfolios.

ICHIVOL_BASELINE_V1 freezes current pipeline entry/exit rules and MUST NOT
gain Market Structure or Context gates. Experimental portfolios run in
parallel (docs/ARCHITECTURE-CONSOLIDEE-V2.md).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

BASELINE_CODE = "ICHIVOL_BASELINE_V1"

# 2026-09-21 (user decision): realistic costs by asset class. Per-side friction (bps) = half quoted spread +
# a slippage tier. ASSUMPTIONS, not measured: crypto from docs/REVUE-SIM-ET-COUTS-ichivol-36 (tick-based),
# CFD/index/FX values are typical retail-broker orders of magnitude (verify against a real broker before trusting).
CRYPTO_FRICTION_BPS: dict[str, float] = {
    "PEPEUSDT": 14.6, "APTUSDT": 10.9, "DOTUSDT": 8.5, "OPUSDT": 8.0, "TONUSDT": 7.1, "ATOMUSDT": 6.9,
    "ARBUSDT": 6.5, "ADAUSDT": 4.2, "NEARUSDT": 3.3, "LTCUSDT": 2.9, "SUIUSDT": 2.6, "UNIUSDT": 2.6,
    "AVAXUSDT": 2.4, "LINKUSDT": 2.4, "DOGEUSDT": 1.6, "SOLUSDT": 1.5, "XRPUSDT": 1.4,
    "BNBUSDT": 1.0, "ETHUSDT": 1.0, "BTCUSDT": 1.0,
}
OTHER_MARKETS_FRICTION_BPS: dict[str, float] = {
    "EURUSD": 0.8, "GBPUSD": 1.2, "XAUUSD": 2.0, "XAGUSD": 4.0, "SPX": 1.5, "NDX": 2.0, "WTI": 3.0,
}
# Non-crypto markets are priced as CFDs / spread-only: no separate commission.
COMMISSION_BPS_BY_SYMBOL: dict[str, float] = {s: 0.0 for s in OTHER_MARKETS_FRICTION_BPS}

# Overnight financing (swap) — ASSUMPTIONS documented in app.brokerage.fee_profiles.
# Long CFD ≈ (benchmark + markup)/365 in bps (~1.86 bps/day). Crypto spot = 0.
from app.brokerage.fee_profiles import (
    FINANCING_ASSUMPTION_META,
    FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED,
    FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED,
)

FINANCING_BPS_PER_DAY_CFD_ASSUMED = FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED
FINANCING_BPS_PER_DAY_BY_SYMBOL: dict[str, float] = {
    **{s: 0.0 for s in CRYPTO_FRICTION_BPS},
    **{s: FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED for s in OTHER_MARKETS_FRICTION_BPS},
}


def market_financing_bps_per_day(symbol: str, *, direction: str = "LONG") -> float:
    """Overnight financing bps/day for symbol×direction (ASSUMPTION via fee_profiles)."""
    if symbol.endswith("USDT") or symbol in CRYPTO_FRICTION_BPS:
        return 0.0
    if direction == "SHORT":
        return float(FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED)
    if symbol in FINANCING_BPS_PER_DAY_BY_SYMBOL:
        return FINANCING_BPS_PER_DAY_BY_SYMBOL[symbol]
    return float(FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED)

BASELINE_PROFILE: dict[str, Any] = {
    "code": BASELINE_CODE,
    "label": "IchiVol baseline V1 (paper broker)",
    "entry": "pipeline_buy_sell",
    "exit": ["pipeline_flipped", "pipeline_downgraded", "stop_hit", "take_profit_hit", "manual_close"],
    # 2026-09-21 (user decision, research_lab/run_activity.py): more, smaller positions. Same gain in simulation,
    # ~40% more trades, drawdown roughly halved (validation -11% vs -19%) and much smaller loss under adverse costs.
    "risk_pct": 0.005,
    "take_profit_r": 2.0,
    "max_open_positions": 10,
    "max_notional_pct": 0.10,
    "max_open_risk_pct": 0.04,
    "daily_loss_limit_pct": 0.03,
    "one_position_per_symbol": True,
    "one_entry_per_signal_run": True,
    "log_rejections": True,
    "commission_bps": 7.5,  # Binance spot with BNB discount (was 5.0, below the real fee)
    "commission_bps_by_symbol": COMMISSION_BPS_BY_SYMBOL,
    "friction_bps_by_symbol": {**CRYPTO_FRICTION_BPS, **OTHER_MARKETS_FRICTION_BPS},
    "financing_bps_per_day_by_symbol": dict(FINANCING_BPS_PER_DAY_BY_SYMBOL),
    "financing_bps_per_day_crypto": 0.0,
    "financing_bps_per_day_default": FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED,
    "financing_bps_per_day_short_default": FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED,
    "financing_assumption": dict(FINANCING_ASSUMPTION_META),
    "slippage_bps": 3.0,
    "spread_bps": 2.0,
    # 2026-09-21 (user decision, from the research study): no short selling (shorts made most of the losses)
    # and lots are held until stop/target/Ichimoku direction change instead of the first gate downgrade.
    # 2026-10-01 (user decision): shorts allowed again on every Ichimoku paper account (bearish market, nothing
    # traded); applied to the existing accounts' stored profiles the same day. RS-D1 is unaffected.
    "allow_short": True,
    "exit_mode": "direction",
    "require_atr_stop": True,
    "valuation_mode": "USDT_AS_EUR_PROXY",
    "initial_cash_eur": 5000.0,
    # 2026-09-28 (user decision): the automatic strategy trades the 1h background loop only. Viewing or refreshing
    # the screener on another timeframe never opens/closes paper positions. Another timeframe = explicit key here,
    # ideally in a separate profile. (A DB row without the key behaves the same: see engine.auto_timeframes.)
    "auto_timeframes": ["1h"],
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
    # Phase 4 — baseline ignores Fibonacci
    "fibonacci_filter": None,
    "fibonacci_confluence_atr_mult": 0.5,
    "fibonacci_require_key_level": True,
    "fibonacci_require_impulse_align": True,
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

# --- Phase 4 Fibonacci (Portfolio F) ---
ICHIVOL_MS_FIB = _with(
    code="ICHIVOL_MS_FIB",
    label="IchiVol + Market Structure + Fibonacci confluence",
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp", "trendln"],
    fibonacci_filter="require_confluence",
    fibonacci_require_key_level=True,
    fibonacci_require_impulse_align=True,
    shadow_on_block=True,
)

# --- Forward test (docs/PLAN-SUIVI-EN-AVANT-2026-09-20.md): frozen for >= 8 weeks -----------------
# Per-side friction (bps) per Binance spot pair: half tick + liquidity-tier slippage. The slippage tier is an
# ASSUMPTION (not measured), see docs/REVUE-SIM-ET-COUTS-ichivol-36-2026-09-20.md. Commission 7.5 bps = spot
# fee with BNB discount. Unlisted symbols fall back to the profile spread/slippage.
FWD_FRICTION_BPS_BY_SYMBOL: dict[str, float] = {
    "PEPEUSDT": 14.6, "APTUSDT": 10.9, "DOTUSDT": 8.5, "OPUSDT": 8.0, "TONUSDT": 7.1, "ATOMUSDT": 6.9,
    "ARBUSDT": 6.5, "ADAUSDT": 4.2, "NEARUSDT": 3.3, "LTCUSDT": 2.9, "SUIUSDT": 2.6, "UNIUSDT": 2.6,
    "AVAXUSDT": 2.4, "LINKUSDT": 2.4, "DOGEUSDT": 1.6, "SOLUSDT": 1.5, "XRPUSDT": 1.4,
    "BNBUSDT": 1.0, "ETHUSDT": 1.0, "BTCUSDT": 1.0,
}
_FWD_COMMON: dict[str, Any] = dict(
    commission_bps=7.5,
    commission_bps_by_symbol={},
    friction_bps_by_symbol=FWD_FRICTION_BPS_BY_SYMBOL,
    log_rejections=True,
    one_position_per_symbol=True,
    one_entry_per_signal_run=True,
    max_open_risk_pct=0.04,
    max_symbol_notional_pct=0.25,
    daily_loss_limit_pct=0.03,
    shadow_on_block=False,
)

FWD_A_REF = _with(
    code="FWD_A_REF",
    label="Forward test - A reference (closed candles, one lot/symbol, aggregate guards, long+short)",
    allow_short=True,
    exit_mode="decision",
    **_FWD_COMMON,
)

FWD_A_LONG = _with(
    code="FWD_A_LONG",
    label="Forward test - A long-only (exit on decision, shorts never opened)",
    allow_short=False,
    exit_mode="decision",
    **_FWD_COMMON,
)

FWD_E_LONG = _with(
    code="FWD_E_LONG",
    label="Forward test - E long-only (exit on Ichimoku direction change, shorts never opened)",
    allow_short=False,
    exit_mode="direction",
    **_FWD_COMMON,
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
    ICHIVOL_MS_FIB["code"]: ICHIVOL_MS_FIB,
    FWD_A_REF["code"]: FWD_A_REF,
    FWD_A_LONG["code"]: FWD_A_LONG,
    FWD_E_LONG["code"]: FWD_E_LONG,
}

# --- RS-D1 paper live (docs/RS-09-RS-D1-PAPER-DESIGN.md) -------------------------------------------------
# Separate account driven only by app/paper/rs_d1_runner.py (rules = rs/book.py, RS-03). Never synced by the
# Ichimoku loop, no manual orders, no T0-MANAGE keys (the protection monitor only enforces its stop).
RS_D1_CODE = "RS_D1_PAPER_V1"
RS_D1_PROFILE: dict[str, Any] = {
    "code": RS_D1_CODE,
    "label": "RS-D1 — validé 2025, holdout 2026 non ouvert",
    "engine": "rs_d1",
    "rules": "docs/RS-03-DONCHIAN-4H-SPEC.md",
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "timeframe": "4h",
    "initial_cash_eur": 5000.0,
    "valuation_mode": "USDT_AS_EUR_PROXY",
    "allow_short": False,
    "risk_pct": 0.005,
    "max_notional_pct": 0.10,
    "max_open_risk_pct": 0.04,
    "daily_loss_limit_pct": 0.03,
    "min_fill_fraction": 0.25,
    "min_notional": 10.0,
    "max_open_positions": 10,
    # RS-03 §6 paper costs: commission 7.5 bps + per-side friction per symbol (== FWD table values).
    "commission_bps": 7.5,
    "commission_bps_by_symbol": {},
    "friction_bps_by_symbol": {"BTCUSDT": 1.0, "ETHUSDT": 1.0, "SOLUSDT": 1.5},
    "financing_bps_per_day_crypto": 0.0,
    "auto_timeframes": [],
    "sync_auto": False,
    "manual_orders": False,
}

# --- Parallel paper accounts (2026-10-01, user decision: "faut que ça bouge") ------------------------------
# Same rules as the baseline, ONE difference each, run side by side so the baseline stays the untouched
# reference: they only add measurement (paper only, virtual cash), they never change the baseline's trades.
# - SHORTS: shorts allowed (the 2026-09-21 ban came from the research study; this measures it live).
# - 4H: the automatic loop on 4h candles instead of 1h (longs only).
# - WIDE: 1h, longs only, on the baseline universe + WIDE_EXTRA_SYMBOLS (liquid Binance spot pairs).
WIDE_EXTRA_SYMBOLS: tuple[str, ...] = (
    # Binance spot, 24h quote volume >= 7 M USDT checked on 2026-10-01 (RENDERUSDT left out: ~5 M).
    "TRXUSDT", "BCHUSDT", "ETCUSDT", "FILUSDT", "INJUSDT", "AAVEUSDT",
    "HBARUSDT", "ICPUSDT", "SEIUSDT", "XLMUSDT", "TIAUSDT",
)

SHORTS_CODE = "ICHIVOL_SHORTS_V1"
H4_CODE = "ICHIVOL_4H_V1"
WIDE_CODE = "ICHIVOL_WIDE_V1"

PARALLEL_PROFILES: dict[str, dict[str, Any]] = {
    SHORTS_CODE: _with(
        code=SHORTS_CODE,
        label="Baseline + shorts (paper parallèle)",
        allow_short=True,
    ),
    H4_CODE: _with(
        code=H4_CODE,
        label="Baseline en 4h (paper parallèle)",
        auto_timeframes=["4h"],
    ),
    WIDE_CODE: _with(
        code=WIDE_CODE,
        label="Baseline univers élargi (paper parallèle)",
        universe="wide",
    ),
}

ALL_PROFILES: dict[str, dict[str, Any]] = {
    BASELINE_CODE: BASELINE_PROFILE,
    **EXPERIMENTAL_PROFILES,
    **PARALLEL_PROFILES,
    RS_D1_CODE: RS_D1_PROFILE,
}


def wants_wide_universe(profile: dict[str, Any] | None) -> bool:
    return (profile or {}).get("universe") == "wide"


def is_rs_engine(profile: dict[str, Any] | None) -> bool:
    """True for portfolios driven by the RS runner (no Ichimoku sync, no manual orders, no TP)."""
    return bool(profile) and profile.get("engine") == "rs_d1"


def profile_for(code: str) -> dict[str, Any]:
    if code in ALL_PROFILES:
        return deepcopy(ALL_PROFILES[code])
    return deepcopy(BASELINE_PROFILE) | {"code": code}


# 2026-09-20: everything was reset to a single virtual portfolio (one account, one lot per symbol).
# The experimental profiles above stay registered as definitions but are no longer seeded or synced.
# 2026-10-01: the PARALLEL_PROFILES are synced next to the baseline (each its own account and cash).
SINGLE_PORTFOLIO_MODE = True


def syncable_profile_codes() -> list[str]:
    """Codes that receive auto_watchlist sync (baseline first: it stays the funnel/reference account)."""
    if SINGLE_PORTFOLIO_MODE:
        return [BASELINE_CODE, *PARALLEL_PROFILES]
    return [
        code
        for code, profile in ALL_PROFILES.items()
        if profile.get("sync_auto", True)
    ]
