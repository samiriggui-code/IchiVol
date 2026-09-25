"""Causal series prep for spectral / cycle estimates."""

from __future__ import annotations

import math
from typing import Sequence

from app.indicators.ichimoku import Candle


def closes(candles: Sequence[Candle]) -> list[float]:
    return [float(c.close) for c in candles]


def log_prices(prices: Sequence[float]) -> list[float]:
    out: list[float] = []
    for p in prices:
        if p <= 0:
            out.append(float("nan"))
        else:
            out.append(math.log(p))
    return out


def log_returns(prices: Sequence[float]) -> list[float]:
    """r[0] = nan; r[i] = log(p[i]/p[i-1])."""
    out: list[float] = [float("nan")]
    for i in range(1, len(prices)):
        a, b = prices[i - 1], prices[i]
        if a <= 0 or b <= 0:
            out.append(float("nan"))
        else:
            out.append(math.log(b / a))
    return out


def detrend_linear(xs: Sequence[float]) -> list[float]:
    """Least-squares linear detrend on the provided window only (causal if window ends at T)."""
    n = len(xs)
    if n < 2:
        return list(xs)
    # Skip NaNs by requiring finite values
    finite_idx = [i for i, v in enumerate(xs) if math.isfinite(v)]
    if len(finite_idx) < 2:
        return [float("nan")] * n
    mean_x = sum(finite_idx) / len(finite_idx)
    mean_y = sum(xs[i] for i in finite_idx) / len(finite_idx)
    num = sum((i - mean_x) * (xs[i] - mean_y) for i in finite_idx)
    den = sum((i - mean_x) ** 2 for i in finite_idx)
    slope = num / den if den > 0 else 0.0
    intercept = mean_y - slope * mean_x
    return [
        (xs[i] - (intercept + slope * i)) if math.isfinite(xs[i]) else float("nan")
        for i in range(n)
    ]


def hann_window(n: int) -> list[float]:
    if n <= 1:
        return [1.0] * n
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


def apply_window(xs: Sequence[float], window: Sequence[float]) -> list[float]:
    return [
        (xs[i] * window[i]) if math.isfinite(xs[i]) else 0.0
        for i in range(min(len(xs), len(window)))
    ]


def finite_series(xs: Sequence[float]) -> list[float]:
    return [x if math.isfinite(x) else 0.0 for x in xs]
