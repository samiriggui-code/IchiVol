"""Produce ChartObjects from a MarketStructureSnapshot.

Selection rules mirror ``ichivol-app/src/lib/structure.ts`` ``toStructureOverlay``
exactly (MAX_ZONES_PER_SIDE=3, MAX_TRENDLINES_PER_SIDE=2, sort by score desc,
trendlines only when drawable time/price endpoints exist). Chart visuals for
zones/lines must not change when the front switches to this producer.
"""

from __future__ import annotations

from typing import Sequence

from app.chart_objects.types import (
    ChartObject,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.indicators.ichimoku import Candle
from app.structure.types import (
    MarketStructureSnapshot,
    PriceZone,
    TrendlineSegment,
)

# Keep in lockstep with structure.ts
MAX_ZONES_PER_SIDE = 3
MAX_TRENDLINES_PER_SIDE = 2


def _normalize_confidence(score: float, max_score: float) -> float:
    """Map a raw detector/consensus score into confidence ∈ [0, 1].

    Formula: ``confidence = clamp(score / max_score, 0, 1)`` where
    ``max_score`` is the highest score in the same candidate pool (same side,
    before top-N truncation). If ``max_score <= 0``, confidence is 0.
    """
    if max_score <= 0:
        return 0.0
    return max(0.0, min(1.0, float(score) / float(max_score)))


def _top_by_score(rows: Sequence, n: int) -> list:
    return sorted(rows, key=lambda r: r.score, reverse=True)[:n]


def _line_endpoints(
    line: TrendlineSegment, series: Sequence[Candle]
) -> tuple[ChartPoint, ChartPoint] | None:
    """Drawable endpoints — same gate as structure.ts ``hasPoints``."""
    if not series:
        return None
    if not (0 <= line.start_bar < len(series) and 0 <= line.end_bar < len(series)):
        return None
    start_time = int(series[line.start_bar].time)
    end_time = int(series[line.end_bar].time)
    if end_time <= start_time:
        return None
    return (
        ChartPoint(time=start_time, price=float(line.price_at(line.start_bar))),
        ChartPoint(time=end_time, price=float(line.price_at(line.end_bar))),
    )


def structure_to_chart_objects(
    snapshot: MarketStructureSnapshot,
    symbol: str,
    timeframe: str,
    candles: Sequence[Candle],
    *,
    max_zones_per_side: int = MAX_ZONES_PER_SIDE,
    max_trendlines_per_side: int = MAX_TRENDLINES_PER_SIDE,
) -> list[ChartObject]:
    """Convert structure snapshot → typed ChartObjects (ENGINE source).

    ``candles`` must be the same window used for ``_line_dict`` / structure API
    (typically ``candles[-window_bars:]``) so trendline bar indices align.
    """
    if not candles:
        return []

    as_of = int(candles[-1].time)
    sym = symbol.upper()
    out: list[ChartObject] = []

    # --- consensus zones (top by score per side) ---
    for side_name, zones in (
        ("support", snapshot.consensus.support_zones),
        ("resistance", snapshot.consensus.resistance_zones),
    ):
        pool = list(zones)
        max_score = max((z.score for z in pool), default=0.0)
        for z in _top_by_score(pool, max_zones_per_side):
            out.append(_zone_object(z, sym, timeframe, as_of, max_score))

    # --- trendlines from all detectors (drawable only, top by score per side) ---
    drawable: list[tuple[TrendlineSegment, tuple[ChartPoint, ChartPoint], str]] = []
    for det_name, ms in snapshot.by_detector.items():
        for line in list(ms.support_trendlines) + list(ms.resistance_trendlines):
            pts = _line_endpoints(line, candles)
            if pts is None:
                continue
            drawable.append((line, pts, det_name))

    for side_name in ("support", "resistance"):
        side_pool = [(ln, pts, det) for ln, pts, det in drawable if ln.side.value == side_name]
        max_score = max((ln.score for ln, _, _ in side_pool), default=0.0)
        ranked = sorted(side_pool, key=lambda row: row[0].score, reverse=True)[
            :max_trendlines_per_side
        ]
        for line, pts, det_name in ranked:
            out.append(
                ChartObject(
                    type=ChartObjectType.TREND_LINE,
                    source=ChartObjectSource.ENGINE,
                    symbol=sym,
                    timeframe=timeframe,
                    points=pts,
                    as_of=as_of,
                    side=line.side.value,
                    label=None,
                    confidence=_normalize_confidence(line.score, max_score),
                    origin={
                        "kind": "structure_trendline",
                        "detector": det_name,
                        "score": line.score,
                        "touch_count": line.touch_count,
                        "source": line.source.value,
                    },
                    subtype=line.side.value,
                )
            )

    # --- breakout candidates → MARKER at last candle ---
    last = candles[-1]
    for b in snapshot.breakout_candidates:
        score = float(getattr(b.zone, "score", 0.0) or 0.0)
        out.append(
            ChartObject(
                type=ChartObjectType.MARKER,
                source=ChartObjectSource.ENGINE,
                symbol=sym,
                timeframe=timeframe,
                points=(ChartPoint(time=as_of, price=float(b.close)),),
                as_of=as_of,
                side=b.side.value,
                label="BO" if b.confirmed else "BO?",
                confidence=_normalize_confidence(score, max(score, 1.0)),
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
                },
                subtype="breakout",
            )
        )

    return out


def _zone_object(
    z: PriceZone,
    symbol: str,
    timeframe: str,
    as_of: int,
    max_score: float,
) -> ChartObject:
    letter = "S" if z.side.value == "support" else "R"
    return ChartObject(
        type=ChartObjectType.ZONE,
        source=ChartObjectSource.ENGINE,
        symbol=symbol,
        timeframe=timeframe,
        points=(),
        as_of=as_of,
        price_low=float(z.low),
        price_high=float(z.high),
        side=z.side.value,
        label=f"{letter} ×{z.touch_count}",
        confidence=_normalize_confidence(z.score, max_score),
        origin={
            "kind": "structure_zone",
            "detector": "consensus",
            "score": z.score,
            "touch_count": z.touch_count,
            "mid": z.mid,
            "sources": [s.value for s in z.sources],
        },
        subtype=z.side.value,
    )
