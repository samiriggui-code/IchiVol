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


def test_idempotent_open_via_signal_payload_format(s):
    """Production `_signal_payload` (no hand-crafted bar_time-only dict).

    Two opens on the same decision bar → 1 order, 1 ledger debit, cash once.
    """
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.db.models import LedgerTransaction
    from app.paper.engine import _signal_payload

    pf = _pf(s, "T13DSIG")
    cash0 = float(pf.cash)
    pipeline = SimpleNamespace(
        decision="BUY",
        direction=SimpleNamespace(value="LONG"),
        stages=[],
    )
    bar_time = 1_700_000_000
    signal = _signal_payload(pipeline, {"bar_time": bar_time, "rvol": 1.2})
    assert "bar_time" in signal
    assert signal["decision"] == "BUY"

    pos1 = open_capital_position(
        s,
        portfolio=pf,
        symbol="BTCUSDT",
        timeframe="1h",
        source="auto_watchlist",
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
    n_orders = len(
        list(s.execute(select(PaperOrder).where(PaperOrder.portfolio_id == pf.id)).scalars())
    )
    n_ledger = len(
        list(
            s.execute(
                select(LedgerTransaction).where(LedgerTransaction.portfolio_id == pf.id)
            ).scalars()
        )
    )

    signal2 = _signal_payload(pipeline, {"bar_time": bar_time, "rvol": 1.2})
    pos2 = open_capital_position(
        s,
        portfolio=pf,
        symbol="BTCUSDT",
        timeframe="1h",
        source="auto_watchlist",
        user_id=None,
        direction="LONG",
        price=100.0,
        decision="BUY",
        stop_distance=2.0,
        signal=signal2,
    )
    assert pos2 is not None
    assert pos2.id == pos1.id
    assert float(pf.cash) == cash1
    n_orders2 = len(
        list(s.execute(select(PaperOrder).where(PaperOrder.portfolio_id == pf.id)).scalars())
    )
    n_ledger2 = len(
        list(
            s.execute(
                select(LedgerTransaction).where(LedgerTransaction.portfolio_id == pf.id)
            ).scalars()
        )
    )
    assert n_orders2 == n_orders == 1
    assert n_ledger2 == n_ledger


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

    # With ledger → FILLED (+ filled_qty / avg_fill_price from order)
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
    order2.filled_price = 50.0
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
    assert float(order2.filled_qty or 0) == pytest.approx(1.0)
    assert float(order2.avg_fill_price or 0) == pytest.approx(50.0)


def test_close_fill_fail_then_retry_succeeds(s, monkeypatch):
    """Fill failure → REJECTED, position OPEN, cash unchanged; retry → CLOSED once."""
    from sqlalchemy import select

    from app.paper.reconcile import reconcile_portfolio

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
    cash_after_open = float(pf.cash)

    def _boom(*_a, **_k):
        raise ValueError("forced_fill_failure")

    monkeypatch.setattr("app.paper.broker.apply_exit_friction", _boom)
    out = close_capital_position(s, pos, price=110.0, reason="manual")
    s.flush()
    assert out.status == "OPEN"
    assert out.close_requested_at is None
    assert float(pf.cash) == cash_after_open

    close_orders = list(
        s.execute(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == pf.id,
                PaperOrder.position_id == pos.id,
                PaperOrder.side == "SELL",
            )
        ).scalars()
    )
    assert len(close_orders) == 1
    assert close_orders[0].status == paper_orders.REJECTED
    assert close_orders[0].client_order_id == paper_orders.client_order_id_close(pos.id, 1)

    from app.paper.risk import apply_exit_friction as real_exit

    monkeypatch.setattr("app.paper.broker.apply_exit_friction", real_exit)
    closed = close_capital_position(s, pos, price=110.0, reason="manual")
    s.flush()
    assert closed.status == "CLOSED"
    assert float(pf.cash) > cash_after_open

    close_orders2 = list(
        s.execute(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == pf.id,
                PaperOrder.position_id == pos.id,
                PaperOrder.side == "SELL",
            )
        ).scalars()
    )
    statuses = sorted(o.status for o in close_orders2)
    assert statuses == [paper_orders.FILLED, paper_orders.REJECTED]
    assert {o.client_order_id for o in close_orders2} == {
        paper_orders.client_order_id_close(pos.id, 1),
        paper_orders.client_order_id_close(pos.id, 2),
    }
    # Cash credited once: second close attempt must not double-credit
    cash_after_close = float(pf.cash)
    close_capital_position(s, pos, price=110.0, reason="manual")
    s.flush()
    assert float(pf.cash) == cash_after_close

    report = reconcile_portfolio(s, pf)
    life = {
        c["name"]: c
        for c in report["checks"]
        if c["name"]
        in {
            "open_has_entry_filled_order",
            "filled_qty_matches_open_position",
            "filled_order_has_ledger",
            "closed_has_close_filled_order",
            "no_stale_non_terminal_orders",
        }
    }
    assert all(c["ok"] for c in life.values()), life


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


def test_migration_backfill_legacy_order(s):
    """downgrade -1 → insert legacy order → upgrade → legacy-{id} + FILLED event @ created_at."""
    import uuid
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    s.rollback()
    s.close()

    engine_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(engine_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(engine_root / "alembic"))

    oid = str(uuid.uuid4())
    created = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)

    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "-1")

        from app.db.session import SessionLocal

        sess = SessionLocal()
        try:
            cols = {
                r[0]
                for r in sess.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='paper_orders'"
                    )
                ).fetchall()
            }
            assert "client_order_id" not in cols
            assert sess.execute(text("SELECT to_regclass('paper_order_events')")).scalar() is None

            pf_id = sess.execute(text("SELECT id FROM paper_portfolios LIMIT 1")).scalar()
            if pf_id is None:
                pytest.skip("no paper_portfolios row for legacy insert")
            sess.execute(
                text(
                    "INSERT INTO paper_orders "
                    "(id, portfolio_id, position_id, symbol, timeframe, side, order_type, "
                    "requested_price, filled_price, qty, notional, fee, spread_bps, slippage_bps, "
                    "status, reason, created_at) "
                    "VALUES (:id, :pid, NULL, 'LEGACYUSDT', '1h', 'BUY', 'MARKET', "
                    "100, 100, 1.5, 150, 0.1, 0, 0, 'FILLED', 'open', :at)"
                ),
                {"id": oid, "pid": pf_id, "at": created},
            )
            sess.commit()
        finally:
            sess.close()

        command.upgrade(cfg, "head")

        sess2 = SessionLocal()
        try:
            row = sess2.execute(
                text(
                    "SELECT client_order_id, filled_qty, avg_fill_price, status "
                    "FROM paper_orders WHERE id = :id"
                ),
                {"id": oid},
            ).fetchone()
            assert row is not None
            assert row[0] == f"legacy-{oid}"
            assert float(row[1]) == pytest.approx(1.5)
            assert float(row[2]) == pytest.approx(100.0)
            assert row[3] == "FILLED"
            ev = sess2.execute(
                text(
                    "SELECT from_status, to_status, at, reason FROM paper_order_events "
                    "WHERE order_id = :id ORDER BY seq"
                ),
                {"id": oid},
            ).fetchall()
            assert len(ev) == 1
            assert ev[0][0] is None
            assert ev[0][1] == "FILLED"
            assert ev[0][3] == "legacy_backfill"
            at = ev[0][2]
            if getattr(at, "tzinfo", None) is None:
                at = at.replace(tzinfo=timezone.utc)
            assert at == created
        finally:
            sess2.close()
    finally:
        command.upgrade(cfg, "head")
        from app.db.session import SessionLocal as SL

        cleanup = SL()
        try:
            cleanup.execute(text("DELETE FROM paper_order_events WHERE order_id = :id"), {"id": oid})
            cleanup.execute(text("DELETE FROM paper_orders WHERE id = :id"), {"id": oid})
            cleanup.commit()
        finally:
            cleanup.close()
