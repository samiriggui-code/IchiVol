"""Multi-method agreement + regime heuristic (not a win probability)."""

from __future__ import annotations

import math
from typing import Sequence

from app.cycle.acf import AcfEstimate
from app.cycle.fft import FftEstimate
from app.cycle.hilbert import HilbertEstimate
from app.cycle.trend import TrendEstimate
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
    trend: TrendEstimate,
    quality: float,
    spectral_concentration: float | None = None,
    acf_peak: float | None = None,
) -> CycleRegime:
    """
    TREND from real trend measures (ER + R²), not Hilbert |I|/|Q|.
    CYCLE requires agreement + spectral/ACF evidence + non-trend window.
    """
    conc = spectral_concentration or 0.0
    peak = acf_peak or 0.0
    # Strong ACF peak alone is enough spectral evidence on a clean sine;
    # require both only when each is merely moderate (keeps RW CYCLE low).
    spectral_ok = (conc >= 0.12 and peak >= 0.15) or peak >= 0.35 or conc >= 0.22

    if quality < 0.18 and not trend.is_trend:
        return CycleRegime.NOISE
    if trend.is_trend and agreement < 0.66:
        return CycleRegime.TREND
    # Pure oscillation: methods agree, stable, spectral peak, not trending
    if (
        not trend.is_trend
        and spectral_ok
        and agreement >= 0.5
        and stability >= 0.35
        and strength >= 0.22
    ):
        return CycleRegime.CYCLE
    if agreement >= 0.33 or stability >= 0.35 or trend.strength >= 0.35:
        return CycleRegime.TRANSITION
    return CycleRegime.NOISE
