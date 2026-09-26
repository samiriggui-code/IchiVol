"""Causal windowed periodogram (stdlib DFT) — dominant cycle period.

N6 — Hann latency: the Hann window weights the *center* of the analysis
window (~window/2 bars of group delay vs the last bar). Dominant-period
estimates therefore describe mid-window conditions, not the forming edge.
Documented intentionally for regime-filter use (do not treat as tick-reactive).
"""

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


def _effective_max_period(n: int, max_period: float) -> float:
    """N1 — ACF/FFT usable lags ~ n/3; do not claim periods beyond that."""
    return min(max_period, max(8.0, n / 3.0))


def _dft_complex(xs: Sequence[float], k: int) -> complex:
    n = len(xs)
    acc = 0j
    for t, x in enumerate(xs):
        angle = -2.0 * math.pi * k * t / n
        acc += x * cmath.exp(1j * angle)
    return acc


def _dft_power_padded(xs: Sequence[float], pad_factor: int = 4) -> list[tuple[float, float]]:
    """
    Zero-padded DFT magnitudes (N2).
    Returns list of (power, period) for k=1..n_pad//2 using period = n_orig/k_equiv
    where frequency bins are refined by padding.
    Period = n_orig / (k * n_orig / n_pad) = n_pad / k.
    """
    n = len(xs)
    if n < 4:
        return []
    n_pad = n * pad_factor
    padded = list(xs) + [0.0] * (n_pad - n)
    out: list[tuple[float, float]] = []
    for k in range(1, n_pad // 2 + 1):
        acc = _dft_complex(padded, k)
        pwr = (acc.real * acc.real + acc.imag * acc.imag) / (n_pad * n_pad)
        # Period in original samples: n_pad/k maps to same physical freq as n/(k*n/n_pad)
        period = n_pad / k
        # Rescale period to original sample rate: frequency f=k/n_pad → period=n_pad/k
        # but we want period in bars of the original series = 1/f = n_pad/k
        # For unpadded, period=n/k. With pad, physical period = n_pad/k * (n/n_pad)? No:
        # DFT bin k on length N corresponds to period N/k samples of that series.
        # Padded series has same sample rate → period = n_pad/k samples.
        out.append((pwr, period))
    return out


def _parabolic_refine(powers: Sequence[float], k_idx: int) -> float:
    """Fractional bin peak via 3-point parabola (N2). k_idx is 0-based into powers."""
    if k_idx <= 0 or k_idx >= len(powers) - 1:
        return float(k_idx + 1)
    y0, y1, y2 = powers[k_idx - 1], powers[k_idx], powers[k_idx + 1]
    denom = y0 - 2 * y1 + y2
    if abs(denom) < 1e-18:
        return float(k_idx + 1)
    delta = 0.5 * (y0 - y2) / denom
    delta = max(-0.5, min(0.5, delta))
    return (k_idx + 1) + delta


def estimate_fft(
    closes: Sequence[float],
    *,
    min_period: float = 8.0,
    max_period: float = 80.0,
) -> FftEstimate:
    """FFT on the provided window only (caller must pass candles ≤ T)."""
    n = len(closes)
    empty = FftEstimate(None, None, None, None, None, 0.0)
    if n < max(16, int(min_period) * 2):
        return empty

    max_p = _effective_max_period(n, max_period)
    series = detrend_linear(log_prices(closes))
    series = finite_series(series)
    win = hann_window(n)
    windowed = apply_window(series, win)

    # Zero-pad for finer frequency grid (N2 / R4).
    # pad×4 was ~390 ms/symbole; pad×2 keeps parabolic refine cheap (<1 s).
    pad_factor = 2
    n_pad = n * pad_factor
    padded = list(windowed) + [0.0] * (n_pad - n)
    powers: list[float] = []
    for k in range(1, n_pad // 2 + 1):
        acc = _dft_complex(padded, k)
        powers.append((acc.real * acc.real + acc.imag * acc.imag) / (n_pad * n_pad))
    if not powers:
        return empty

    total = sum(powers)
    if total <= 0:
        return empty

    candidates: list[tuple[float, float, int]] = []  # power, period, k_idx
    for k_idx, pwr in enumerate(powers):
        k = k_idx + 1
        period = n_pad / k
        if min_period <= period <= max_p:
            candidates.append((pwr, period, k_idx))
    if not candidates:
        return empty

    candidates.sort(key=lambda t: t[0], reverse=True)
    top_pwr, _top_period_raw, top_idx = candidates[0]
    k_ref = _parabolic_refine(powers, top_idx)
    top_period = n_pad / k_ref
    if top_period < min_period or top_period > max_p:
        top_period = candidates[0][1]

    second_period = candidates[1][1] if len(candidates) > 1 else None
    concentration = top_pwr / total
    rms = math.sqrt(sum(x * x for x in windowed) / n)
    strength = max(0.0, min(1.0, concentration * 4.0))
    return FftEstimate(
        dominant_period=top_period,
        secondary_period=second_period,
        spectral_power=top_pwr,
        spectral_concentration=concentration,
        amplitude_normalized=rms if math.isfinite(rms) else None,
        strength=strength,
    )
