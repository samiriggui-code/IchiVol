"""Open Interest + Funding Rate context -- V2 "participation avancée"
(docs/METHODS-ROADMAP.md). Never votes LONG/SHORT and never gates on its
own (same rule as CVD, app/indicators/cvd.py): this enriches the
Participation stage's context; RVOL alone still decides pass/fail/watch
(docs/TRADING_ARCHITECTURE_V2.md §7 rule 2).

OI trend is read relative to the instrument's own recent history (same
percentile-style philosophy as ATR/RVOL): rising/falling/flat over a
rolling window, since an absolute OI number means nothing without knowing
the asset's normal range. Funding rate is read directly (already a
normalized, cross-asset-comparable percentage) -- a large positive rate
means crowded longs paying shorts, a large negative rate means crowded
shorts.

Both series come from a separate Binance Futures endpoint
(app/market_data/binance_futures.py), fetched independently of the OHLCV
candles, and are aligned to each candle causally: only a data point whose
own timestamp is <= the candle's own time is ever used, via the same
"most recent point already known" scan used elsewhere in this codebase
(app/backtest/experiments.py::_align_mtf_directions,
app/indicators/location.py's AVWAP anchor). See
tests/indicators/test_oi_funding_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.market_data.binance_futures import FundingPoint, OpenInterestPoint


class OiTrend(str, Enum):
    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class FundingBias(str, Enum):
    CROWDED_LONG = "CROWDED_LONG"
    CROWDED_SHORT = "CROWDED_SHORT"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OiFundingParams:
    oi_window: int = 20
    oi_change_threshold: float = 0.02
    """+-this fraction of change over `oi_window` bars -> RISING/FALLING."""
    funding_crowded_threshold: float = 0.0005
    """0.05% per 8h funding interval -- a commonly-cited "hot" level where
    the funding cost itself starts pressuring the crowded side."""


@dataclass(frozen=True)
class OiFundingState:
    time: int
    open_interest: float | None
    oi_trend: OiTrend
    funding_rate: float | None
    funding_bias: FundingBias


def _align_latest(candles: Sequence[Candle], points: Sequence) -> list[int]:
    """For each candle, the index into `points` of the most recent point
    whose time <= the candle's time (-1 if none yet)."""
    result: list[int] = []
    idx = -1
    n = len(points)
    for candle in candles:
        while idx + 1 < n and points[idx + 1].time <= candle.time:
            idx += 1
        result.append(idx)
    return result


def compute_oi_funding(
    candles: Sequence[Candle],
    oi_points: Sequence[OpenInterestPoint],
    funding_points: Sequence[FundingPoint],
    params: OiFundingParams = OiFundingParams(),
) -> list[OiFundingState]:
    oi_idx_per_candle = _align_latest(candles, oi_points)
    funding_idx_per_candle = _align_latest(candles, funding_points)

    out: list[OiFundingState] = []
    oi_history: list[float | None] = []

    for i, candle in enumerate(candles):
        oi_idx = oi_idx_per_candle[i]
        oi_value = oi_points[oi_idx].open_interest if oi_idx >= 0 else None
        oi_history.append(oi_value)

        if oi_value is None:
            oi_trend = OiTrend.UNKNOWN
        else:
            start = max(0, i - params.oi_window + 1)
            window = [v for v in oi_history[start : i + 1] if v is not None]
            if len(window) < 2 or window[0] == 0:
                oi_trend = OiTrend.UNKNOWN
            else:
                change = (window[-1] - window[0]) / window[0]
                if change > params.oi_change_threshold:
                    oi_trend = OiTrend.RISING
                elif change < -params.oi_change_threshold:
                    oi_trend = OiTrend.FALLING
                else:
                    oi_trend = OiTrend.FLAT

        funding_idx = funding_idx_per_candle[i]
        funding_rate = funding_points[funding_idx].rate if funding_idx >= 0 else None
        if funding_rate is None:
            funding_bias = FundingBias.UNKNOWN
        elif funding_rate > params.funding_crowded_threshold:
            funding_bias = FundingBias.CROWDED_LONG
        elif funding_rate < -params.funding_crowded_threshold:
            funding_bias = FundingBias.CROWDED_SHORT
        else:
            funding_bias = FundingBias.NEUTRAL

        out.append(
            OiFundingState(
                time=candle.time,
                open_interest=oi_value,
                oi_trend=oi_trend,
                funding_rate=funding_rate,
                funding_bias=funding_bias,
            )
        )

    return out
