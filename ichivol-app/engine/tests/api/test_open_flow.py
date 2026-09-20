"""Open-position journey at API level (decision -> confirm -> accept/refuse -> position
-> journal -> account), on the real dev DB with a controlled scan result.

The baseline portfolio is shared dev state: its cash/realized are snapshotted and
restored, and every row created for the synthetic symbol is removed afterwards.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.api import routes
from app.brokerage import persistence as ledger_db
from app.db.models import (
    LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.main import app
from app.paper.strategy_profiles import BASELINE_CODE

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False

pytestmark = pytest.mark.skipif(not DB, reason="Postgres not reachable")

SYMBOL = "OPENFLOWX"
USER = "user-openflow-test"


def _row(decision="BUY", price=100.0, stop=2.0):
    direction = Direction.LONG if decision == "BUY" else Direction.NEUTRAL
    return SimpleNamespace(
        symbol=SYMBOL, price=price, candles=[], evidence=None, context=None,
        atr=SimpleNamespace(suggested_stop_distance=stop),
        pipeline=PipelineResult(decision=decision, direction=direction, stages=[]),
    )


@pytest.fixture()
def client(monkeypatch):
    s = SessionLocal()
    pf = s.query(PaperPortfolio).filter_by(code=BASELINE_CODE).one_or_none()
    if pf is None:
        from app.paper.portfolio import ensure_baseline_portfolio
        pf = ensure_baseline_portfolio(s)
        s.commit()
    snap = (pf.id, pf.cash, pf.realized_pnl)
    monkeypatch.setattr(routes, "scan_symbol", lambda *a, **k: _row())
    # tests/api/conftest-independent: TestClient without lifespan (no background threads)
    yield TestClient(app), pf.id, s
    s.rollback()
    pid = snap[0]
    pos_ids = [p.id for p in s.query(PaperPosition).filter_by(portfolio_id=pid, symbol=SYMBOL)]
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter(LedgerTransaction.ref.in_(pos_ids or ["-"])))
    ).delete(synchronize_session=False)
    s.query(LedgerTransaction).filter(LedgerTransaction.ref.in_(pos_ids or ["-"])).delete(synchronize_session=False)
    s.query(PaperJournalEvent).filter(PaperJournalEvent.position_id.in_(pos_ids or ["-"])).delete(synchronize_session=False)
    s.query(PaperOrder).filter_by(portfolio_id=pid, symbol=SYMBOL).delete()
    s.query(PaperPosition).filter_by(portfolio_id=pid, symbol=SYMBOL).delete()
    pf = s.get(PaperPortfolio, pid)
    pf.cash, pf.realized_pnl = snap[1], snap[2]
    s.commit()
    s.close()


def _post(c):
    return c.post("/api/engine/paper/positions", params={"symbol": SYMBOL, "user_id": USER, "timeframe": "1h"})


def _state(pid):
    s = SessionLocal()
    try:
        pf = s.get(PaperPortfolio, pid)
        return {
            "cash": pf.cash,
            "positions": s.query(PaperPosition).filter_by(portfolio_id=pid, symbol=SYMBOL, status="OPEN").count(),
            "orders": s.query(PaperOrder).filter_by(portfolio_id=pid, symbol=SYMBOL).count(),
            "opened_events": s.query(PaperJournalEvent).join(PaperPosition, PaperPosition.id == PaperJournalEvent.position_id)
            .filter(PaperPosition.symbol == SYMBOL, PaperPosition.portfolio_id == pid, PaperJournalEvent.event_type == "OPENED").count(),
        }
    finally:
        s.close()


def test_accepted_confirmation_creates_exactly_one_position_and_debits_once(client):
    c, pid, _ = client
    before = _state(pid)
    r = _post(c)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True and body["status"] == "OPEN" and body["qty"] > 0
    after = _state(pid)
    assert after["positions"] == 1 and after["orders"] == 1 and after["opened_events"] == 1
    debit = before["cash"] - after["cash"]
    assert debit == pytest.approx(body["notional"] + body["entry_fee"], rel=1e-9)  # one debit: notional + fee
    s = SessionLocal()
    try:
        assert s.query(LedgerTransaction).filter_by(ref=body["id"]).count() == 1  # journal comptable: une écriture
    finally:
        s.close()


def test_repeated_or_double_confirmation_never_duplicates(client):
    c, pid, _ = client
    first = _post(c).json()
    cash_after_first = _state(pid)["cash"]
    second = _post(c)
    assert second.status_code == 200
    j = second.json()
    assert j["id"] == first["id"] and j.get("already_open") is True and j["created"] is False
    st = _state(pid)
    assert st["positions"] == 1 and st["orders"] == 1 and st["cash"] == cash_after_first  # no second debit


def test_simultaneous_double_click_creates_one_position(client):
    c, pid, _ = client
    out: list[int] = []

    def go():
        out.append(_post(TestClient(app)).status_code)

    threads = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(code == 200 for code in out), out
    st = _state(pid)
    assert st["positions"] == 1 and st["orders"] == 1 and st["opened_events"] == 1


def test_refusal_shows_reason_and_leaves_account_untouched(client, monkeypatch):
    c, pid, _ = client
    monkeypatch.setattr(routes, "scan_symbol", lambda *a, **k: _row(decision="NO_TRADE"))
    before = _state(pid)
    r = _post(c)
    assert r.status_code == 422 and "not_actionable" in r.json()["detail"]  # motif exploitable par l'UI
    assert _state(pid) == before  # no debit, no position, no order, no "executed" journal event


def test_refusal_for_insufficient_funds_leaves_account_untouched(client, monkeypatch):
    c, pid, s = client
    pf = s.get(PaperPortfolio, pid)
    real_cash = pf.cash
    pf.cash = 0.5
    s.commit()
    try:
        before = _state(pid)
        r = _post(c)
        assert r.status_code == 422
        assert _state(pid) == before
    finally:
        pf = s.get(PaperPortfolio, pid)
        pf.cash = real_cash
        s.commit()


def test_account_identity_after_refresh(client):
    """cash + invested + unrealized - open entry fees == equity - realized +/- ... i.e. the
    overview must explain total P&L: realized + unrealized - entry fees of open lots."""
    c, pid, _ = client
    _post(c)
    acc = c.get(f"/api/engine/paper/portfolios/{BASELINE_CODE}/overview").json()["account"]
    assert acc["equity"] == pytest.approx(acc["cash"] + acc["invested"] + acc["unrealized_pnl"], abs=0.02)
    if "pnl_explained" in acc:
        assert acc["total_pnl"] == pytest.approx(acc["pnl_explained"], abs=0.02)


def test_stale_signal_refused_with_reason_and_no_effect(client, monkeypatch):
    c, pid, _ = client

    def stale_row(*a, **k):
        r = _row()
        r.signal_timing = {"stale": True, "lag_bars": 1984}
        return r

    monkeypatch.setattr(routes, "scan_symbol", stale_row)
    before = _state(pid)
    r = _post(c)
    assert r.status_code == 422 and "stale_data" in r.json()["detail"]
    assert _state(pid) == before


def test_auto_sync_skips_stale_rows(client):
    from app.paper import engine as paper_engine

    c, pid, s = client
    row = _row()
    row.exchange, row.timeframe = "binance", "1h"
    row.signal_timing = {"stale": True}
    before = _state(pid)
    paper_engine.sync_auto_watchlist(s, [row])
    assert _state(pid) == before  # nothing opened for a stale row


def test_auto_loop_never_closes_a_manually_confirmed_lot_on_signal_downgrade(client):
    """Regression (2026-09-20 19:55Z): the cross-source lookup handed user_confirmed lots to the
    auto loop, which closed them with pipeline_downgraded."""
    from app.paper import engine as paper_engine

    c, pid, s = client
    opened = _post(c).json()
    assert opened["status"] == "OPEN" and opened["source"] == "user_confirmed"
    row = _row(decision="NO_TRADE")  # signal no longer BUY
    row.exchange, row.timeframe = "binance", "1h"
    paper_engine.sync_auto_watchlist(s, [row])
    s.expire_all()
    pos = s.get(PaperPosition, opened["id"])
    assert pos.status == "OPEN" and pos.exit_reason is None
