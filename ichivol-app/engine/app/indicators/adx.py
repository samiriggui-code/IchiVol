"""Average Directional Index (ADX) -- V3 experimental candidate
(docs/METHODS-ROADMAP.md: "ADX | Force de tendance ? | Filtre régime |
V3/test | OHLCV | garder seulement si backtest prouve un edge"). Same
question as ATR ("Régime" -- tradable? choppy? trending?), never LONG/SHORT
(docs/METHODS-ROADMAP.md §6 rule 3: "ATR / ADX / Wyckoff ne votent jamais").

This module is deliberately NOT wired into the live pipeline's decision by
default -- app/backtest/experiments.py has a PIPELINE_ADX_FILTER variant
that backtests "does gating entries on ADX trend strength actually help"
before this earns a permanent seat next to ATR (the CDC's own rule: prove
it, don't assume it, same as CVD/OI/Funding and the RVOL/ATR recalibration
earlier).

Standard Wilder (1978) formula, no shortcuts:
  TR, +DM, -DM per bar -> Wilder-smoothed (running EMA-like recursion,
  first value = a plain sum over `period` bars) -> +DI/-DI -> DX ->
  ADX = Wilder-smoothed DX. Entirely a running-state recursion (each step
  depends only on the previous smoothed value and the current bar), so it
  is causal by construction -- see tests/indicators/test_adx_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class TrendStrength(str, Enum):
    ABSENT = "ABSENT"
    DEVELOPING = "DEVELOPING"
    TRENDING = "TRENDING"
    STRONG = "STRONG"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AdxParams:
    period: int = 14
    weak_threshold: float = 20.0
    """ADX below this -> ABSENT (no real trend, classic chop zone)."""
    trending_threshold: float = 25.0
    """Wilder's own classic cutoff for "a trend exists"."""
    strong_threshold: float = 40.0
    """ADX at or above this -> STRONG."""


@dataclass(frozen=True)
class AdxState:
    time: int
    plus_di: float | None
    minus_di: float | None
    adx: float | None
    strength: TrendStrength


def _classify(adx_value: float, params: AdxParams) -> TrendStrength:
    if adx_value < params.weak_threshold:
        return TrendStrength.ABSENT
    if adx_value < params.trending_threshold:
        return TrendStrength.DEVELOPING
    if adx_value < params.strong_threshold:
        return TrendStrength.TRENDING
    return TrendStrength.STRONG


def compute_adx(candles: Sequence[Candle], params: AdxParams = AdxParams()) -> list[AdxState]:
    period = params.period
    out: list[AdxState] = []

    tr_buffer: list[float] = []
    plus_dm_buffer: list[float] = []
    minus_dm_buffer: list[float] = []
    dx_values: list[float] = []

    smoothed_tr: float | None = None
    smoothed_plus_dm: float | None = None
    smoothed_minus_dm: float | None = None
    adx_smoothed: float | None = None

    prev_high = prev_low = prev_close = None

    for i, c in enumerate(candles):
        if i == 0:
            tr = c.high - c.low
            plus_dm = 0.0
            minus_dm = 0.0
        else:
            tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
            up_move = c.high - prev_high
            down_move = prev_low - c.low
            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        prev_high, prev_low, prev_close = c.high, c.low, c.close

        if smoothed_tr is None:
            tr_buffer.append(tr)
            plus_dm_buffer.append(plus_dm)
            minus_dm_buffer.append(minus_dm)
            if len(tr_buffer) < period:
                out.append(AdxState(c.time, None, None, None, TrendStrength.UNKNOWN))
                continue
            smoothed_tr = sum(tr_buffer)
            smoothed_plus_dm = sum(plus_dm_buffer)
            smoothed_minus_dm = sum(minus_dm_buffer)
        else:
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm

        plus_di = 100 * smoothed_plus_dm / smoothed_tr if smoothed_tr > 0 else 0.0
        minus_di = 100 * smoothed_minus_dm / smoothed_tr if smoothed_tr > 0 else 0.0
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0

        if adx_smoothed is None:
            dx_values.append(dx)
            if len(dx_values) < period:
                out.append(AdxState(c.time, plus_di, minus_di, None, TrendStrength.UNKNOWN))
                continue
            adx_smoothed = sum(dx_values) / period
        else:
            adx_smoothed = (adx_smoothed * (period - 1) + dx) / period

        out.append(AdxState(c.time, plus_di, minus_di, adx_smoothed, _classify(adx_smoothed, params)))

    return out
