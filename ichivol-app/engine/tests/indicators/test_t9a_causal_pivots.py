"""T9a — causal fractal pivots: anti-lookahead + parity with legacy loops."""

from __future__ import annotations

import pytest

from app.indicators.pivots import (
    CausalPivot,
    detect_causal_extrema,
    detect_causal_ohlc_fractals,
    fractal_confirmed_at,
)
from app.indicators.structure import StructureParams, compute_structure
from app.fibonacci.context import _fractal_pivots, compute_fib_context
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_pivot_never_appears_before_confirmation_index():
    """A pivot at j is unknown until i = j + right (anti-lookahead)."""
    candles = _make_candles(80, seed=7)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    left, right = 2, 2
    hi, lo = detect_causal_ohlc_fractals(highs, lows, left=left, right=right)
    for p in (*hi, *lo):
        assert p.confirmed_bar == p.bar_index + right
        # Truncation before confirmed_bar must not contain this pivot
        trunc = detect_causal_ohlc_fractals(
            highs[: p.confirmed_bar],
            lows[: p.confirmed_bar],
            left=left,
            right=right,
        )
        trunc_bars = {x.bar_index for x in (*trunc[0], *trunc[1])}
        assert p.bar_index not in trunc_bars
        # At confirmation bar (length = confirmed_bar + 1) it appears
        full_to_confirm = detect_causal_ohlc_fractals(
            highs[: p.confirmed_bar + 1],
            lows[: p.confirmed_bar + 1],
            left=left,
            right=right,
        )
        assert p.bar_index in {x.bar_index for x in (*full_to_confirm[0], *full_to_confirm[1])}


def test_fractal_confirmed_at_matches_detect_extrema():
    candles = _make_candles(60, seed=42)
    highs = [c.high for c in candles]
    collected = []
    for i in range(len(highs)):
        hit = fractal_confirmed_at(highs, i, left=3, right=3, mode="max")
        if hit is not None:
            collected.append((hit[0], hit[1], hit[0] + 3))
    assert collected == detect_causal_extrema(highs, left=3, right=3, mode="max")


def test_fib_fractal_wrapper_matches_shared_core():
    candles = _make_candles(100, seed=11)
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    a, b = _fractal_pivots(highs, lows, 2, 2)
    hi, lo = detect_causal_ohlc_fractals(highs, lows, left=2, right=2)
    assert a == [(p.bar_index, p.price) for p in hi]
    assert b == [(p.bar_index, p.price) for p in lo]


def test_structure_outputs_unchanged_vs_inline_reference():
    """Golden lock: compute_structure still matches the pre-T9a inline algorithm."""
    candles = _make_candles(120, seed=19)
    params = StructureParams(swing_lookback=2)
    got = compute_structure(candles, params)

    # Inline reference (legacy loop) — must stay in sync with historical goldens.
    k = 2
    last_high = last_low = prev_high = prev_low = None
    from app.indicators.structure import StructureBias, BosEvent, StructureState

    bias = StructureBias.UNKNOWN
    ref: list[StructureState] = []
    for i in range(len(candles)):
        j = i - k
        if j - k >= 0:
            window = candles[j - k : j + k + 1]
            highs = [c.high for c in window]
            lows = [c.low for c in window]
            if candles[j].high == max(highs):
                prev_high, last_high = last_high, candles[j].high
            if candles[j].low == min(lows):
                prev_low, last_low = last_low, candles[j].low
            if prev_high is not None and prev_low is not None:
                if last_high > prev_high and last_low > prev_low:
                    bias = StructureBias.BULLISH
                elif last_high < prev_high and last_low < prev_low:
                    bias = StructureBias.BEARISH
                else:
                    bias = StructureBias.MIXED
        bos = BosEvent.UNKNOWN
        if last_high is not None and last_low is not None and i > 0:
            close = candles[i].close
            prev_close = candles[i - 1].close
            if prev_close <= last_high < close:
                bos = BosEvent.BULLISH
            elif prev_close >= last_low > close:
                bos = BosEvent.BEARISH
            else:
                bos = BosEvent.NONE
        ref.append(
            StructureState(
                time=candles[i].time,
                last_swing_high=last_high,
                last_swing_low=last_low,
                bias=bias,
                bos=bos,
            )
        )
    assert got == ref


def test_fib_context_stable_on_seed():
    candles = _make_candles(150, seed=7)
    ctx = compute_fib_context(candles, left=2, right=2)
    assert ctx is not None
    # Recompute — deterministic
    assert compute_fib_context(candles, left=2, right=2) == ctx


@pytest.mark.parametrize("kind", ["high", "low"])
def test_causal_pivot_dataclass(kind):
    p = CausalPivot(bar_index=5, price=100.0, confirmed_bar=7, kind=kind)  # type: ignore[arg-type]
    assert p.confirmed_bar == p.bar_index + 2
