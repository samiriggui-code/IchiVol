"""Ichimoku Kinko Hyo engine.

Numeric core (Tenkan/Kijun/Senkou A/B via Donchian midpoint, forward-shifted
cloud) mirrors ichivol-app/src/lib/ichimoku.ts so server and historical
client-side computations agree. On top of that, this module derives the
richer structured state described in the mission brief (price_vs_kumo,
tk_cross, future_kumo, kumo_breakout, kumo_thickness, trend_strength, score).

Anti-lookahead invariant (see tests/indicators/test_ichimoku_lookahead.py):
every field at index i is a pure function of candles[0..i]. In particular,
this module never reads candles[i + k] for k > 0 anywhere. This matters
because both reference repos studied for this project handle the Chikou
Span differently:

- shikokuchuo/ichimoku (R) stores chikou[i] = close[i + kijun - 1] (a
  genuinely future value at row i), but only ever *consumes* it after
  re-aligning the comparison forward by (kijun - 1) rows, so the resulting
  condition is recorded at the row where that close price actually became
  known.
- AndErem314/BacktestBot (Python) also stores chikou_span[i] = close[i+26],
  but then compares it directly against close[i-26] *at row i* with no
  re-alignment -- a genuine lookahead bug that measurably inflates its own
  published backtest results (see _research findings).

Rather than storing a future value and re-aligning it downstream (easy to
get wrong, as BacktestBot shows), this engine never materializes a "future
chikou" field at all. `chikou_state` instead asks a strictly causal
question directly: "as of the close of bar i, is price now clear of where
the cloud stood `displacement` periods ago?" -- comparing candles[i].close
(current) against the cloud at index i - displacement (past). Same trading
intuition as the classical Chikou Span, zero lookahead by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    taker_buy_volume: float | None = None
    """Taker buy volume for this bar, when the provider's own kline response
    already carries it (Binance spot: field already present, no extra API
    call -- see app/market_data/binance.py). `None` everywhere else
    (Twelve Data, biquote); app/indicators/cvd.py degrades gracefully when
    so, same convention as MTF being optional."""


@dataclass(frozen=True)
class IchimokuParams:
    tenkan: int = 9
    kijun: int = 26
    senkou_b: int = 52
    displacement: int = 26


class PriceVsKumo(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    INSIDE = "INSIDE"
    UNKNOWN = "UNKNOWN"


class CrossState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class ChikouState(str, Enum):
    CLEAR_BULLISH = "CLEAR_BULLISH"
    CLEAR_BEARISH = "CLEAR_BEARISH"
    OBSTRUCTED = "OBSTRUCTED"
    UNKNOWN = "UNKNOWN"


class Strength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IchimokuState:
    time: int
    tenkan: Optional[float]
    kijun: Optional[float]
    senkou_a: Optional[float]
    senkou_b: Optional[float]
    cloud_top: Optional[float]
    cloud_bot: Optional[float]
    price_vs_kumo: PriceVsKumo
    tk_cross: CrossState
    tk_strength: Strength
    future_kumo: CrossState
    chikou_state: ChikouState
    kumo_breakout: CrossState
    kumo_thickness: Optional[float]
    trend_strength: Strength
    score: Optional[float]


def _donchian_mid(candles: Sequence[Candle], end: int, length: int) -> Optional[float]:
    start = end - length + 1
    if start < 0:
        return None
    window = candles[start : end + 1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    return (hi + lo) / 2


def _tk_strength_from_gap(rel_gap: float) -> Strength:
    if rel_gap >= 0.01:
        return Strength.STRONG
    if rel_gap >= 0.003:
        return Strength.MODERATE
    return Strength.WEAK


def compute_ichimoku(
    candles: Sequence[Candle],
    params: IchimokuParams = IchimokuParams(),
) -> list[IchimokuState]:
    n = len(candles)
    d = params.displacement

    # Raw lines, causal at index i by construction: `_donchian_mid(candles, i, L)`
    # only ever looks at candles[i-L+1 .. i].
    tenkan_raw: list[Optional[float]] = [None] * n
    kijun_raw: list[Optional[float]] = [None] * n
    span_a_raw: list[Optional[float]] = [None] * n
    span_b_raw: list[Optional[float]] = [None] * n

    for i in range(n):
        tenkan_raw[i] = _donchian_mid(candles, i, params.tenkan)
        kijun_raw[i] = _donchian_mid(candles, i, params.kijun)
        if tenkan_raw[i] is not None and kijun_raw[i] is not None:
            span_a_raw[i] = (tenkan_raw[i] + kijun_raw[i]) / 2
        span_b_raw[i] = _donchian_mid(candles, i, params.senkou_b)

    cloud_top_hist: list[Optional[float]] = [None] * n
    cloud_bot_hist: list[Optional[float]] = [None] * n
    out: list[IchimokuState] = []

    for i in range(n):
        tenkan = tenkan_raw[i]
        kijun = kijun_raw[i]
        close = candles[i].close

        # "Today's" displayed cloud was computed from data as of i-d (<=i): safe.
        cloud_idx = i - d
        sa = span_a_raw[cloud_idx] if cloud_idx >= 0 else None
        sb = span_b_raw[cloud_idx] if cloud_idx >= 0 else None
        cloud_top = max(sa, sb) if sa is not None and sb is not None else None
        cloud_bot = min(sa, sb) if sa is not None and sb is not None else None
        cloud_top_hist[i] = cloud_top
        cloud_bot_hist[i] = cloud_bot

        if cloud_top is None or cloud_bot is None:
            price_vs_kumo = PriceVsKumo.UNKNOWN
        elif close > cloud_top:
            price_vs_kumo = PriceVsKumo.ABOVE
        elif close < cloud_bot:
            price_vs_kumo = PriceVsKumo.BELOW
        else:
            price_vs_kumo = PriceVsKumo.INSIDE

        if tenkan is None or kijun is None:
            tk_cross = CrossState.UNKNOWN
            tk_strength = Strength.UNKNOWN
        else:
            rel_gap = abs(tenkan - kijun) / close if close else 0.0
            tk_strength = _tk_strength_from_gap(rel_gap)
            prev_t = tenkan_raw[i - 1] if i > 0 else None
            prev_k = kijun_raw[i - 1] if i > 0 else None
            if prev_t is None or prev_k is None:
                tk_cross = CrossState.NONE
            elif prev_t <= prev_k and tenkan > kijun:
                tk_cross = CrossState.BULLISH
            elif prev_t >= prev_k and tenkan < kijun:
                tk_cross = CrossState.BEARISH
            else:
                tk_cross = CrossState.NONE

        # Raw (not-yet-displayed) cloud computed from data through *today* only.
        # This is a legitimate forward-looking forecast built from present
        # information -- not a read of future candles.
        sa_now, sb_now = span_a_raw[i], span_b_raw[i]
        if sa_now is None or sb_now is None:
            future_kumo = CrossState.UNKNOWN
        elif sa_now > sb_now:
            future_kumo = CrossState.BULLISH
        elif sa_now < sb_now:
            future_kumo = CrossState.BEARISH
        else:
            future_kumo = CrossState.NONE

        # Chikou re-cast causally: compare *current* close (known now) against
        # the cloud as it stood `d` periods ago (already known back then, and
        # therefore also known now). Never touches candles[i + d].
        ref_idx = i - d
        ref_top = cloud_top_hist[ref_idx] if ref_idx >= 0 else None
        ref_bot = cloud_bot_hist[ref_idx] if ref_idx >= 0 else None
        if ref_top is None or ref_bot is None:
            chikou_state = ChikouState.UNKNOWN
        elif close > ref_top:
            chikou_state = ChikouState.CLEAR_BULLISH
        elif close < ref_bot:
            chikou_state = ChikouState.CLEAR_BEARISH
        else:
            chikou_state = ChikouState.OBSTRUCTED

        # Kumo breakout: transition event, needs bar i-1 (already known at i).
        prev_top = cloud_top_hist[i - 1] if i > 0 else None
        prev_bot = cloud_bot_hist[i - 1] if i > 0 else None
        if cloud_top is None or cloud_bot is None or prev_top is None or prev_bot is None:
            kumo_breakout = CrossState.UNKNOWN if cloud_top is None else CrossState.NONE
        else:
            prev_close = candles[i - 1].close
            if prev_close <= prev_top and close > cloud_top:
                kumo_breakout = CrossState.BULLISH
            elif prev_close >= prev_bot and close < cloud_bot:
                kumo_breakout = CrossState.BEARISH
            else:
                kumo_breakout = CrossState.NONE

        kumo_thickness = (
            cloud_top - cloud_bot if cloud_top is not None and cloud_bot is not None else None
        )

        score, weight = 0.0, 0.0

        def _vote(state: Enum, bullish: Enum, bearish: Enum, w: float) -> None:
            nonlocal score, weight
            if state == bullish:
                score += w
                weight += w
            elif state == bearish:
                score -= w
                weight += w
            elif state not in (CrossState.UNKNOWN, PriceVsKumo.UNKNOWN, ChikouState.UNKNOWN):
                weight += w

        _vote(price_vs_kumo, PriceVsKumo.ABOVE, PriceVsKumo.BELOW, 3.0)
        _vote(tk_cross, CrossState.BULLISH, CrossState.BEARISH, 2.0)
        _vote(future_kumo, CrossState.BULLISH, CrossState.BEARISH, 2.0)
        _vote(chikou_state, ChikouState.CLEAR_BULLISH, ChikouState.CLEAR_BEARISH, 2.0)
        _vote(kumo_breakout, CrossState.BULLISH, CrossState.BEARISH, 3.0)

        final_score = (score / weight * 100) if weight > 0 else None
        if final_score is None:
            trend_strength = Strength.UNKNOWN
        elif abs(final_score) >= 60:
            trend_strength = Strength.STRONG
        elif abs(final_score) >= 25:
            trend_strength = Strength.MODERATE
        else:
            trend_strength = Strength.WEAK

        out.append(
            IchimokuState(
                time=candles[i].time,
                tenkan=tenkan,
                kijun=kijun,
                senkou_a=sa,
                senkou_b=sb,
                cloud_top=cloud_top,
                cloud_bot=cloud_bot,
                price_vs_kumo=price_vs_kumo,
                tk_cross=tk_cross,
                tk_strength=tk_strength,
                future_kumo=future_kumo,
                chikou_state=chikou_state,
                kumo_breakout=kumo_breakout,
                kumo_thickness=kumo_thickness,
                trend_strength=trend_strength,
                score=final_score,
            )
        )

    return out
