"""Ichimoku Analytics — research features (Kijun / Kumo), not live votes.

All fields at index i are causal functions of candles[0..i] and of the
already-causal IchimokuState / ATR series. Nothing here is wired into
build_pipeline / combiner — Strategy Lab only.

Formulas (see module docstring per field in IchimokuAnalyticsState):
  kijun_slope_raw        = kijun[i] - kijun[i - lookback]
  kijun_slope_atr_norm   = slope_raw / ATR[i]
  price_kijun_distance_* = close - kijun (raw / % / ATR)
  kijun_break            = close crosses kijun (rising-edge)
  kijun_retest           = after break, |close-kijun| <= tol * ATR within N bars
  kijun_bounce           = near Kijun + directional reaction candle
  kumo_orientation       = Senkou A vs B (displaced cloud already causal)
  kumo_twist             = orientation flip
  kumo_thickness_*       = expose existing cloud_top - cloud_bot (+ % / ATR)
  tk_cross_age_*         = single shared implementation for Lab + analytics
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.atr import AtrState, compute_atr
from app.indicators.ichimoku import (
    Candle,
    CrossState,
    IchimokuParams,
    IchimokuState,
    compute_ichimoku,
)


class SlopeState(str, Enum):
    RISING = "RISING"
    FLAT = "FLAT"
    FALLING = "FALLING"
    UNKNOWN = "UNKNOWN"


class KumoOrientation(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class BreakState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IchimokuAnalyticsParams:
    slope_lookback: int = 3
    """Bars between kijun samples for slope_raw."""
    slope_flat_atr_frac: float = 0.05
    """|slope|/ATR below this → FLAT (noise band)."""
    retest_atr_tol: float = 0.25
    """Retest zone: |close - kijun| <= tol * ATR."""
    retest_max_bars_after_break: int = 10
    bounce_atr_tol: float = 0.25


@dataclass(frozen=True)
class IchimokuAnalyticsState:
    time: int
    kijun_slope_raw: float | None
    kijun_slope_atr_normalized: float | None
    kijun_slope_state: SlopeState
    price_kijun_distance: float | None
    price_kijun_distance_pct: float | None
    price_kijun_distance_atr: float | None
    kijun_break: BreakState
    kijun_retest_bullish: bool
    kijun_retest_bearish: bool
    kijun_bounce_bullish: bool
    kijun_bounce_bearish: bool
    bars_since_kijun_break_bullish: int | None
    bars_since_kijun_break_bearish: int | None
    kumo_orientation: KumoOrientation
    kumo_twist: bool
    bars_since_kumo_twist: int | None
    kumo_thickness_raw: float | None
    kumo_thickness_pct: float | None
    kumo_thickness_atr: float | None
    tk_cross_age_bullish: int | None
    tk_cross_age_bearish: int | None


def tk_cross_ages(ichi: Sequence[IchimokuState]) -> tuple[list[int | None], list[int | None]]:
    """Shared TK cross age (also used by strategy_lab.features)."""
    age_bull: list[int | None] = []
    age_bear: list[int | None] = []
    last_bull: int | None = None
    last_bear: int | None = None
    for i, s in enumerate(ichi):
        if s.tk_cross == CrossState.BULLISH:
            last_bull = i
        if s.tk_cross == CrossState.BEARISH:
            last_bear = i
        age_bull.append(None if last_bull is None else i - last_bull)
        age_bear.append(None if last_bear is None else i - last_bear)
    return age_bull, age_bear


def _orientation(sa: float | None, sb: float | None) -> KumoOrientation:
    if sa is None or sb is None:
        return KumoOrientation.UNKNOWN
    if sa > sb:
        return KumoOrientation.BULLISH
    if sa < sb:
        return KumoOrientation.BEARISH
    return KumoOrientation.FLAT


def compute_ichimoku_analytics(
    candles: Sequence[Candle],
    *,
    ichi: Sequence[IchimokuState] | None = None,
    atr: Sequence[AtrState] | None = None,
    ichi_params: IchimokuParams = IchimokuParams(),
    params: IchimokuAnalyticsParams = IchimokuAnalyticsParams(),
) -> list[IchimokuAnalyticsState]:
    n = len(candles)
    if ichi is None:
        ichi = compute_ichimoku(candles, ichi_params)
    if atr is None:
        atr = compute_atr(candles)
    if len(ichi) != n or len(atr) != n:
        raise ValueError("ichi/atr length must match candles")

    age_bull, age_bear = tk_cross_ages(ichi)
    lookback = max(1, int(params.slope_lookback))
    flat_frac = float(params.slope_flat_atr_frac)
    retest_tol = float(params.retest_atr_tol)
    retest_max = max(1, int(params.retest_max_bars_after_break))
    bounce_tol = float(params.bounce_atr_tol)

    out: list[IchimokuAnalyticsState] = []
    last_break_bull: int | None = None
    last_break_bear: int | None = None
    last_twist: int | None = None
    prev_orient = KumoOrientation.UNKNOWN

    for i, c in enumerate(candles):
        s = ichi[i]
        kijun = s.kijun
        atr_v = atr[i].atr
        close = c.close

        # --- slope ---
        slope_raw: float | None = None
        slope_atr: float | None = None
        slope_state = SlopeState.UNKNOWN
        ref_i = i - lookback
        if kijun is not None and ref_i >= 0 and ichi[ref_i].kijun is not None:
            slope_raw = kijun - ichi[ref_i].kijun  # type: ignore[operator]
            if atr_v is not None and atr_v > 0:
                slope_atr = slope_raw / atr_v
                if abs(slope_atr) < flat_frac:
                    slope_state = SlopeState.FLAT
                elif slope_atr > 0:
                    slope_state = SlopeState.RISING
                else:
                    slope_state = SlopeState.FALLING

        # --- distance ---
        dist = close - kijun if kijun is not None else None
        dist_pct = (dist / close) if dist is not None and close else None
        dist_atr = (dist / atr_v) if dist is not None and atr_v and atr_v > 0 else None

        # --- break (rising-edge close vs kijun) ---
        brk = BreakState.UNKNOWN
        if kijun is None:
            brk = BreakState.UNKNOWN
        elif i == 0 or ichi[i - 1].kijun is None:
            brk = BreakState.NONE
        else:
            prev_close = candles[i - 1].close
            prev_k = ichi[i - 1].kijun
            assert prev_k is not None
            if prev_close <= prev_k and close > kijun:
                brk = BreakState.BULLISH
                last_break_bull = i
            elif prev_close >= prev_k and close < kijun:
                brk = BreakState.BEARISH
                last_break_bear = i
            else:
                brk = BreakState.NONE

        age_brk_bull = None if last_break_bull is None else i - last_break_bull
        age_brk_bear = None if last_break_bear is None else i - last_break_bear

        # --- retest ---
        retest_bull = False
        retest_bear = False
        if (
            dist_atr is not None
            and age_brk_bull is not None
            and 1 <= age_brk_bull <= retest_max
            and abs(dist_atr) <= retest_tol
        ):
            retest_bull = True
        if (
            dist_atr is not None
            and age_brk_bear is not None
            and 1 <= age_brk_bear <= retest_max
            and abs(dist_atr) <= retest_tol
        ):
            retest_bear = True

        # --- bounce (near + reaction) ---
        bounce_bull = False
        bounce_bear = False
        if kijun is not None and atr_v is not None and atr_v > 0:
            band = bounce_tol * atr_v
            near = abs(close - kijun) <= band
            if near and c.low <= kijun + band and close > kijun and close >= c.open:
                bounce_bull = True
            if near and c.high >= kijun - band and close < kijun and close <= c.open:
                bounce_bear = True

        # --- kumo orientation / twist ---
        orient = _orientation(s.senkou_a, s.senkou_b)
        twist = False
        if (
            orient in (KumoOrientation.BULLISH, KumoOrientation.BEARISH)
            and prev_orient in (KumoOrientation.BULLISH, KumoOrientation.BEARISH)
            and orient != prev_orient
        ):
            twist = True
            last_twist = i
        if orient != KumoOrientation.UNKNOWN:
            prev_orient = orient
        age_twist = None if last_twist is None else i - last_twist

        # --- thickness (reuse raw from ichimoku) ---
        thick = s.kumo_thickness
        thick_pct = (thick / close) if thick is not None and close else None
        thick_atr = (thick / atr_v) if thick is not None and atr_v and atr_v > 0 else None

        out.append(
            IchimokuAnalyticsState(
                time=c.time,
                kijun_slope_raw=slope_raw,
                kijun_slope_atr_normalized=slope_atr,
                kijun_slope_state=slope_state,
                price_kijun_distance=dist,
                price_kijun_distance_pct=dist_pct,
                price_kijun_distance_atr=dist_atr,
                kijun_break=brk,
                kijun_retest_bullish=retest_bull,
                kijun_retest_bearish=retest_bear,
                kijun_bounce_bullish=bounce_bull,
                kijun_bounce_bearish=bounce_bear,
                bars_since_kijun_break_bullish=age_brk_bull,
                bars_since_kijun_break_bearish=age_brk_bear,
                kumo_orientation=orient,
                kumo_twist=twist,
                bars_since_kumo_twist=age_twist,
                kumo_thickness_raw=thick,
                kumo_thickness_pct=thick_pct,
                kumo_thickness_atr=thick_atr,
                tk_cross_age_bullish=age_bull[i],
                tk_cross_age_bearish=age_bear[i],
            )
        )

    return out
