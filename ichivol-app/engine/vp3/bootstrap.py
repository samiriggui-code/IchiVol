"""Bootstrap helpers §9.2 — paired block (bar returns) + simple trade bootstrap."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


BLOCK_MEAN: dict[str, int] = {"1h": 24, "4h": 6, "1d": 1}
DEFAULT_BOOT_N = 10_000
DEFAULT_SEED = 7


@dataclass(frozen=True)
class BootstrapCI:
    mean: float
    lo: float
    hi: float
    n: int
    excludes_zero: bool


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def bootstrap_mean_ci(
    values: list[float],
    *,
    n_boot: int = DEFAULT_BOOT_N,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
) -> BootstrapCI:
    """Simple i.i.d. bootstrap of the mean (trade expectancy IC)."""
    if not values:
        return BootstrapCI(float("nan"), float("nan"), float("nan"), 0, False)
    rng = random.Random(seed)
    n = len(values)
    obs = sum(values) / n
    samples: list[float] = []
    for _ in range(n_boot):
        s = sum(values[rng.randrange(n)] for _ in range(n)) / n
        samples.append(s)
    samples.sort()
    lo = _percentile(samples, alpha / 2)
    hi = _percentile(samples, 1 - alpha / 2)
    return BootstrapCI(obs, lo, hi, n_boot, lo > 0 or hi < 0)


def paired_block_delta_ci(
    returns_a: list[float],
    returns_b: list[float],
    *,
    interval: str,
    n_boot: int = DEFAULT_BOOT_N,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
    metric: str = "mean",
) -> BootstrapCI:
    """Stationary-ish block bootstrap, paired indices, Δ = A − B on bar returns.

    metric: "mean" → Δ mean return ; "sharpe" → Δ of (mean/std) without annualisation
    (same ranking as annualised Sharpe for comparison IC).
    """
    n = min(len(returns_a), len(returns_b))
    if n < 2:
        return BootstrapCI(float("nan"), float("nan"), float("nan"), 0, False)
    a = returns_a[:n]
    b = returns_b[:n]
    block = max(1, BLOCK_MEAN.get(interval, 24))
    rng = random.Random(seed)

    def _metric(xs: list[float]) -> float:
        mu = sum(xs) / len(xs)
        if metric == "mean":
            return mu
        var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
        if var <= 0:
            return 0.0
        return mu / math.sqrt(var)

    obs = _metric(a) - _metric(b)
    samples: list[float] = []
    for _ in range(n_boot):
        idx: list[int] = []
        while len(idx) < n:
            start = rng.randrange(n)
            for k in range(block):
                idx.append((start + k) % n)
                if len(idx) >= n:
                    break
        aa = [a[i] for i in idx]
        bb = [b[i] for i in idx]
        samples.append(_metric(aa) - _metric(bb))
    samples.sort()
    lo = _percentile(samples, alpha / 2)
    hi = _percentile(samples, 1 - alpha / 2)
    return BootstrapCI(obs, lo, hi, n_boot, lo > 0 or hi < 0)
