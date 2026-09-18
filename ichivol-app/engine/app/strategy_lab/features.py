"""Causal per-bar feature snapshot for ruleset evaluation.

Every field at index i is derived only from candles[0..i] via existing
Grand V2 indicators (Ichimoku, RVOL, structure, ATR, CMF, RSI) plus
Ichimoku Analytics (Kijun / Kumo research layer — not live votes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.atr import AtrParams, AtrState, compute_atr
from app.indicators.cmf import CmfParams, CmfState, compute_cmf
from app.indicators.ichimoku import (
    CrossState,
    IchimokuParams,
    IchimokuState,
    PriceVsKumo,
    compute_ichimoku,
)
from app.indicators.ichimoku import Candle
from app.indicators.ichimoku_analytics import (
    BreakState,
    IchimokuAnalyticsParams,
    IchimokuAnalyticsState,
    KumoOrientation,
    SlopeState,
    compute_ichimoku_analytics,
)
from app.indicators.rsi import RsiParams, RsiState, compute_rsi
from app.indicators.rvol import RvolParams, RvolState, compute_rvol
from app.indicators.structure import (
    BosEvent,
    StructureBias,
    StructureParams,
    StructureState,
    compute_structure,
)


@dataclass(frozen=True)
class FeatureBar:
    index: int
    time: int
    price_above_kumo: bool
    price_below_kumo: bool
    tenkan_above_kijun: bool
    tenkan_below_kijun: bool
    tk_cross_bullish: bool
    tk_cross_bearish: bool
    tk_cross_age_bullish: int | None
    """Bars since last bullish TK cross including current; None if never."""
    tk_cross_age_bearish: int | None
    kumo_breakout_bullish: bool
    kumo_breakout_bearish: bool
    rvol: float | None
    bos_bullish: bool
    bos_bearish: bool
    structure_bias_bullish: bool
    structure_bias_bearish: bool
    atr: float | None
    atr_percentile: float | None
    atr_expansion: bool
    """True when ATR is known and strictly greater than previous bar's ATR."""
    cmf: float | None
    rsi: float | None
    # --- Ichimoku Analytics (research) ---
    kijun_slope_state: str
    kijun_slope_atr_normalized: float | None
    price_kijun_distance_atr: float | None
    kijun_break_bullish: bool
    kijun_break_bearish: bool
    kijun_retest_bullish: bool
    kijun_retest_bearish: bool
    kijun_bounce_bullish: bool
    kijun_bounce_bearish: bool
    kumo_orientation: str
    kumo_twist: bool
    bars_since_kumo_twist: int | None
    kumo_thickness_atr: float | None
    kumo_thickness_pct: float | None


@dataclass(frozen=True)
class FeatureSeries:
    candles: list[Candle]
    bars: list[FeatureBar]
    ichimoku: list[IchimokuState]
    analytics: list[IchimokuAnalyticsState]
    rvol: list[RvolState]
    structure: list[StructureState]
    atr: list[AtrState]
    cmf: list[CmfState]
    rsi: list[RsiState]


def build_feature_series(
    candles: Sequence[Candle],
    *,
    ichi_params: IchimokuParams = IchimokuParams(),
    analytics_params: IchimokuAnalyticsParams = IchimokuAnalyticsParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    atr_params: AtrParams = AtrParams(),
    cmf_params: CmfParams = CmfParams(),
    rsi_params: RsiParams = RsiParams(),
) -> FeatureSeries:
    ichi = compute_ichimoku(candles, ichi_params)
    rvol = compute_rvol(candles, rvol_params)
    structure = compute_structure(candles, structure_params)
    atr = compute_atr(candles, atr_params)
    cmf = compute_cmf(candles, cmf_params)
    rsi = compute_rsi(candles, rsi_params)
    analytics = compute_ichimoku_analytics(
        candles,
        ichi=ichi,
        atr=atr,
        ichi_params=ichi_params,
        params=analytics_params,
    )

    bars: list[FeatureBar] = []
    for i, c in enumerate(candles):
        s = ichi[i]
        a = analytics[i]
        tenkan_above = (
            s.tenkan is not None and s.kijun is not None and s.tenkan > s.kijun
        )
        tenkan_below = (
            s.tenkan is not None and s.kijun is not None and s.tenkan < s.kijun
        )
        atr_prev = atr[i - 1].atr if i > 0 else None
        atr_now = atr[i].atr
        expansion = (
            atr_now is not None and atr_prev is not None and atr_now > atr_prev
        )
        bars.append(
            FeatureBar(
                index=i,
                time=c.time,
                price_above_kumo=s.price_vs_kumo == PriceVsKumo.ABOVE,
                price_below_kumo=s.price_vs_kumo == PriceVsKumo.BELOW,
                tenkan_above_kijun=tenkan_above,
                tenkan_below_kijun=tenkan_below,
                tk_cross_bullish=s.tk_cross == CrossState.BULLISH,
                tk_cross_bearish=s.tk_cross == CrossState.BEARISH,
                tk_cross_age_bullish=a.tk_cross_age_bullish,
                tk_cross_age_bearish=a.tk_cross_age_bearish,
                kumo_breakout_bullish=s.kumo_breakout == CrossState.BULLISH,
                kumo_breakout_bearish=s.kumo_breakout == CrossState.BEARISH,
                rvol=rvol[i].rvol,
                bos_bullish=structure[i].bos == BosEvent.BULLISH,
                bos_bearish=structure[i].bos == BosEvent.BEARISH,
                structure_bias_bullish=structure[i].bias == StructureBias.BULLISH,
                structure_bias_bearish=structure[i].bias == StructureBias.BEARISH,
                atr=atr_now,
                atr_percentile=atr[i].percentile,
                atr_expansion=expansion,
                cmf=cmf[i].cmf,
                rsi=rsi[i].rsi,
                kijun_slope_state=a.kijun_slope_state.value,
                kijun_slope_atr_normalized=a.kijun_slope_atr_normalized,
                price_kijun_distance_atr=a.price_kijun_distance_atr,
                kijun_break_bullish=a.kijun_break == BreakState.BULLISH,
                kijun_break_bearish=a.kijun_break == BreakState.BEARISH,
                kijun_retest_bullish=a.kijun_retest_bullish,
                kijun_retest_bearish=a.kijun_retest_bearish,
                kijun_bounce_bullish=a.kijun_bounce_bullish,
                kijun_bounce_bearish=a.kijun_bounce_bearish,
                kumo_orientation=a.kumo_orientation.value,
                kumo_twist=a.kumo_twist,
                bars_since_kumo_twist=a.bars_since_kumo_twist,
                kumo_thickness_atr=a.kumo_thickness_atr,
                kumo_thickness_pct=a.kumo_thickness_pct,
            )
        )

    return FeatureSeries(
        candles=list(candles),
        bars=bars,
        ichimoku=ichi,
        analytics=analytics,
        rvol=rvol,
        structure=structure,
        atr=atr,
        cmf=cmf,
        rsi=rsi,
    )


# Re-export enums for Lab consumers
__all__ = [
    "FeatureBar",
    "FeatureSeries",
    "build_feature_series",
    "SlopeState",
    "KumoOrientation",
    "BreakState",
]
