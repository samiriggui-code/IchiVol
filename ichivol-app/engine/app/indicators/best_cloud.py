"""BEST Cloud — two-moving-average cloud, experimental confirmation feature.

Concept (after the open-source "BEST Cloud ALL MA" by Daveatt; the math is
re-implemented here with no TradingView dependency, and the script's own
defaults were NOT verified):

    cloud     = band between MA_fast and MA_slow
    BULLISH   = MA_fast > MA_slow and close above the cloud
    BEARISH   = MA_fast < MA_slow and close below the cloud
    NEUTRAL   = anything else (incl. close inside the cloud)

Highly likely to be redundant with Ichimoku (price vs Kumo, Tenkan vs Kijun);
that is what the Lab ablation is for. NOT wired into decision/pipeline.py or
decision/combiner.py (docs/ICHIVOL_V2_ROADMAP.md, tranche T-EXP).

Causal: state at bar i only reads closes[0..i]; callers pass closed candles.
Defaults (EMA 20 / EMA 50) are fixed a priori — do not tune on the ablation
window. MA type is limited to SMA/EMA on purpose (fewer degrees of freedom).
MAs are undefined until ``period`` closes exist (EMA is SMA-seeded).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.ppo import _ema_series

MA_TYPES = ("EMA", "SMA")


class CloudTrend(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"  # warm-up


class CloudCross(str, Enum):
    BULLISH_CROSS = "BULLISH_CROSS"  # fast crosses above slow
    BEARISH_CROSS = "BEARISH_CROSS"
    NONE = "NONE"


@dataclass(frozen=True)
class BestCloudParams:
    fast_period: int = 20
    slow_period: int = 50
    fast_type: str = "EMA"
    slow_type: str = "EMA"

    def __post_init__(self) -> None:
        if self.fast_type not in MA_TYPES or self.slow_type not in MA_TYPES:
            raise ValueError(f"ma type must be one of {MA_TYPES}")
        if self.fast_period < 1 or self.slow_period <= self.fast_period:
            raise ValueError("BestCloudParams requires 1 <= fast_period < slow_period")


@dataclass(frozen=True)
class BestCloudState:
    time: int
    fast_ma: float | None
    slow_ma: float | None
    cloud_upper: float | None
    cloud_lower: float | None
    cloud_width: float | None
    cloud_width_pct: float | None
    """(upper - lower) / close * 100."""
    price_above_cloud: bool
    price_below_cloud: bool
    price_inside_cloud: bool
    trend: CloudTrend
    cross: CloudCross
    last_cross: CloudCross
    bars_since_cross: int | None
    """0 on the cross bar itself; None if no cross yet."""
    distance_price_cloud_pct: float | None
    """Signed % of close: >0 above upper edge, <0 below lower edge, 0 inside."""


def _sma_series(values: Sequence[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def _ma(values: Sequence[float], period: int, kind: str) -> list[float | None]:
    return _sma_series(values, period) if kind == "SMA" else _ema_series(values, period)


def compute_best_cloud(
    candles: Sequence[Candle],
    params: BestCloudParams = BestCloudParams(),
) -> list[BestCloudState]:
    closes = [c.close for c in candles]
    fast = _ma(closes, params.fast_period, params.fast_type)
    slow = _ma(closes, params.slow_period, params.slow_type)

    out: list[BestCloudState] = []
    last_cross = CloudCross.NONE
    since: int | None = None

    for i, c in enumerate(candles):
        f, s = fast[i], slow[i]
        pf = fast[i - 1] if i > 0 else None
        ps = slow[i - 1] if i > 0 else None

        cross = CloudCross.NONE
        if f is not None and s is not None and pf is not None and ps is not None:
            if pf <= ps and f > s:
                cross = CloudCross.BULLISH_CROSS
            elif pf >= ps and f < s:
                cross = CloudCross.BEARISH_CROSS
        if cross != CloudCross.NONE:
            last_cross = cross
            since = 0
        elif since is not None:
            since += 1

        if f is None or s is None:
            out.append(
                BestCloudState(
                    time=c.time,
                    fast_ma=f,
                    slow_ma=s,
                    cloud_upper=None,
                    cloud_lower=None,
                    cloud_width=None,
                    cloud_width_pct=None,
                    price_above_cloud=False,
                    price_below_cloud=False,
                    price_inside_cloud=False,
                    trend=CloudTrend.UNKNOWN,
                    cross=cross,
                    last_cross=last_cross,
                    bars_since_cross=since,
                    distance_price_cloud_pct=None,
                )
            )
            continue

        upper, lower = max(f, s), min(f, s)
        above = c.close > upper
        below = c.close < lower
        inside = not above and not below
        if f > s and above:
            trend = CloudTrend.BULLISH
        elif f < s and below:
            trend = CloudTrend.BEARISH
        else:
            trend = CloudTrend.NEUTRAL

        if c.close == 0.0:
            width_pct = dist_pct = None
        else:
            width_pct = (upper - lower) / c.close * 100.0
            if above:
                dist_pct = (c.close - upper) / c.close * 100.0
            elif below:
                dist_pct = (c.close - lower) / c.close * 100.0
            else:
                dist_pct = 0.0

        out.append(
            BestCloudState(
                time=c.time,
                fast_ma=f,
                slow_ma=s,
                cloud_upper=upper,
                cloud_lower=lower,
                cloud_width=upper - lower,
                cloud_width_pct=width_pct,
                price_above_cloud=above,
                price_below_cloud=below,
                price_inside_cloud=inside,
                trend=trend,
                cross=cross,
                last_cross=last_cross,
                bars_since_cross=since,
                distance_price_cloud_pct=dist_pct,
            )
        )
    return out
