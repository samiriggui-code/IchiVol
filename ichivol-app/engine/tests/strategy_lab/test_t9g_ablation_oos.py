"""T9g — ablation × walk-forward OOS (observation-only recommendations)."""

from __future__ import annotations

from app.agents.types import Direction
from app.strategy_lab.ablation_oos import (
    decide_recommendation,
    run_ablation_oos_study_on_candles,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles

_TINY_LAYERS = (
    ("A_KUMO", {"price_above_kumo": True}),
    ("B_RVOL", {"rvol_min": 1.0}),
)


def test_decide_promote_reject_inconclusive():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=0.1,
        is_expectancy_delta=0.02,
        total_oos_trades=20,
        n_folds=3,
        min_oos_trades=5,
    )
    assert rec == "promote"
    assert reasons

    rec, reasons = decide_recommendation(
        oos_expectancy_delta=-0.01,
        oos_profit_factor_delta=0.0,
        is_expectancy_delta=0.05,
        total_oos_trades=20,
        n_folds=3,
        min_oos_trades=5,
    )
    assert rec == "reject"

    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=0.0,
        is_expectancy_delta=0.0,
        total_oos_trades=2,
        n_folds=3,
        min_oos_trades=5,
    )
    assert rec == "inconclusive"
    assert "min_oos_trades" in reasons[0]


def test_ablation_oos_additive_on_synthetic():
    candles = _make_candles(280, seed=11)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        layers=_TINY_LAYERS,
        direction=Direction.LONG,
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=1,
    )
    assert report.n_bars == 280
    assert report.compare_mode == "additive"
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.label == "B_RVOL"
    assert c.recommendation in ("promote", "reject", "inconclusive")
    assert "no auto-reject" in report.disclaimer.lower()
    assert "FeatureStatus" in report.disclaimer or "featurestatus" in report.disclaimer.lower()
    body = report.to_dict()
    assert body["candidates"][0]["baseline_ruleset_id"]
    assert body["candidates"][0]["variant_ruleset_id"]


def test_ablation_oos_leave_one_layer():
    candles = _make_candles(260, seed=5)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="ETHUSDT",
        timeframe="1h",
        compare_mode="leave_one_layer_out",
        layers=_TINY_LAYERS,
        train_bars=70,
        test_bars=25,
        step_bars=25,
        warmup_bars=52,
        min_oos_trades=1,
    )
    assert report.compare_mode == "leave_one_layer_out"
    assert len(report.candidates) == 2
    labels = {c.label for c in report.candidates}
    assert labels == {"A_KUMO", "B_RVOL"}
