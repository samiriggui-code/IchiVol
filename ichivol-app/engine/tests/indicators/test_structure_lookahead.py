"""Anti-lookahead proof for structure.py, same truncation method as
Ichimoku/RVOL: state at bar T-1 computed over the full history must match
the same bar computed over just the first T candles.
"""

from __future__ import annotations

from dataclasses import fields

from app.indicators.structure import StructureParams, compute_structure
from tests.indicators.test_ichimoku_lookahead import _make_candles

PARAMS = StructureParams(swing_lookback=2)
N = 220
TRUNCATION_POINTS = [10, 27, 53, 79, 105, 150, N - 1]


def test_truncation_is_stable_for_every_field():
    candles = _make_candles(N, seed=11)
    full_states = compute_structure(candles, PARAMS)
    field_names = [f.name for f in fields(full_states[0]) if f.name != "time"]

    for t in TRUNCATION_POINTS:
        truncated_states = compute_structure(candles[:t], PARAMS)
        bar_full = full_states[t - 1]
        bar_trunc = truncated_states[-1]
        for name in field_names:
            v_full = getattr(bar_full, name)
            v_trunc = getattr(bar_trunc, name)
            assert v_trunc == v_full, (
                f"Field '{name}' changed when future candles were added (T={t}): "
                f"truncated={v_trunc!r} full={v_full!r}"
            )
