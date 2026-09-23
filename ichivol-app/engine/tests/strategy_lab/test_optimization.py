"""Tests — Strategy Lab Phase 8 optimization / walk-forward-opt."""

from __future__ import annotations

import pytest

from app.indicators.ichimoku import Candle
from app.strategy_lab.optimization import (
    apply_params,
    expand_param_grid,
    resolve_param_grid,
    run_optimize_on_candles,
    run_walk_forward_opt_on_candles,
)
from app.strategy_lab.ruleset import parse_ruleset


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _series(n: int = 700) -> list[Candle]:
    candles = []
    for i in range(n):
        base = 100 + i * 0.2
        candles.append(
            _c(i, base, base + 2, base - 1, base + 1, 80 + (120 if i % 15 == 0 else 0))
        )
    return candles


def _base_rs():
    return parse_ruleset(
        {
            "id": "IV_OPT_TEST",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.1},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )


def test_resolve_grid_skips_missing_conditions():
    rs = parse_ruleset(
        {
            "id": "IV_ONLY_RVOL",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    grid = resolve_param_grid(
        rs,
        {
            "rvol_min": [1.2, 1.5],
            "tk_cross_age_max": [2, 3],  # not on base → skipped
            "stop_atr": [1.0],
        },
    )
    assert "rvol_min" in grid
    assert "stop_atr" in grid
    assert "tk_cross_age_max" not in grid


def test_expand_and_apply_params():
    combos = expand_param_grid({"rvol_min": [1.2, 1.5], "stop_atr": [1.0, 1.5]})
    assert len(combos) == 4
    rs = apply_params(_base_rs(), {"rvol_min": 2.0, "stop_atr": 1.5})
    assert rs.conditions["rvol_min"] == 2.0
    assert rs.stop_atr == 1.5


def test_apply_params_preserves_any_of():
    base = parse_ruleset(
        {
            "id": "IV_OPT_ANY",
            "direction": "LONG",
            "conditions": {
                "all": {"rvol_min": 1.1},
                "any": {"bos_bullish": True, "tk_cross_bullish": True},
            },
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    rs = apply_params(base, {"rvol_min": 2.0, "stop_atr": 1.5})
    assert rs.condition_group.all_of["rvol_min"] == 2.0
    assert rs.condition_group.any_of == {
        "bos_bullish": True,
        "tk_cross_bullish": True,
    }
    assert rs.stop_atr == 1.5


def test_optimize_ranks_candidates():
    report = run_optimize_on_candles(
        _series(500),
        _base_rs(),
        symbol="TEST",
        timeframe="1h",
        grid={"rvol_min": [1.0, 1.5], "stop_atr": [1.0], "target_atr": [2.0]},
        objective="expectancy",
        min_trades=1,
        warmup_bars=52,
    )
    assert report.n_candidates == 2
    assert any(c.n_trades > 0 for c in report.ranking)
    # best may still be None if scores fail min_trades gate with weird fills;
    # with min_trades=1 and signals present, expect a winner
    scored = [c for c in report.ranking if c.score is not None]
    assert scored
    assert report.best is not None
    assert report.best.params["rvol_min"] in (1.0, 1.5)


def test_walk_forward_opt_picks_params_per_fold():
    report = run_walk_forward_opt_on_candles(
        _series(700),
        _base_rs(),
        symbol="TEST",
        timeframe="1h",
        mode="rolling",
        train_bars=200,
        test_bars=50,
        step_bars=50,
        warmup_bars=52,
        grid={"rvol_min": [1.0, 1.3], "stop_atr": [1.0], "target_atr": [2.0]},
        objective="expectancy",
        min_trades=1,
        persist=False,
    )
    assert len(report.folds) >= 2
    assert report.folds[0].test is not None
    assert isinstance(report.folds[0].best_params, dict)
    assert report.oos_summary["n_folds"] == len(report.folds)
    assert "keys" in report.param_stability


def test_grid_too_large_raises():
    rs = _base_rs()
    huge = {"rvol_min": list(range(20)), "stop_atr": list(range(10))}
    with pytest.raises(ValueError, match="combinations"):
        resolve_param_grid(rs, huge)
