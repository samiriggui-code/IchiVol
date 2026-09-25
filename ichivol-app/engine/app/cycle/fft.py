"""Causal windowed periodogram (stdlib DFT) — dominant cycle period."""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import apply_window, detrend_linear, finite_series, hann_window, log_prices


@dataclass(frozen=True)
class FftEstimate:
    dominant_period: float | None
    secondary_period: float | None
    spectral_power: float | None
    spectral_concentration: float | None
    amplitude_normalized: float | None
    strength: float


def _dft_power(xs: Sequence[float]) -> list[float]:
    """One-sided power for k = 1..n//2 (exclude DC)."""
    n = len(xs)
    if n < 4:
        return []
    powers: list[float] = []
    for k in range(1, n // 2 + 1):
        acc = 0j
        for t, x in enumerate(xs):
            angle = -2.0 * math.pi * k * t / n
            acc += x * cmath.exp(1j * angle)
        powers.append((acc.real * acc.real + acc.imag * acc.imag) / (n * n))
    return powers


def estimate_fft(
    closes: Sequence[float],
    *,
    min_period: float = 8.0,
    max_period: float = 80.0,
) -> FftEstimate:
    """FFT on the provided window only (caller must pass candles <= T)."""
    n = len(closes)
    empty = FftEstimate(None, None, None, None, None, 0.0)
    if n < max(16, int(min_period) * 2):
        return empty

    series = detrend_linear(log_prices(closes))
    series = finite_series(series)
    win = hann_window(n)
    windowed = apply_window(series, win)
    powers = _dft_power(windowed)
    if not powers:
        return empty

    total = sum(powers)
    if total <= 0:
        return empty

    candidates: list[tuple[float, float, int]] = []  # power, period, k
    for k, pwr in enumerate(powers, start=1):
        period = n / k
        if min_period <= period <= max_period:
            candidates.append((pwr, period, k))
    if not candidates:
        return empty

    candidates.sort(key=lambda t: t[0], reverse=True)
    top_pwr, top_period, _ = candidates[0]
    second_period = candidates[1][1] if len(candidates) > 1 else None
    concentration = top_pwr / total
    # Amplitude proxy: RMS of windowed series scaled by concentration
    rms = math.sqrt(sum(x * x for x in windowed) / n)
    strength = max(0.0, min(1.0, concentration * 4.0))  # soft scale
    return FftEstimate(
        dominant_period=top_period,
        secondary_period=second_period,
        spectral_power=top_pwr,
        spectral_concentration=concentration,
        amplitude_normalized=rms if math.isfinite(rms) else None,
        strength=strength,
    )
