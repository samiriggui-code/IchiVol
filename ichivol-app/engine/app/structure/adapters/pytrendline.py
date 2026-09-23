"""pytrendline-inspired offline detector (clean-room, pivot-constrained).

Exhaustive search is O(N³) — hard-capped via ``pytrendline_max_bars``.
Intended for cache / nightly / STRUCTURE_PYTRENDLINE experiments, not
the screener hot path when ``pytrendline_offline_only`` is True.
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


def _pivots(candles: Sequence[Candle], lookback: int = 3) -> tuple[list[PivotPoint], list[PivotPoint]]:
    n = len(candles)
    lows: list[PivotPoint] = []
    highs: list[PivotPoint] = []
    last = n - 1
    # Force first/last as anchors (pytrendline-style) — provisional / repaint.
    if n >= 2:
        lows.append(
            PivotPoint(
                0,
                candles[0].time,
                candles[0].low,
                LevelSide.SUPPORT,
                0.5,
                confirmed_bar=last,
                provisional=True,
            )
        )
        highs.append(
            PivotPoint(
                0,
                candles[0].time,
                candles[0].high,
                LevelSide.RESISTANCE,
                0.5,
                confirmed_bar=last,
                provisional=True,
            )
        )
    for i in range(n):
        j = i - lookback
        if j - lookback < 0:
            continue
        window = candles[j - lookback : j + lookback + 1]
        if candles[j].low == min(c.low for c in window):
            lows.append(
                PivotPoint(
                    j,
                    candles[j].time,
                    candles[j].low,
                    LevelSide.SUPPORT,
                    confirmed_bar=i,
                    provisional=False,
                )
            )
        if candles[j].high == max(c.high for c in window):
            highs.append(
                PivotPoint(
                    j,
                    candles[j].time,
                    candles[j].high,
                    LevelSide.RESISTANCE,
                    confirmed_bar=i,
                    provisional=False,
                )
            )
    if n >= 2:
        lows.append(
            PivotPoint(
                last,
                candles[last].time,
                candles[last].low,
                LevelSide.SUPPORT,
                0.5,
                confirmed_bar=last,
                provisional=True,
            )
        )
        highs.append(
            PivotPoint(
                last,
                candles[last].time,
                candles[last].high,
                LevelSide.RESISTANCE,
                0.5,
                confirmed_bar=last,
                provisional=True,
            )
        )
    # unique by bar
    def uniq(pts: list[PivotPoint]) -> list[PivotPoint]:
        seen: set[int] = set()
        out: list[PivotPoint] = []
        for p in pts:
            if p.bar_index in seen:
                continue
            seen.add(p.bar_index)
            out.append(p)
        return out

    return uniq(lows), uniq(highs)


def _detect_side(
    candles: Sequence[Candle],
    pivots: Sequence[PivotPoint],
    side: LevelSide,
    atr: float | None,
    params: StructureEngineParams,
) -> tuple[list[TrendlineSegment], list[dict]]:
    if len(pivots) < 2:
        return [], []
    tol = touch_tolerance(atr, params.max_pt_error_atr_mult, pivots[0].price)
    breakout_tol = touch_tolerance(atr, params.breakout_atr_mult, pivots[0].price)
    n = len(candles)
    lines: list[TrendlineSegment] = []
    breakouts: list[dict] = []

    for a in range(len(pivots)):
        for b in range(a + 1, len(pivots)):
            p0, p1 = pivots[a], pivots[b]
            if p1.bar_index <= p0.bar_index:
                continue
            slope = (p1.price - p0.price) / (p1.bar_index - p0.bar_index)
            intercept = p0.price - slope * p0.bar_index
            point_idxs: list[int] = []
            errs: list[float] = []
            breakout_at: int | None = None
            for k in range(p0.bar_index, n):
                y = slope * k + intercept
                c = candles[k]
                price = c.low if side == LevelSide.SUPPORT else c.high
                err = abs(price - y)
                if err <= tol:
                    point_idxs.append(k)
                    errs.append(err)
                # breakout: close through line beyond tolerance
                if side == LevelSide.SUPPORT and c.close < y - breakout_tol:
                    breakout_at = k
                    break
                if side == LevelSide.RESISTANCE and c.close > y + breakout_tol:
                    breakout_at = k
                    break

            if len(point_idxs) < params.min_touches:
                continue
            # ignore broken lines for S/R "clean" set (pytrendline ignore_breakouts=True)
            if breakout_at is not None:
                breakouts.append(
                    {
                        "side": side.value,
                        "breakout_bar": breakout_at,
                        "slope": slope,
                        "intercept": intercept,
                        "points": len(point_idxs),
                    }
                )
                continue

            mean_err = sum(errs) / len(errs) if errs else tol
            avg_range = atr or (sum(c.high - c.low for c in candles) / n)
            score = (avg_range / max(mean_err, 1e-9)) * (2.5 ** min(len(point_idxs), 8))
            lines.append(
                TrendlineSegment(
                    side=side,
                    slope=slope,
                    intercept=intercept,
                    start_bar=min(point_idxs),
                    end_bar=max(point_idxs),
                    touch_count=len(point_idxs),
                    score=score,
                    source=DetectorSource.PYTRENDLINE,
                    pivot_bars=tuple(point_idxs),
                )
            )

    lines.sort(key=lambda x: x.score, reverse=True)
    return lines[: params.max_lines_per_side], breakouts


class PyTrendlineStructureAdapter:
    """Offline / capped exhaustive detector (clean-room pytrendline-inspired)."""

    name = DetectorSource.PYTRENDLINE.value

    def detect(
        self,
        candles: Sequence[Candle],
        params: StructureEngineParams = StructureEngineParams(),
        *,
        atr: float | None = None,
        allow_online: bool = False,
    ) -> MarketStructure:
        if params.pytrendline_offline_only and not allow_online:
            # Still compute on capped window — caller marks usage as offline
            pass

        series = _window(candles, min(params.pytrendline_max_bars, params.window_bars))
        if len(series) < 10:
            return MarketStructure(
                source=DetectorSource.PYTRENDLINE,
                meta={"reason": "insufficient_bars", "offline_only": params.pytrendline_offline_only},
            )

        atr_val = atr if atr is not None else last_atr(series, params.atr_period)
        lows, highs = _pivots(series)
        sup_lines, sup_bo = _detect_side(series, lows, LevelSide.SUPPORT, atr_val, params)
        res_lines, res_bo = _detect_side(series, highs, LevelSide.RESISTANCE, atr_val, params)

        last = len(series) - 1
        half = (atr_val or 0.0) * params.zone_atr_mult
        zones_s: list[PriceZone] = []
        zones_r: list[PriceZone] = []
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
                sources=(DetectorSource.PYTRENDLINE,),
                atr_width=width * 2,
            )
            if line.side == LevelSide.SUPPORT:
                zones_s.append(zone)
            else:
                zones_r.append(zone)

        return MarketStructure(
            source=DetectorSource.PYTRENDLINE,
            pivots=tuple(lows + highs),
            support_trendlines=tuple(sup_lines),
            resistance_trendlines=tuple(res_lines),
            support_zones=tuple(zones_s),
            resistance_zones=tuple(zones_r),
            structure_score=float(len(sup_lines) + len(res_lines)),
            meta={
                "bars": len(series),
                "atr": atr_val,
                "offline_only": params.pytrendline_offline_only,
                "breakouts": (sup_bo + res_bo)[:20],
                "implementation": "clean_room_offline_capped",
            },
        )
