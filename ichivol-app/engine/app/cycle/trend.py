"""Trend / cycle discrimination for CycleRegime (observe-only).

TREND must be a real trend measure — not Hilbert |I| vs |Q| (which labeled
long cycles as TREND). Uses Kaufman efficiency ratio + OLS R² on log-price.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.cycle.preprocess import log_prices


@dataclass(frozen=True)
class TrendEstimate:
    efficiency_ratio: float
    r_squared: float
    is_trend: bool
    strength: float


def efficiency_ratio(closes: Sequence[float]) -> float:
    """Kaufman ER on the full window: |net| / sum(|Δ|). Cycle → low; trend → high."""
    n = len(closes)
    if n < 3:
        return 0.0
    path = 0.0
    for i in range(1, n):
        path += abs(closes[i] - closes[i - 1])
    if path <= 1e-12:
        return 0.0
    return abs(closes[-1] - closes[0]) / path


def log_price_r_squared(closes: Sequence[float]) -> float:
    """R² of linear regression of log-price vs time index on the window."""
    ys = [y for y in log_prices(closes) if math.isfinite(y)]
    n = len(ys)
    if n < 4:
        return 0.0
    xs = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den_x = sum((xs[i] - mean_x) ** 2 for i in range(n))
    den_y = sum((ys[i] - mean_y) ** 2 for i in range(n))
    if den_x <= 1e-18 or den_y <= 1e-18:
        return 0.0
    r = num / math.sqrt(den_x * den_y)
    return max(0.0, min(1.0, r * r))


def estimate_trend(
    closes: Sequence[float],
    *,
    er_threshold: float = 0.42,
    r2_threshold: float = 0.55,
) -> TrendEstimate:
    """
    Calibrated roughly so pure sines → not TREND, strong linear drifts → TREND.
    Random-walk false TREND rate is controlled in synthetic tests / study nulls.
    """
    er = efficiency_ratio(closes)
    r2 = log_price_r_squared(closes)
    # Require both a directed path (ER) and a linear fit (R²)
    is_trend = er >= er_threshold and r2 >= r2_threshold
    strength = max(0.0, min(1.0, 0.5 * er + 0.5 * r2))
    return TrendEstimate(
        efficiency_ratio=er,
        r_squared=r2,
        is_trend=is_trend,
        strength=strength,
    )
