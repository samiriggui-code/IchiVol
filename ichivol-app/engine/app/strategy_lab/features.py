"""Causal per-bar feature snapshot for ruleset evaluation.

Every field at index i is derived only from candles[0..i] via existing
Grand V2 indicators (Ichimoku, RVOL, structure, ATR, CMF, RSI) plus
Ichimoku Analytics (Kijun / Kumo research layer — not live votes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.indicators.atr import AtrParams, AtrState
from app.indicators.cmf import CmfParams, CmfState
from app.indicators.ichimoku import (
    CrossState,
    IchimokuParams,
    IchimokuState,
    PriceVsKumo,
)
from app.indicators.ichimoku import Candle
from app.indicators.ichimoku_analytics import (
    BreakState,
    IchimokuAnalyticsParams,
    IchimokuAnalyticsState,
    KumoOrientation,
    SlopeState,
)
from app.indicators.registry import REGISTRY
from app.indicators.rsi import RsiParams, RsiState
from app.indicators.best_cloud import (
    BestCloudParams,
    BestCloudState,
    CloudCross,
)
from app.indicators.ppo import PpoCross, PpoParams, PpoState
from app.indicators.rvol import RvolParams, RvolState
from app.indicators.structure import (
    BosEvent,
    StructureBias,
    StructureEventType,
    StructureParams,
    StructureState,
)
from app.indicators.impulse import ImpulseParams, ImpulseState


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
    # --- T-EXP experimental features (Lab only; NOT live votes, see ROADMAP) ---
    ppo: float | None = None
    ppo_signal: float | None = None
    ppo_histogram: float | None = None
    ppo_above_signal: bool = False
    ppo_below_signal: bool = False
    ppo_above_zero: bool = False
    ppo_below_zero: bool = False
    ppo_histogram_rising: bool = False
    ppo_histogram_falling: bool = False
    ppo_signal_cross_bullish: bool = False
    ppo_signal_cross_bearish: bool = False
    ppo_cross_age_bullish: int | None = None
    """Bars since last signal cross, only while that cross was bullish."""
    ppo_cross_age_bearish: int | None = None
    ppo_momentum: str = "UNKNOWN"
    best_cloud_trend: str = "UNKNOWN"
    best_cloud_bullish: bool = False
    best_cloud_bearish: bool = False
    best_cloud_inside: bool = False
    best_cloud_cross_bullish: bool = False
    best_cloud_cross_bearish: bool = False
    best_cloud_cross_age_bullish: int | None = None
    best_cloud_cross_age_bearish: int | None = None
    best_cloud_distance_pct: float | None = None
    # --- T9b CHoCH / break quality (alongside legacy bos_*; no decision change) ---
    choch_bullish: bool = False
    choch_bearish: bool = False
    break_quality: str | None = None
    """wick | close | confirmed when a StructureEvent is known this bar."""
    # --- T9c impulse (EXPERIMENTAL Lab; no decision change) ---
    impulse_bullish: bool = False
    impulse_bearish: bool = False
    impulse_displacement_atr: float | None = None


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
    ppo: list[PpoState] = field(default_factory=list)
    best_cloud: list[BestCloudState] = field(default_factory=list)


def _ppo_kwargs(p: PpoState) -> dict:
    bullish = p.last_signal_cross == PpoCross.BULLISH
    bearish = p.last_signal_cross == PpoCross.BEARISH
    return dict(
        ppo=p.ppo,
        ppo_signal=p.signal,
        ppo_histogram=p.histogram,
        ppo_above_signal=p.ppo_above_signal,
        ppo_below_signal=p.ppo_below_signal,
        ppo_above_zero=p.ppo_above_zero,
        ppo_below_zero=p.ppo_below_zero,
        ppo_histogram_rising=p.histogram_rising,
        ppo_histogram_falling=p.histogram_falling,
        ppo_signal_cross_bullish=p.signal_cross == PpoCross.BULLISH,
        ppo_signal_cross_bearish=p.signal_cross == PpoCross.BEARISH,
        ppo_cross_age_bullish=p.bars_since_signal_cross if bullish else None,
        ppo_cross_age_bearish=p.bars_since_signal_cross if bearish else None,
        ppo_momentum=p.momentum.value,
    )


def _best_cloud_kwargs(b: BestCloudState) -> dict:
    bullish = b.last_cross == CloudCross.BULLISH_CROSS
    bearish = b.last_cross == CloudCross.BEARISH_CROSS
    return dict(
        best_cloud_trend=b.trend.value,
        best_cloud_bullish=b.trend.value == "BULLISH",
        best_cloud_bearish=b.trend.value == "BEARISH",
        best_cloud_inside=b.price_inside_cloud,
        best_cloud_cross_bullish=b.cross == CloudCross.BULLISH_CROSS,
        best_cloud_cross_bearish=b.cross == CloudCross.BEARISH_CROSS,
        best_cloud_cross_age_bullish=b.bars_since_cross if bullish else None,
        best_cloud_cross_age_bearish=b.bars_since_cross if bearish else None,
        best_cloud_distance_pct=b.distance_price_cloud_pct,
    )


def _choch_bullish(s: StructureState) -> bool:
    ev = s.event
    return (
        ev is not None
        and ev.type == StructureEventType.CHOCH
        and ev.direction == "bullish"
    )


def _choch_bearish(s: StructureState) -> bool:
    ev = s.event
    return (
        ev is not None
        and ev.type == StructureEventType.CHOCH
        and ev.direction == "bearish"
    )


def _break_quality(s: StructureState) -> str | None:
    return s.event.break_quality.value if s.event is not None else None


def _impulse_bullish(s: ImpulseState) -> bool:
    ev = s.event
    return ev is not None and ev.direction == "bullish"


def _impulse_bearish(s: ImpulseState) -> bool:
    ev = s.event
    return ev is not None and ev.direction == "bearish"


def _impulse_disp(s: ImpulseState) -> float | None:
    return s.event.displacement_atr if s.event is not None else None


def build_feature_series(
    candles: Sequence[Candle],
    *,
    ichi_params: IchimokuParams = IchimokuParams(),
    analytics_params: IchimokuAnalyticsParams = IchimokuAnalyticsParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    impulse_params: ImpulseParams = ImpulseParams(),
    atr_params: AtrParams = AtrParams(),
    cmf_params: CmfParams = CmfParams(),
    rsi_params: RsiParams = RsiParams(),
    ppo_params: PpoParams = PpoParams(),
    best_cloud_params: BestCloudParams = BestCloudParams(),
) -> FeatureSeries:
    computed = REGISTRY.compute_many(
        [
            "ichimoku",
            "rvol",
            "structure",
            "impulse",
            "atr",
            "cmf",
            "rsi",
            "ppo",
            "best_cloud",
            "ichimoku_analytics",
        ],
        candles,
        params_by_id={
            "ichimoku": ichi_params,
            "rvol": rvol_params,
            "structure": structure_params,
            "impulse": impulse_params,
            "atr": atr_params,
            "cmf": cmf_params,
            "rsi": rsi_params,
            "ppo": ppo_params,
            "best_cloud": best_cloud_params,
            "ichimoku_analytics": analytics_params,
        },
    )
    ichi = computed["ichimoku"]
    rvol = computed["rvol"]
    structure = computed["structure"]
    impulse = computed["impulse"]
    atr = computed["atr"]
    cmf = computed["cmf"]
    rsi = computed["rsi"]
    ppo = computed["ppo"]
    best_cloud = computed["best_cloud"]
    analytics = computed["ichimoku_analytics"]

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
                choch_bullish=_choch_bullish(structure[i]),
                choch_bearish=_choch_bearish(structure[i]),
                break_quality=_break_quality(structure[i]),
                impulse_bullish=_impulse_bullish(impulse[i]),
                impulse_bearish=_impulse_bearish(impulse[i]),
                impulse_displacement_atr=_impulse_disp(impulse[i]),
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
                **_ppo_kwargs(ppo[i]),
                **_best_cloud_kwargs(best_cloud[i]),
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
        ppo=ppo,
        best_cloud=best_cloud,
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
