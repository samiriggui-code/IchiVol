"""Price Percent Oscillator (PPO) — normalized momentum, experimental feature.

    PPO       = (EMA_fast - EMA_slow) / EMA_slow * 100
    signal    = EMA(PPO, signal_period)
    histogram = PPO - signal

Never votes LONG/SHORT on its own and is NOT wired into decision/pipeline.py
or decision/combiner.py: it is a Lab feature measured through ablation
(docs/ICHIVOL_V2_ROADMAP.md, tranche T-EXP). A signal-line cross is a feature,
not a BUY/SELL.

Causal: state at bar i only reads closes[0..i]. Callers must pass closed
candles only (screener ``_closed_only`` / ``closed_candles``); this module has
no clock and cannot tell a forming bar from a closed one.

EMAs are seeded with the SMA of the first ``period`` values (TA-Lib / most
platforms), so PPO exists from index ``slow - 1`` and the signal line from
``slow + signal - 2``. Earlier bars are ``UNKNOWN`` / ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class PpoCross(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"


class PpoMomentum(str, Enum):
    STRONG_BULLISH = "STRONG_BULLISH"  # ppo > 0, histogram > 0 and rising
    BULLISH = "BULLISH"  # ppo > 0, histogram > 0 (not rising)
    NEUTRAL = "NEUTRAL"  # mixed: e.g. ppo > 0 but histogram <= 0
    BEARISH = "BEARISH"  # ppo < 0, histogram < 0 (not falling)
    STRONG_BEARISH = "STRONG_BEARISH"  # ppo < 0, histogram < 0 and falling
    UNKNOWN = "UNKNOWN"  # warm-up


@dataclass(frozen=True)
class PpoParams:
    """Fixed a priori (12/26/9). Do not tune on the ablation window."""

    fast: int = 12
    slow: int = 26
    signal: int = 9

    def __post_init__(self) -> None:
        if self.fast < 1 or self.signal < 1 or self.slow <= self.fast:
            raise ValueError("PpoParams requires 1 <= fast < slow and signal >= 1")


@dataclass(frozen=True)
class PpoState:
    time: int
    ppo: float | None
    signal: float | None
    histogram: float | None
    ppo_above_signal: bool
    ppo_below_signal: bool
    ppo_above_zero: bool
    ppo_below_zero: bool
    histogram_positive: bool
    histogram_negative: bool
    histogram_rising: bool
    histogram_falling: bool
    signal_cross: PpoCross
    zero_cross: PpoCross
    last_signal_cross: PpoCross
    """Direction of the most recent signal cross (NONE if never)."""
    last_zero_cross: PpoCross
    momentum: PpoMomentum
    bars_since_signal_cross: int | None
    """0 on the cross bar itself; None if no cross yet."""
    bars_since_zero_cross: int | None


def _ema_series(values: Sequence[float | None], period: int) -> list[float | None]:
    """EMA over ``values`` (leading Nones allowed), SMA-seeded."""
    out: list[float | None] = [None] * len(values)
    k = 2.0 / (period + 1.0)
    seed: list[float] = []
    prev: float | None = None
    for i, v in enumerate(values):
        if v is None:
            continue
        if prev is None:
            seed.append(v)
            if len(seed) == period:
                prev = sum(seed) / period
                out[i] = prev
            continue
        prev = prev + k * (v - prev)
        out[i] = prev
    return out


def _cross(prev: float | None, curr: float | None) -> PpoCross:
    if prev is None or curr is None:
        return PpoCross.NONE
    if prev <= 0.0 < curr:
        return PpoCross.BULLISH
    if prev >= 0.0 > curr:
        return PpoCross.BEARISH
    return PpoCross.NONE


def compute_ppo(
    candles: Sequence[Candle],
    params: PpoParams = PpoParams(),
) -> list[PpoState]:
    closes = [c.close for c in candles]
    ema_fast = _ema_series(closes, params.fast)
    ema_slow = _ema_series(closes, params.slow)

    ppo_vals: list[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None or s == 0.0:
            ppo_vals.append(None)
        else:
            ppo_vals.append((f - s) / s * 100.0)
    signal_vals = _ema_series(ppo_vals, params.signal)
    hist_vals: list[float | None] = [
        None if p is None or s is None else p - s
        for p, s in zip(ppo_vals, signal_vals)
    ]

    out: list[PpoState] = []
    last_signal_cross = PpoCross.NONE
    last_zero_cross = PpoCross.NONE
    since_signal: int | None = None
    since_zero: int | None = None

    for i, c in enumerate(candles):
        ppo, sig, hist = ppo_vals[i], signal_vals[i], hist_vals[i]
        prev_ppo = ppo_vals[i - 1] if i > 0 else None
        prev_hist = hist_vals[i - 1] if i > 0 else None

        signal_cross = _cross(prev_hist, hist)
        zero_cross = _cross(prev_ppo, ppo)

        if signal_cross != PpoCross.NONE:
            last_signal_cross = signal_cross
            since_signal = 0
        elif since_signal is not None:
            since_signal += 1
        if zero_cross != PpoCross.NONE:
            last_zero_cross = zero_cross
            since_zero = 0
        elif since_zero is not None:
            since_zero += 1

        rising = hist is not None and prev_hist is not None and hist > prev_hist
        falling = hist is not None and prev_hist is not None and hist < prev_hist

        if ppo is None or hist is None:
            momentum = PpoMomentum.UNKNOWN
        elif ppo > 0 and hist > 0:
            momentum = PpoMomentum.STRONG_BULLISH if rising else PpoMomentum.BULLISH
        elif ppo < 0 and hist < 0:
            momentum = PpoMomentum.STRONG_BEARISH if falling else PpoMomentum.BEARISH
        else:
            momentum = PpoMomentum.NEUTRAL

        out.append(
            PpoState(
                time=c.time,
                ppo=ppo,
                signal=sig,
                histogram=hist,
                ppo_above_signal=hist is not None and hist > 0,
                ppo_below_signal=hist is not None and hist < 0,
                ppo_above_zero=ppo is not None and ppo > 0,
                ppo_below_zero=ppo is not None and ppo < 0,
                histogram_positive=hist is not None and hist > 0,
                histogram_negative=hist is not None and hist < 0,
                histogram_rising=rising,
                histogram_falling=falling,
                signal_cross=signal_cross,
                zero_cross=zero_cross,
                last_signal_cross=last_signal_cross,
                last_zero_cross=last_zero_cross,
                momentum=momentum,
                bars_since_signal_cross=since_signal,
                bars_since_zero_cross=since_zero,
            )
        )
    return out
