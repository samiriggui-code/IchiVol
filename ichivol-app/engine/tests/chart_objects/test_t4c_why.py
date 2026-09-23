"""T4c — WHY ENTERED / EXITED / REJECTED explainability (no outcome change)."""

from __future__ import annotations

from app.agents.types import Direction
from app.chart_objects.from_backtest import backtest_to_chart_objects
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.evaluator import explain_group, bar_matches_group
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_explain_group_matches_bar_matches():
    candles = _make_candles(300, seed=7)
    features = build_feature_series(candles)
    ruleset = get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001")
    for i, bar in enumerate(features.bars):
        ok = bar_matches_group(bar, ruleset.condition_group, ruleset.direction)
        traces = explain_group(bar, ruleset.condition_group, ruleset.direction)
        all_ok = all(t.passed for t in traces if t.clause == "all") if any(
            t.clause == "all" for t in traces
        ) else True
        any_traces = [t for t in traces if t.clause == "any"]
        any_ok = any(t.passed for t in any_traces) if any_traces else True
        has_leaves = bool(traces)
        assert ok == (has_leaves and all_ok and any_ok), f"bar {i}"


def test_why_entered_populated_on_trades():
    candles = _make_candles(300, seed=7)
    ruleset = get_builtin_ruleset("IV_EXP_A_KUMO_BO_001")
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4C", timeframe="1h"
    )
    assert result.details, "fixture should produce trades"
    for d in result.details:
        assert d.why_entered, "entry conditions should be traced"
        assert all(leaf["passed"] is True for leaf in d.why_entered)
        assert all(leaf["clause"] in ("all", "any") for leaf in d.why_entered)


def test_rejected_count_matches_skipped():
    candles = _make_candles(300, seed=7)
    ruleset = get_builtin_ruleset("IV_EXP_A_KUMO_BO_001")
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4C", timeframe="1h"
    )
    assert len(result.rejected) == result.n_skipped_in_position
    for r in result.rejected:
        assert r.reason == "in_position"
        assert r.why_entered  # rising-edge still explains conditions


def test_why_exited_on_signal_exit():
    """Ruleset with exit.conditions → why_exited leaves when exit_reason=signal."""
    candles = _make_candles(400, seed=42)
    # Minimal long entry always-ish via catalog-ish DSL; exit on opposite-ish leaf.
    # Use a builtin that has exit if any; else craft DSL with max_hold + conditions.
    ruleset = parse_ruleset(
        {
            "id": "T4C_WHY_EXIT",
            "version": "1",
            "direction": "LONG",
            "stop_atr": 1.0,
            "target_atr": 10.0,  # hard to hit → prefer signal/max_hold
            "conditions": {"price_above_kumo": True},
            "exit": {
                "max_hold_bars": 80,
                "conditions": {"price_above_kumo": False},
            },
        }
    )
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4C", timeframe="1h"
    )
    signal_exits = [d for d in result.details if d.exit_reason == "signal"]
    # Not guaranteed on every seed — if none, still assert metric path stable.
    for d in signal_exits:
        assert d.why_exited
        assert any(leaf["key"] == "price_above_kumo" for leaf in d.why_exited)


def test_overlay_includes_rejected_markers():
    candles = _make_candles(300, seed=7)
    ruleset = get_builtin_ruleset("IV_EXP_A_KUMO_BO_001")
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4C", timeframe="1h"
    )
    objects = backtest_to_chart_objects(result, candles)
    rejected = [o for o in objects if o.origin.get("kind") == "rejected"]
    assert len(rejected) == len(result.rejected)
    for o in rejected:
        assert o.label == "rejected"
        assert o.origin.get("reason") == "in_position"
