"""PPO value tests — hand-computed reference, warm-up, crosses, momentum."""

from __future__ import annotations

import math

import pytest

from app.indicators.ichimoku import Candle
from app.indicators.ppo import PpoCross, PpoMomentum, PpoParams, compute_ppo


def _series(closes: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=c, high=c + 1, low=c - 1, close=c, volume=100.0)
        for i, c in enumerate(closes)
    ]


# PPO tracks slope: phase-shift so the slope peaks after warm-up (bar ~75), then
# histogram turns negative (~bar 90) before ppo crosses zero (price peak + lag).
_CYCLE = [100 + 20 * math.sin(2 * math.pi * (i - 75) / 300) for i in range(300)]


def _ref_ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    out[period - 1] = e
    for i in range(period, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def test_matches_independent_reference():
    closes = [100 + 5 * math.sin(i / 4) + i * 0.1 for i in range(120)]
    p = PpoParams()
    states = compute_ppo(_series(closes), p)

    fast = _ref_ema(closes, p.fast)
    slow = _ref_ema(closes, p.slow)
    ppo = [
        None if f is None or s is None else (f - s) / s * 100
        for f, s in zip(fast, slow)
    ]
    first = p.slow - 1
    sig_seed = sum(ppo[first : first + p.signal]) / p.signal
    sig = [None] * len(closes)
    sig[first + p.signal - 1] = sig_seed
    k = 2 / (p.signal + 1)
    for i in range(first + p.signal, len(closes)):
        sig[i] = ppo[i] * k + sig[i - 1] * (1 - k)

    for i, st in enumerate(states):
        if ppo[i] is None:
            assert st.ppo is None
        else:
            assert st.ppo == pytest.approx(ppo[i], rel=1e-12, abs=1e-12)
        if sig[i] is None:
            assert st.signal is None and st.histogram is None
        else:
            assert st.signal == pytest.approx(sig[i], rel=1e-12, abs=1e-12)
            assert st.histogram == pytest.approx(ppo[i] - sig[i], abs=1e-12)


def test_warmup_indices():
    p = PpoParams()
    states = compute_ppo(_series([100.0 + i for i in range(80)]), p)
    assert all(s.ppo is None for s in states[: p.slow - 1])
    assert states[p.slow - 1].ppo is not None
    assert states[p.slow - 1].signal is None
    assert states[p.slow + p.signal - 3].signal is None
    assert states[p.slow + p.signal - 2].signal is not None
    assert all(s.momentum == PpoMomentum.UNKNOWN for s in states[: p.slow - 1])


def test_constant_price_is_flat_zero():
    states = compute_ppo(_series([50.0] * 60))
    last = states[-1]
    assert last.ppo == pytest.approx(0.0, abs=1e-12)
    assert last.histogram == pytest.approx(0.0, abs=1e-12)
    assert last.momentum == PpoMomentum.NEUTRAL
    assert last.signal_cross == PpoCross.NONE


def test_short_series_is_all_unknown():
    states = compute_ppo(_series([1.0, 2.0, 3.0]))
    assert len(states) == 3
    assert all(s.ppo is None and s.momentum == PpoMomentum.UNKNOWN for s in states)


def test_uptrend_is_bullish_above_zero():
    # Accelerating trend (growth rate rises); constant-rate growth converges to
    # histogram == 0, so it would not exercise the histogram.
    closes = [100 * math.exp(1e-4 * i * i) for i in range(150)]
    last = compute_ppo(_series(closes))[-1]
    assert last.ppo_above_zero and not last.ppo_below_zero
    assert last.histogram_positive
    assert last.momentum in (PpoMomentum.BULLISH, PpoMomentum.STRONG_BULLISH)


def test_reversal_produces_bearish_signal_cross_and_ages():
    closes = _CYCLE
    states = compute_ppo(_series(closes))

    cross_idx = [i for i, s in enumerate(states) if s.signal_cross == PpoCross.BEARISH]
    assert cross_idx, "expected a bearish signal cross after reversal"
    i = cross_idx[0]
    assert states[i].bars_since_signal_cross == 0
    assert states[i].last_signal_cross == PpoCross.BEARISH
    assert states[i + 3].bars_since_signal_cross == 3
    assert states[i].ppo_below_signal and not states[i].ppo_above_signal

    zero_idx = [j for j, s in enumerate(states) if s.zero_cross == PpoCross.BEARISH]
    assert zero_idx and zero_idx[0] > i, "zero cross lags the signal cross"
    bearish = (PpoMomentum.BEARISH, PpoMomentum.STRONG_BEARISH)
    assert any(s.momentum in bearish for s in states[zero_idx[0] : zero_idx[0] + 40])


def test_pullback_inside_uptrend_is_neutral_not_bearish():
    """ppo > 0 but histogram < 0 (momentum slowing) must read NEUTRAL."""
    closes = _CYCLE
    states = compute_ppo(_series(closes))
    hits = [s for s in states if s.ppo_above_zero and s.histogram_negative]
    assert hits, "expected a decelerating-uptrend bar"
    assert all(s.momentum == PpoMomentum.NEUTRAL for s in hits)


def test_params_validation():
    with pytest.raises(ValueError):
        PpoParams(fast=26, slow=12)
