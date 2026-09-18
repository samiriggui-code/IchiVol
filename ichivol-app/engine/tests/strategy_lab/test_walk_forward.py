"""Tests — Strategy Lab Phase 7 walk-forward."""

from __future__ import annotations

import pytest

from app.indicators.ichimoku import Candle
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.walk_forward import (
    generate_expanding_folds,
    generate_rolling_folds,
    run_walk_forward_on_candles,
)


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def test_generate_rolling_folds_non_overlapping_test():
    folds = generate_rolling_folds(600, train_bars=200, test_bars=50, step_bars=50, warmup_bars=52)
    assert len(folds) >= 2
    for f in folds:
        assert f.train_end == f.test_start
        assert f.test_end - f.test_start == 50
        assert f.train_end - f.train_start == 200


def test_generate_expanding_folds_grows_train():
    folds = generate_expanding_folds(
        600, initial_train_bars=150, test_bars=50, step_bars=50, warmup_bars=52
    )
    assert len(folds) >= 2
    assert folds[0].train_start == folds[1].train_start == 52
    assert folds[1].train_end > folds[0].train_end


def test_walk_forward_runs_oos_summary():
    candles = []
    for i in range(700):
        base = 100 + i * 0.2
        candles.append(
            _c(i, base, base + 2, base - 1, base + 1, 80 + (120 if i % 15 == 0 else 0))
        )
    rs = parse_ruleset(
        {
            "id": "IV_WF_TEST",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.1},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    report = run_walk_forward_on_candles(
        candles,
        rs,
        symbol="TEST",
        timeframe="1h",
        mode="rolling",
        train_bars=200,
        test_bars=50,
        step_bars=50,
        warmup_bars=52,
        include_train=True,
        persist=False,
    )
    assert report.n_bars == 700
    assert len(report.folds) >= 2
    assert report.folds[0].test is not None
    assert report.folds[0].train is not None
    assert report.oos_summary["n_folds"] == len(report.folds)
    assert "mean_oos_expectancy" in report.oos_summary


def test_not_enough_bars_raises():
    candles = [_c(i, 100, 101, 99, 100) for i in range(80)]
    rs = parse_ruleset(
        {
            "id": "IV_WF_SMALL",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
        }
    )
    with pytest.raises(ValueError, match="not enough bars"):
        run_walk_forward_on_candles(
            candles,
            rs,
            symbol="TEST",
            timeframe="1h",
            train_bars=400,
            test_bars=100,
            warmup_bars=52,
        )
