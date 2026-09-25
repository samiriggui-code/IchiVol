"""Causal autocorrelation period peak (stdlib)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import detrend_linear, log_returns


@dataclass(frozen=True)
class AcfEstimate:
    dominant_period: float | None
    peak_corr: float | None
    strength: float


def _acf_at_lag(xs: Sequence[float], lag: int) -> float | None:
    n = len(xs)
    if lag <= 0 or lag >= n - 2:
        return None
    a = xs[: n - lag]
    b = xs[lag:]
    pairs = [(x, y) for x, y in zip(a, b) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 8:
        return None
    mean_a = sum(x for x, _ in pairs) / len(pairs)
    mean_b = sum(y for _, y in pairs) / len(pairs)
    num = sum((x - mean_a) * (y - mean_b) for x, y in pairs)
    den_a = math.sqrt(sum((x - mean_a) ** 2 for x, _ in pairs))
    den_b = math.sqrt(sum((y - mean_b) ** 2 for _, y in pairs))
    if den_a <= 1e-12 or den_b <= 1e-12:
        return None
    return num / (den_a * den_b)


def estimate_acf(
    closes: Sequence[float],
    *,
    min_period: int = 8,
    max_period: int = 80,
) -> AcfEstimate:
    empty = AcfEstimate(None, None, 0.0)
    if len(closes) < max(min_period * 3, 32):
        return empty

    rets = detrend_linear(log_returns(closes)[1:])  # drop leading nan from returns
    # log_returns[0]=nan already dropped by [1:]; still may have nan — zero-fill for ACF length
    series = [r if math.isfinite(r) else 0.0 for r in rets]
    if len(series) < max_period + 8:
        return empty

    best_lag: int | None = None
    best_corr = -1.0
    # Seek local maxima of ACF in [min_period, max_period]
    prev = None
    for lag in range(min_period, min(max_period, len(series) // 3) + 1):
        c = _acf_at_lag(series, lag)
        if c is None:
            continue
        if prev is not None and lag > min_period:
            c_prev = _acf_at_lag(series, lag - 1)
            c_next = _acf_at_lag(series, lag + 1) if lag + 1 <= max_period else None
            if (
                c_prev is not None
                and c > c_prev
                and (c_next is None or c >= c_next)
                and c > best_corr
            ):
                best_corr = c
                best_lag = lag
        prev = c

    if best_lag is None:
        # Fallback: global max ACF in band (may be weak)
        for lag in range(min_period, min(max_period, len(series) // 3) + 1):
            c = _acf_at_lag(series, lag)
            if c is not None and c > best_corr:
                best_corr = c
                best_lag = lag

    if best_lag is None or best_corr < 0.05:
        return empty

    strength = max(0.0, min(1.0, best_corr))
    return AcfEstimate(dominant_period=float(best_lag), peak_corr=best_corr, strength=strength)
