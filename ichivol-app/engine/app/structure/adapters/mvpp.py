"""MVPP-inspired Market Structure adapter (clean-room).

Ideas inspired by public descriptions of mvpp/trend-line-detector
(Williams fractals, volume-adaptive wick/body, min 3 touches, scoring,
dedup) — reimplemented causally on IchiVol ``Candle`` sequences.

Does NOT copy proprietary source. Line scoring omits volume by default
to avoid double-counting with RVOL.
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


def _vol_sma(volumes: Sequence[float], i: int, lookback: int) -> float:
    start = max(0, i - lookback + 1)
    window = volumes[start : i + 1]
    return sum(window) / len(window) if window else 0.0


def _adaptive_prices(
    candles: Sequence[Candle],
    params: StructureEngineParams,
) -> tuple[list[float], list[float], list[bool]]:
    """Resistance/support price per bar: wick on high-vol, else body."""
    volumes = [c.volume for c in candles]
    res: list[float] = []
    sup: list[float] = []
    high_vol: list[bool] = []
    for i, c in enumerate(candles):
        sma = _vol_sma(volumes, i, params.vol_sma_lookback)
        is_hv = sma > 0 and c.volume > params.high_vol_mult * sma
        high_vol.append(is_hv)
        if is_hv:
            res.append(c.high)
            sup.append(c.low)
        else:
            res.append(max(c.open, c.close))
            sup.append(min(c.open, c.close))
    return res, sup, high_vol


def _causal_fractal_pivots(
    candles: Sequence[Candle],
    prices: Sequence[float],
    high_vol: Sequence[bool],
    side: LevelSide,
    left: int,
    right: int,
) -> list[PivotPoint]:
    """Pivot at j confirmed only when bar i = j + right is known."""
    n = len(candles)
    pivots: list[PivotPoint] = []
    for i in range(n):
        j = i - right
        if j - left < 0:
            continue
        window = prices[j - left : j + right + 1]
        if len(window) < left + right + 1:
            continue
        center = prices[j]
        if side == LevelSide.RESISTANCE:
            if center != max(window):
                continue
        else:
            if center != min(window):
                continue
        # Prominence vs neighbors (no future bounce — causal)
        neighbors = [prices[k] for k in range(j - left, j + right + 1) if k != j]
        if not neighbors:
            continue
        mean_n = sum(neighbors) / len(neighbors)
        price_range = max(prices) - min(prices) or 1.0
        if side == LevelSide.RESISTANCE:
            prominence = max(0.0, (center - mean_n) / price_range)
        else:
            prominence = max(0.0, (mean_n - center) / price_range)
        quality = max(0.05, min(1.0, prominence ** 0.5))
        pivots.append(
            PivotPoint(
                bar_index=j,
                time=candles[j].time,
                price=center,
                side=side,
                quality=quality,
                is_high_volume=high_vol[j],
            )
        )
    # Dedup same bar
    seen: set[int] = set()
    unique: list[PivotPoint] = []
    for p in pivots:
        if p.bar_index in seen:
            continue
        seen.add(p.bar_index)
        unique.append(p)
    return unique


def _line_through(p0: PivotPoint, p1: PivotPoint) -> tuple[float, float] | None:
    if p1.bar_index == p0.bar_index:
        return None
    slope = (p1.price - p0.price) / (p1.bar_index - p0.bar_index)
    intercept = p0.price - slope * p0.bar_index
    return slope, intercept


def _touches(
    pivots: Sequence[PivotPoint],
    slope: float,
    intercept: float,
    tol: float,
) -> list[PivotPoint]:
    hit: list[PivotPoint] = []
    for p in pivots:
        y = slope * p.bar_index + intercept
        if abs(p.price - y) <= tol:
            hit.append(p)
    return hit


def _candle_through_ok(
    candles: Sequence[Candle],
    slope: float,
    intercept: float,
    start: int,
    end: int,
    side: LevelSide,
    touch_count: int,
) -> bool:
    if end <= start:
        return False
    violations = 0
    spanned = 0
    for i in range(start, end + 1):
        spanned += 1
        y = slope * i + intercept
        c = candles[i]
        if side == LevelSide.SUPPORT:
            # Body closes clearly through support
            if min(c.open, c.close) < y and c.close < y:
                violations += 1
        else:
            if max(c.open, c.close) > y and c.close > y:
                violations += 1
    if touch_count >= 4:
        return violations / max(spanned, 1) <= 0.05
    return violations == 0


def _score_line(
    touches: Sequence[PivotPoint],
    start: int,
    end: int,
    n_bars: int,
    *,
    include_volume: bool,
) -> float:
    touch_w = 2.0 ** min(len(touches), 8)
    quality = sum(p.quality for p in touches) / len(touches)
    span_w = (end - start) / max(n_bars, 1)
    recency = 1.0 + 0.5 * (end / max(n_bars, 1))
    vol_w = 1.0
    if include_volume:
        hv = sum(1 for p in touches if p.is_high_volume) / len(touches)
        vol_w = 1.0 + 0.25 * hv
    return touch_w * quality * max(span_w, 0.05) * recency * vol_w


def _dedup_lines(lines: list[TrendlineSegment], price_range: float) -> list[TrendlineSegment]:
    kept: list[TrendlineSegment] = []
    for line in sorted(lines, key=lambda x: x.score, reverse=True):
        dup = False
        for other in kept:
            slope_diff = abs(line.slope - other.slope)
            scale = max(abs(other.slope), abs(line.slope), price_range * 0.001)
            if slope_diff / scale < 0.10:
                mid = (line.end_bar + other.end_bar) / 2
                if abs(line.price_at(int(mid)) - other.price_at(int(mid))) < price_range * 0.02:
                    dup = True
                    break
            overlap = set(line.pivot_bars) & set(other.pivot_bars)
            if line.pivot_bars and len(overlap) / min(len(line.pivot_bars), len(other.pivot_bars)) >= 0.5:
                dup = True
                break
        if not dup:
            kept.append(line)
    return kept


def _fit_trendlines(
    candles: Sequence[Candle],
    pivots: Sequence[PivotPoint],
    side: LevelSide,
    params: StructureEngineParams,
    atr: float | None,
) -> list[TrendlineSegment]:
    if len(pivots) < params.min_touches:
        return []
    # Exclude rightmost pivot from fit anchors (edge artefact), keep for touches
    fit_pivots = list(pivots[:-1]) if len(pivots) > params.min_touches else list(pivots)
    if len(fit_pivots) < 2:
        return []
    prices = [p.price for p in pivots]
    price_range = max(prices) - min(prices) or 1.0
    tol = touch_tolerance(atr, params.touch_atr_mult, price_range)
    n = len(candles)
    candidates: list[TrendlineSegment] = []

    for a in range(len(fit_pivots)):
        for b in range(a + 1, len(fit_pivots)):
            pair = _line_through(fit_pivots[a], fit_pivots[b])
            if pair is None:
                continue
            slope, intercept = pair
            hits = _touches(pivots, slope, intercept, tol)
            if len(hits) < params.min_touches:
                continue
            start = min(p.bar_index for p in hits)
            end = max(p.bar_index for p in hits)
            if not _candle_through_ok(candles, slope, intercept, start, end, side, len(hits)):
                continue
            score = _score_line(
                hits,
                start,
                end,
                n,
                include_volume=params.include_volume_in_line_score,
            )
            candidates.append(
                TrendlineSegment(
                    side=side,
                    slope=slope,
                    intercept=intercept,
                    start_bar=start,
                    end_bar=end,
                    touch_count=len(hits),
                    score=score,
                    source=DetectorSource.MVPP,
                    pivot_bars=tuple(sorted(p.bar_index for p in hits)),
                )
            )

    deduped = _dedup_lines(candidates, price_range)
    return sorted(deduped, key=lambda x: x.score, reverse=True)[: params.max_lines_per_side]


def _zones_from_lines(
    lines: Sequence[TrendlineSegment],
    last_bar: int,
    atr: float | None,
    params: StructureEngineParams,
) -> list[PriceZone]:
    half = (atr or 0.0) * params.zone_atr_mult
    if half <= 0:
        half = 0.0
    zones: list[PriceZone] = []
    for line in lines:
        mid = line.price_at(last_bar)
        width = half if half > 0 else abs(mid) * 0.002
        zones.append(
            PriceZone(
                side=line.side,
                low=mid - width,
                high=mid + width,
                mid=mid,
                score=line.score,
                touch_count=line.touch_count,
                sources=(DetectorSource.MVPP,),
                atr_width=width * 2 if width else None,
            )
        )
    return zones


class MvppStructureAdapter:
    """Primary structure detector (clean-room MVPP-inspired)."""

    name = DetectorSource.MVPP.value

    def detect(
        self,
        candles: Sequence[Candle],
        params: StructureEngineParams = StructureEngineParams(),
        *,
        atr: float | None = None,
    ) -> MarketStructure:
        series = _window(candles, params.window_bars)
        if len(series) < params.fractal_left + params.fractal_right + 3:
            return MarketStructure(source=DetectorSource.MVPP, meta={"reason": "insufficient_bars"})

        atr_val = atr if atr is not None else last_atr(series, params.atr_period)
        res_p, sup_p, high_vol = _adaptive_prices(series, params)
        res_pivots = _causal_fractal_pivots(
            series, res_p, high_vol, LevelSide.RESISTANCE, params.fractal_left, params.fractal_right
        )
        sup_pivots = _causal_fractal_pivots(
            series, sup_p, high_vol, LevelSide.SUPPORT, params.fractal_left, params.fractal_right
        )
        res_lines = _fit_trendlines(series, res_pivots, LevelSide.RESISTANCE, params, atr_val)
        sup_lines = _fit_trendlines(series, sup_pivots, LevelSide.SUPPORT, params, atr_val)
        last_bar = len(series) - 1
        res_zones = _zones_from_lines(res_lines, last_bar, atr_val, params)
        sup_zones = _zones_from_lines(sup_lines, last_bar, atr_val, params)

        score = 0.0
        if res_lines or sup_lines:
            scores = [ln.score for ln in res_lines + sup_lines]
            score = sum(scores) / len(scores)

        return MarketStructure(
            source=DetectorSource.MVPP,
            pivots=tuple(sup_pivots + res_pivots),
            support_trendlines=tuple(sup_lines),
            resistance_trendlines=tuple(res_lines),
            support_zones=tuple(sup_zones),
            resistance_zones=tuple(res_zones),
            structure_score=score,
            meta={
                "bars": len(series),
                "atr": atr_val,
                "volume_in_line_score": params.include_volume_in_line_score,
                "implementation": "clean_room_causal",
            },
        )
