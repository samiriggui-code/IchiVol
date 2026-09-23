"""trendln-inspired second-opinion adapter (clean-room, no findiff dep).

Geometric extrema + horizontal clustering + simple diagonals.
No volume — safe beside RVOL / MVPP wick classifier.
"""

from __future__ import annotations

from typing import Sequence

from app.indicators.ichimoku import Candle
from app.structure.atr_utils import last_atr, touch_tolerance
from app.structure.params import StructureEngineParams
from app.structure.types import (
    DetectorSource,
    LevelSide,
    MarketStructure,
    PivotPoint,
    PriceZone,
    TrendlineSegment,
)


def _window(candles: Sequence[Candle], max_bars: int) -> list[Candle]:
    if len(candles) <= max_bars:
        return list(candles)
    return list(candles[-max_bars:])


def _extrema(
    candles: Sequence[Candle],
    lookback: int,
) -> tuple[list[PivotPoint], list[PivotPoint]]:
    """Causal local extrema: confirmed at i when j = i - lookback is extremum."""
    n = len(candles)
    highs: list[PivotPoint] = []
    lows: list[PivotPoint] = []
    for i in range(n):
        j = i - lookback
        if j - lookback < 0:
            continue
        window = candles[j - lookback : j + lookback + 1]
        if candles[j].high == max(c.high for c in window):
            highs.append(
                PivotPoint(
                    bar_index=j,
                    time=candles[j].time,
                    price=candles[j].high,
                    side=LevelSide.RESISTANCE,
                    quality=1.0,
                    confirmed_bar=i,
                    provisional=False,
                )
            )
        if candles[j].low == min(c.low for c in window):
            lows.append(
                PivotPoint(
                    bar_index=j,
                    time=candles[j].time,
                    price=candles[j].low,
                    side=LevelSide.SUPPORT,
                    quality=1.0,
                    confirmed_bar=i,
                    provisional=False,
                )
            )
    return lows, highs


def _cluster_horizontals(
    pivots: Sequence[PivotPoint],
    side: LevelSide,
    atr: float | None,
    params: StructureEngineParams,
) -> list[PriceZone]:
    if not pivots:
        return []
    tol = touch_tolerance(atr, params.consensus_atr_mult, pivots[0].price)
    sorted_p = sorted(pivots, key=lambda p: p.price)
    clusters: list[list[PivotPoint]] = []
    current: list[PivotPoint] = [sorted_p[0]]
    for p in sorted_p[1:]:
        if abs(p.price - current[-1].price) <= tol:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)

    zones: list[PriceZone] = []
    for cluster in clusters:
        if len(cluster) < params.horizontal_min_touches:
            continue
        prices = [p.price for p in cluster]
        mid = sum(prices) / len(prices)
        half = (atr or abs(mid) * 0.002) * params.zone_atr_mult
        zones.append(
            PriceZone(
                side=side,
                low=mid - half,
                high=mid + half,
                mid=mid,
                score=float(len(cluster)),
                touch_count=len(cluster),
                sources=(DetectorSource.TRENDLN,),
                atr_width=half * 2,
            )
        )
    return sorted(zones, key=lambda z: z.score, reverse=True)[: params.max_lines_per_side]


def _simple_diagonals(
    pivots: Sequence[PivotPoint],
    side: LevelSide,
    atr: float | None,
    params: StructureEngineParams,
    n_bars: int,
) -> list[TrendlineSegment]:
    if len(pivots) < params.min_touches:
        return []
    tol = touch_tolerance(atr, params.touch_atr_mult, pivots[0].price)
    lines: list[TrendlineSegment] = []
    for a in range(len(pivots)):
        for b in range(a + 1, len(pivots)):
            p0, p1 = pivots[a], pivots[b]
            if p1.bar_index == p0.bar_index:
                continue
            slope = (p1.price - p0.price) / (p1.bar_index - p0.bar_index)
            intercept = p0.price - slope * p0.bar_index
            hits = [
                p
                for p in pivots
                if abs(p.price - (slope * p.bar_index + intercept)) <= tol
            ]
            if len(hits) < params.min_touches:
                continue
            start = min(p.bar_index for p in hits)
            end = max(p.bar_index for p in hits)
            score = (2.0 ** len(hits)) * ((end - start) / max(n_bars, 1))
            lines.append(
                TrendlineSegment(
                    side=side,
                    slope=slope,
                    intercept=intercept,
                    start_bar=start,
                    end_bar=end,
                    touch_count=len(hits),
                    score=score,
                    source=DetectorSource.TRENDLN,
                    pivot_bars=tuple(sorted(p.bar_index for p in hits)),
                )
            )
    lines.sort(key=lambda x: x.score, reverse=True)
    return lines[: params.max_lines_per_side]


class TrendlnStructureAdapter:
    """Second-opinion geometric detector (clean-room trendln-inspired)."""

    name = DetectorSource.TRENDLN.value

    def detect(
        self,
        candles: Sequence[Candle],
        params: StructureEngineParams = StructureEngineParams(),
        *,
        atr: float | None = None,
    ) -> MarketStructure:
        series = _window(candles, params.window_bars)
        if len(series) < params.extrema_lookback * 2 + 3:
            return MarketStructure(source=DetectorSource.TRENDLN, meta={"reason": "insufficient_bars"})

        atr_val = atr if atr is not None else last_atr(series, params.atr_period)
        lows, highs = _extrema(series, params.extrema_lookback)
        sup_zones = _cluster_horizontals(lows, LevelSide.SUPPORT, atr_val, params)
        res_zones = _cluster_horizontals(highs, LevelSide.RESISTANCE, atr_val, params)
        sup_lines = _simple_diagonals(lows, LevelSide.SUPPORT, atr_val, params, len(series))
        res_lines = _simple_diagonals(highs, LevelSide.RESISTANCE, atr_val, params, len(series))

        # Promote diagonals to zones at last bar
        last = len(series) - 1
        half = (atr_val or 0.0) * params.zone_atr_mult
        for line in sup_lines + res_lines:
            mid = line.price_at(last)
            width = half if half > 0 else abs(mid) * 0.002
            zone = PriceZone(
                side=line.side,
                low=mid - width,
                high=mid + width,
                mid=mid,
                score=line.score,
                touch_count=line.touch_count,
                sources=(DetectorSource.TRENDLN,),
                atr_width=width * 2,
            )
            if line.side == LevelSide.SUPPORT:
                sup_zones.append(zone)
            else:
                res_zones.append(zone)

        return MarketStructure(
            source=DetectorSource.TRENDLN,
            pivots=tuple(lows + highs),
            support_trendlines=tuple(sup_lines),
            resistance_trendlines=tuple(res_lines),
            support_zones=tuple(sup_zones[: params.max_lines_per_side]),
            resistance_zones=tuple(res_zones[: params.max_lines_per_side]),
            structure_score=float(len(sup_zones) + len(res_zones)),
            meta={"bars": len(series), "atr": atr_val, "implementation": "clean_room_geometric"},
        )
