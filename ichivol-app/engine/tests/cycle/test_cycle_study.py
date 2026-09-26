"""Regime-filter study tests (non-circular) for Cycle harness — P1/P4."""

from __future__ import annotations

import math
import time

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
        CycleStudyParams(
            window=96, horizon=8, min_period=8, max_period=40, null_draws=2, stride=8
        ),
    )
    assert result["ok"] is True
    assert result["kind"] == "regime_filter_study"
    assert result["n_scored"] > 0
    assert "surrogate_cycle_rates" in result
    assert "random_walk" in result["surrogate_cycle_rates"]
    assert "garch" in result["surrogate_cycle_rates"]  # P4
    assert "future_er_by_regime" in result
    assert "er_gap_cycle_minus_global" in result
    assert "null_er_gap_distributions" in result
    assert result["null_draws"] == 2
    assert result["stride"] == 8
    rw = result["null_er_gap_distributions"]["random_walk"]
    assert "observed_gap_percentile" in rw
    assert "percentile_resolution" in rw
    assert math.isclose(rw["percentile_resolution"], 1.0 / (rw["n_gaps"] + 1))
    assert result["verdict"]["promote_to_decision"] is False


def test_walk_forward_alias_insufficient_bars():
    candles = make_sine_candles(50, period=16.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=96, horizon=8, null_draws=1),
    )
    assert result["ok"] is False
    assert result["error"] == "insufficient_bars"


def test_walk_forward_alias_ok_shape():
    candles = make_sine_candles(280, period=20.0)
    result = run_cycle_walk_forward(
        candles,
        CycleStudyParams(
            window=96, horizon=8, min_period=8, max_period=40, null_draws=2, stride=8
        ),
    )
    assert result["ok"] is True
    assert math.isfinite(result["series_cycle_rate"])


def test_p1_study_budget_limit500_under_20s():
    """P1 — /study budget: limit=500, window=96, null_draws=5, stride=horizon < 20 s."""
    candles = make_sine_candles(500, period=20.0)
    t0 = time.perf_counter()
    result = run_cycle_regime_study(
        candles,
        CycleStudyParams(window=96, horizon=8, null_draws=5, stride=8),
    )
    elapsed = time.perf_counter() - t0
    assert result["ok"] is True
    assert result["null_draws"] == 5
    assert result["stride"] == 8
    assert elapsed < 20.0, f"study took {elapsed:.2f}s (budget 20s)"


def test_null_draws_clamped_to_50():
    candles = make_sine_candles(200, period=16.0)
    result = run_cycle_regime_study(
        candles,
        CycleStudyParams(window=64, horizon=4, null_draws=99, stride=4),
    )
    assert result["ok"] is True
    assert result["null_draws"] == 50
