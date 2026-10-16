"""P2 — ProtectionSpec + fee-aware trail lock + virtual costs (QuantDinger)."""

from __future__ import annotations

import pytest

from app.agents.types import Direction
from app.paper.protection_spec import ProtectionSpec
from app.paper.virtual_execution_costs import resolve_virtual_execution_cost_policy
from app.strategy_lab.stop_trail import trailing_exit_locks_net_profit


def test_protection_spec_to_trail_dict() -> None:
    spec = ProtectionSpec(breakeven_at_r=1.0, atr_trail_mult=1.5, commission_bps=5, slippage_bps=3)
    assert spec.enabled
    trail = spec.to_protection_trail_dict()
    assert trail is not None
    assert trail["breakeven_at_r"] == 1.0
    assert trail["atr_trail_mult"] == 1.5


def test_protection_spec_from_value_trailing_block() -> None:
    spec = ProtectionSpec.from_value(
        {
            "stop_loss_pct": 0.02,
            "trailing": {"breakeven_at_r": 1.0, "atr_trail_mult": 1.2},
        }
    )
    assert spec is not None
    assert spec.stop_loss_pct == 0.02
    assert spec.breakeven_at_r == 1.0


def test_trailing_exit_locks_net_profit_long() -> None:
    # 5+3 bps → round trip 16 bps = 0.0016
    assert trailing_exit_locks_net_profit(
        Direction.LONG,
        entry_price=100.0,
        exit_price=100.10,
        commission_bps=5.0,
        slippage_bps=3.0,
    ) is False
    assert trailing_exit_locks_net_profit(
        Direction.LONG,
        entry_price=100.0,
        exit_price=100.20,
        commission_bps=5.0,
        slippage_bps=3.0,
    ) is True


def test_virtual_costs_reject_live() -> None:
    with pytest.raises(ValueError, match="live"):
        resolve_virtual_execution_cost_policy(payload={"mode": "live"})


def test_virtual_costs_paper_metadata() -> None:
    pol = resolve_virtual_execution_cost_policy(
        strategy_profile={"commission_bps": 7, "slippage_bps": 2}
    )
    assert pol.mode == "paper"
    assert pol.commission_for(quantity=1.0, fill_price=10_000) == pytest.approx(7.0)
    meta = pol.metadata()
    assert meta["round_trip_fraction"] == pytest.approx(2.0 * 9 / 10_000)
