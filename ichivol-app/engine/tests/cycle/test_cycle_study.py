"""Walk-forward + null-model tests for Cycle study harness."""

from __future__ import annotations

import math

from app.cycle.study import CycleStudyParams, run_cycle_walk_forward
from app.indicators.ichimoku import Candle


def _sine_candles(n: int, period: float = 20.0) -> list[Candle]:
    base = 100.0
    out: list[Candle] = []
    for i in range(n):
        price = base * math.exp(0.02 * math.sin(2 * math.pi * i / period))
        t = 1_700_000_000 + i * 3600
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def test_walk_forward_returns_verdict_structure():
    candles = _sine_candles(280, period=20.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=96, horizon=8, min_period=8, max_period=40),
    )
    assert result["ok"] is True
    assert result["n_scored"] > 0
    assert "period" in result and "phase" in result
    assert result["verdict"]["promote_to_decision"] is False
    assert "engine" in result["period"]
    assert "null_random" in result["period"]


def test_walk_forward_insufficient_bars():
    candles = _sine_candles(50, period=16.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=96, horizon=8),
    )
    assert result["ok"] is False
    assert result["error"] == "insufficient_bars"
