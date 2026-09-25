"""Benchmark CycleState latency (stdlib) — 1 / N symbols synthetic."""

from __future__ import annotations

import math
import time
from statistics import mean

from app.cycle.engine import CycleParams, compute_cycle_state
from app.indicators.ichimoku import Candle


def _sine(n: int = 300, period: float = 20.0, seed: int = 0) -> list[Candle]:
    base = 100.0 + seed
    out: list[Candle] = []
    for i in range(n):
        price = base * math.exp(0.02 * math.sin(2 * math.pi * i / period))
        t = 1_700_000_000 + i * 3600
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def run_benchmark(
    *,
    n_symbols: int = 1,
    bars: int = 300,
    window: int = 128,
    repeats: int = 3,
) -> dict:
    params = CycleParams(window=window)
    series = [_sine(bars, period=18 + (k % 5), seed=k) for k in range(n_symbols)]
    times: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        for candles in series:
            compute_cycle_state(candles, params)
        times.append(time.perf_counter() - t0)
    total = mean(times)
    return {
        "n_symbols": n_symbols,
        "bars": bars,
        "window": window,
        "repeats": repeats,
        "seconds_total_mean": total,
        "ms_per_symbol_mean": (total / n_symbols) * 1000.0,
        "note": "Synthetic sine series; wall-clock on local CPU. Not a live market guarantee.",
    }


if __name__ == "__main__":
    for n in (1, 40, 100):
        print(run_benchmark(n_symbols=n))
