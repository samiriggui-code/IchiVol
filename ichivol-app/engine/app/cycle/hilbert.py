"""Causal cycle period + phase (stdlib).

Period: Ehlers Homodyne Discriminator with gain-compensated FIR (when it
locks); otherwise ``None`` so consensus can rely on FFT/ACF.

Phase: single-bin OLS / Goertzel fit of the detrended log-price at a period
hint (FFT/ACF median), with time origin at the **last bar**. That yields the
instantaneous phase at T with group delay ≈ 0 (verified on pure sines).
The earlier FIR/Homodyne atan2(Q,I) and EMA demod paths did not (Claude B1).

``trend_mode`` always False — TREND lives in ``app.cycle.trend``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import detrend_linear, log_prices

_H_TAPS = (0.0962, 0.5769, 0.5769, 0.0962)
# Goertzel / OLS phase is end-relative → no group delay to compensate in tests.
PHASE_GROUP_DELAY_BARS = 0.0


@dataclass(frozen=True)
class HilbertEstimate:
    dominant_period: float | None
    phase: float | None
    phase_deg: float | None
    in_phase: float | None
    quadrature: float | None
    trend_mode: bool
    strength: float
    phase_delay_bars: float = PHASE_GROUP_DELAY_BARS


def _hilbert_fir(xs: Sequence[float], i: int, gain: float) -> float:
    return (
        _H_TAPS[0] * xs[i]
        + _H_TAPS[1] * xs[i - 2]
        - _H_TAPS[2] * xs[i - 4]
        - _H_TAPS[3] * xs[i - 6]
    ) * gain


def _homodyne_period(
    price: Sequence[float],
    *,
    min_period: float,
    max_period: float,
) -> float | None:
    n = len(price)
    if n < 48:
        return None
    smooth = [0.0] * n
    detrender = [0.0] * n
    i1 = [0.0] * n
    q1 = [0.0] * n
    i2 = [0.0] * n
    q2 = [0.0] * n
    re = [0.0] * n
    im = [0.0] * n
    sp = 0.5 * (min_period + max_period)
    periods: list[float] = []

    for i in range(n):
        if i < 6:
            smooth[i] = price[i]
            continue
        smooth[i] = (
            4.0 * price[i] + 3.0 * price[i - 1] + 2.0 * price[i - 2] + price[i - 3]
        ) / 10.0
        gain = 0.075 * sp + 0.54
        detrender[i] = _hilbert_fir(smooth, i, gain)
        if i < 12:
            continue
        q1[i] = _hilbert_fir(detrender, i, gain)
        i1[i] = detrender[i - 3]
        j_i = _hilbert_fir(i1, i, gain)
        j_q = _hilbert_fir(q1, i, gain)
        i2[i] = 0.2 * (i1[i] - j_q) + 0.8 * i2[i - 1]
        q2[i] = 0.2 * (q1[i] + j_i) + 0.8 * q2[i - 1]
        re[i] = 0.2 * (i2[i] * i2[i - 1] + q2[i] * q2[i - 1]) + 0.8 * re[i - 1]
        im[i] = 0.2 * (i2[i] * q2[i - 1] - q2[i] * i2[i - 1]) + 0.8 * im[i - 1]
        if abs(re[i]) > 1e-12:
            period = abs(2.0 * math.pi / math.atan2(im[i], re[i]))
        else:
            period = sp
        # N3 — soft clamp: blend toward band instead of hard park at bounds
        if period < min_period:
            period = 0.5 * (period + min_period)
        elif period > max_period:
            period = 0.5 * (period + max_period)
        period = max(min_period * 0.75, min(max_period * 1.25, period))
        sp = 0.33 * period + 0.67 * sp
        # Report only in-band smoothed period
        periods.append(max(min_period, min(max_period, sp)))

    if len(periods) < 16:
        return None
    tail = periods[-16:]
    mean_p = sum(tail) / len(tail)
    seed = 0.5 * (min_period + max_period)
    if abs(mean_p - seed) < 0.5:
        var = sum((x - mean_p) ** 2 for x in tail) / len(tail)
        if var < 0.25:
            return None
    return mean_p


def _goertzel_phase(
    series: Sequence[float],
    period: float,
) -> tuple[float | None, float | None, float | None]:
    """OLS single-bin fit → (phase01, I, Q) at last bar (t=0 at end).

    Models ``x[t] ≈ A·cos(ωt) + B·sin(ωt)`` with ``t = i - (n-1)``.
    For ``amp·sin(ωt + φ)``: A = amp·sin(φ), B = amp·cos(φ) → φ = atan2(A, B).
    """
    n = len(series)
    if period < 4 or n < int(period) + 8:
        return None, None, None
    omega = 2.0 * math.pi / period
    cc = ss = cs = 0.0
    yc = ys = 0.0
    for i, x in enumerate(series):
        if not math.isfinite(x):
            continue
        t = i - (n - 1)
        c = math.cos(omega * t)
        s = math.sin(omega * t)
        yc += x * c
        ys += x * s
        cc += c * c
        ss += s * s
        cs += c * s
    det = cc * ss - cs * cs
    if abs(det) < 1e-18:
        return None, None, None
    a = (yc * ss - ys * cs) / det  # cos coeff = I
    b = (ys * cc - yc * cs) / det  # sin coeff = Q
    if abs(a) < 1e-15 and abs(b) < 1e-15:
        return None, None, None
    phase01 = (math.atan2(a, b) / (2.0 * math.pi)) % 1.0
    return phase01, a, b


def estimate_hilbert(
    closes: Sequence[float],
    *,
    min_period: float = 8.0,
    max_period: float = 80.0,
    period_hint: float | None = None,
) -> HilbertEstimate:
    empty = HilbertEstimate(None, None, None, None, None, False, 0.0)
    n = len(closes)
    if n < 32:
        return empty

    raw = log_prices(closes)
    for i, v in enumerate(raw):
        if not math.isfinite(v):
            raw[i] = raw[i - 1] if i else 0.0

    homodyne_p = _homodyne_period(raw, min_period=min_period, max_period=max_period)
    period = None
    if period_hint is not None and min_period <= period_hint <= max_period:
        period = float(period_hint)
    elif homodyne_p is not None:
        period = homodyne_p

    series = detrend_linear(raw)
    series = [x if math.isfinite(x) else 0.0 for x in series]

    phase01 = None
    i_val = None
    q_val = None
    if period is not None:
        phase01, i_val, q_val = _goertzel_phase(series, period)

    phase_deg = (phase01 * 360.0) if phase01 is not None else None

    mean_p = sum(raw) / n
    var_p = sum((x - mean_p) ** 2 for x in raw) / n
    std_p = math.sqrt(var_p) if var_p > 0 else 1e-9
    amp = 0.0
    if i_val is not None and q_val is not None:
        amp = math.hypot(i_val, q_val)
    # N4 — normalize amplitude by window std so strength is scale-free
    strength = 0.0
    if period is not None:
        strength = max(0.0, min(1.0, amp / std_p))

    return HilbertEstimate(
        dominant_period=homodyne_p,
        phase=phase01,
        phase_deg=phase_deg,
        in_phase=i_val,
        quadrature=q_val,
        trend_mode=False,
        strength=strength,
        phase_delay_bars=PHASE_GROUP_DELAY_BARS,
    )
