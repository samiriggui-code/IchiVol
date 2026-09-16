"""Anti-lookahead proof for the RVOL engine, same method as
test_ichimoku_lookahead.py: recompute over a truncated prefix of the
candle history and require the last bar's state to match the same bar's
state computed with the full history.
"""

from __future__ import annotations

import random
from dataclasses import fields

from app.indicators.rvol import RvolParams, compute_rvol
from tests.indicators.test_ichimoku_lookahead import _make_candles

PARAMS = RvolParams()
N = 220
TRUNCATION_POINTS = [3, 10, 27, 53, 79, 105, 150, N - 1]


def test_truncation_is_stable_for_every_field():
    candles = _make_candles(N, seed=7)
    full_states = compute_rvol(candles, PARAMS)
    field_names = [f.name for f in fields(full_states[0]) if f.name != "time"]

    for t in TRUNCATION_POINTS:
        truncated_states = compute_rvol(candles[:t], PARAMS)
        bar_full = full_states[t - 1]
        bar_trunc = truncated_states[-1]
        for name in field_names:
            v_full = getattr(bar_full, name)
            v_trunc = getattr(bar_trunc, name)
            assert v_trunc == v_full, (
                f"Field '{name}' changed when future candles were added (T={t}): "
                f"truncated={v_trunc!r} full={v_full!r}"
            )


def test_truncation_check_catches_a_forward_looking_average():
    """Negative control: a deliberately broken 'centered' average (using
    volume[i+1] as well as volume[i-1]) must fail the same truncation
    check, so a clean pass above is meaningful."""
    candles = _make_candles(N, seed=7)

    def broken_centered_rvol(cs):
        n = len(cs)
        out = []
        for i in range(n):
            lo, hi = max(0, i - 1), min(n - 1, i + 1)
            window = [c.volume for c in cs[lo : hi + 1]]
            avg = sum(window) / len(window)
            out.append(cs[i].volume / avg if avg else None)
        return out

    t = 150
    full = broken_centered_rvol(candles)
    truncated = broken_centered_rvol(candles[:t])
    assert full[t - 1] != truncated[-1]
