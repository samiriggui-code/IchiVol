"""Causal Fibonacci retracement context from swing high/low.

Levels: 23.6 · 38.2 · 50 · 61.8 · 78.6 of the last confirmed impulse.
Uses fractal pivots via ``app.indicators.pivots`` (T9a shared causal core).
Impulse selection + Fib levels remain fibonacci-specific.
Default left/right = 2 (historical Fib defaults — not MVPP's 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.pivots import detect_causal_ohlc_fractals
from app.structure.atr_utils import last_atr

FIB_RATIOS: tuple[float, ...] = (0.236, 0.382, 0.5, 0.618, 0.786)

# Key confluence ratios (architecture example highlights 61.8)
DEFAULT_KEY_RATIOS: tuple[float, ...] = (0.5, 0.618, 0.786)


@dataclass(frozen=True)
class FibLevel:
    ratio: float
    price: float


@dataclass(frozen=True)
class FibContext:
    """Snapshot of Fib retracement vs last close."""

    swing_low: float
    swing_high: float
    impulse: str  # "up" | "down"
    levels: tuple[FibLevel, ...]
    close: float
    atr: float | None
    nearest_ratio: float | None
    nearest_price: float | None
    distance_atr: float | None
    confluence: bool
    key_confluence: bool

    def to_payload(self) -> dict:
        return {
            "swing_low": self.swing_low,
            "swing_high": self.swing_high,
            "impulse": self.impulse,
            "levels": [{"ratio": lv.ratio, "price": lv.price} for lv in self.levels],
            "close": self.close,
            "atr": self.atr,
            "nearest_ratio": self.nearest_ratio,
            "nearest_price": self.nearest_price,
            "distance_atr": self.distance_atr,
            "confluence": self.confluence,
            "key_confluence": self.key_confluence,
        }


def _fractal_pivots(
    highs: Sequence[float],
    lows: Sequence[float],
    left: int,
    right: int,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return (high_pivots, low_pivots) as (bar_index, price), causal (T9a)."""
    hi, lo = detect_causal_ohlc_fractals(highs, lows, left=left, right=right)
    return [(p.bar_index, p.price) for p in hi], [(p.bar_index, p.price) for p in lo]

def _pick_impulse_swings(
    high_pivots: list[tuple[int, float]],
    low_pivots: list[tuple[int, float]],
) -> tuple[float, float, str] | None:
    """Last completed impulse: older pivot → newer opposite pivot."""
    if not high_pivots or not low_pivots:
        return None

    last_h_i, last_h = high_pivots[-1]
    last_l_i, last_l = low_pivots[-1]

    if last_h_i > last_l_i:
        # Low then high → up impulse; retracement from high toward low
        # Find the most recent low before this high
        prior_lows = [p for p in low_pivots if p[0] < last_h_i]
        if not prior_lows:
            return None
        swing_low = prior_lows[-1][1]
        swing_high = last_h
        if swing_high <= swing_low:
            return None
        return swing_low, swing_high, "up"

    # High then low → down impulse
    prior_highs = [p for p in high_pivots if p[0] < last_l_i]
    if not prior_highs:
        return None
    swing_high = prior_highs[-1][1]
    swing_low = last_l
    if swing_high <= swing_low:
        return None
    return swing_low, swing_high, "down"


def compute_fib_levels(swing_low: float, swing_high: float, impulse: str) -> tuple[FibLevel, ...]:
    """Retracement prices from the impulse extreme back toward the origin."""
    span = swing_high - swing_low
    if span <= 0:
        return ()
    levels: list[FibLevel] = []
    for ratio in FIB_RATIOS:
        if impulse == "up":
            # Retrace down from high
            price = swing_high - ratio * span
        else:
            # Retrace up from low
            price = swing_low + ratio * span
        levels.append(FibLevel(ratio=ratio, price=price))
    return tuple(levels)


def compute_fib_context(
    candles: Sequence[Candle],
    *,
    left: int = 2,
    right: int = 2,
    atr_period: int = 14,
    confluence_atr_mult: float = 0.5,
    key_ratios: Sequence[float] = DEFAULT_KEY_RATIOS,
) -> FibContext | None:
    """Build Fib context for the last bar. None if swings insufficient."""
    if len(candles) < left + right + 5:
        return None

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    high_pivots, low_pivots = _fractal_pivots(highs, lows, left, right)
    picked = _pick_impulse_swings(high_pivots, low_pivots)
    if picked is None:
        return None

    swing_low, swing_high, impulse = picked
    levels = compute_fib_levels(swing_low, swing_high, impulse)
    if not levels:
        return None

    close = float(candles[-1].close)
    atr = last_atr(candles, atr_period)
    tol = (atr * confluence_atr_mult) if atr and atr > 0 else abs(close) * 0.002

    nearest = min(levels, key=lambda lv: abs(lv.price - close))
    dist = abs(nearest.price - close)
    distance_atr = (dist / atr) if atr and atr > 0 else None
    confluence = dist <= tol
    key_set = {round(r, 4) for r in key_ratios}
    key_confluence = confluence and round(nearest.ratio, 4) in key_set

    return FibContext(
        swing_low=swing_low,
        swing_high=swing_high,
        impulse=impulse,
        levels=levels,
        close=close,
        atr=atr,
        nearest_ratio=nearest.ratio,
        nearest_price=nearest.price,
        distance_atr=distance_atr,
        confluence=confluence,
        key_confluence=key_confluence,
    )
