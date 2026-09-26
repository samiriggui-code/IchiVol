"""Produce ChartObjects from FVG states (T9d) — layer=fvg rectangles.

Uses ``REGISTRY.compute("fvg", ...)`` (T1e — no direct ``compute_fvg`` outside
``app/indicators/``).
"""

from __future__ import annotations

from typing import Sequence

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
    round_chart_coord,
)
from app.indicators.fvg import FvgParams, FvgState
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY


def fvg_to_chart_objects(
    candles: Sequence[Candle],
    symbol: str,
    timeframe: str,
    *,
    params: FvgParams | None = None,
) -> list[ChartObject]:
    """Emit rectangles for active (open/partial) FVGs.

    End time = last candle (extends to as_of until mitigated). Deterministic
    id uses type/source/symbol/tf/coords/subtype (layer not in fingerprint).
    """
    if not candles:
        return []
    states: list[FvgState] = REGISTRY.compute("fvg", candles, params or FvgParams())
    as_of = int(candles[-1].time)
    sym = symbol.upper()
    out: list[ChartObject] = []
    for ev in states[-1].active:
        if ev.start_bar < 0 or ev.start_bar >= len(candles):
            continue
        t0 = int(candles[ev.start_bar].time)
        if as_of <= t0:
            continue
        # CI-R8: lineage outside id fingerprint (end point = as_of → new id/bar).
        pl = round_chart_coord(ev.price_low)
        ph = round_chart_coord(ev.price_high)
        lineage_key = f"fvg:{ev.direction}:{t0}:{pl}:{ph}"
        out.append(
            ChartObject(
                type=ChartObjectType.RECTANGLE,
                source=ChartObjectSource.ENGINE,
                layer=ChartObjectLayer.FVG,
                symbol=sym,
                timeframe=timeframe,
                points=(
                    ChartPoint(time=t0, price=ev.price_low),
                    ChartPoint(time=as_of, price=ev.price_high),
                ),
                price_low=ev.price_low,
                price_high=ev.price_high,
                as_of=as_of,
                side="support" if ev.direction == "bullish" else "resistance",
                subtype=ev.direction,
                confidence=1.0,
                origin={
                    "kind": "fvg",
                    "direction": ev.direction,
                    "status": ev.status,
                    "fill_ratio": ev.fill_ratio,
                    "gap_atr": ev.gap_atr,
                    "start_bar": ev.start_bar,
                    "mid_bar": ev.mid_bar,
                    "end_bar": ev.end_bar,
                    "discovery_bar": ev.bar,
                    "lineage_key": lineage_key,
                },
            )
        )
    return out


__all__ = ["fvg_to_chart_objects"]
