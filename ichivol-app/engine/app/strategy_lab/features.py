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
from app.indicators.fvg import FvgParams, FvgState
from app.fibonacci.context import (
    DEFAULT_KEY_RATIOS,
    compute_fib_levels,
    swings_from_impulse,
)
from app.structure.atr_utils import last_atr
from app.strategy_lab.live_parity import live_parity_kwargs


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
    # --- T9d FVG (EXPERIMENTAL Lab; no decision change) ---
    fvg_bullish: bool = False
    fvg_bearish: bool = False
    fvg_active: bool = False
    fvg_status: str | None = None
    """open | partial | filled | invalidated when an FVG event is known this bar."""
    # --- T9f Fib Lab (anchored on T9c impulse when active; no decision change) ---
    fib_confluence: bool = False
    fib_key_confluence: bool = False
    fib_impulse_up: bool = False
    fib_impulse_down: bool = False
    fib_anchor_impulse: bool = False
    fib_nearest_ratio: float | None = None
    # --- T12b Lab ↔ live parity (ADD-ONLY; no live threshold changes) ---
    chikou_state: str = "UNKNOWN"
    future_kumo: str = "UNKNOWN"
    ichimoku_score: float | None = None
    ichimoku_direction: str = "NEUTRAL"
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    donchian_breakout: str = "UNKNOWN"
    regime_trending: bool = False
    regime_ranging: bool = False
    regime_high_volatility: bool = False
    regime_low_volatility: bool = False
    regime_normal_volatility: bool = False
    regime_bull: bool = False
    regime_bear: bool = False
    regime_sideways: bool = False
    regime_stage_pass: str = "pending"
    above_vwap: bool = False
    below_vwap: bool = False
    avwap_aligned: bool = False
    avwap_opposed: bool = False
    inside_value_area: bool = False
    beyond_value_area: bool = False
    wrong_side_value_area: bool = False
    congestion_hvn: bool = False
    location_stage_pass: str = "pending"
    cvd_bias: str = "UNKNOWN"
    rvol_faible: bool = False
    rvol_normal: bool = False
    rvol_eleve: bool = False
    rvol_fort: bool = False
    rvol_extreme: bool = False
    participation_stage_pass: str = "pending"


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


def _fvg_bullish(s: FvgState) -> bool:
    return s.event is not None and s.event.direction == "bullish"


def _fvg_bearish(s: FvgState) -> bool:
    return s.event is not None and s.event.direction == "bearish"


def _fib_kwargs_from_impulse(
    impulse_state: ImpulseState,
    candles: Sequence[Candle],
    bar_index: int,
    *,
    confluence_atr_mult: float = 0.5,
) -> dict:
    """Stamp Fib Lab fields from active ImpulseEvent (causal at bar_index)."""
    empty = dict(
        fib_confluence=False,
        fib_key_confluence=False,
        fib_impulse_up=False,
        fib_impulse_down=False,
        fib_anchor_impulse=False,
        fib_nearest_ratio=None,
    )
    active = impulse_state.active
    if active is None or active.bar > bar_index:
        return empty
    picked = swings_from_impulse(active)
    if picked is None:
        return empty
    swing_low, swing_high, impulse = picked
    levels = compute_fib_levels(swing_low, swing_high, impulse)
    if not levels:
        return empty
    close = float(candles[bar_index].close)
    atr = last_atr(candles[: bar_index + 1], 14)
    tol = (atr * confluence_atr_mult) if atr and atr > 0 else abs(close) * 0.002
    nearest = min(levels, key=lambda lv: abs(lv.price - close))
    dist = abs(nearest.price - close)
    confluence = dist <= tol
    key_set = {round(r, 4) for r in DEFAULT_KEY_RATIOS}
    key_confluence = confluence and round(nearest.ratio, 4) in key_set
    return dict(
        fib_confluence=confluence,
        fib_key_confluence=key_confluence,
        fib_impulse_up=impulse == "up",
        fib_impulse_down=impulse == "down",
        fib_anchor_impulse=True,
        fib_nearest_ratio=nearest.ratio,
    )


def build_feature_series(
    candles: Sequence[Candle],
    *,
    ichi_params: IchimokuParams = IchimokuParams(),
    analytics_params: IchimokuAnalyticsParams = IchimokuAnalyticsParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    impulse_params: ImpulseParams = ImpulseParams(),
    fvg_params: FvgParams = FvgParams(),
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
            "fvg",
            "atr",
            "cmf",
            "rsi",
            "ppo",
            "best_cloud",
            "ichimoku_analytics",
            "location",
            "adx",
            "donchian",
            "cvd",
        ],
        candles,
        params_by_id={
            "ichimoku": ichi_params,
            "rvol": rvol_params,
            "structure": structure_params,
            "impulse": impulse_params,
            "fvg": fvg_params,
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
    fvg = computed["fvg"]
    atr = computed["atr"]
    cmf = computed["cmf"]
    rsi = computed["rsi"]
    ppo = computed["ppo"]
    best_cloud = computed["best_cloud"]
    analytics = computed["ichimoku_analytics"]
    location = computed["location"]
    adx = computed["adx"]
    donchian = computed["donchian"]
    cvd = computed["cvd"]

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
        parity = live_parity_kwargs(
            ichi=s,
            rvol=rvol[i],
            atr=atr[i],
            adx=adx[i],
            donchian=donchian[i],
            location=location[i],
            cvd=cvd[i],
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
                fvg_bullish=_fvg_bullish(fvg[i]),
                fvg_bearish=_fvg_bearish(fvg[i]),
                fvg_active=len(fvg[i].active) > 0,
                fvg_status=fvg[i].event.status if fvg[i].event is not None else None,
                **_fib_kwargs_from_impulse(impulse[i], candles, i),
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
                **parity,
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
