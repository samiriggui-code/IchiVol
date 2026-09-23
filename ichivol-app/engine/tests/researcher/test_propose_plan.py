"""Researcher propose_experiment_plan tests."""

from __future__ import annotations

import pytest

from app.agents.types import Direction
from app.auditor import AuditReport, build_audit_report_from_trade
from app.backtest.engine import Trade
from app.researcher import propose_experiment_plan
from app.strategy_lab.ruleset_backtest import RulesetTradeDetail


def _stopped_report() -> AuditReport:
    trade = Trade(
        entry_time=1,
        exit_time=2,
        direction=Direction.LONG,
        entry_price=100.0,
        exit_price=95.0,
        log_return=-0.05,
        cost_log=0.001,
    )
    detail = RulesetTradeDetail(
        trade=trade,
        exit_reason="stop",
        stop_price=95.0,
        target_price=110.0,
        atr_at_signal=1.0,
        signal_index=0,
        entry_index=1,
        exit_index=2,
        why_entered=({"key": "rvol_min", "passed": False},),
        why_exited=(),
    )
    return build_audit_report_from_trade(
        detail,
        symbol="BTCUSDT",
        timeframe="1h",
        ruleset_id="IV_TEST",
        trade_index=0,
    )


def test_plan_from_stopped_audit():
    plan = propose_experiment_plan(_stopped_report())
    assert plan.status == "proposed"
    assert "never auto-runs" in plan.disclaimer.lower()
    tools = {s.tool for s in plan.steps}
    assert "run_regime_slices" in tools or "run_ablation" in tools
    assert plan.symbol == "BTCUSDT"


def test_plan_from_dict_filter_hypothesis():
    report = {
        "symbol": "ETHUSDT",
        "timeframe": "4h",
        "ruleset_id": "IV_X",
        "hypotheses": [
            {
                "id": "h_max_hold_too_short",
                "statement": "max hold",
                "suggested_experiment": "wf",
                "status": "proposed",
            }
        ],
    }
    plan = propose_experiment_plan(report, hypothesis_ids=["h_max_hold_too_short"])
    assert plan.steps[0].tool == "run_walk_forward_opt"
    assert plan.source_hypothesis_ids == ["h_max_hold_too_short"]


def test_empty_hypotheses_fail():
    with pytest.raises(ValueError, match="no hypotheses"):
        propose_experiment_plan(
            {
                "symbol": "X",
                "timeframe": "1h",
                "hypotheses": [],
            }
        )
