"""Real-DB test: paper broker open/close double-writes the ledger and reconciles."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy.exc import OperationalError

from app.brokerage import persistence as ledger_db
from app.brokerage.ledger import Cause, DuplicateConflict, Leg
from app.db.models import LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.paper import broker

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")


@pytest.fixture()
def session():
    s = SessionLocal()
    code = f"LEDGERTEST_{uuid.uuid4().hex[:8]}"
    p = PaperPortfolio(code=code, label="t", currency="EUR", initial_cash=5000.0, cash=5000.0, strategy_profile={})
    s.add(p)
    s.flush()
    s.info["portfolio"] = p
    yield s
    pid = p.id
    s.rollback()
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))
    ).delete(synchronize_session=False)
    s.query(LedgerTransaction).filter_by(portfolio_id=pid).delete()
    s.query(PaperOrder).filter_by(portfolio_id=pid).delete()
    s.query(PaperPosition).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open(s, direction="LONG"):
    return broker.open_capital_position(
        s, portfolio=s.info["portfolio"], symbol="LEDGERX", timeframe="1h", source="test", user_id=None,
        direction=direction, price=100.0, decision="BUY", stop_distance=2.0,
        signal={"bar_time": f"ledger-{direction}"},
    )


@pytest.mark.parametrize("direction,exit_price", [("LONG", 104.0), ("SHORT", 104.0), ("LONG", 96.0)])
def test_open_close_reconciles_with_cash_field(session, direction, exit_price):
    p = session.info["portfolio"]
    pos = _open(session, direction)
    assert pos is not None
    assert ledger_db.is_reconciled(session, p)
    broker.close_capital_position(session, pos, price=exit_price, reason="test")
    session.flush()
    assert ledger_db.is_reconciled(session, p), ledger_db.reconcile_cash(session, p)
    causes = {l.cause for t in session.query(LedgerTransaction).filter_by(portfolio_id=p.id) for l in t.legs}
    assert {"deposit", "execution", "commission"} <= causes


def test_replayed_event_does_not_double_bill(session):
    p = session.info["portfolio"]
    pos = _open(session)
    n = session.query(LedgerTransaction).filter_by(portfolio_id=p.id).count()
    now = datetime.now(timezone.utc)
    tx = session.query(LedgerTransaction).filter_by(portfolio_id=p.id, key=f"open:{pos.id}").one()
    legs = [Leg(l.currency, D(l.amount), Cause(l.cause), l.memo) for l in tx.legs]
    ledger_db.post(session, p.id, f"open:{pos.id}", now, legs, ref=pos.id)  # replay
    assert session.query(LedgerTransaction).filter_by(portfolio_id=p.id).count() == n
    with pytest.raises(DuplicateConflict):
        ledger_db.post(session, p.id, f"open:{pos.id}", now, [Leg("EUR", D("-1"), Cause.EXECUTION)], ref=pos.id)


def test_double_close_does_not_double_credit(session):
    p = session.info["portfolio"]
    pos = _open(session)
    broker.close_capital_position(session, pos, price=104.0, reason="first")
    session.flush()
    cash_after_first, realized_after_first = p.cash, p.realized_pnl
    broker.close_capital_position(session, pos, price=110.0, reason="replay")  # replay after restart
    session.flush()
    assert p.cash == cash_after_first and p.realized_pnl == realized_after_first
    assert pos.exit_reason == "first"
    assert ledger_db.is_reconciled(session, p)


def test_ledger_failure_never_blocks_the_trade(session, monkeypatch):
    p = session.info["portfolio"]

    def boom(*a, **k):
        raise RuntimeError("ledger table missing")

    monkeypatch.setattr(ledger_db, "post", boom)
    pos = _open(session)
    assert pos is not None and pos.status == "OPEN"  # trade went through
    session.flush()
    ev = session.query(PaperJournalEvent).filter_by(portfolio_id=p.id, event_type="LEDGER_ERROR").all()
    assert {e.payload["what"] for e in ev} == {"opening", "open"}  # both ledger writes failed, both recorded
    assert all("ledger table missing" in e.payload["error"] for e in ev)


def test_non_finite_values_are_refused_before_any_mutation(session):
    import pytest as _pt

    with _pt.raises(ValueError):
        ledger_db.to_decimal(float("nan"))
    pos = _open(session)
    p = session.info["portfolio"]
    cash = p.cash
    with _pt.raises(ValueError):
        broker.close_capital_position(session, pos, price=float("nan"), reason="bad")
    assert p.cash == cash and pos.status == "OPEN"
