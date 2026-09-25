"""Multi-method agreement + regime heuristic (not a win probability)."""

from __future__ import annotations

import math
from typing import Sequence

from app.cycle.acf import AcfEstimate
from app.cycle.fft import FftEstimate
from app.cycle.hilbert import HilbertEstimate
from app.cycle.types import CycleRegime


def _rel_close(a: float | None, b: float | None, tol: float = 0.25) -> bool:
    if a is None or b is None or a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= tol


def methods_agreement(
    fft: FftEstimate,
    hilbert: HilbertEstimate,
    acf: AcfEstimate,
) -> float:
    """0..1 score of period agreement across methods. Not P(win)."""
    periods = [
        p
        for p in (fft.dominant_period, hilbert.dominant_period, acf.dominant_period)
        if p is not None and p > 0
    ]
    if len(periods) < 2:
        return 0.0
    pairs = 0
    ok = 0
    for i in range(len(periods)):
        for j in range(i + 1, len(periods)):
            pairs += 1
            if _rel_close(periods[i], periods[j]):
                ok += 1
    return ok / pairs if pairs else 0.0


def median_period(periods: Sequence[float | None]) -> float | None:
    vals = sorted(p for p in periods if p is not None and p > 0)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def cycle_stability(period_history: Sequence[float | None]) -> float:
    """Stability of recent dominant-period estimates (0..1)."""
    vals = [p for p in period_history if p is not None and p > 0]
    if len(vals) < 3:
        return 0.0
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    cv = math.sqrt(var) / mean
    return max(0.0, min(1.0, 1.0 - cv))


def infer_regime(
    *,
    agreement: float,
    strength: float,
    stability: float,
    hilbert: HilbertEstimate,
    quality: float,
) -> CycleRegime:
    if quality < 0.25 or strength < 0.15:
        return CycleRegime.NOISE
    if hilbert.trend_mode and agreement < 0.5:
        return CycleRegime.TREND
    if agreement >= 0.66 and stability >= 0.5 and strength >= 0.35:
        return CycleRegime.CYCLE
    if agreement >= 0.33 or stability >= 0.35:
        return CycleRegime.TRANSITION
    return CycleRegime.NOISE
