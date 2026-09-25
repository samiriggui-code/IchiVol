"""Causal Hilbert / Ehlers-inspired dominant cycle period + phase (stdlib).

Uses a short FIR Hilbert transformer (Ehlers-style coefficients) to build
in-phase / quadrature, then:
- period from smoothed phase rate of change
- phase from atan2(Q, I)
- trend_mode when |I| dominates cycle energy over a lookback

Not a TA-Lib dependency. Observe-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import detrend_linear, log_prices

# John Ehlers Hilbert transformer FIR (public literature) — causal taps.
_HILBERT_TAPS = (0.0962, 0.5769, 0.5769, 0.0962)
_HILBERT_DELAY = 3  # center offset for in-phase alignment


@dataclass(frozen=True)
class HilbertEstimate:
    dominant_period: float | None
    phase: float | None
    phase_deg: float | None
    in_phase: float | None
    quadrature: float | None
    trend_mode: bool
    strength: float


def _smooth(xs: Sequence[float], length: int) -> list[float]:
    out: list[float] = []
    for i in range(len(xs)):
        j0 = max(0, i - length + 1)
        chunk = [xs[j] for j in range(j0, i + 1) if math.isfinite(xs[j])]
        out.append(sum(chunk) / len(chunk) if chunk else float("nan"))
    return out


def estimate_hilbert(
    closes: Sequence[float],
    *,
    min_period: float = 8.0,
    max_period: float = 80.0,
) -> HilbertEstimate:
    empty = HilbertEstimate(None, None, None, None, None, False, 0.0)
    n = len(closes)
    if n < 32:
        return empty

    price = detrend_linear(log_prices(closes))
    # Homodyne-style I/Q via delayed Hilbert FIR on price
    i_line: list[float] = [float("nan")] * n
    q_line: list[float] = [float("nan")] * n
    for i in range(6, n):
        # Quadrature via FIR on recent samples
        q = (
            _HILBERT_TAPS[0] * price[i]
            + _HILBERT_TAPS[1] * price[i - 2]
            - _HILBERT_TAPS[2] * price[i - 4]
            - _HILBERT_TAPS[3] * price[i - 6]
        )
        # In-phase = price delayed to align with Q
        i_val = price[i - _HILBERT_DELAY]
        if not (math.isfinite(q) and math.isfinite(i_val)):
            continue
        q_line[i] = q
        i_line[i] = i_val

    # Instantaneous period from phase delta
    periods: list[float] = [float("nan")] * n
    phases: list[float] = [float("nan")] * n
    for i in range(1, n):
        ii, qq = i_line[i], q_line[i]
        ii0, qq0 = i_line[i - 1], q_line[i - 1]
        if not all(math.isfinite(v) for v in (ii, qq, ii0, qq0)):
            continue
        phase = math.atan2(qq, ii)
        phases[i] = phase
        prev = math.atan2(qq0, ii0)
        dphi = phase - prev
        # Wrap to (-pi, pi]
        while dphi <= -math.pi:
            dphi += 2 * math.pi
        while dphi > math.pi:
            dphi -= 2 * math.pi
        if abs(dphi) < 1e-9:
            continue
        raw_period = abs(2 * math.pi / dphi)
        periods[i] = max(min_period, min(max_period, raw_period))

    sm_period = _smooth(periods, 7)
    last_i = n - 1
    period = sm_period[last_i] if math.isfinite(sm_period[last_i]) else None
    phase = phases[last_i] if math.isfinite(phases[last_i]) else None
    phase01 = ((phase / (2 * math.pi)) % 1.0) if phase is not None else None
    phase_deg = (phase01 * 360.0) if phase01 is not None else None

    # Trend mode: |I| energy >> |Q| energy over recent bars
    look = min(20, n)
    i_energy = sum(abs(i_line[j]) for j in range(n - look, n) if math.isfinite(i_line[j]))
    q_energy = sum(abs(q_line[j]) for j in range(n - look, n) if math.isfinite(q_line[j]))
    trend_mode = i_energy > 1.5 * q_energy and (i_energy + q_energy) > 0
    amp = math.hypot(
        i_line[last_i] if math.isfinite(i_line[last_i]) else 0.0,
        q_line[last_i] if math.isfinite(q_line[last_i]) else 0.0,
    )
    strength = 0.0
    if period is not None and not trend_mode:
        strength = max(0.0, min(1.0, amp * 10.0))  # log-price scale soft clip
    elif period is not None:
        strength = max(0.0, min(0.4, amp * 5.0))

    return HilbertEstimate(
        dominant_period=period,
        phase=phase01,
        phase_deg=phase_deg,
        in_phase=i_line[last_i] if math.isfinite(i_line[last_i]) else None,
        quadrature=q_line[last_i] if math.isfinite(q_line[last_i]) else None,
        trend_mode=trend_mode,
        strength=strength,
    )
