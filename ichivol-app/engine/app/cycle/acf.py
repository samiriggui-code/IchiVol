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

    rets = detrend_linear(log_returns(closes)[1:])
    series = [r if math.isfinite(r) else 0.0 for r in rets]
    # N1 — usable lag ≤ len//3
    lag_cap = min(max_period, len(series) // 3)
    if len(series) < min_period + 8 or lag_cap < min_period:
        return empty

    # N5 — noise floor ≈ 1/√n ; require peak above ~1.5× that
    noise_floor = 1.0 / math.sqrt(max(len(series), 1))
    min_corr = max(0.12, 1.5 * noise_floor)

    # Prefer the *first* significant local peak (fundamental). Harmonics of a
    # pure sine also have |ρ|≈1, so max-peak picking returns 2P/3P and breaks
    # short-period agreement (Claude B2 / N5).
    # Always compare lag-1 even when lag-1 < min_period — otherwise the left
    # edge (lag==min_period) is a false peak whenever ρ is still declining
    # from a non-searched lag (e.g. P=40 → spurious lag=8).
    first_lag: int | None = None
    first_corr = -1.0
    for lag in range(min_period, lag_cap + 1):
        c = _acf_at_lag(series, lag)
        if c is None or c < min_corr:
            continue
        c_prev = _acf_at_lag(series, lag - 1)
        c_next = _acf_at_lag(series, lag + 1) if lag + 1 <= lag_cap else None
        is_local = (c_prev is None or c > c_prev) and (c_next is None or c >= c_next)
        if is_local:
            first_lag = lag
            first_corr = c
            break

    if first_lag is None:
        return empty

    strength = max(0.0, min(1.0, (first_corr - min_corr) / max(1e-9, 1.0 - min_corr)))
    return AcfEstimate(
        dominant_period=float(first_lag),
        peak_corr=first_corr,
        strength=strength,
    )
