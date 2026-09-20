"""First full chain on a real DB: quote -> order -> fill -> fee schedule -> ledger -> net result."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.brokerage import persistence as ledger_db
from app.brokerage import quote_paper
from app.db.models import (
    LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.market_data.contracts import Provenance, Quote

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres not reachable")

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


class FakeProvider:
    id = "binance"

    def __init__(self, bid, ask, bid_size=100.0, ask_size=100.0, age=0.0):
        t = datetime.fromtimestamp(NOW.timestamp() - age, tz=timezone.utc)
        self.q = Quote("BTCUSDT", bid, ask, Provenance("binance", t, t), bid_size=bid_size, ask_size=ask_size)
        self.broken = False

    def fetch_quote(self, symbol):
        if self.broken:
            raise RuntimeError("provider down")
        return self.q


@pytest.fixture()
def session():
    s = SessionLocal()
    p = PaperPortfolio(
        code=f"CHAIN_{uuid.uuid4().hex[:8]}", label="t", currency="USDT", initial_cash=5000.0, cash=5000.0,
        strategy_profile={"fee_profile_id": "BINANCE_SPOT_STANDARD_ASSUMED", "risk_pct": 0.01,
                          "take_profit_r": 2.0, "max_notional_pct": 0.25, "max_open_positions": 5},
    )
    s.add(p)
    s.flush()
    s.info["p"] = p
    yield s
    pid = p.id
    s.rollback()
    s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))).delete(synchronize_session=False)
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
        s.query(m).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open(s, prov, stop=500.0):
    return quote_paper.open_at_market(
        s, portfolio=s.info["p"], provider=prov, instrument_id="BTCUSDT", timeframe="1h",
        direction="LONG", decision="BUY", stop_distance=stop, now=NOW,
    )


def test_full_chain_net_result_equals_gross_minus_fees_and_reconciles(session):
    p = session.info["p"]
    pos = _open(session, FakeProvider(bid=80000.0, ask=80010.0))
    assert pos is not None and pos.entry_price == 80010.0  # buy at ask, spread in price
    order = session.query(PaperOrder).filter_by(position_id=pos.id).one()
    assert order.spread_bps == 0.0 and order.slippage_bps == 0.0  # no second spread charge

    closed = quote_paper.close_at_market(session, pos, provider=FakeProvider(bid=81000.0, ask=81010.0), reason="test", now=NOW)
    session.flush()
    assert closed.exit_price == 81000.0  # sell at bid
    gross = pos.qty * (81000.0 - 80010.0)
    fees = pos.entry_fee + pos.exit_fee
    assert fees == pytest.approx(0.001 * (pos.qty * 80010.0) + 0.001 * (pos.qty * 81000.0), abs=1e-7)  # schedule rounds to 8 decimals
    assert p.cash - 5000.0 == pytest.approx(gross - fees, abs=1e-6)  # net = gross - costs
    assert ledger_db.is_reconciled(session, p)

    ev = {e.event_type: e.payload for e in session.query(PaperJournalEvent).filter_by(portfolio_id=p.id)}
    assert ev["OPENED"]["execution"]["model"] == "quote_based" and ev["OPENED"]["fee"]["id"] == "BINANCE_SPOT_STANDARD_ASSUMED"
    assert "ASSUMPTION" in ev["OPENED"]["fee"]["source"]
    assert ev["CLOSED"]["execution"]["model"] == "quote_based"


def test_partial_fill_when_top_of_book_too_small(session):
    pos = _open(session, FakeProvider(bid=80000.0, ask=80010.0, ask_size=0.001))
    assert pos is not None and pos.qty == pytest.approx(0.001)
    assert ledger_db.is_reconciled(session, session.info["p"])


def test_no_trade_on_stale_or_unavailable_quote(session):
    assert _open(session, FakeProvider(80000.0, 80010.0, age=60.0)) is None
    down = FakeProvider(80000.0, 80010.0)
    down.broken = True
    assert _open(session, down) is None
    assert session.query(LedgerTransaction).filter_by(portfolio_id=session.info["p"].id).count() == 0
