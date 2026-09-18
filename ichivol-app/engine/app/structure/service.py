"""High-level Market Structure detection service."""

from __future__ import annotations

from typing import Sequence

from app.indicators.ichimoku import Candle
from app.structure.adapters.mvpp import MvppStructureAdapter
from app.structure.adapters.pytrendline import PyTrendlineStructureAdapter
from app.structure.adapters.trendln import TrendlnStructureAdapter
from app.structure.atr_utils import last_atr
from app.structure.breakout import evaluate_breakout
from app.structure.consensus import build_consensus
from app.structure.params import StructureEngineParams
from app.structure.types import MarketStructureSnapshot, PriceZone


def detect_market_structure(
    candles: Sequence[Candle],
    params: StructureEngineParams = StructureEngineParams(),
    *,
    include_pytrendline: bool = False,
    rvol: float | None = None,
) -> MarketStructureSnapshot:
    """Run MVPP + trendln (+ optional pytrendline) and build consensus zones.

    ``include_pytrendline`` defaults False for screener safety (O(N³) capped).
    """
    if not candles:
        empty = build_consensus([], params, atr=None)
        return MarketStructureSnapshot(consensus=empty)

    atr = last_atr(candles, params.atr_period)
    mvpp = MvppStructureAdapter().detect(candles, params, atr=atr)
    trendln = TrendlnStructureAdapter().detect(candles, params, atr=atr)
    by_det = {mvpp.source.value: mvpp, trendln.source.value: trendln}
    parts = [mvpp, trendln]

    if include_pytrendline:
        pyt = PyTrendlineStructureAdapter().detect(
            candles, params, atr=atr, allow_online=True
        )
        by_det[pyt.source.value] = pyt
        parts.append(pyt)

    consensus = build_consensus(parts, params, atr=atr)
    last = candles[-1]
    nearest_s = _nearest(consensus.support_zones, last.close)
    nearest_r = _nearest(consensus.resistance_zones, last.close)
    dist_s = nearest_s.distance(last.close) if nearest_s else None
    dist_r = nearest_r.distance(last.close) if nearest_r else None

    breakouts = evaluate_breakout(
        last,
        list(consensus.resistance_zones) + list(consensus.support_zones),
        atr=atr,
        rvol=rvol,
    )

    return MarketStructureSnapshot(
        consensus=consensus,
        by_detector=by_det,
        atr=atr,
        last_close=last.close,
        distance_to_support=dist_s,
        distance_to_resistance=dist_r,
        breakout_candidates=tuple(breakouts),
        retest_candidates=(),
    )


def _nearest(zones: Sequence[PriceZone], price: float) -> PriceZone | None:
    if not zones:
        return None
    return min(zones, key=lambda z: z.distance(price))
