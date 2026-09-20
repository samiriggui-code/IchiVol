"""BEST Cloud anti-lookahead + closed-candle discipline."""

from __future__ import annotations

from dataclasses import fields, replace

from app.indicators.best_cloud import BestCloudParams, compute_best_cloud
from app.market_data.quality import closed_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles

N = 220
TRUNCATION_POINTS = [10, 20, 21, 49, 50, 51, 105, 150, N - 1]
PARAM_SETS = [
    BestCloudParams(),
    BestCloudParams(fast_period=9, slow_period=21, fast_type="SMA", slow_type="EMA"),
]


def test_truncation_is_stable_for_every_field():
    candles = _make_candles(N, seed=41)
    for params in PARAM_SETS:
        full = compute_best_cloud(candles, params)
        names = [f.name for f in fields(full[0]) if f.name != "time"]
        for t in TRUNCATION_POINTS:
            trunc = compute_best_cloud(candles[:t], params)
            for name in names:
                assert getattr(trunc[-1], name) == getattr(full[t - 1], name), (
                    f"BestCloud field {name!r} changed with future candles "
                    f"(T={t}, {params})"
                )


def test_future_mutation_does_not_change_past():
    candles = _make_candles(N, seed=42)
    base = compute_best_cloud(candles)
    k = 150
    mutated = list(candles)
    for j in range(k + 1, N):
        mutated[j] = replace(mutated[j], close=mutated[j].close * 3.0)
    assert base[: k + 1] == compute_best_cloud(mutated)[: k + 1]


def test_forming_bar_excluded_by_closed_candles():
    tf = 3600
    candles = _make_candles(120, seed=43)
    candles = [replace(c, time=1_700_000_000 + i * tf) for i, c in enumerate(candles)]
    closed = closed_candles(candles, tf, candles[-1].time + tf // 2)
    assert len(closed) == len(candles) - 1
    assert compute_best_cloud(closed)[-1] == compute_best_cloud(candles)[-2]
