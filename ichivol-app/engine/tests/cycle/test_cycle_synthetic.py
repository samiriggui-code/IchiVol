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


@pytest.mark.parametrize("period", [12.0, 20.0, 40.0])
def test_r1_phase_robust_light_noise(period: float):
    """R1 — amp=0.03 noise=0.01 → R ≥ 0.85, bias ≤ 0.08."""
    from app.cycle.acf import estimate_acf
    from app.cycle.consensus import median_period
    from app.cycle.fft import estimate_fft

    window = 128
    n = max(window + 100, int(period * 16))
    candles = make_sine_candles(n, period, amp=0.03, noise=0.01, seed=1)
    phases: list[float] = []
    truths: list[float] = []
    max_p = min(80.0, window / 2.5)
    for end in range(n - 50, n):
        closes = [c.close for c in candles[end + 1 - window : end + 1]]
        fft = estimate_fft(closes, min_period=8.0, max_period=max_p)
        acf = estimate_acf(closes, min_period=8, max_period=int(window / 3.0))
        hint = median_period([fft.dominant_period, acf.dominant_period])
        h = estimate_hilbert(closes, min_period=8.0, max_period=max_p, period_hint=hint)
        if h.phase is None:
            continue
        phases.append(h.phase)
        truths.append(((end - PHASE_GROUP_DELAY_BARS) / period) % 1.0)
    assert len(phases) >= 15, f"P={period} too few published phases"
    r = _resultant_R(phases, truths)
    err = sum(_circ_delta(p, t) for p, t in zip(phases, truths)) / len(phases)
    assert r >= 0.85, f"noise0.01 P={period} R={r:.3f} err={err:.3f}"
    assert err <= 0.08, f"noise0.01 P={period} err={err:.3f} R={r:.3f}"


@pytest.mark.parametrize("period", [12.0, 20.0, 40.0])
def test_r1_phase_heavy_noise_not_confidently_wrong(period: float):
    """R1 — noise=0.03 → phase None or low conf; never high-conf wrong phase."""
    from app.cycle.acf import estimate_acf
    from app.cycle.consensus import median_period
    from app.cycle.fft import estimate_fft
    from app.cycle.hilbert import PHASE_CONFIDENCE_MIN

    window = 128
    n = max(window + 100, int(period * 16))
    candles = make_sine_candles(n, period, amp=0.03, noise=0.03, seed=2)
    max_p = min(80.0, window / 2.5)
    high_wrong = 0
    for end in range(n - 50, n):
        closes = [c.close for c in candles[end + 1 - window : end + 1]]
        fft = estimate_fft(closes, min_period=8.0, max_period=max_p)
        acf = estimate_acf(closes, min_period=8, max_period=int(window / 3.0))
        hint = median_period([fft.dominant_period, acf.dominant_period])
        h = estimate_hilbert(closes, min_period=8.0, max_period=max_p, period_hint=hint)
        true_ph = ((end - PHASE_GROUP_DELAY_BARS) / period) % 1.0
        conf = h.phase_confidence or 0.0
        if h.phase is None:
            continue
        assert conf >= PHASE_CONFIDENCE_MIN
        if _circ_delta(h.phase, true_ph) > 0.15 and conf >= PHASE_CONFIDENCE_MIN:
            high_wrong += 1
    assert high_wrong == 0, f"P={period} confidently-wrong phases={high_wrong}"


def test_r2_agent_cycle_drops_forming_bar(monkeypatch):
    """R2 — agent get_cycle_state uses closed_candles with injected now."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.market_data import binance

    tf = 3600
    t0 = 1_700_000_000
    candles = [
        Candle(time=t0 + i * tf, open=1, high=1, low=1, close=100 + i, volume=1)
        for i in range(80)
    ]
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, timeframe, limit: candles)
    client = TestClient(app)
    now = t0 + 79 * tf + tf // 2
    res = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "get_cycle_state",
            "args": {"symbol": "BTCUSDT", "window": 64, "limit": 80, "now": now},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["n_bars"] == 79
    assert body["now"] == now


def test_p2_goertzel_phase_sine_plus_linear_trend_non_integer_period():
    """P2 — sinus + linear trend + non-integer period → phase err ≤ 0.05 when confident."""
    from app.cycle.hilbert import PHASE_CONFIDENCE_MIN, _goertzel_phase_short
    from app.cycle.preprocess import detrend_linear

    period = 17.3  # non-integer
    n = 200
    amp = 0.02
    drift = 0.0015  # linear trend in log-price space
    true_phase0 = 0.37  # desired phase at last bar (fit t=0)
    series_raw: list[float] = []
    for i in range(n):
        # Align so last bar has phase true_phase0 under the fit time origin.
        ph = ((i - (n - 1)) / period + true_phase0) % 1.0
        series_raw.append(drift * i + amp * math.sin(2.0 * math.pi * ph))

    series = detrend_linear(series_raw)
    phase01, _a, _b, r2 = _goertzel_phase_short(series, period)
    assert phase01 is not None
    assert r2 >= PHASE_CONFIDENCE_MIN, f"R²={r2:.3f} below floor"
    err = _circ_delta(phase01, true_phase0)
    assert err <= 0.05, f"phase err={err:.4f} R²={r2:.3f} est={phase01:.4f} true={true_phase0}"
