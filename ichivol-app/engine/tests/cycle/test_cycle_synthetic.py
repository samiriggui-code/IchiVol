"""Claude review probes — T-CYCLE B1/B2 synthetic truth (observe-only)."""

from __future__ import annotations

import math

import pytest

from app.cycle.engine import CycleParams, compute_cycle_series, compute_cycle_state
from app.cycle.hilbert import PHASE_GROUP_DELAY_BARS, estimate_hilbert
from app.cycle.study import (
    make_random_walk_candles,
    make_sine_candles,
    validate_cycle_synthetic,
)
from app.cycle.types import CycleRegime
from app.indicators.ichimoku import Candle
from app.market_data.quality import closed_candles


def _circ_delta(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def _resultant_R(phases: list[float], truths: list[float]) -> float:
    if not phases:
        return 0.0
    cx = sum(math.cos(2 * math.pi * (p - t)) for p, t in zip(phases, truths))
    sx = sum(math.sin(2 * math.pi * (p - t)) for p, t in zip(phases, truths))
    return math.hypot(cx, sx) / len(phases)


@pytest.mark.parametrize("period", [12.0, 20.0, 40.0])
def test_b1_hilbert_phase_tracks_sine(period: float):
    """B1 — after known delay compensation: R ≥ 0.9, circ err ≤ 0.05."""
    from app.cycle.acf import estimate_acf
    from app.cycle.fft import estimate_fft
    from app.cycle.consensus import median_period

    window = 128
    n = max(window + 100, int(period * 16))
    candles = make_sine_candles(n, period)
    phases: list[float] = []
    truths: list[float] = []
    max_p = min(80.0, window / 2.5)
    for end in range(n - 50, n):
        w0 = max(0, end + 1 - window)
        closes = [c.close for c in candles[w0 : end + 1]]
        fft = estimate_fft(closes, min_period=8.0, max_period=max_p)
        acf = estimate_acf(closes, min_period=8, max_period=int(window / 3.0))
        hint = median_period([fft.dominant_period, acf.dominant_period])
        h = estimate_hilbert(
            closes,
            min_period=8.0,
            max_period=max_p,
            period_hint=hint,
        )
        if h.phase is None or hint is None:
            continue
        true_ph = ((end - PHASE_GROUP_DELAY_BARS) / period) % 1.0
        phases.append(h.phase)
        truths.append(true_ph)
    assert len(phases) >= 20, "insufficient phase samples"
    r = _resultant_R(phases, truths)
    err = sum(_circ_delta(p, t) for p, t in zip(phases, truths)) / len(phases)
    assert r >= 0.9, f"phase R={r:.3f} err={err:.3f} for P={period}"
    assert err <= 0.05, f"phase err={err:.3f} R={r:.3f} for P={period}"


@pytest.mark.parametrize("period", [12.0, 20.0, 32.0, 48.0])
def test_b2_sine_is_mostly_cycle_not_trend(period: float):
    """B2 — sine → CYCLE ≥ 80%, TREND ≤ 10%."""
    # P=48 needs window ≥ 2.5*48 so FFT can resolve; ACF lag cap = window/3
    window = 160 if period >= 40 else 128
    candles = make_sine_candles(max(window + 120, int(period * 16)), period)
    params = CycleParams(window=window, max_period=min(80.0, window / 2.5))
    states = compute_cycle_series(candles, params)[window:]
    assert states
    n = len(states)
    cycle = sum(1 for s in states if s.regime == CycleRegime.CYCLE) / n
    trend = sum(1 for s in states if s.regime == CycleRegime.TREND) / n
    assert cycle >= 0.80, f"P={period} CYCLE={cycle:.2%} TREND={trend:.2%}"
    assert trend <= 0.10, f"P={period} TREND={trend:.2%} CYCLE={cycle:.2%}"


def test_b2_random_walk_cycle_false_positive_rate():
    """B2 — RW → CYCLE ≤ 5% (mean over seeds)."""
    window = 128
    params = CycleParams(window=window, max_period=min(80.0, window / 3.0))
    rates: list[float] = []
    for seed in range(5):
        candles = make_random_walk_candles(window + 500, seed=seed)
        states = compute_cycle_series(candles, params)[window:]
        n = len(states) or 1
        rates.append(sum(1 for s in states if s.regime == CycleRegime.CYCLE) / n)
    mean_rate = sum(rates) / len(rates)
    assert mean_rate <= 0.05, f"RW CYCLE rates={rates} mean={mean_rate:.3f}"


def test_b4_closed_candles_drops_forming_with_injected_now():
    """B4 — forming bar excluded when now is mid-bar."""
    tf = 3600
    t0 = 1_700_000_000
    candles = [
        Candle(time=t0 + i * tf, open=1, high=1, low=1, close=100 + i, volume=1)
        for i in range(10)
    ]
    # Last bar open at t0+9*tf; inject now before it closes
    now = t0 + 9 * tf + tf // 2
    closed = closed_candles(candles, tf, now)
    assert len(closed) == 9
    assert closed[-1].time == t0 + 8 * tf


def test_validate_cycle_synthetic_bundle_ok():
    report = validate_cycle_synthetic(window=128)
    assert report["ok"] is True
    assert "phase_period_rows" in report
    assert "random_walk" in report


def test_no_buy_sell_fields_after_fix():
    state = compute_cycle_state(make_sine_candles(200, 20.0), CycleParams(window=96))
    d = state.to_dict()
    blob = str(d).lower()
    for forbidden in ("buy", "sell", "long", "short", "probability_win"):
        assert forbidden not in blob
