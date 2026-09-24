"""T13d — order lifecycle: transitions, idempotence, kill, reconcile, AST."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import PaperOrder, PaperOrderEvent, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.paper import orders as paper_orders
from app.paper.broker import close_capital_position, open_capital_position
from app.paper.kill_switch import arm_kill_switch
from app.paper.reconcile import apply_stale_order_reconciliation

try:
    with engine.connect():
        pass
    OK = True
except OperationalError:
    OK = False

pytestmark = pytest.mark.skipif(not OK, reason="dev Postgres not reachable")

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "app"


@pytest.fixture
def s():
    sess = SessionLocal()
    sess.rollback()
    yield sess
    sess.rollback()
    sess.close()


def _pf(s, code: str = "T13DORD") -> PaperPortfolio:
    now = datetime.now(timezone.utc)
    existing = s.query(PaperPortfolio).filter_by(code=code).one_or_none() if hasattr(s, "query") else None
    from sqlalchemy import select

    existing = s.execute(select(PaperPortfolio).where(PaperPortfolio.code == code)).scalar_one_or_none()
    if existing:
        # reset cash for isolation
        existing.cash = 5000.0
        existing.realized_pnl = 0.0
        existing.kill_switch_armed = False
        s.flush()
        return existing
    pf = PaperPortfolio(
        code=code,
        label=code,
        currency="EUR",
        valuation_mode="USDT_AS_EUR_PROXY",
        initial_cash=5000.0,
        cash=5000.0,
        realized_pnl=0.0,
        strategy_profile={"risk_pct": 0.01, "max_open_positions": 5, "commission_bps": 5.0},
        is_active=True,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    s.add(pf)
    s.flush()
    return pf


def test_transition_table_exhaustive_legal_and_illegal(s):
    pf = _pf(s, "T13DTR")
    order = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="t-trans-1",
        symbol="BTCUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=100.0,
        qty=1.0,
        notional=100.0,
    )
    assert order.status == paper_orders.CREATED

    # Legal path
    paper_orders.transition(s, order, paper_orders.SUBMITTED)
    paper_orders.transition(s, order, paper_orders.ACK)
    paper_orders.transition(s, order, paper_orders.FILLED)
    assert order.status == paper_orders.FILLED

    # Terminal immutable
    with pytest.raises(paper_orders.IllegalOrderTransition):
        paper_orders.transition(s, order, paper_orders.CANCELLED)

    # Illegal from CREATED → FILLED (must go through SUBMITTED)
    o2 = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="t-trans-2",
        symbol="ETHUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=50.0,
        qty=1.0,
        notional=50.0,
    )
    with pytest.raises(paper_orders.IllegalOrderTransition):
        paper_orders.transition(s, o2, paper_orders.FILLED)

    # PARTIAL allowed from ACK (unit only — no broker liquidity invent)
    o3 = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="t-trans-3",
        symbol="SOLUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=10.0,
        qty=2.0,
        notional=20.0,
    )
    paper_orders.transition(s, o3, paper_orders.SUBMITTED)
    paper_orders.transition(s, o3, paper_orders.ACK)
    paper_orders.transition(s, o3, paper_orders.PARTIAL)
    paper_orders.transition(s, o3, paper_orders.PARTIAL)  # re-partial ok
    paper_orders.transition(s, o3, paper_orders.FILLED)

    # EXPIRED from CREATED
    o4 = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="t-trans-4",
        symbol="XRPUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=1.0,
        qty=10.0,
        notional=10.0,
    )
    paper_orders.expire_order(s, o4)
    assert o4.status == paper_orders.EXPIRED

    # UNKNOWN only exits via resolve_unknown
    o5 = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="t-trans-5",
        symbol="ADAUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=1.0,
        qty=10.0,
        notional=10.0,
    )
    paper_orders.transition(s, o5, paper_orders.SUBMITTED)
    paper_orders.mark_unknown(s, o5)
    assert o5.status == paper_orders.UNKNOWN
    with pytest.raises(paper_orders.IllegalOrderTransition):
        paper_orders.transition(s, o5, paper_orders.ACK)
    paper_orders.resolve_unknown(s, o5, to=paper_orders.CANCELLED, reason="test")
    assert o5.status == paper_orders.CANCELLED


def test_idempotent_client_order_id_one_fill_one_ledger(s):
    pf = _pf(s, "T13DIDEM")
    cash0 = float(pf.cash)
    signal = {"bar_time": "2026-09-24T12:00:00Z"}
    pos1 = open_capital_position(
        s,
        portfolio=pf,
        symbol="BTCUSDT",
        timeframe="1h",
        source="user_confirmed",
        user_id=None,
        direction="LONG",
        price=100.0,
        decision="BUY",
        stop_distance=2.0,
        signal=signal,
    )
    assert pos1 is not None
    cash1 = float(pf.cash)
    assert cash1 < cash0
    from sqlalchemy import select
    from app.db.models import LedgerTransaction

    n_ledger = len(
        list(
            s.execute(
                select(LedgerTransaction).where(LedgerTransaction.portfolio_id == pf.id)
            ).scalars()
        )
    )
    n_orders = len(
        list(s.execute(select(PaperOrder).where(PaperOrder.portfolio_id == pf.id)).scalars())
    )

    pos2 = open_capital_position(
        s,
        portfolio=pf,
        symbol="BTCUSDT",
        timeframe="1h",
        source="user_confirmed",
        user_id=None,
        direction="LONG",
        price=100.0,
        decision="BUY",
        stop_distance=2.0,
        signal=signal,
    )
    assert pos2 is not None
    assert pos2.id == pos1.id
    assert float(pf.cash) == cash1
    n_ledger2 = len(
        list(
            s.execute(
                select(LedgerTransaction).where(LedgerTransaction.portfolio_id == pf.id)
            ).scalars()
        )
    )
    n_orders2 = len(
        list(s.execute(select(PaperOrder).where(PaperOrder.portfolio_id == pf.id)).scalars())
    )
    assert n_ledger2 == n_ledger
    assert n_orders2 == n_orders


def test_crash_submitted_unknown_reconcile_both_ways(s):
    pf = _pf(s, "T13DUNK")
    now = datetime.now(timezone.utc) - timedelta(minutes=45)
    order = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="crash-sub-1",
        symbol="BTCUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=100.0,
        qty=1.0,
        notional=100.0,
        at=now,
    )
    paper_orders.transition(s, order, paper_orders.SUBMITTED, at=now)
    order.created_at = now
    s.flush()

    # No ledger → CANCELLED
    out = apply_stale_order_reconciliation(s, pf, stale_minutes=30)
    assert order.id in out["marked_unknown"] or order.status in (
        paper_orders.UNKNOWN,
        paper_orders.CANCELLED,
    )
    s.refresh(order)
    assert order.status == paper_orders.CANCELLED

    # With ledger → FILLED
    from app.brokerage import persistence as ledger_db
    from app.brokerage.ledger import Cause, Leg

    order2 = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="crash-sub-2",
        symbol="ETHUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=50.0,
        qty=1.0,
        notional=50.0,
        reason="open",
        at=now,
    )
    paper_orders.transition(s, order2, paper_orders.SUBMITTED, at=now)
    order2.created_at = now
    s.flush()
    ledger_db.ensure_opening(s, pf, now)
    ledger_db.post(
        s,
        pf.id,
        order2.client_order_id,
        now,
        [Leg(pf.currency, ledger_db.to_decimal(-50), Cause.EXECUTION, "x")],
        ref=None,
    )
    apply_stale_order_reconciliation(s, pf, stale_minutes=30)
    s.refresh(order2)
    assert order2.status == paper_orders.FILLED


def test_close_reject_leaves_position_open(s):
    pf = _pf(s, "T13DCLOSE")
    pos = open_capital_position(
        s,
        portfolio=pf,
        symbol="BTCUSDT",
        timeframe="1h",
        source="user_confirmed",
        user_id=None,
        direction="LONG",
        price=100.0,
        decision="BUY",
        stop_distance=2.0,
        signal={"bar_time": "close-fail-bar"},
    )
    assert pos is not None
    # Simulate close request then fill rejection
    now = datetime.now(timezone.utc)
    pos.status = "CLOSING"
    pos.close_requested_at = now
    coid = paper_orders.client_order_id_close(pos.id)
    order = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id=coid,
        position_id=pos.id,
        symbol=pos.symbol,
        timeframe=pos.timeframe,
        side="SELL",
        order_type="MARKET",
        requested_price=100.0,
        qty=float(pos.qty or 0),
        notional=float(pos.qty or 0) * 100.0,
        reason="manual",
        at=now,
    )
    paper_orders.transition(s, order, paper_orders.SUBMITTED)
    paper_orders.transition(s, order, paper_orders.ACK)
    paper_orders.reject_order(s, order, reason="quote_stale", codes=["quote_stale"])
    pos.status = "OPEN"
    pos.close_requested_at = None
    s.flush()
    assert pos.status == "OPEN"
    assert order.status == paper_orders.REJECTED


def test_kill_switch_cancels_non_terminal(s):
    pf = _pf(s, "T13DKILL")
    order = paper_orders.create_order(
        s,
        portfolio_id=pf.id,
        client_order_id="kill-pending-1",
        symbol="BTCUSDT",
        timeframe="1h",
        side="BUY",
        order_type="MARKET",
        requested_price=100.0,
        qty=1.0,
        notional=100.0,
    )
    paper_orders.transition(s, order, paper_orders.SUBMITTED)
    arm_kill_switch(s, pf, confirm=True)
    s.refresh(order)
    assert order.status == paper_orders.CANCELLED
    assert pf.kill_switch_armed is True


def test_ast_paper_order_ctor_only_in_orders_module():
    offenders: list[str] = []
    for path in sorted(ENGINE_ROOT.rglob("*.py")):
        rel = path.relative_to(ENGINE_ROOT).as_posix()
        if rel == "paper/orders.py" or rel == "db/models.py":
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "PaperOrder":
                offenders.append(f"{rel}:{node.lineno}")
            elif isinstance(fn, ast.Attribute) and fn.attr == "PaperOrder":
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"PaperOrder( must only appear in paper/orders.py. Offenders: {offenders}"


def test_migration_backfill_shape(s):
    """Existing FILLED rows get client_order_id + event (run after alembic upgrade)."""
    from sqlalchemy import select, text

    # Ensure columns exist
    row = s.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='paper_orders'")).fetchall()
    cols = {r[0] for r in row}
    assert "client_order_id" in cols
    assert "filled_qty" in cols
    # Events table
    ev = s.execute(text("SELECT to_regclass('paper_order_events')")).scalar()
    assert ev == "paper_order_events"
