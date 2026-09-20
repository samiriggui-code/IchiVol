"""PPO anti-lookahead + closed-candle discipline."""

from __future__ import annotations

from dataclasses import fields, replace

from app.indicators.ppo import PpoParams, compute_ppo
from app.market_data.quality import closed_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles

PARAMS = PpoParams()
N = 220
TRUNCATION_POINTS = [10, 26, 27, 35, 36, 60, 105, 150, N - 1]


def test_truncation_is_stable_for_every_field():
    candles = _make_candles(N, seed=31)
    full = compute_ppo(candles, PARAMS)
    names = [f.name for f in fields(full[0]) if f.name != "time"]

    for t in TRUNCATION_POINTS:
        trunc = compute_ppo(candles[:t], PARAMS)
        for name in names:
            assert getattr(trunc[-1], name) == getattr(full[t - 1], name), (
                f"PPO field {name!r} changed when future candles were added (T={t})"
            )


def test_future_mutation_does_not_change_past():
    candles = _make_candles(N, seed=32)
    base = compute_ppo(candles, PARAMS)
    k = 150
    mutated = list(candles)
    for j in range(k + 1, N):
        mutated[j] = replace(mutated[j], close=mutated[j].close * 3.0, high=mutated[j].high * 3.0)
    alt = compute_ppo(mutated, PARAMS)
    assert base[: k + 1] == alt[: k + 1]


def test_forming_bar_excluded_by_closed_candles():
    """Decisions use closed bars: dropping the forming bar == truncating it."""
    tf = 3600
    candles = _make_candles(120, seed=33)
    candles = [replace(c, time=1_700_000_000 + i * tf) for i, c in enumerate(candles)]
    now = candles[-1].time + tf // 2  # last bar still forming
    closed = closed_candles(candles, tf, now)
    assert len(closed) == len(candles) - 1

    with_forming = compute_ppo(candles, PARAMS)
    on_closed = compute_ppo(closed, PARAMS)
    assert on_closed[-1] == with_forming[-2]
