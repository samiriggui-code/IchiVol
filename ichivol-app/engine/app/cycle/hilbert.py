"""Causal cycle period + phase (stdlib).

Period: Ehlers Homodyne Discriminator with gain-compensated FIR (when it
locks); otherwise ``None`` so consensus can rely on FFT/ACF.

Phase: single-bin OLS / Goertzel on the **last ~2 periods** of detrended
log-price (not the full window — full-window OLS amplifies period error
into the last bar under noise; Claude R1). Model ``x ≈ c + a·cos + b·sin``
(P2 — constant term). Time origin at the last bar. ``phase_confidence`` is
the OLS R² on that short fit; below ``PHASE_CONFIDENCE_MIN`` phase fields
are cleared.

``trend_mode`` always False — TREND lives in ``app.cycle.trend``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import detrend_linear, log_prices

_H_TAPS = (0.0962, 0.5769, 0.5769, 0.0962)
PHASE_GROUP_DELAY_BARS = 0.0
# Publish phase only when short-window OLS R² clears this floor (R1).
PHASE_CONFIDENCE_MIN = 0.55
PHASE_FIT_PERIODS = 2.0


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
    phase_confidence: float | None = None


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
        if period < min_period:
            period = 0.5 * (period + min_period)
        elif period > max_period:
            period = 0.5 * (period + max_period)
        period = max(min_period * 0.75, min(max_period * 1.25, period))
        sp = 0.33 * period + 0.67 * sp
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


def _goertzel_phase_short(
    series: Sequence[float],
    period: float,
    *,
    n_periods: float = PHASE_FIT_PERIODS,
) -> tuple[float | None, float | None, float | None, float]:
    """OLS on last ``n_periods`` cycles → (phase01, I, Q, R²).

    Model: ``x ≈ c + a·cos(ωt) + b·sin(ωt)`` (P2 — constant term so a linear
    trend residual / DC offset does not inflate R² or bias phase). Time origin
    at the last bar. Fitting the full window lets a small period hint error
    wind up into a large phase bias; restricting to ~2P keeps the bias bounded.
    """
    n = len(series)
    if period < 4 or n < int(period) + 4:
        return None, None, None, 0.0
    fit_len = max(int(n_periods * period), int(period) + 4)
    fit_len = min(fit_len, n)
    start = n - fit_len
    omega = 2.0 * math.pi / period

    # Accumulate normal equations for [c, a, b].
    n_obs = 0.0
    sc = ss = 0.0  # Σ cos, Σ sin
    scc = sss = scs = 0.0  # Σ cos², Σ sin², Σ cos·sin
    sx = sxc = sxs = 0.0  # Σ x, Σ x·cos, Σ x·sin
    samples: list[tuple[float, float, float]] = []  # x, cos, sin
    for i in range(start, n):
        x = series[i]
        if not math.isfinite(x):
            continue
        t = i - (n - 1)  # last bar = 0
        c = math.cos(omega * t)
        s = math.sin(omega * t)
        n_obs += 1.0
        sc += c
        ss += s
        scc += c * c
        sss += s * s
        scs += c * s
        sx += x
        sxc += x * c
        sxs += x * s
        samples.append((x, c, s))
    if len(samples) < 8:
        return None, None, None, 0.0

    # Solve 3×3: M · [c, a, b]^T = [sx, sxc, sxs]^T via Cramer's / cofactors.
    # M = [[n, sc, ss], [sc, scc, scs], [ss, scs, sss]]
    det = (
        n_obs * (scc * sss - scs * scs)
        - sc * (sc * sss - scs * ss)
        + ss * (sc * scs - scc * ss)
    )
    if abs(det) < 1e-18:
        return None, None, None, 0.0
    det_c = (
        sx * (scc * sss - scs * scs)
        - sc * (sxc * sss - scs * sxs)
        + ss * (sxc * scs - scc * sxs)
    )
    det_a = (
        n_obs * (sxc * sss - scs * sxs)
        - sx * (sc * sss - scs * ss)
        + ss * (sc * sxs - sxc * ss)
    )
    det_b = (
        n_obs * (scc * sxs - sxc * scs)
        - sc * (sc * sxs - sxc * ss)
        + sx * (sc * scs - scc * ss)
    )
    const = det_c / det
    a = det_a / det
    b = det_b / det
    if abs(a) < 1e-15 and abs(b) < 1e-15:
        return None, None, None, 0.0

    mean_x = sx / n_obs
    ss_tot = sum((x - mean_x) ** 2 for x, _, _ in samples)
    ss_res = sum((x - (const + a * c + b * s)) ** 2 for x, c, s in samples)
    if ss_tot <= 1e-18:
        r2 = 0.0
    else:
        r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot))

    phase01 = (math.atan2(a, b) / (2.0 * math.pi)) % 1.0
    return phase01, a, b, r2


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
    phase_conf: float | None = None
    if period is not None:
        phase01, i_val, q_val, r2 = _goertzel_phase_short(series, period)
        phase_conf = r2
        # R1 — refuse to publish a high-confidence-looking wrong phase
        if phase01 is not None and r2 < PHASE_CONFIDENCE_MIN:
            phase01 = None

    phase_deg = (phase01 * 360.0) if phase01 is not None else None

    mean_p = sum(raw) / n
    var_p = sum((x - mean_p) ** 2 for x in raw) / n
    std_p = math.sqrt(var_p) if var_p > 0 else 1e-9
    amp = 0.0
    if i_val is not None and q_val is not None:
        amp = math.hypot(i_val, q_val)
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
        phase_confidence=phase_conf,
    )
