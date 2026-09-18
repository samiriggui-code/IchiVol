"""Unit tests for paper risk sizing (no DB)."""

from __future__ import annotations

from app.paper.risk import apply_entry_friction, apply_exit_friction, size_position


def test_size_long_1pct_risk_2r():
    sized = size_position(
        equity=5000.0,
        cash=5000.0,
        direction="LONG",
        entry_price=100.0,
        stop_distance=2.0,
        risk_pct=0.01,
        take_profit_r=2.0,
        max_notional_pct=1.0,
        commission_bps=0.0,
        spread_bps=0.0,
        slippage_bps=0.0,
    )
    assert sized is not None
    assert sized.risk_amount == 50.0
    assert sized.qty == 25.0
    assert sized.stop_price == 98.0
    assert sized.take_profit_price == 104.0


def test_size_caps_notional_at_25pct():
    sized = size_position(
        equity=5000.0,
        cash=5000.0,
        direction="LONG",
        entry_price=100.0,
        stop_distance=2.0,
        risk_pct=0.01,
        max_notional_pct=0.25,
        commission_bps=0.0,
        spread_bps=0.0,
        slippage_bps=0.0,
    )
    assert sized is not None
    assert sized.notional == 1250.0
    assert sized.qty == 12.5


def test_entry_friction_is_adverse():
    assert apply_entry_friction(100.0, direction="LONG", spread_bps=10, slippage_bps=0) > 100.0
    assert apply_entry_friction(100.0, direction="SHORT", spread_bps=10, slippage_bps=0) < 100.0
    assert apply_exit_friction(100.0, direction="LONG", spread_bps=10, slippage_bps=0) < 100.0


def test_size_rejects_zero_stop():
    assert (
        size_position(
            equity=5000.0,
            cash=5000.0,
            direction="LONG",
            entry_price=100.0,
            stop_distance=0.0,
        )
        is None
    )


def test_size_respects_cash():
    sized = size_position(
        equity=5000.0,
        cash=50.0,
        direction="LONG",
        entry_price=100.0,
        stop_distance=1.0,
        risk_pct=0.01,
        commission_bps=0.0,
        spread_bps=0.0,
        slippage_bps=0.0,
    )
    assert sized is not None
    assert sized.notional <= 50.0 + 1e-9
