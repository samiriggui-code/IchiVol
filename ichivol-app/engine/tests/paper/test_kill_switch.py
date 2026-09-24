"""T13c — kill switch + daily loss lock tests."""

from __future__ import annotations

from app.paper.kill_switch import (
    arm_kill_switch,
    disarm_kill_switch,
    maybe_trip_daily_loss_lock,
    unlock_daily_loss,
)
from app.paper.risk_kernel import (
    OpenPlan,
    PortfolioState,
    evaluate,
    market_state_from_profile,
)
from app.paper.strategy_profiles import BASELINE_PROFILE
from app.db.session import SessionLocal
from app.paper.portfolio import ensure_baseline_portfolio


def _state(**kwargs) -> PortfolioState:
    base = dict(
        cash=10_000.0,
        equity=10_000.0,
        profile=dict(BASELINE_PROFILE),
        open_positions=(),
        day_start_equity=10_000.0,
    )
    base.update(kwargs)
    return PortfolioState(**base)


def test_kill_switch_blocks_entry():
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
        ),
        _state(kill_switch_armed=True),
        market,
    )
    assert not d.accepted
    assert d.primary_code() == "kill_switch"


def test_daily_loss_locked_blocks_even_if_equity_recovered():
    """Latched lock persists — equity back above limit still blocked until human unlock."""
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
        ),
        _state(equity=10_000.0, day_start_equity=10_000.0, daily_loss_locked=True),
        market,
    )
    assert not d.accepted
    assert d.primary_code() == "daily_loss_halt"


def test_kill_blocks_manual_notional_path():
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=100.0,
            stop_distance=2.0,
            manual_notional=50.0,
        ),
        _state(kill_switch_armed=True),
        market,
        apply_gates=False,
        check_size=False,
    )
    assert not d.accepted
    assert d.primary_code() == "kill_switch"


def test_arm_disarm_requires_confirm_and_persists():
    session = SessionLocal()
    try:
        pf = ensure_baseline_portfolio(session)
        session.commit()
        try:
            arm_kill_switch(session, pf, confirm=False)
            assert False, "expected confirm_required"
        except ValueError as exc:
            assert "confirm" in str(exc)
        arm_kill_switch(session, pf, confirm=True)
        session.commit()
        session.refresh(pf)
        assert pf.kill_switch_armed is True
        disarm_kill_switch(session, pf, confirm=True)
        session.commit()
        session.refresh(pf)
        assert pf.kill_switch_armed is False
    finally:
        session.close()


def test_trip_daily_loss_latches_and_needs_unlock():
    session = SessionLocal()
    try:
        from app.paper.gates import day_start_equity

        pf = ensure_baseline_portfolio(session)
        pf.daily_loss_locked = False
        pf.daily_loss_locked_at = None
        session.commit()
        start = day_start_equity(session, pf)
        # Breach: 4% below day start (limit 3%)
        equity = start * 0.95
        tripped = maybe_trip_daily_loss_lock(session, pf, equity=equity)
        session.commit()
        session.refresh(pf)
        assert tripped is True
        assert pf.daily_loss_locked is True
        market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
        d = evaluate(
            OpenPlan(
                symbol="BTCUSDT",
                timeframe="1h",
                direction="LONG",
                price=50_000.0,
                stop_distance=500.0,
            ),
            _state(
                equity=start,
                day_start_equity=start,
                daily_loss_locked=True,
            ),
            market,
        )
        assert d.primary_code() == "daily_loss_halt"
        unlock_daily_loss(session, pf, confirm=True)
        session.commit()
        session.refresh(pf)
        assert pf.daily_loss_locked is False
    finally:
        session.close()
