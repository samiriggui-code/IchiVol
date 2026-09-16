"""Anti-lookahead tests for the Ichimoku engine.

Mission rule (brief §11): before trusting any backtest, prove that at
instant T the engine never used data that would not yet exist at T.

Method: compute the full indicator series over N candles, then recompute it
over just the first T candles (T < N) -- exactly what would have been in a
live system's window at that moment -- and require the state at the last
bar of the truncated series to be byte-for-byte identical to the state at
index T-1 of the full series. If any field secretly depended on
candles[T..N), truncating would change it (it would typically become
UNKNOWN/None, since the "future" data feeding it would no longer exist).

test_truncation_check_catches_backtestbot_style_bug is a negative control:
it re-implements the exact lookahead pattern found in
_research/backtestbot's ichimoku_strategy.py (comparing a shifted-into-the-
future Chikou value against a past close, at the *current* row) and shows
this same truncation check correctly flags it as broken. That's the proof
the check methodology is meaningful, not just tautological against our own
implementation.
"""

from __future__ import annotations

import random
from dataclasses import fields

from app.indicators.ichimoku import Candle, IchimokuParams, compute_ichimoku


def _make_candles(n: int, seed: int = 42) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    candles: list[Candle] = []
    for i in range(n):
        drift = rng.uniform(-1.5, 1.5)
        open_ = price
        close = max(1.0, price + drift)
        high = max(open_, close) + rng.uniform(0, 1.0)
        low = min(open_, close) - rng.uniform(0, 1.0)
        volume = rng.uniform(10, 1000)
        candles.append(Candle(time=i, open=open_, high=high, low=low, close=close, volume=volume))
        price = close
    return candles


PARAMS = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
N = 220
TRUNCATION_POINTS = [10, 27, 53, 79, 105, 150, 200, N - 1]


def test_truncation_is_stable_for_every_field():
    candles = _make_candles(N)
    full_states = compute_ichimoku(candles, PARAMS)

    for t in TRUNCATION_POINTS:
        truncated_states = compute_ichimoku(candles[:t], PARAMS)
        current_bar_full = full_states[t - 1]
        current_bar_truncated = truncated_states[-1]

        assert current_bar_truncated == current_bar_full, (
            f"Lookahead detected at truncation point T={t}: state computed with only "
            f"the first {t} candles differs from the state computed with the full "
            f"{N}-candle history, at the same bar. Some field must be reading data "
            f"beyond index {t - 1}.\n"
            f"  truncated={current_bar_truncated}\n"
            f"  full     ={current_bar_full}"
        )


def test_no_field_ever_improves_with_more_future_data():
    """Stronger, per-field version of the above: walk T from small to N and
    make sure each field, once non-UNKNOWN/non-None, never *changes* value
    purely because more future candles were appended after it.
    """
    candles = _make_candles(N)
    full_states = compute_ichimoku(candles, PARAMS)
    field_names = [f.name for f in fields(full_states[0]) if f.name != "time"]

    for t in range(30, N, 17):
        truncated_states = compute_ichimoku(candles[:t], PARAMS)
        bar_full = full_states[t - 1]
        bar_trunc = truncated_states[-1]
        for name in field_names:
            v_full = getattr(bar_full, name)
            v_trunc = getattr(bar_trunc, name)
            assert v_trunc == v_full, (
                f"Field '{name}' changed when future candles were added "
                f"(T={t}): truncated={v_trunc!r} full={v_full!r}"
            )


def _naive_backtestbot_style_chikou_signal(candles: list[Candle], displacement: int):
    """Deliberately reproduces the lookahead bug found in
    _research/backtestbot/strategy/ichimoku_strategy.py:
    `chikou_span = close.shift(-displacement)` stored at row i (i.e.
    chikou_span[i] == close[i + displacement], a *future* close), then
    compared at row i against `close[i - displacement]` (a past close).
    Returns a list[bool | None], one per candle, aligned like our engine.
    """
    n = len(candles)
    closes = [c.close for c in candles]
    out: list[bool | None] = [None] * n
    for i in range(n):
        future_idx = i + displacement
        past_idx = i - displacement
        if future_idx >= n or past_idx < 0:
            out[i] = None
            continue
        out[i] = closes[future_idx] > closes[past_idx]
    return out


def test_truncation_check_catches_backtestbot_style_bug():
    """Negative control: confirms our truncation methodology actually
    detects the known BacktestBot-style lookahead bug, so a clean pass on
    our own engine (above) is meaningful rather than a check that would
    pass anything.
    """
    candles = _make_candles(N)
    d = PARAMS.displacement
    full_signal = _naive_backtestbot_style_chikou_signal(candles, d)

    t = 150
    truncated_signal = _naive_backtestbot_style_chikou_signal(candles[:t], d)

    # At the current bar (t-1), the full-history run "knows" a future close
    # (index t-1+d) that simply does not exist yet in the truncated window,
    # so the two runs disagree at exactly the bar a live system would be
    # deciding on right now -- the signature of lookahead bias.
    assert full_signal[t - 1] is not None
    assert truncated_signal[-1] is None
    assert truncated_signal[-1] != full_signal[t - 1]
