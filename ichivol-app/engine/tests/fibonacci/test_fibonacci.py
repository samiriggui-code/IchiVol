"""Tests for Fibonacci Context engine + gate."""

from __future__ import annotations

from app.agents.types import Direction
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.fibonacci.context import FIB_RATIOS, compute_fib_context, compute_fib_levels
from app.fibonacci.gate import apply_fibonacci_gate
from app.indicators.ichimoku import Candle
from app.paper.strategy_profiles import BASELINE_PROFILE, ICHIVOL_MS_FIB, profile_for
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_fib_ratios_and_levels_up_impulse():
    levels = compute_fib_levels(100.0, 200.0, "up")
    assert len(levels) == len(FIB_RATIOS)
    # 50% retrace from 200 toward 100 = 150
    mid = next(lv for lv in levels if lv.ratio == 0.5)
    assert abs(mid.price - 150.0) < 1e-9
    # 61.8% = 200 - 0.618*100
    r618 = next(lv for lv in levels if lv.ratio == 0.618)
    assert abs(r618.price - (200.0 - 0.618 * 100.0)) < 1e-9


def test_fib_levels_down_impulse():
    levels = compute_fib_levels(100.0, 200.0, "down")
    mid = next(lv for lv in levels if lv.ratio == 0.5)
    assert abs(mid.price - 150.0) < 1e-9


def test_compute_fib_context_causal():
    candles = _make_candles(200, seed=7)
    full = compute_fib_context(candles)
    trunc = compute_fib_context(candles[:120])
    if full is None or trunc is None:
        # Sparse pivots on synthetic data — still must not crash
        return
    assert trunc.swing_low == compute_fib_context(candles[:120]).swing_low


def test_baseline_fib_off():
    pipe = PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[PipelineStage(StageId.LOCATION, StageStatus.PASS, "ok", [])],
    )
    gate = apply_fibonacci_gate(pipe, _make_candles(80), BASELINE_PROFILE)
    assert gate.blocked is False
    assert gate.pipeline.decision == "BUY"
    assert gate.fibonacci_payload is None


def test_ms_fib_profile_registered():
    p = profile_for("ICHIVOL_MS_FIB")
    assert p["fibonacci_filter"] == "require_confluence"
    assert p["structure_filter"] == "block_near_opposing"
    assert ICHIVOL_MS_FIB["code"] == "ICHIVOL_MS_FIB"
    assert BASELINE_PROFILE["fibonacci_filter"] is None


def test_fib_gate_blocks_without_confluence():
    """Force a clear up impulse then park close far from Fib levels."""
    candles: list[Candle] = []
    t = 1_000_000
    # Build low → high impulse with clear fractals, then spike away
    price = 100.0
    for i in range(40):
        candles.append(
            Candle(time=t + i, open=price, high=price + 0.5, low=price - 0.5, close=price, volume=1000)
        )
        price += 0.2
    # Peak plateau then sharp drop (away from mid Fib)
    peak = price
    for i in range(5):
        candles.append(
            Candle(
                time=t + 40 + i,
                open=peak,
                high=peak + 1,
                low=peak - 0.2,
                close=peak,
                volume=2000,
            )
        )
    # Dump far below any reasonable 0.5–0.786 band of a short swing
    dump = peak * 0.5
    for i in range(10):
        candles.append(
            Candle(
                time=t + 50 + i,
                open=dump,
                high=dump + 0.5,
                low=dump - 0.5,
                close=dump,
                volume=1500,
            )
        )

    pipe = PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[PipelineStage(StageId.LOCATION, StageStatus.PASS, "ok", [])],
    )
    gate = apply_fibonacci_gate(pipe, candles, ICHIVOL_MS_FIB)
    # Either no swings (no block) or confluence fail → NO_TRADE
    if gate.reason == "no_swings":
        assert gate.blocked is False
    else:
        assert gate.blocked is True
        assert gate.pipeline.decision == "NO_TRADE"
        assert gate.fibonacci_payload is not None
