"""ATR helpers for zone / touch tolerances (no new deps)."""

from __future__ import annotations

from typing import Sequence

from app.indicators.atr import AtrParams
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY


def last_atr(candles: Sequence[Candle], period: int = 14) -> float | None:
    if len(candles) < 2:
        return None
    states = REGISTRY.compute("atr", candles, AtrParams(period=period))
    for state in reversed(states):
        if state.atr is not None and state.atr > 0:
            return float(state.atr)
    return None


def touch_tolerance(atr: float | None, atr_mult: float, price_fallback: float) -> float:
    if atr is not None and atr > 0:
        return atr * atr_mult
    return max(price_fallback * 0.01, 1e-9)
