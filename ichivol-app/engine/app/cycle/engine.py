"""Compose FFT + Hilbert + ACF + trend into causal CycleState series."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.cycle.acf import estimate_acf
from app.cycle.consensus import (
    cycle_stability,
    infer_regime,
    median_period,
    methods_agreement,
)
from app.cycle.fft import estimate_fft
from app.cycle.hilbert import estimate_hilbert
from app.cycle.preprocess import closes
from app.cycle.trend import estimate_trend
from app.cycle.types import CycleRegime, CycleState
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class CycleParams:
    window: int = 128
    min_period: float = 8.0
    max_period: float = 80.0
    stability_lookback: int = 16


def _empty_state(time: int) -> CycleState:
    return CycleState(
        time=time,
        dominant_period_candles=None,
        secondary_period_candles=None,
        phase=None,
        phase_deg=None,
        amplitude_normalized=None,
        spectral_power=None,
        spectral_concentration=None,
        cycle_strength=0.0,
        cycle_stability=0.0,
        regime=CycleRegime.NOISE,
        bars_to_next_phase=None,
        quality=0.0,
        methods_agreement=0.0,
        methods={},
    )


def _state_at_window(
    window_candles: Sequence[Candle],
    *,
    params: CycleParams,
    period_history: list[float | None],
) -> CycleState:
    px = closes(window_candles)
    t = int(window_candles[-1].time)
    max_p = min(params.max_period, max(8.0, len(px) / 2.5))
    acf_max = min(max_p, max(8.0, len(px) / 3.0))
    fft = estimate_fft(px, min_period=params.min_period, max_period=max_p)
    acf = estimate_acf(
        px,
        min_period=int(params.min_period),
        max_period=int(acf_max),
    )
    # Hint for phase only — not double-counted in dominant median (Claude R5).
    hint = median_period([fft.dominant_period, acf.dominant_period])
    hilbert = estimate_hilbert(
        px,
        min_period=params.min_period,
        max_period=max_p,
        period_hint=hint,
    )
    trend = estimate_trend(px)
    agreement = methods_agreement(fft, hilbert, acf)
    dominant = median_period(
        [fft.dominant_period, hilbert.dominant_period, acf.dominant_period]
    )
    period_history.append(dominant)
    hist = period_history[-params.stability_lookback :]
    stability = cycle_stability(hist)

    # N4 — do not take max of noisy strengths alone; blend with agreement
    raw_strength = (fft.strength + hilbert.strength + acf.strength) / 3.0
    strength = max(0.0, min(1.0, 0.55 * raw_strength + 0.45 * agreement))
    # N4 — quality must be able to go low: require signal, not just full window
    bar_q = min(1.0, len(window_candles) / float(params.window))
    quality = max(
        0.0,
        min(1.0, 0.25 * bar_q + 0.45 * strength + 0.30 * agreement),
    )
    regime = infer_regime(
        agreement=agreement,
        strength=strength,
        stability=stability,
        trend=trend,
        quality=quality,
        spectral_concentration=fft.spectral_concentration,
        acf_peak=acf.peak_corr,
    )

    # R1 — phase already gated inside estimate_hilbert; keep bars_to_next None if no phase
    phase = hilbert.phase
    phase_deg = hilbert.phase_deg
    bars_to_next = None
    if phase is not None and dominant is not None and dominant > 0 and regime == CycleRegime.CYCLE:
        frac = phase % 1.0
        next_boundary = (int(frac * 4) + 1) / 4.0
        if next_boundary >= 1.0:
            next_boundary = 1.0
        delta = next_boundary - frac
        if delta <= 0:
            delta += 1.0
        bars_to_next = delta * dominant

    return CycleState(
        time=t,
        dominant_period_candles=dominant,
        secondary_period_candles=fft.secondary_period,
        phase=phase,
        phase_deg=phase_deg,
        amplitude_normalized=fft.amplitude_normalized,
        spectral_power=fft.spectral_power,
        spectral_concentration=fft.spectral_concentration,
        cycle_strength=strength,
        cycle_stability=stability,
        regime=regime,
        bars_to_next_phase=bars_to_next,
        quality=quality,
        methods_agreement=agreement,
        methods={
            "fft": {
                "dominant_period": fft.dominant_period,
                "secondary_period": fft.secondary_period,
                "concentration": fft.spectral_concentration,
                "strength": fft.strength,
                "hann_latency_note": "Hann centers energy ~window/2 bars before last bar",
            },
            "hilbert": {
                "dominant_period": hilbert.dominant_period,
                "phase_deg": hilbert.phase_deg,
                "phase_delay_bars": hilbert.phase_delay_bars,
                "phase_confidence": hilbert.phase_confidence,
                "trend_mode": False,
                "strength": hilbert.strength,
            },
            "acf": {
                "dominant_period": acf.dominant_period,
                "peak_corr": acf.peak_corr,
                "strength": acf.strength,
            },
            "trend": {
                "efficiency_ratio": trend.efficiency_ratio,
                "r_squared": trend.r_squared,
                "is_trend": trend.is_trend,
                "strength": trend.strength,
            },
        },
    )


def compute_cycle_series(
    candles: Sequence[Candle],
    params: CycleParams | None = None,
) -> list[CycleState]:
    """One CycleState per bar; early bars are NOISE warmup. Causal by construction."""
    p = params or CycleParams()
    n = len(candles)
    out: list[CycleState] = []
    period_history: list[float | None] = []
    min_bars = max(32, int(p.min_period) * 3)
    for i in range(n):
        if i + 1 < min_bars:
            out.append(_empty_state(int(candles[i].time)))
            period_history.append(None)
            continue
        start = max(0, i + 1 - p.window)
        window = candles[start : i + 1]
        out.append(_state_at_window(window, params=p, period_history=period_history))
    return out


def compute_cycle_state(
    candles: Sequence[Candle],
    params: CycleParams | None = None,
) -> CycleState:
    """CycleState at the last candle only (API / agent helper)."""
    p = params or CycleParams()
    if not candles:
        return _empty_state(0)
    n = len(candles)
    min_bars = max(32, int(p.min_period) * 3)
    if n < min_bars:
        return _empty_state(int(candles[-1].time))

    period_history: list[float | None] = []
    start_i = max(min_bars - 1, n - p.stability_lookback)
    state = _empty_state(int(candles[-1].time))
    for i in range(start_i, n):
        w0 = max(0, i + 1 - p.window)
        state = _state_at_window(candles[w0 : i + 1], params=p, period_history=period_history)
    return state
