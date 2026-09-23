"""T0-BROKER fidelity: close cash math, overnight financing, reconcile, liquidation.

Disposable portfolios only (unique codes); ICHIVOL_BASELINE_V1 is never touched.
Skipped when Postgres is unreachable.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.brokerage import persistence as ledger_db
from app.brokerage.ledger import Cause
from app.db.models import (
    LedgerLeg,
    LedgerTransaction,
    PaperJournalEvent,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.paper import broker
from app.paper.financing import apply_daily_financing
from app.paper.liquidation import liquidation_value
from app.paper.reconcile import reconcile_portfolio
from app.paper.strategy_profiles import BASELINE_PROFILE

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False

pytestmark = pytest.mark.skipif(not DB, reason="Postgres not reachable")


@pytest.fixture()
def session():
    s = SessionLocal()
    code = f"FID_{uuid.uuid4().hex[:10]}"
    prof = deepcopy(BASELINE_PROFILE)
    prof["code"] = code
    p = PaperPortfolio(
        code=code,
        label="t0-broker-fidelity",
        currency="EUR",
        initial_cash=5000.0,
        cash=5000.0,
        strategy_profile=prof,
    )
    s.add(p)
    s.flush()
    s.info["portfolio"] = p
    yield s
    pid = p.id
    s.rollback()
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))
    ).delete(synchronize_session=False)
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
        s.query(m).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open(
    s,
    *,
    symbol="FIDBTCUSDT",
    direction="LONG",
    price=100.0,
    notional=500.0,
    stop_distance: float | None = None,
):
    # Default stop ~2% of price so FX quotes (e.g. EURUSD≈1.10) still size.
    sd = stop_distance if stop_distance is not None else max(price * 0.02, 1e-6)
    return broker.open_capital_position(
        s,
        portfolio=s.info["portfolio"],
        symbol=symbol,
        timeframe="1h",
        source="test",
        user_id=None,
        direction=direction,
        price=price,
        decision="BUY",
        stop_distance=sd,
        manual_notional=notional,
    )


@pytest.mark.parametrize(
    "exit_mid,expect_loss",
    [
        (95.0, True),   # −5% mid
        (105.0, False),  # +5% mid
    ],
)
def test_close_long_cash_delta_and_realized_sign(session, exit_mid, expect_loss):
    p = session.info["portfolio"]
    pos = _open(session)
    assert pos is not None and pos.status == "OPEN"
    invested = float(pos.notional)
    qty = float(pos.qty)
    cash_before = float(p.cash)

    broker.close_capital_position(session, pos, price=exit_mid, reason="fidelity_close")
    session.flush()

    assert pos.status == "CLOSED"
    sell = (
        session.query(PaperOrder)
        .filter_by(portfolio_id=p.id, position_id=pos.id, side="SELL", status="FILLED")
        .one()
    )
    exit_fill = float(sell.filled_price)
    exit_fee = float(sell.fee)
    cash_delta = float(p.cash) - cash_before
    assert cash_delta == pytest.approx(qty * exit_fill - exit_fee, rel=1e-9, abs=1e-6)

    if expect_loss:
        assert cash_delta < invested
        assert float(pos.realized_pnl) < 0
    else:
        assert float(pos.realized_pnl) > 0

    assert ledger_db.is_reconciled(session, p), ledger_db.reconcile_cash(session, p)
    causes = {
        leg.cause
        for tx in session.query(LedgerTransaction).filter_by(portfolio_id=p.id)
        for leg in tx.legs
    }
    assert {"deposit", "execution", "commission"} <= causes


def test_financing_three_days_idempotent(session):
    p = session.info["portfolio"]
    pos = _open(session, symbol="EURUSD", price=1.10, notional=1000.0, stop_distance=0.01)
    assert pos is not None and pos.status == "OPEN"

    days = [date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25)]
    applied_all = []
    for d in days:
        applied_all.extend(
            apply_daily_financing(
                session,
                p,
                as_of=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
                force_day=d,
            )
        )
    session.flush()
    assert len(applied_all) == 3
    assert len({a["day"] for a in applied_all}) == 3

    again = apply_daily_financing(
        session,
        p,
        as_of=datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc),
        force_day=date(2026, 9, 25),
    )
    assert again == []

    fin_legs = (
        session.query(LedgerLeg)
        .join(LedgerTransaction, LedgerLeg.transaction_id == LedgerTransaction.id)
        .filter(
            LedgerTransaction.portfolio_id == p.id,
            LedgerLeg.cause == Cause.FINANCING.value,
        )
        .all()
    )
    assert len(fin_legs) == 3
    assert all(float(leg.amount) < 0 for leg in fin_legs)
    assert ledger_db.is_reconciled(session, p), ledger_db.reconcile_cash(session, p)


def test_reconcile_healthy_then_missing_sell_anomaly(session):
    p = session.info["portfolio"]
    pos = _open(session)
    broker.close_capital_position(session, pos, price=102.0, reason="fidelity_close")
    session.flush()

    report = reconcile_portfolio(session, p)
    assert report["ok"] is True
    assert report["anomaly_count"] == 0
    assert all(c["ok"] for c in report["checks"])

    sell = (
        session.query(PaperOrder)
        .filter_by(portfolio_id=p.id, position_id=pos.id, side="SELL")
        .one()
    )
    session.delete(sell)
    session.flush()

    broken = reconcile_portfolio(session, p)
    assert broken["ok"] is False
    assert broken["anomaly_count"] >= 1
    names = {c["name"] for c in broken["checks"] if not c["ok"]}
    assert "closed_positions_have_open_and_close_orders" in names


def test_liquidation_value_below_equity_when_fees(session):
    p = session.info["portfolio"]
    pos = _open(session, symbol="FIDBTCUSDT", price=100.0, notional=500.0)
    assert pos is not None
    mark = float(pos.entry_price)  # mid ≈ entry fill; exit friction still applies
    opens = [pos]
    invested = float(pos.notional)
    equity = float(p.cash) + invested  # unrealized ~0 at mark≈entry
    liq, missing = liquidation_value(p, opens, {pos.symbol.upper(): mark})
    assert missing == []
    assert liq < equity
