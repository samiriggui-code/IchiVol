"""Average True Range and volatility regime. Mission realignment
(docs/METHODS-ROADMAP.md §4 step 4): ATR answers "Regime" (tradable? dead?
extreme?) and "Risk" (stop/size hint) -- it never votes LONG/SHORT
(docs/TRADING_ARCHITECTURE_V2.md §7 rule 4).

Regime is judged relative to the instrument's *own* recent history (a
percentile rank of current ATR within a trailing window), not a fixed
absolute threshold -- an ATR of "50" means nothing without knowing the
asset's normal range, exactly the same reasoning already applied to RVOL's
LOW/NORMAL/SIGNIFICANT/STRONG/ANOMALY buckets in app/indicators/rvol.py.

Anti-lookahead by construction: ATR at bar i depends only on
candles[max(0, i-period+1) .. i], and its percentile depends only on
atr values already computed at indices <= i. See
tests/indicators/test_atr_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class VolatilityRegime(str, Enum):
    DEAD = "DEAD"
    NORMAL = "NORMAL"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AtrParams:
    period: int = 14
    regime_lookback: int = 100
    dead_percentile: float = 0.15
    extreme_percentile: float = 0.90
    stop_multiplier: float = 1.5
    """Suggested stop distance = ATR * stop_multiplier -- a hint for
    whoever sizes a position, never a command; risk sizing itself is out
    of scope for this engine (docs/TRADING_ARCHITECTURE_V2.md: no Kelly,
    no Consensus, not this pass)."""


@dataclass(frozen=True)
class AtrState:
    time: int
    true_range: float
    atr: float | None
    percentile: float | None
    regime: VolatilityRegime
    suggested_stop_distance: float | None


def _true_range(candles: Sequence[Candle], i: int) -> float:
    if i == 0:
        return candles[0].high - candles[0].low
    prev_close = candles[i - 1].close
    return max(
        candles[i].high - candles[i].low,
        abs(candles[i].high - prev_close),
        abs(candles[i].low - prev_close),
    )


def compute_atr(
    candles: Sequence[Candle],
    params: AtrParams = AtrParams(),
) -> list[AtrState]:
    n = len(candles)
    true_ranges = [_true_range(candles, i) for i in range(n)]
    atr_series: list[float | None] = [None] * n
    out: list[AtrState] = []

    for i in range(n):
        start = max(0, i - params.period + 1)
        window = true_ranges[start : i + 1]
        atr_val = sum(window) / len(window)
        atr_series[i] = atr_val

        pct_start = max(0, i - params.regime_lookback + 1)
        history = [v for v in atr_series[pct_start : i + 1] if v is not None]
        percentile = (
            sum(1 for v in history if v <= atr_val) / len(history)
            if len(history) >= 2
            else None
        )

        if percentile is None:
            regime = VolatilityRegime.UNKNOWN
        elif percentile <= params.dead_percentile:
            regime = VolatilityRegime.DEAD
        elif percentile >= params.extreme_percentile:
            regime = VolatilityRegime.EXTREME
        else:
            regime = VolatilityRegime.NORMAL

        out.append(
            AtrState(
                time=candles[i].time,
                true_range=true_ranges[i],
                atr=atr_val,
                percentile=percentile,
                regime=regime,
                suggested_stop_distance=(
                    atr_val * params.stop_multiplier if atr_val is not None else None
                ),
            )
        )

    return out
