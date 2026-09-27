"""Produce ChartObjects for BSL / SSL — equal highs / lows (layer=liquidity).

Uses causal fractals (T9a) + ATR clustering. No lookahead: a pool is known
only when the 2nd pivot is confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
    round_chart_coord,
)
from app.indicators.ichimoku import Candle
from app.indicators.pivots import CausalPivot, detect_causal_ohlc_fractals
from app.structure.atr_utils import last_atr, touch_tolerance


@dataclass(frozen=True)
class LiquidityParams:
    """Equal-highs / equal-lows detector knobs."""

    swing_left: int = 2
    swing_right: int = 2
    atr_period: int = 14
    cluster_atr_mult: float = 0.15
    min_touches: int = 2
    max_pools: int = 8
    lookback_pivots: int = 40


def _cluster_pivots(
    pivots: list[CausalPivot],
    *,
    tol: float,
    min_touches: int,
) -> list[list[CausalPivot]]:
    if not pivots:
        return []
    ordered = sorted(pivots, key=lambda p: p.price)
    clusters: list[list[CausalPivot]] = []
    cur: list[CausalPivot] = [ordered[0]]
    for p in ordered[1:]:
        ref = sum(x.price for x in cur) / len(cur)
        if abs(p.price - ref) <= tol:
            cur.append(p)
        else:
            if len(cur) >= min_touches:
                clusters.append(cur)
            cur = [p]
    if len(cur) >= min_touches:
        clusters.append(cur)
    return clusters


def _sweep_bar(
    candles: Sequence[Candle],
    *,
    level: float,
    kind: str,
    after_bar: int,
    tol: float,
) -> int | None:
    """First bar after ``after_bar`` that takes liquidity beyond the pool."""
    for i in range(after_bar + 1, len(candles)):
        c = candles[i]
        if kind == "high" and float(c.high) > level + tol:
            return i
        if kind == "low" and float(c.low) < level - tol:
            return i
    return None


def liquidity_to_chart_objects(
    candles: Sequence[Candle],
    symbol: str,
    timeframe: str,
    *,
    params: LiquidityParams | None = None,
) -> list[ChartObject]:
    """Emit horizontal BSL/SSL segments for equal highs / equal lows."""
    if len(candles) < 10:
        return []
    p = params or LiquidityParams()
    atr = last_atr(candles, p.atr_period)
    mid = float(candles[-1].close)
    tol = touch_tolerance(atr, p.cluster_atr_mult, mid)
    if tol <= 0:
        return []

    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    hi_piv, lo_piv = detect_causal_ohlc_fractals(
        highs, lows, left=p.swing_left, right=p.swing_right
    )
    # Prefer recent pivots (budget).
    hi_piv = hi_piv[-p.lookback_pivots :]
    lo_piv = lo_piv[-p.lookback_pivots :]

    as_of = int(candles[-1].time)
    sym = symbol.upper()
    out: list[ChartObject] = []

    for kind, pivots, side, label, subtype in (
        ("high", hi_piv, "resistance", "BSL", "equal_highs"),
        ("low", lo_piv, "support", "SSL", "equal_lows"),
    ):
        for cluster in _cluster_pivots(pivots, tol=tol, min_touches=p.min_touches):
            cluster_sorted = sorted(cluster, key=lambda x: x.bar_index)
            level = sum(x.price for x in cluster_sorted) / len(cluster_sorted)
            t0 = int(candles[cluster_sorted[0].bar_index].time)
            known_bar = max(x.confirmed_bar for x in cluster_sorted)
            if known_bar < 0 or known_bar >= len(candles):
                continue
            known_at = int(candles[known_bar].time)
            last_pivot_bar = cluster_sorted[-1].bar_index
            swept_i = _sweep_bar(
                candles, level=level, kind=kind, after_bar=last_pivot_bar, tol=tol
            )
            if swept_i is not None:
                t1 = int(candles[swept_i].time)
                status = "swept"
            else:
                t1 = as_of
                status = "open"
            if t1 <= t0:
                continue
            px = round_chart_coord(level)
            lineage_key = f"liquidity:{subtype}:{t0}:{px}"
            conf = min(1.0, 0.45 + 0.12 * (len(cluster_sorted) - 2))
            out.append(
                ChartObject(
                    type=ChartObjectType.TREND_LINE,
                    source=ChartObjectSource.ENGINE,
                    layer=ChartObjectLayer.LIQUIDITY,
                    symbol=sym,
                    timeframe=timeframe,
                    points=(
                        ChartPoint(time=t0, price=float(level)),
                        ChartPoint(time=t1, price=float(level)),
                    ),
                    as_of=as_of,
                    side=side,
                    label=label,
                    confidence=conf,
                    subtype=subtype,
                    origin={
                        "kind": "liquidity",
                        "producer": "liquidity_engine",
                        "direction": "bearish" if kind == "high" else "bullish",
                        "status": status,
                        "level": float(level),
                        "touch_count": len(cluster_sorted),
                        "known_at": known_at,
                        "lineage_key": lineage_key,
                        "reason": (
                            f"{'Sommets' if kind == 'high' else 'Creux'} égaux "
                            f"×{len(cluster_sorted)} @ {px}"
                        ),
                        "used_by_decision": False,
                    },
                )
            )

    # Keep most recent by start time, cap.
    out.sort(key=lambda o: o.points[0].time, reverse=True)
    return out[: p.max_pools]
