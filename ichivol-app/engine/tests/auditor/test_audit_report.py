"""T6 — AuditReport unit tests."""

from __future__ import annotations

from app.agents.types import Direction
from app.auditor import AUDITOR_VERSION, build_audit_report_from_trade
from app.backtest.engine import Trade
from app.strategy_lab.ruleset_backtest import RulesetTradeDetail


def _detail(
    *,
    direction: Direction = Direction.LONG,
    log_return: float = 0.02,
    cost_log: float = 0.001,
    exit_reason: str = "target",
    why_entered: tuple[dict, ...] = (),
) -> RulesetTradeDetail:
    trade = Trade(
        entry_time=1,
        exit_time=2,
        direction=direction,
        entry_price=100.0,
        exit_price=102.0,
        log_return=log_return,
        cost_log=cost_log,
    )
    return RulesetTradeDetail(
        trade=trade,
        exit_reason=exit_reason,
        stop_price=95.0,
        target_price=110.0,
        atr_at_signal=1.0,
        signal_index=0,
        entry_index=1,
        exit_index=2,
        why_entered=why_entered,
        why_exited=(),
    )


def test_audit_winner_target():
    d = _detail(
        log_return=0.03,
        exit_reason="target",
        why_entered=({"key": "tk_bullish", "passed": True},),
    )
    rep = build_audit_report_from_trade(
        d, symbol="BTCUSDT", timeframe="1h", ruleset_id="IV_X", trade_index=0
    )
    assert rep.version == AUDITOR_VERSION
    assert rep.outcome["net_return_pct"] > 0
    assert "tk_bullish" in rep.what_worked
    assert all(h.status == "proposed" for h in rep.hypotheses)
    body = rep.to_dict()
    assert "never auto-applied" in body["disclaimer"].lower()


def test_audit_stopped_out_hypothesis():
    d = _detail(
        log_return=-0.02,
        exit_reason="stop",
        why_entered=({"key": "rvol_ok", "passed": False},),
    )
    rep = build_audit_report_from_trade(
        d, symbol="ETHUSDT", timeframe="1h", ruleset_id="IV_Y", trade_index=3
    )
    ids = {h.id for h in rep.hypotheses}
    assert "h_stop_widen_or_filter" in ids
    assert any("entry_leaf_failed" in x for x in rep.what_failed)
    assert all(h.status == "proposed" for h in rep.hypotheses)


def test_audit_max_hold_hypothesis():
    d = _detail(log_return=0.0, cost_log=0.001, exit_reason="max_hold")
    rep = build_audit_report_from_trade(
        d, symbol="X", timeframe="1h", ruleset_id=None, trade_index=1
    )
    assert any(h.id == "h_max_hold_too_short" for h in rep.hypotheses)
