"""Bootstrap helpers §9.2 — paired stationary block (Politis–Romano) + trade bootstrap."""

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


def stationary_block_indices(
    n: int,
    block_mean: int,
    rng: random.Random,
) -> list[int]:
    """Politis–Romano stationary bootstrap indices (geometric block lengths, circular).

    P(end block) = p = 1/block_mean ⇒ E[length] = block_mean.
    """
    if n < 1:
        return []
    p = 1.0 / max(1, block_mean)
    idx: list[int] = []
    while len(idx) < n:
        start = rng.randrange(n)
        # geometric length ≥ 1
        while True:
            idx.append(start % n)
            start += 1
            if len(idx) >= n or rng.random() < p:
                break
    return idx[:n]


def assert_aligned_timestamps(
    times_a: list[int] | None,
    times_b: list[int] | None,
) -> None:
    """VP3-R5 — bar timestamps must match before pairing."""
    if times_a is None and times_b is None:
        return
    if times_a is None or times_b is None:
        raise ValueError("paired bootstrap: one side missing timestamps")
    if len(times_a) != len(times_b):
        raise ValueError(
            f"paired bootstrap: timestamp length mismatch {len(times_a)} vs {len(times_b)}"
        )
    for i, (ta, tb) in enumerate(zip(times_a, times_b)):
        if ta != tb:
            raise ValueError(
                f"paired bootstrap: timestamp mismatch at i={i}: {ta} != {tb}"
            )


def max_drawdown_from_returns(returns: list[float]) -> float:
    """Max drawdown fraction (≤ 0) from a simple-return path starting at 1.0."""
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        eq *= 1.0 + r
        if eq > peak:
            peak = eq
        if peak > 0:
            mdd = min(mdd, eq / peak - 1.0)
    return mdd


def paired_block_delta_ci(
    returns_a: list[float],
    returns_b: list[float],
    *,
    interval: str,
    n_boot: int = DEFAULT_BOOT_N,
    seed: int = DEFAULT_SEED,
    alpha: float = 0.05,
    metric: str = "mean",
    times_a: list[int] | None = None,
    times_b: list[int] | None = None,
) -> BootstrapCI:
    """Stationary block bootstrap (Politis–Romano), paired indices, Δ = A − B.

    metric:
      - "mean" → Δ mean return
      - "sharpe" → Δ of (mean/std) without annualisation
      - "maxdd" → Δ maxDD (fraction ≤ 0); positive Δ favours A (less severe DD)
    """
    assert_aligned_timestamps(times_a, times_b)
    if times_a is not None:
        n = len(times_a)
        a = list(returns_a[:n])
        b = list(returns_b[:n])
        if len(a) != n or len(b) != n:
            raise ValueError("paired bootstrap: returns length ≠ timestamps")
    else:
        n = min(len(returns_a), len(returns_b))
        if n < 2:
            return BootstrapCI(float("nan"), float("nan"), float("nan"), 0, False)
        a = returns_a[:n]
        b = returns_b[:n]
    if n < 2:
        return BootstrapCI(float("nan"), float("nan"), float("nan"), 0, False)

    block = max(1, BLOCK_MEAN.get(interval, 24))
    rng = random.Random(seed)

    def _metric(xs: list[float]) -> float:
        if metric == "maxdd":
            return max_drawdown_from_returns(xs)
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
        idx = stationary_block_indices(n, block, rng)
        aa = [a[i] for i in idx]
        bb = [b[i] for i in idx]
        samples.append(_metric(aa) - _metric(bb))
    samples.sort()
    lo = _percentile(samples, alpha / 2)
    hi = _percentile(samples, 1 - alpha / 2)
    return BootstrapCI(obs, lo, hi, n_boot, lo > 0 or hi < 0)


def mean_block_length_sample(
    n: int,
    block_mean: int,
    *,
    n_draws: int = 5000,
    seed: int = DEFAULT_SEED,
) -> float:
    """Empirical mean geometric block length (for unit tests)."""
    rng = random.Random(seed)
    p = 1.0 / max(1, block_mean)
    lengths: list[int] = []
    for _ in range(n_draws):
        length = 1
        while rng.random() >= p:
            length += 1
            if length > n * 2:
                break
        lengths.append(length)
    return sum(lengths) / len(lengths)
