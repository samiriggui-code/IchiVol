from __future__ import annotations

import math

from app.cycle.engine import CycleParams, compute_cycle_series
from app.indicators.ichimoku import Candle


def _sine_candles(n: int, period: float, seed_amp: float = 1.0) -> list[Candle]:
    """Synthetic causal series with a known dominant cycle in log-price space."""
    out: list[Candle] = []
    base = 100.0
    for i in range(n):
        # Additive sine on log-price ≈ multiplicative on price
        phase = 2.0 * math.pi * i / period
        price = base * math.exp(seed_amp * 0.02 * math.sin(phase))
        t = 1_700_000_000 + i * 3600
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def test_sine_wave_fft_near_true_period():
    period = 20.0
    candles = _sine_candles(220, period=period)
    params = CycleParams(window=128, min_period=8.0, max_period=60.0)
    states = compute_cycle_series(candles, params)
    last = states[-1]
    assert last.dominant_period_candles is not None
    # Allow generous band: windowed DFT on short series is approximate
    assert 14.0 <= last.dominant_period_candles <= 28.0, last.dominant_period_candles
    assert last.quality > 0.0
    assert "fft" in last.methods
    assert "hilbert" in last.methods
    assert "acf" in last.methods


def test_cycle_state_has_no_trade_fields():
    candles = _sine_candles(160, period=24.0)
    state = compute_cycle_series(candles, CycleParams(window=96))[-1]
    d = state.to_dict()
    for forbidden in ("buy", "sell", "long", "short", "probability_win"):
        assert forbidden not in d
    assert d["regime"] in {"TREND", "CYCLE", "TRANSITION", "NOISE"}


def test_compute_cycle_state_matches_series_tail():
    """API fast path must match full-series last bar (causal + short stability hist)."""
    from app.cycle.engine import compute_cycle_state

    candles = _sine_candles(180, period=20.0)
    params = CycleParams(window=96, stability_lookback=16)
    full = compute_cycle_series(candles, params)[-1]
    fast = compute_cycle_state(candles, params)
    assert fast.time == full.time
    assert fast.dominant_period_candles == full.dominant_period_candles
    assert fast.phase == full.phase
    assert abs(fast.quality - full.quality) < 1e-12
    assert fast.regime == full.regime
    assert fast.methods_agreement == full.methods_agreement
