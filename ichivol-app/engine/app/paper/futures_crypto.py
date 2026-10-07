"""Futures & Crypto paper portfolio: YM (E-mini Dow), MGC (Micro Gold) and BTC.

A dedicated account next to the baseline (which stays the frozen reference): it trades only its own three
markets, with the baseline's Ichimoku x RVOL rules on the 1h background loop, and a global open-risk cap so
the three markets can never all carry a full-size position at once.

BTC is configurable because the instrument is not the same depending on the data source and the broker:

- ``spot``: Binance spot BTCUSDT (real exchange volume, minute-level stop monitoring).
- ``perpetual``: Binance USD-M BTCUSDT perpetual (its own candles; funding charged as an assumption).
- ``cme``: CME Micro Bitcoin (MBT, 0.1 BTC). No free CME feed is wired: prices come from Binance spot BTCUSDT,
  so the CME basis is NOT in the P&L. Said in every payload that shows it.

YM and MGC have no free futures feed either: YM is priced from the Dow Jones CFD (biquote US30), MGC from spot
gold (biquote XAUUSD). Contract sizes are real CME specs; paper quantities stay fractional (a real account
needs whole contracts, see ``contracts_for``).

All costs below are ASSUMPTIONS (typical retail futures / exchange fees), not measured fills.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Mapping

FUTURES_CRYPTO_CODE = "FUTURES_CRYPTO_V1"
FUTURES_CRYPTO_LABEL = "Futures & Crypto — YM, MGC, BTC"

BTC_MODES: tuple[str, ...] = ("spot", "perpetual", "cme")
DEFAULT_BTC_MODE = "spot"

# One entry per market slot of the portfolio. ``symbol`` is the IchiVol instrument id the paper broker trades
# (app/universe/catalog.py); ``contract_size`` is the CME / venue unit in the instrument's own quantity unit.
MARKETS: dict[str, dict[str, Any]] = {
    "YM": {
        "slot": "YM",
        "symbol": "YM",
        "name": "E-mini Dow Jones",
        "venue": "CME (CBOT)",
        "contract": "YM",
        "contract_size": 5.0,
        "contract_unit": "5 $ par point de l'indice Dow Jones",
        "price_source": "biquote US30 (CFD Dow Jones)",
        "price_note": "Pas de flux futures gratuit : le cours est celui du CFD Dow Jones, pas du contrat YM. "
        "L'écart de base (quelques dizaines de points) n'est pas dans le P&L.",
    },
    "MGC": {
        "slot": "MGC",
        "symbol": "MGC",
        "name": "Micro Gold",
        "venue": "CME (COMEX)",
        "contract": "MGC",
        "contract_size": 10.0,
        "contract_unit": "10 onces troy d'or",
        "price_source": "biquote XAUUSD (or spot)",
        "price_note": "Pas de flux futures gratuit : le cours est celui de l'or spot, pas du contrat MGC. "
        "L'écart de base (portage) n'est pas dans le P&L.",
    },
}

BTC_VARIANTS: dict[str, dict[str, Any]] = {
    "spot": {
        "slot": "BTC",
        "mode": "spot",
        "symbol": "BTCUSDT",
        "name": "Bitcoin spot",
        "venue": "Binance spot",
        "contract": "BTCUSDT",
        "contract_size": 1.0,
        "contract_unit": "1 BTC",
        "price_source": "Binance spot BTCUSDT",
        "price_note": "Cours et volume réels de Binance spot. Stop et objectif surveillés à la minute.",
    },
    "perpetual": {
        "slot": "BTC",
        "mode": "perpetual",
        "symbol": "BTCPERP",
        "name": "Bitcoin perpétuel",
        "venue": "Binance USDⓈ-M",
        "contract": "BTCUSDT perpétuel",
        "contract_size": 1.0,
        "contract_unit": "1 BTC",
        "price_source": "Binance USDⓈ-M BTCUSDT perpétuel",
        "price_note": "Bougies du perpétuel lui-même. Le funding est simulé par une hypothèse fixe "
        "(3 pb par jour payés en achat), pas par le taux réel.",
    },
    "cme": {
        "slot": "BTC",
        "mode": "cme",
        "symbol": "BTCCME",
        "name": "Micro Bitcoin CME",
        "venue": "CME",
        "contract": "MBT",
        "contract_size": 0.1,
        "contract_unit": "0,1 BTC",
        "price_source": "Binance spot BTCUSDT (pas de flux CME branché)",
        "price_note": "Aucun flux CME gratuit n'est branché : le cours est celui de BTC spot. La prime ou "
        "décote du contrat CME (souvent 0,5 à 2 %) n'est pas dans le P&L.",
    },
}

# Per-side friction (half spread + slippage) and commission, bps — ASSUMPTIONS.
FRICTION_BPS: dict[str, float] = {"YM": 0.5, "MGC": 1.0, "BTCUSDT": 1.0, "BTCPERP": 1.0, "BTCCME": 1.5}
COMMISSION_BPS: dict[str, float] = {"YM": 0.1, "MGC": 0.3, "BTCUSDT": 7.5, "BTCPERP": 5.0, "BTCCME": 2.0}
# Futures carry no overnight swap (the carry is in the futures price). Perpetual: funding assumption of
# 1 bp per 8h paid by longs (received by shorts).
FINANCING_BPS_LONG: dict[str, float] = {"YM": 0.0, "MGC": 0.0, "BTCUSDT": 0.0, "BTCPERP": 3.0, "BTCCME": 0.0}
FINANCING_BPS_SHORT: dict[str, float] = {"YM": 0.0, "MGC": 0.0, "BTCUSDT": 0.0, "BTCPERP": -3.0, "BTCCME": 0.0}

# Every instrument id this portfolio may ever hold (any BTC mode).
ALL_SYMBOLS: frozenset[str] = frozenset(
    [m["symbol"] for m in MARKETS.values()] + [v["symbol"] for v in BTC_VARIANTS.values()]
)


def is_dedicated(profile: Mapping[str, Any] | None) -> bool:
    """True for a portfolio that trades its own market list instead of the shared watchlist."""
    return bool(profile) and bool(profile.get("dedicated_markets"))


def btc_mode(profile: Mapping[str, Any] | None) -> str:
    mode = str((profile or {}).get("btc_mode") or DEFAULT_BTC_MODE)
    return mode if mode in BTC_MODES else DEFAULT_BTC_MODE


def markets_for(profile: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The three market slots, BTC resolved to the configured mode."""
    return [dict(MARKETS["YM"]), dict(MARKETS["MGC"]), dict(BTC_VARIANTS[btc_mode(profile)])]


def traded_symbols(profile: Mapping[str, Any] | None) -> list[str]:
    return [m["symbol"] for m in markets_for(profile)]


def market_for_symbol(symbol: str) -> dict[str, Any] | None:
    for m in MARKETS.values():
        if m["symbol"] == symbol:
            return dict(m)
    for v in BTC_VARIANTS.values():
        if v["symbol"] == symbol:
            return dict(v)
    return None


def contracts_for(symbol: str, qty: float | None) -> float | None:
    """Paper quantity expressed in exchange contracts (fractional: a real account needs whole contracts)."""
    m = market_for_symbol(symbol)
    if m is None or qty is None:
        return None
    return abs(float(qty)) / float(m["contract_size"])


def with_btc_mode(profile: Mapping[str, Any], mode: str) -> dict[str, Any]:
    if mode not in BTC_MODES:
        raise ValueError(f"unknown_btc_mode: {mode}")
    out = dict(profile)
    out["btc_mode"] = mode
    return out


# Last verdict the 1h loop handed to this portfolio, per market (what the paper strategy actually acted on:
# the pipeline gate, not the combiner badge). In-process, so empty after an engine restart until the next cycle.
_LAST_SEEN: dict[str, dict[str, Any]] = {}
_LAST_SEEN_LOCK = threading.Lock()


def _enum(v: Any) -> Any:
    return getattr(v, "value", v)


def remember_signal(row: Any, pipeline: Any, *, action: str | None) -> None:
    stages = [
        {
            "id": _enum(getattr(st, "id", None)),
            "status": _enum(getattr(st, "status", None)),
            "summary": getattr(st, "summary", None),
        }
        for st in (getattr(pipeline, "stages", None) or [])
    ]
    timing = getattr(row, "signal_timing", None) or {}
    bar_close = timing.get("signal_bar_close")
    snap = {
        "decision": getattr(pipeline, "decision", None),
        "direction": _enum(getattr(pipeline, "direction", None)),
        "price": getattr(row, "price", None),
        "timeframe": getattr(row, "timeframe", None),
        "bar_close": datetime.fromtimestamp(int(bar_close), timezone.utc).isoformat() if bar_close else None,
        "seen_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
        "action": action,
    }
    with _LAST_SEEN_LOCK:
        _LAST_SEEN[str(row.symbol)] = snap


def last_signal(symbol: str) -> dict[str, Any] | None:
    with _LAST_SEEN_LOCK:
        hit = _LAST_SEEN.get(symbol)
        return dict(hit) if hit is not None else None


def clear_signals() -> None:
    with _LAST_SEEN_LOCK:
        _LAST_SEEN.clear()
