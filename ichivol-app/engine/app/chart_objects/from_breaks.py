"""Produce ChartObjects for BOS / CHoCH / breakouts — layer=breaks.

T9b ``StructureEvent`` markers via ``REGISTRY.compute("structure")`` (T1e).
Optional consensus breakout candidates (moved off structure layer).
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
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY
from app.indicators.structure import (
    BreakQuality,
    StructureEventType,
    StructureParams,
)
from app.structure.types import MarketStructureSnapshot

_QUALITY_CONFIDENCE = {
    BreakQuality.WICK: 0.4,
    BreakQuality.CLOSE: 0.7,
    BreakQuality.CONFIRMED: 1.0,
}


def _event_label(event_type: StructureEventType, direction: str) -> str:
    arrow = "↑" if direction == "bullish" else "↓"
    if event_type == StructureEventType.CHOCH:
        return f"CHoCH{arrow}"
    return f"BOS{arrow}"


def breaks_to_chart_objects(
    candles: Sequence[Candle],
    symbol: str,
    timeframe: str,
    *,
    snapshot: MarketStructureSnapshot | None = None,
    params: StructureParams | None = None,
    max_events: int = 40,
    include_breakouts: bool = True,
) -> list[ChartObject]:
    """Emit MARKER overlays for structure breaks (ENGINE, layer=breaks)."""
    if not candles:
        return []
    as_of = int(candles[-1].time)
    sym = symbol.upper()
    out: list[ChartObject] = []

    states = REGISTRY.compute("structure", candles, params or StructureParams())
    event_objs: list[ChartObject] = []
    for st in states:
        ev = st.event
        if ev is None:
            continue
        if ev.bar < 0 or ev.bar >= len(candles):
            continue
        t = int(candles[ev.bar].time)
        if t > as_of:
            continue
        side = "support" if ev.direction == "bullish" else "resistance"
        # CI-R8: type + swing_time (event bar), independent of as_of.
        lineage_key = f"structure_event:{ev.type.value}:{t}"
        event_objs.append(
            ChartObject(
                type=ChartObjectType.MARKER,
                source=ChartObjectSource.ENGINE,
                layer=ChartObjectLayer.BREAKS,
                symbol=sym,
                timeframe=timeframe,
                points=(ChartPoint(time=t, price=float(ev.level)),),
                as_of=as_of,
                side=side,
                label=_event_label(ev.type, ev.direction),
                confidence=_QUALITY_CONFIDENCE.get(ev.break_quality, 0.5),
                origin={
                    "kind": "structure_event",
                    "event_type": ev.type.value,
                    "direction": ev.direction,
                    "break_quality": ev.break_quality.value,
                    "level": ev.level,
                    "bar": ev.bar,
                    "swing_time": t,
                    "displacement_atr": ev.displacement_atr,
                    "rvol": ev.rvol,
                    "lineage_key": lineage_key,
                },
                subtype=ev.type.value.lower(),
            )
        )
    # Keep the most recent events (by bar / time).
    event_objs.sort(key=lambda o: o.points[0].time)
    out.extend(event_objs[-max_events:])

    if include_breakouts and snapshot is not None:
        last = candles[-1]
        for b in snapshot.breakout_candidates:
            score = float(getattr(b.zone, "score", 0.0) or 0.0)
            conf = min(1.0, score / max(score, 1.0)) if score > 0 else 0.5
            # CI-R8: kind + bar (ephemeral candidate at current bar).
            lineage_key = f"breakout:{b.side.value}:{as_of}"
            out.append(
                ChartObject(
                    type=ChartObjectType.MARKER,
                    source=ChartObjectSource.ENGINE,
                    layer=ChartObjectLayer.BREAKS,
                    symbol=sym,
                    timeframe=timeframe,
                    points=(ChartPoint(time=as_of, price=float(b.close)),),
                    as_of=as_of,
                    side=b.side.value,
                    label="BO" if b.confirmed else "BO?",
                    confidence=conf,
                    origin={
                        "kind": "breakout_candidate",
                        "detector": "consensus",
                        "confirmed": b.confirmed,
                        "reason": b.reason,
                        "distance_atr": b.distance_atr,
                        "body_ratio": b.body_ratio,
                        "rvol": b.rvol,
                        "score": score,
                        "last_open": last.open,
                        "lineage_key": lineage_key,
                    },
                    subtype="breakout",
                )
            )

    return out


__all__ = ["breaks_to_chart_objects"]
