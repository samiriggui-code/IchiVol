"""Produce ChartObjects from Fib context (T9e) — layer=fibonacci levels.

Anchors on T9c ImpulseEvent via ``compute_fib_context(..., anchor="auto")``.
Uses REGISTRY-backed impulse path (no direct compute_impulse outside indicators).
"""

from __future__ import annotations

from typing import Sequence

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.fibonacci.context import DEFAULT_KEY_RATIOS, compute_fib_context
from app.indicators.ichimoku import Candle
from app.indicators.impulse import ImpulseParams


def fibonacci_to_chart_objects(
    candles: Sequence[Candle],
    symbol: str,
    timeframe: str,
    *,
    impulse_params: ImpulseParams | None = None,
    key_only: bool = False,
) -> list[ChartObject]:
    """Emit horizontal lines for Fib ratios (key ratios by default for clutter)."""
    if not candles:
        return []
    ctx = compute_fib_context(
        candles,
        anchor="auto",
        impulse_params=impulse_params or ImpulseParams(),
    )
    if ctx is None:
        return []
    as_of = int(candles[-1].time)
    # Prefer known_bar time for the level point when available
    t = as_of
    if ctx.known_bar is not None and 0 <= ctx.known_bar < len(candles):
        t = int(candles[ctx.known_bar].time)
    sym = symbol.upper()
    key_set = {round(r, 4) for r in DEFAULT_KEY_RATIOS}
    out: list[ChartObject] = []
    for lv in ctx.levels:
        if key_only and round(lv.ratio, 4) not in key_set:
            continue
        out.append(
            ChartObject(
                type=ChartObjectType.HORIZONTAL_LINE,
                source=ChartObjectSource.ENGINE,
                layer=ChartObjectLayer.FIBONACCI,
                symbol=sym,
                timeframe=timeframe,
                points=(ChartPoint(time=t, price=lv.price),),
                as_of=as_of,
                side="support" if ctx.impulse == "up" else "resistance",
                subtype=f"{ctx.impulse}_{lv.ratio}",
                label=f"{lv.ratio:.3f}".rstrip("0").rstrip("."),
                confidence=1.0,
                origin={
                    "kind": "fibonacci",
                    "ratio": lv.ratio,
                    "impulse": ctx.impulse,
                    "anchor_source": ctx.anchor_source,
                    "start_bar": ctx.start_bar,
                    "end_bar": ctx.end_bar,
                    "known_bar": ctx.known_bar,
                    "displacement_atr": ctx.displacement_atr,
                    "swing_low": ctx.swing_low,
                    "swing_high": ctx.swing_high,
                },
            )
        )
    return out


__all__ = ["fibonacci_to_chart_objects"]
