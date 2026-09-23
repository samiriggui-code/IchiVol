"""Ground agent-drawn ChartObjects on real OHLCV (anti-hallucination).

Agent draw_* must not invent times or prices. After shape validation, every
point (and ZONE price_low/high) is checked against the fetched candle series.
"""

from __future__ import annotations

from typing import Sequence

from app.chart_objects.types import ChartObject
from app.indicators.ichimoku import Candle

# Wide band: not a precision test — only blocks absurd invented prices.
_PRICE_BAND_LO = 0.5
_PRICE_BAND_HI = 1.5
_PRICE_LOOKBACK = 300
# Projected extensions may land a few bars past the last closed candle.
_MAX_PROJECTED_BARS = 5


def _bar_step(candles: Sequence[Candle]) -> int:
    if len(candles) >= 2:
        step = int(candles[-1].time) - int(candles[-2].time)
        if step > 0:
            return step
    return 3600


def assert_object_grounded(
    obj: ChartObject,
    candles: Sequence[Candle],
    *,
    max_projected_bars: int = _MAX_PROJECTED_BARS,
) -> None:
    """Raise ``ValueError('point_not_grounded: …')`` if obj is not on the series."""
    if not candles:
        raise ValueError("point_not_grounded: empty candle series")

    times = {int(c.time) for c in candles}
    last_time = int(candles[-1].time)
    step = _bar_step(candles)
    projected = bool(obj.origin.get("projected"))
    max_proj_time = last_time + max_projected_bars * step

    window = list(candles[-_PRICE_LOOKBACK:])
    lo = min(float(c.low) for c in window)
    hi = max(float(c.high) for c in window)
    price_min = lo * _PRICE_BAND_LO
    price_max = hi * _PRICE_BAND_HI

    def check_time(t: int, label: str) -> None:
        if t in times:
            return
        if projected and last_time < t <= max_proj_time:
            return
        raise ValueError(
            f"point_not_grounded: {label} time={t} not on series "
            f"(last={last_time}, projected={projected}, "
            f"max_proj={max_proj_time})"
        )

    def check_price(p: float, label: str) -> None:
        if price_min <= p <= price_max:
            return
        raise ValueError(
            f"point_not_grounded: {label} price={p} outside "
            f"[{price_min}, {price_max}] "
            f"(series high/low band ×{_PRICE_BAND_LO}–{_PRICE_BAND_HI})"
        )

    for i, pt in enumerate(obj.points):
        check_time(int(pt.time), f"points[{i}]")
        check_price(float(pt.price), f"points[{i}]")

    if obj.price_low is not None:
        check_price(float(obj.price_low), "price_low")
    if obj.price_high is not None:
        check_price(float(obj.price_high), "price_high")
