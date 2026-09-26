"""Regime-filter study tests (non-circular) for Cycle harness."""

from __future__ import annotations

import math

from app.cycle.study import (
    CycleStudyParams,
    make_sine_candles,
    run_cycle_regime_study,
    run_cycle_walk_forward,
)


def test_regime_study_returns_surrogates_and_future_er():
    candles = make_sine_candles(280, period=20.0)
    result = run_cycle_regime_study(
        candles,
        CycleStudyParams(window=96, horizon=8, min_period=8, max_period=40),
    )
    assert result["ok"] is True
    assert result["kind"] == "regime_filter_study"
    assert result["n_scored"] > 0
    assert "surrogate_cycle_rates" in result
    assert "random_walk" in result["surrogate_cycle_rates"]
    assert "future_er_by_regime" in result
    assert result["verdict"]["promote_to_decision"] is False


def test_walk_forward_alias_insufficient_bars():
    candles = make_sine_candles(50, period=16.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=96, horizon=8),
    )
    assert result["ok"] is False
    assert result["error"] == "insufficient_bars"


def test_walk_forward_alias_ok_shape():
    candles = make_sine_candles(280, period=20.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=96, horizon=8, min_period=8, max_period=40),
    )
    assert result["ok"] is True
    assert math.isfinite(result["series_cycle_rate"])
