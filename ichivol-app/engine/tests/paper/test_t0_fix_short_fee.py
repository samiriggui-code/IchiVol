"""T0-FIX-SHORT-FEE — SHORT realized must deduct entry fees (open + renforts).

Conservation: cash_after − cash_before_open == realized_pnl (no financing).
Covers plain close, partial then remainder, reinforce then close, and
exhausting partial.
"""

from __future__ import annotations

import uuid
from copy import deepcopy

import pytest
from sqlalchemy.exc import OperationalError

from app.brokerage import persistence as ledger_db
from app.db.models import (
    LedgerLeg,
    LedgerTransaction,
    PaperJournalEvent,
    PaperOrder,
    PaperPartialExit,
    PaperPortfolio,
    PaperPosition,
    PaperReinforceAdd,
)
from app.db.session import SessionLocal, engine
from app.paper import broker
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
    code = f"SFE_{uuid.uuid4().hex[:10]}"
    prof = deepcopy(BASELINE_PROFILE)
    prof.update(
        {
            "code": code,
            "allow_short": True,
            "commission_bps": 10.0,  # non-zero so entry_fee is material
            "slippage_bps": 0.0,
            "spread_bps": 0.0,
        }
    )
    p = PaperPortfolio(
        code=code,
        label="t0-fix-short-fee",
        currency="EUR",
        initial_cash=10_000.0,
        cash=10_000.0,
        strategy_profile=prof,
    )
    s.add(p)
    s.flush()
    s.info["p"] = p
    yield s
    pid = p.id
    s.rollback()
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))
    ).delete(synchronize_session=False)
    for m in (
        LedgerTransaction,
        PaperOrder,
        PaperJournalEvent,
        PaperReinforceAdd,
        PaperPartialExit,
        PaperPosition,
    ):
        s.query(m).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open_short(s, *, price=100.0, notional=1000.0, stop_distance=5.0):
    return broker.open_capital_position(
        s,
        portfolio=s.info["p"],
        symbol="BTCUSDT",
        timeframe="1h",
        source="user_confirmed",
        user_id=None,
        direction="SHORT",
        price=price,
        decision="SELL",
        stop_distance=stop_distance,
        manual_notional=notional,
    )


def test_short_close_cash_equals_realized_with_entry_fee(session):
    p = session.info["p"]
    cash0 = float(p.cash)
    pos = _open_short(session)
    assert pos is not None
    entry_fee = float(pos.entry_fee or 0.0)
    assert entry_fee > 0
    broker.close_capital_position(session, pos, price=90.0, reason="short_fee_plain")
    session.flush()
    assert pos.status == "CLOSED"
    # Gross price PnL − exit_fee − entry_fee
    assert float(pos.realized_pnl) == pytest.approx(
        float(p.cash) - cash0, abs=1e-6
    )
    assert float(pos.realized_pnl) < broker.short_realized_currency(
        float(pos.qty), float(pos.entry_price), float(pos.exit_price)
    )
    assert ledger_db.is_reconciled(session, p)


def test_short_partial_then_close_cash_equals_realized(session):
    p = session.info["p"]
    cash0 = float(p.cash)
    pos = _open_short(session)
    assert pos is not None
    qty0 = float(pos.qty)
    half = qty0 * 0.5
    r1 = broker.partial_close_capital_position(
        session,
        pos,
        price=95.0,
        qty=half,
        fraction=0.5,
        r_multiple=1.0,
    )
    assert r1 is not None and pos.status == "OPEN"
    # First slice deducts proportional entry fee
    assert float(r1.realized_pnl) < broker.short_realized_currency(
        half, float(pos.entry_price), float(r1.price)
    )

    broker.close_capital_position(session, pos, price=90.0, reason="short_fee_remainder")
    session.flush()
    assert pos.status == "CLOSED"
    assert float(p.cash) - cash0 == pytest.approx(float(pos.realized_pnl), abs=1e-6)
    assert ledger_db.is_reconciled(session, p)


def test_short_reinforce_then_close_deducts_all_entry_fees(session):
    p = session.info["p"]
    cash0 = float(p.cash)
    pos = _open_short(session)
    assert pos is not None
    fee0 = float(pos.entry_fee or 0.0)
    iq = float(pos.initial_qty or pos.qty)
    r0 = float(pos.risk_amount or 0.0)
    assert r0 > 0

    add = broker.reinforce_add_capital_position(
        session,
        pos,
        price=95.0,  # favorable for SHORT
        add_fraction=0.5,
        r_multiple=1.0,
        initial_qty=iq,
        initial_risk=r0,
        max_exposure=2.0,
        risk_policy="tighten_stop",
    )
    assert add is not None
    assert float(pos.entry_fee) == pytest.approx(fee0 + float(add.fee))

    broker.close_capital_position(session, pos, price=90.0, reason="short_fee_reinforce")
    session.flush()
    assert pos.status == "CLOSED"
    # Restored entry_fee includes open + reinforce
    assert float(pos.entry_fee) == pytest.approx(fee0 + float(add.fee))
    assert float(p.cash) - cash0 == pytest.approx(float(pos.realized_pnl), abs=1e-6)
    assert ledger_db.is_reconciled(session, p)


def test_short_exhausting_partial_deducts_entry_fee(session):
    p = session.info["p"]
    cash0 = float(p.cash)
    pos = _open_short(session)
    assert pos is not None
    qty0 = float(pos.qty)
    r = broker.partial_close_capital_position(
        session,
        pos,
        price=92.0,
        qty=qty0,
        fraction=1.0,
        r_multiple=1.5,
    )
    assert r is not None and pos.status == "CLOSED"
    assert float(p.cash) - cash0 == pytest.approx(float(pos.realized_pnl), abs=1e-6)
    assert float(r.realized_pnl) == pytest.approx(float(pos.realized_pnl), abs=1e-6)
    assert ledger_db.is_reconciled(session, p)
