"""Frozen strategy profiles for paper portfolios.

ICHIVOL_BASELINE_V1 freezes current pipeline entry/exit rules and MUST NOT
gain Market Structure or Context gates. Experimental portfolios run in
parallel (docs/ARCHITECTURE-CONSOLIDEE-V2.md).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.sessions.decision_windows import DEFAULT_DECISION_WINDOWS

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
    "allow_short": False,
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

# Baseline rules, but the signal only opens / closes at the 1h candles tied to the Tokyo / London / New York
# opens and closes (app/sessions/decision_windows.py). Stop / target stay watched every minute.
SESSIONS_CODE = "ICHIVOL_SESSIONS_V1"
ICHIVOL_SESSIONS_V1 = _with(
    code=SESSIONS_CODE,
    label="Baseline - decisions only at Tokyo / London / New York opens and closes",
    decision_windows=list(DEFAULT_DECISION_WINDOWS),
)

# 2026-10-07 (user decision): a dedicated account for three markets -- YM (E-mini Dow), MGC (Micro Gold) and
# BTC (spot / perpetual / CME, configurable) -- next to the existing universe, never replacing it. Baseline entry
# and exit rules on the 1h loop; only its own markets (app/paper/futures_crypto.py). The global open-risk cap is
# what stops YM + gold + BTC from all carrying a full-size position at once: 1 % of capital in total for 0.5 %
# per trade, so at most two full-risk positions, the third is refused ("open_risk_cap") until one closes.
from app.paper import futures_crypto as _fc

FUTURES_CRYPTO_CODE = _fc.FUTURES_CRYPTO_CODE
FUTURES_CRYPTO_V1 = _with(
    code=FUTURES_CRYPTO_CODE,
    label=_fc.FUTURES_CRYPTO_LABEL,
    dedicated_markets=True,
    btc_mode=_fc.DEFAULT_BTC_MODE,
    max_open_positions=3,
    # No leverage in the paper broker (notional comes out of cash): 30 % of capital per market at most.
    max_notional_pct=0.30,
    max_open_risk_pct=0.01,
    commission_bps_by_symbol=dict(_fc.COMMISSION_BPS),
    friction_bps_by_symbol=dict(_fc.FRICTION_BPS),
    financing_bps_per_day_by_symbol=dict(_fc.FINANCING_BPS_LONG),
    financing_bps_per_day_short_by_symbol=dict(_fc.FINANCING_BPS_SHORT),
    financing_bps_per_day_default=0.0,
    financing_bps_per_day_short_default=0.0,
)

EXPERIMENTAL_PROFILES: dict[str, dict[str, Any]] = {
    ICHIVOL_SESSIONS_V1["code"]: ICHIVOL_SESSIONS_V1,
    FUTURES_CRYPTO_V1["code"]: FUTURES_CRYPTO_V1,
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

# --- Parallel paper accounts (2026-10-01, user decision: "faut que ça bouge"; back in main 2026-10-17) ------
# Same rules as the baseline, ONE difference each, run side by side so the baseline stays the untouched
# reference: they only add measurement (paper only, virtual cash), they never change the baseline's trades.
# - SHORTS: shorts allowed (the 2026-09-21 ban came from the research study; this measures it live).
# - 4H: the automatic loop on 4h candles instead of 1h (longs only).
# - WIDE: 1h, longs only, on the baseline universe + WIDE_EXTRA_SYMBOLS (liquid Binance spot pairs).
# - COMBO (2026-10-17, user decision): every confirmation filter stacked on the baseline signal -- market structure,
#   Fibonacci confluence, RSI, CMF/OBV flow and hard ATR regime. Downgrade only: a filter can refuse a trade, never
#   create one. Refused trades are followed as shadows so we can see what each filter cost or saved.
# They first ran from an unmerged branch (2026-10-01); once main was deployed they kept their DB rows but nothing
# synced them any more. An existing account keeps the profile stored in its row (ensure_portfolio never rewrites it).
WIDE_EXTRA_SYMBOLS: tuple[str, ...] = (
    # Binance spot, 24h quote volume >= 7 M USDT checked on 2026-10-01 (RENDERUSDT left out: ~5 M).
    "TRXUSDT", "BCHUSDT", "ETCUSDT", "FILUSDT", "INJUSDT", "AAVEUSDT",
    "HBARUSDT", "ICPUSDT", "SEIUSDT", "XLMUSDT", "TIAUSDT",
)

SHORTS_CODE = "ICHIVOL_SHORTS_V1"
H4_CODE = "ICHIVOL_4H_V1"
WIDE_CODE = "ICHIVOL_WIDE_V1"
COMBO_CODE = "ICHIVOL_COMBO_V1"

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
    COMBO_CODE: _with(
        code=COMBO_CODE,
        label="Tout combiné : Ichimoku + structure + Fibonacci + RSI/flux (paper parallèle)",
        structure_filter="block_near_opposing",
        structure_detectors=["mvpp", "trendln"],
        fibonacci_filter="require_confluence",
        context_rsi=True,
        context_cmf=True,
        context_obv=True,
        context_regime_hard=True,
        shadow_on_block=True,
    ),
}

ALL_PROFILES: dict[str, dict[str, Any]] = {
    BASELINE_CODE: BASELINE_PROFILE,
    **EXPERIMENTAL_PROFILES,
    **PARALLEL_PROFILES,
    RS_D1_CODE: RS_D1_PROFILE,
}


def wants_wide_universe(profile: dict[str, Any] | None) -> bool:
    return (profile or {}).get("universe") in ("wide", "main")


def explicit_universe(profile: dict[str, Any] | None) -> list[str] | None:
    """Liste explicite des symboles d'un profil (portefeuille unique), ou None (anciens profils)."""
    syms = (profile or {}).get("universe_symbols")
    return list(syms) if isinstance(syms, (list, tuple)) else None


def is_rs_engine(profile: dict[str, Any] | None) -> bool:
    """True for portfolios driven by the RS runner (no Ichimoku sync, no manual orders, no TP)."""
    return bool(profile) and profile.get("engine") == "rs_d1"


def profile_for(code: str) -> dict[str, Any]:
    if code in ALL_PROFILES:
        return deepcopy(ALL_PROFILES[code])
    return deepcopy(BASELINE_PROFILE) | {"code": code}


# =========================================================================================================
# 2026-10-27 (décision du propriétaire) : UN SEUL portefeuille paper, ICHIVOL_MAIN_V1, 50 000 € virtuels.
# « On vire tous les portefeuilles et on part sur un nouveau seul portefeuille qui trade tout. »
# Les huit anciens comptes (RETIRED_CODES) ne sont plus jamais créés, synchronisés ni affichés ; leurs données
# sont sauvegardées puis supprimées par scripts/repairs/2026-10-27_portefeuille_unique_suppression_anciens.sql.
# Toute la technologie IchiVol travaille pour ce compte : scan 1h (Ichimoku × RVOL), Ève + JEV (autopilote),
# ordres manuels ; les filtres structure / Fibonacci / RSI / flux / régime et les fenêtres de sessions, qui
# n'existaient que dans des comptes retirés, tournent ici en OBSERVATION (calculés et enregistrés sur chaque
# signal, ils ne refusent rien tant qu'aucun avantage n'est démontré). Doc : docs/PORTEFEUILLE-UNIQUE-2026-10-27.md.
# =========================================================================================================
MAIN_CODE = "ICHIVOL_MAIN_V1"
MAIN_LABEL = "IchiVol — portefeuille unique (50 000 €)"
MAIN_INITIAL_CASH_EUR = 50_000.0

RETIRED_CODES: tuple[str, ...] = (
    BASELINE_CODE, H4_CODE, WIDE_CODE, SHORTS_CODE, SESSIONS_CODE, COMBO_CODE, RS_D1_CODE, FUTURES_CRYPTO_CODE,
)

# Hypothèses de friction par côté (bps) pour les paires de l'univers élargi : AUCUNE n'est mesurée. Valeurs
# volontairement plus prudentes que les grandes paires (volume 24 h >= 7 M USDT relevé le 2026-10-01, carnet plus
# mince) : rangées comme les paires de même liquidité du tableau CRYPTO_FRICTION_BPS. À vérifier sur fills réels.
WIDE_FRICTION_BPS_ASSUMED: dict[str, float] = {
    "TRXUSDT": 3.0, "BCHUSDT": 4.0, "XLMUSDT": 4.0, "ETCUSDT": 5.0, "AAVEUSDT": 5.0, "FILUSDT": 6.0,
    "HBARUSDT": 6.0, "INJUSDT": 7.0, "ICPUSDT": 7.0, "SEIUSDT": 8.0, "TIAUSDT": 8.0,
}
# Futures : seul YM rejoint le compte (aucun autre instrument de l'univers ne suit le Dow Jones). Coûts =
# hypothèses de app/paper/futures_crypto.py. MGC (même cotation que XAUUSD), BTCPERP et BTCCME (même sous-jacent
# que BTCUSDT, déjà tradé en spot avec un vrai volume) sont exclus : ce serait deux lots sur le même prix.
MAIN_FUTURES_SYMBOLS: tuple[str, ...] = ("YM",)

# Règle de liquidité minimale (deux niveaux) :
# 1. statique (univers) : un instrument n'entre que s'il a une friction documentée et <= MAIN_MAX_FRICTION_BPS
#    par côté (coût aller-retour max ~ 2 x 12 + 2 x 7,5 = 39 bps en crypto) ; sinon il est exclu, avec la raison ;
# 2. dynamique (boucle 1h) : une paire crypto à volume réel (Binance) n'ouvre rien si son volume des dernières
#    24 h est < MAIN_MIN_QUOTE_VOLUME_24H (en USDT). Les CFD (volume de ticks, pas d'échange) sautent ce contrôle.
MAIN_MAX_FRICTION_BPS = 12.0
MAIN_MIN_QUOTE_VOLUME_24H = 5_000_000.0


def _main_candidates() -> list[str]:
    from app.universe.catalog import default_watchlist

    out: list[str] = []
    for s in [*default_watchlist(), *WIDE_EXTRA_SYMBOLS, *MAIN_FUTURES_SYMBOLS]:
        if s not in out:
            out.append(s)
    return out


MAIN_FRICTION_BPS: dict[str, float] = {
    **CRYPTO_FRICTION_BPS,
    **WIDE_FRICTION_BPS_ASSUMED,
    **OTHER_MARKETS_FRICTION_BPS,
    **{s: _fc.FRICTION_BPS[s] for s in MAIN_FUTURES_SYMBOLS},
}
MAIN_COMMISSION_BPS_BY_SYMBOL: dict[str, float] = {
    **COMMISSION_BPS_BY_SYMBOL,
    **{s: _fc.COMMISSION_BPS[s] for s in MAIN_FUTURES_SYMBOLS},
}
MAIN_FINANCING_BPS_LONG: dict[str, float] = {
    **FINANCING_BPS_PER_DAY_BY_SYMBOL,
    **{s: 0.0 for s in WIDE_FRICTION_BPS_ASSUMED},
    **{s: _fc.FINANCING_BPS_LONG[s] for s in MAIN_FUTURES_SYMBOLS},
}

# Symboles que le moteur sait voir mais que le compte ne trade pas, avec la raison (affichée et documentée).
STRUCTURAL_EXCLUSIONS: dict[str, str] = {
    "USDJPY": "coté en JPY : aucune conversion de devise de cotation, la taille serait fausse",
    "AAPL": "actions Twelve Data : quota gratuit trop faible pour la boucle de fond",
    "TSLA": "actions Twelve Data : quota gratuit trop faible pour la boucle de fond",
    "MGC": "même cotation que XAUUSD (or spot) : double exposition au même prix",
    "BTCPERP": "même sous-jacent que BTCUSDT (déjà tradé en spot) : double exposition",
    "BTCCME": "aucun flux CME : cotation BTCUSDT spot, double exposition",
}


def liquidity_exclusion(symbol: str, friction: dict[str, float] | None = None,
                        max_bps: float = MAIN_MAX_FRICTION_BPS) -> str | None:
    """Raison d'exclusion par la règle statique de liquidité, ou None si l'instrument passe."""
    table = MAIN_FRICTION_BPS if friction is None else friction
    if symbol not in table:
        return "aucune friction documentée : coût inconnu, refusé par prudence"
    if float(table[symbol]) > max_bps:
        return f"friction {table[symbol]:g} bps par côté > {max_bps:g} bps (règle de liquidité)"
    return None


def main_universe() -> tuple[list[str], dict[str, str]]:
    """(symboles tradés, {symbole exclu: raison}) du portefeuille unique."""
    traded: list[str] = []
    excluded: dict[str, str] = dict(STRUCTURAL_EXCLUSIONS)
    for s in _main_candidates():
        if s in STRUCTURAL_EXCLUSIONS:
            continue
        why = liquidity_exclusion(s)
        if why is None:
            traded.append(s)
        else:
            excluded[s] = why
    return traded, excluded


_MAIN_TRADED, _MAIN_EXCLUDED = main_universe()

MAIN_PROFILE: dict[str, Any] = _with(
    code=MAIN_CODE,
    label=MAIN_LABEL,
    initial_cash_eur=MAIN_INITIAL_CASH_EUR,
    # Taille : 0,5 % du capital risqué par trade (250 € au départ), lot plafonné à 10 % du capital (5 000 €),
    # 10 lots au plus, risque ouvert total <= 4 % (2 000 €), arrêt des entrées à -3 % sur la journée.
    risk_pct=0.005,
    max_notional_pct=0.10,
    max_symbol_notional_pct=0.10,
    max_open_positions=10,
    max_open_risk_pct=0.04,
    daily_loss_limit_pct=0.03,
    take_profit_r=2.0,
    one_position_per_symbol=True,
    one_entry_per_signal_run=True,
    min_notional=50.0,
    # Pas de vente à découvert (aucun compte n'a montré d'avantage en short ; à valider par le propriétaire).
    allow_short=False,
    exit_mode="direction",
    auto_timeframes=["1h"],
    # Univers explicite : tout ce que le moteur sait trader, moins les exclusions documentées.
    universe="main",
    universe_symbols=list(_MAIN_TRADED),
    universe_exclusions=dict(_MAIN_EXCLUDED),
    max_friction_bps=MAIN_MAX_FRICTION_BPS,
    min_quote_volume_24h=MAIN_MIN_QUOTE_VOLUME_24H,
    # Coûts réalistes par classe (hypothèses documentées) : crypto spot 7,5 bps de commission + friction par
    # paire ; CFD forex / métaux / indices / pétrole : spread seul + financement de nuit ; YM : coûts futures.
    commission_bps=7.5,
    commission_bps_by_symbol=MAIN_COMMISSION_BPS_BY_SYMBOL,
    friction_bps_by_symbol=MAIN_FRICTION_BPS,
    financing_bps_per_day_by_symbol=MAIN_FINANCING_BPS_LONG,
    # Filtres de confirmation (structure MVPP + trendln, Fibonacci, RSI, CMF/OBV, régime ATR) et fenêtres de
    # sessions : calculés sur chaque signal et enregistrés, en observation seulement (filters_mode="observe").
    structure_filter="block_near_opposing",
    structure_detectors=["mvpp", "trendln"],
    fibonacci_filter="require_confluence",
    context_rsi=True,
    context_cmf=True,
    context_obv=True,
    context_regime_hard=True,
    filters_mode="observe",
    shadow_on_block=False,
    decision_windows=list(DEFAULT_DECISION_WINDOWS),
    decision_windows_mode="observe",
    # Qui décide pour ce compte (informatif) et règle d'arbitrage (appliquée par app/paper/engine.py).
    engines=["scan_1h_ichimoku_rvol", "eve_autopilot_jev", "ordres_manuels"],
    arbitration="un_lot_par_symbole_premier_arrive",
    # Emplacement réservé du futur indicateur VWAP (plan d'intégration rendu par la recherche VWAP) : il
    # s'ajoutera comme un filtre de plus dans la chaîne structure -> Fibonacci -> contexte d'engine.py, d'abord
    # en observation. Aucune clé n'est lue tant qu'il n'existe pas.
    sync_auto=True,
    manual_orders=True,
)

ALL_PROFILES[MAIN_CODE] = MAIN_PROFILE

# Un seul compte synchronisé. Les définitions des anciens profils restent dans ce fichier (lecture de
# l'historique, backtests), mais aucun n'est plus créé ni synchronisé.
SINGLE_PORTFOLIO_MODE = True
PARALLEL_SYNCED_CODES: tuple[str, ...] = ()
DEFAULT_PORTFOLIO_CODE = MAIN_CODE


def is_retired(code: str | None) -> bool:
    return bool(code) and code in RETIRED_CODES


def syncable_profile_codes() -> list[str]:
    """Codes that receive auto_watchlist sync: the single portfolio only (2026-10-27)."""
    return [MAIN_CODE]
