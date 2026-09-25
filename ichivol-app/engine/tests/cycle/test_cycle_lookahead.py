"""Anti-lookahead: state at T from truncated series must match full series at T."""

from __future__ import annotations

from dataclasses import fields

from app.cycle.engine import CycleParams, compute_cycle_series
from app.cycle.types import CycleState
from tests.cycle.test_cycle_values import _sine_candles

PARAMS = CycleParams(window=64, min_period=8.0, max_period=40.0)
N = 140
# Skip early warmup; probe mid/late bars
TRUNCATION_POINTS = [48, 64, 80, 100, 120, N - 1]


def _comparable(state: CycleState) -> dict:
    out = {}
    for f in fields(state):
        if f.name == "methods":
            # Nested floats — compare dominant periods only for stability
            m = state.methods
            out["methods.fft.period"] = m.get("fft", {}).get("dominant_period")
            out["methods.hilbert.period"] = m.get("hilbert", {}).get("dominant_period")
            out["methods.acf.period"] = m.get("acf", {}).get("dominant_period")
            continue
        out[f.name] = getattr(state, f.name)
    return out


def _close(a, b, tol: float = 1e-9) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if hasattr(a, "value") and hasattr(b, "value"):
        return a.value == b.value
    if isinstance(a, float) and isinstance(b, float):
        if a != a and b != b:  # NaN
            return True
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    return a == b


def test_truncation_is_stable_for_cycle_fields():
    candles = _sine_candles(N, period=18.0)
    full = compute_cycle_series(candles, PARAMS)

    for t in TRUNCATION_POINTS:
        truncated = compute_cycle_series(candles[:t], PARAMS)
        bar_full = full[t - 1]
        bar_trunc = truncated[-1]
        assert bar_trunc.time == bar_full.time
        left = _comparable(bar_trunc)
        right = _comparable(bar_full)
        for key in left:
            assert _close(left[key], right[key]), (
                f"Field '{key}' changed when future candles were added (T={t}): "
                f"truncated={left[key]!r} full={right[key]!r}"
            )
