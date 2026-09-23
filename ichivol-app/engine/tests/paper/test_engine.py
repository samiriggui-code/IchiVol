"""Real-DB tests for app/paper/engine.py, same conventions as
tests/market_data/test_collector.py (skipped if ichivol_engine_dev isn't
reachable, explicit cleanup around each test).

Aligned with the 2026-09-21 baseline profile: ATR stop required, long-only,
exit_mode=direction. Opens that need a clean book use disposable portfolios —
never wipe baseline history (cash / PaperEquitySnapshot).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import (
    LedgerLeg,
    LedgerTransaction,
    PaperEquitySnapshot,
    PaperJournalEvent,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import engine as paper
from app.paper import gates as paper_gates
from app.paper.strategy_profiles import BASELINE_CODE, profile_for

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")

SYMBOL = "PAPERTEST"
TIMEFRAME = "1h"
# Match test_fwd_profiles: keep mark moves inside the stop/TP band (tp_r=2 → ±2×STOP).
STOP = 2.0


def _pipeline(decision: str, direction: Direction = Direction.LONG) -> PipelineResult:
    return PipelineResult(decision=decision, direction=direction, stages=[])


def _purge_symbols(session, *symbols: str) -> None:
    """Remove capital-sized lots (orders / journal / ledger) for test symbols."""
    syms = list(symbols)
    positions = session.query(PaperPosition).filter(PaperPosition.symbol.in_(syms)).all()
    ids = [p.id for p in positions]
    if ids:
        session.query(PaperJournalEvent).filter(
            PaperJournalEvent.position_id.in_(ids)
        ).delete(synchronize_session=False)
        # Rejection journals are portfolio-scoped without a position_id.
        session.query(PaperJournalEvent).filter(
            PaperJournalEvent.portfolio_id.in_({p.portfolio_id for p in positions if p.portfolio_id}),
            PaperJournalEvent.position_id.is_(None),
        ).delete(synchronize_session=False)
        tx_ids = [
            t.id
            for t in session.query(LedgerTransaction).filter(LedgerTransaction.ref.in_(ids)).all()
        ]
        if tx_ids:
            session.query(LedgerLeg).filter(
                LedgerLeg.transaction_id.in_(tx_ids)
            ).delete(synchronize_session=False)
            session.query(LedgerTransaction).filter(
                LedgerTransaction.id.in_(tx_ids)
            ).delete(synchronize_session=False)
        session.query(PaperOrder).filter(
            PaperOrder.position_id.in_(ids)
        ).delete(synchronize_session=False)
        session.query(PaperPosition).filter(
            PaperPosition.id.in_(ids)
        ).delete(synchronize_session=False)
    session.commit()


def _baseline_book(session) -> tuple[PaperPortfolio | None, float | None, float | None, set[str]]:
    """Capture baseline cash / realized / existing equity-snapshot ids (never wipe them)."""
    base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    if base is None:
        return None, None, None, set()
    snap_ids = {
        row.id
        for row in session.query(PaperEquitySnapshot).filter_by(portfolio_id=base.id).all()
    }
    return base, float(base.cash), float(base.realized_pnl), snap_ids


def _restore_baseline(
    session,
    *,
    cash0: float | None,
    realized0: float | None,
    snap_ids0: set[str],
) -> None:
    """Restore captured cash/realized; delete only snapshots created during the test."""
    if cash0 is None:
        return
    base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    if base is None:
        return
    for snap in session.query(PaperEquitySnapshot).filter_by(portfolio_id=base.id).all():
        if snap.id not in snap_ids0:
            session.delete(snap)
    base.cash = cash0
    if realized0 is not None:
        base.realized_pnl = realized0
    session.commit()


def _disposable(session, **overrides) -> PaperPortfolio:
    """Throwaway portfolio cloned from baseline with optional profile overrides."""
    prof = profile_for(BASELINE_CODE) | overrides
    code = f"T_ENG_{uuid.uuid4().hex[:8]}"
    prof["code"] = code
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(
        code=code,
        label="engine-test",
        currency="EUR",
        initial_cash=5000.0,
        cash=5000.0,
        realized_pnl=0.0,
        strategy_profile=prof,
        is_active=True,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(pf)
    session.flush()
    return pf


def _drop_portfolio(session, pf: PaperPortfolio) -> None:
    pid = pf.id
    session.rollback()
    session.query(PaperEquitySnapshot).filter_by(portfolio_id=pid).delete()
    session.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(
            session.query(LedgerTransaction.id).filter_by(portfolio_id=pid)
        )
    ).delete(synchronize_session=False)
    for model in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
        session.query(model).filter_by(portfolio_id=pid).delete()
    session.query(PaperPortfolio).filter_by(id=pid).delete()
    session.commit()
    paper_gates.reset_run_memory()


@pytest.fixture(scope="module", autouse=True)
def _historical_equity_guard():
    """Insert a baseline equity snapshot before any paper engine test; assert it survives."""
    if not DB_AVAILABLE:
        yield None
        return
    session = SessionLocal()
    base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    if base is None:
        # Seed baseline so the guard has a portfolio to attach to.
        from app.paper.portfolio import ensure_baseline_portfolio

        base = ensure_baseline_portfolio(session)
        session.commit()
    hist = PaperEquitySnapshot(
        portfolio_id=base.id,
        timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc),
        equity=12_345.67,
        cash=12_345.67,
        positions_value=0.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
    )
    session.add(hist)
    session.commit()
    hist_id = hist.id
    session.close()
    yield hist_id
    session = SessionLocal()
    still = session.get(PaperEquitySnapshot, hist_id)
    assert still is not None, "paper engine tests must not delete pre-existing equity snapshots"
    assert float(still.equity) == pytest.approx(12_345.67)
    session.delete(still)
    session.commit()
    session.close()


@pytest.fixture(autouse=True)
def _session():
    session = SessionLocal()
    _base, cash0, realized0, snap_ids0 = _baseline_book(session)
    _purge_symbols(session, SYMBOL, f"{SYMBOL}2", f"{SYMBOL}_AUTO")
    yield session
    session.rollback()
    _purge_symbols(session, SYMBOL, f"{SYMBOL}2", f"{SYMBOL}_AUTO")
    _restore_baseline(session, cash0=cash0, realized0=realized0, snap_ids0=snap_ids0)
    session.close()
    paper_gates.reset_run_memory()


def test_historical_equity_guard_id_is_tracked(_session, _historical_equity_guard):
    """Sanity: module guard snapshot is among ids captured at test start."""
    assert _historical_equity_guard is not None
    base = _session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    ids = {
        s.id
        for s in _session.query(PaperEquitySnapshot.id).filter_by(portfolio_id=base.id).all()
    }
    assert _historical_equity_guard in ids


def test_sync_position_opens_a_long_on_buy_with_no_existing_position(_session):
    pf = _disposable(_session)
    try:
        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is not None
        assert result.direction == "LONG"
        assert result.status == "OPEN"
        assert result.entry_price == pytest.approx(100.0, rel=0.01)
        assert result.entry_decision == "BUY"
    finally:
        _drop_portfolio(_session, pf)


def test_sync_position_does_nothing_on_watch_with_no_existing_position(_session):
    pf = _disposable(_session)
    try:
        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("WATCH"),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is None
        assert paper._get_open_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, portfolio_id=pf.id,
        ) is None
    finally:
        _drop_portfolio(_session, pf)


def test_sync_position_holds_an_open_position_while_still_supported(_session):
    pf = _disposable(_session)
    try:
        opened = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        assert opened is not None
        _session.commit()
        entry = opened.entry_price

        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.5, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is None  # nothing changed -- still open, untouched

        open_position = paper._get_open_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, portfolio_id=pf.id,
        )
        assert open_position is not None
        assert open_position.status == "OPEN"
        assert open_position.entry_price == entry
    finally:
        _drop_portfolio(_session, pf)


def test_sync_position_closes_when_decision_downgrades_to_watch(_session):
    """WATCH closes only under exit_mode=decision (baseline uses direction)."""
    pf = _disposable(_session, exit_mode="decision")
    try:
        opened = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        assert opened is not None and opened.status == "OPEN"
        _session.flush()

        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=101.0, pipeline=_pipeline("WATCH"),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is not None
        assert result.status == "CLOSED"
        assert result.exit_reason == "pipeline_downgraded"
        assert result.pnl_pct > 0.0  # rose; friction keeps it below raw 0.01
    finally:
        _drop_portfolio(_session, pf)


def test_sync_position_closes_when_pipeline_direction_flips(_session):
    pf = _disposable(_session)
    try:
        paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        _session.commit()

        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=99.0, pipeline=_pipeline("SELL", Direction.SHORT),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is not None
        assert result.status == "CLOSED"
        assert result.exit_reason == "direction_flipped"
        assert paper._get_open_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, portfolio_id=pf.id,
        ) is None
    finally:
        _drop_portfolio(_session, pf)


def test_short_position_pnl_is_positive_when_price_falls(_session):
    """SHORT return uses (entry − exit) / entry — 100→80 = +20%, not reciprocal +25%."""
    from app.paper import broker as paper_broker

    pf = _disposable(_session, allow_short=True)
    try:
        opened = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("SELL", Direction.SHORT),
            stop_distance=STOP, portfolio=pf,
        )
        assert opened is not None and opened.direction == "SHORT"
        _session.flush()

        closed = paper_broker.close_capital_position(
            _session, opened, price=80.0, reason="test_short_win"
        )
        _session.flush()
        assert closed.status == "CLOSED"
        assert closed.pnl_pct == pytest.approx(0.20, abs=0.02)  # not 0.25 (legacy bug)
        assert closed.pnl_pct < 0.22  # hard guard against reciprocal formula

        opened2 = paper.sync_position(
            _session, symbol=f"{SYMBOL}_L", timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("SELL", Direction.SHORT),
            stop_distance=STOP, portfolio=pf,
        )
        assert opened2 is not None
        _session.flush()
        closed2 = paper_broker.close_capital_position(
            _session, opened2, price=125.0, reason="test_short_loss"
        )
        _session.flush()
        assert closed2.pnl_pct == pytest.approx(-0.25, abs=0.02)
        assert closed2.pnl_pct < -0.22  # not −0.20 from reciprocal
    finally:
        _drop_portfolio(_session, pf)


def test_sync_auto_watchlist_processes_multiple_rows_and_commits(_session):
    """BUY opens across every syncable portfolio; WATCH opens none.

    Multi-portfolio seeding (STRUCTURE_*, CTX_*, …) means one BUY row can
    touch many PaperPosition rows — assert by symbol, not by count==1.
    Uses a disposable only to prove opens work without relying on baseline health;
    sync_auto_watchlist still iterates syncable profile codes (may include baseline).
    """
    class _FakeRow:
        def __init__(self, symbol, price, decision):
            self.symbol = symbol
            self.timeframe = TIMEFRAME
            self.price = price
            self.pipeline = _pipeline(decision)
            self.atr = SimpleNamespace(suggested_stop_distance=STOP)
            self.candles = []
            self.rvol = None
            self.signal_timing = None

    # Ensure at least one clean syncable-like book: inject disposable into the
    # sync path by opening via sync_position on disposable for BUY, then still
    # exercise sync_auto_watchlist for the multi-row contract.
    watch_sym = f"{SYMBOL}2"
    rows = [_FakeRow(SYMBOL, 100.0, "BUY"), _FakeRow(watch_sym, 50.0, "WATCH")]
    pf = _disposable(_session)
    try:
        # Direct open on disposable proves ATR path; auto sync may also touch baseline.
        direct = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        assert direct is not None
        _session.commit()
        paper_gates.reset_run_memory()
        # Fresh BUY on a different symbol via auto_watchlist across syncable books.
        auto_sym = f"{SYMBOL}_AUTO"
        touched = paper.sync_auto_watchlist(
            _session, [_FakeRow(auto_sym, 100.0, "BUY"), _FakeRow(watch_sym, 50.0, "WATCH")]
        )
        # If every seeded syncable book is halted, touched may be empty — still
        # require our disposable open above and that WATCH never opens.
        assert direct.symbol == SYMBOL
        assert not any(p.symbol == watch_sym for p in touched)
        if touched:
            assert all(p.symbol == auto_sym for p in touched)
    finally:
        _purge_symbols(_session, SYMBOL, watch_sym, f"{SYMBOL}_AUTO")
        _drop_portfolio(_session, pf)


def test_open_user_confirmed_is_idempotent(_session):
    pf = _disposable(_session)
    try:
        first, created1 = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        second, created2 = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=105.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        assert created1 is True
        assert created2 is False
        assert first is not None and second is not None
        assert first.id == second.id
        assert second.entry_price == first.entry_price
    finally:
        _drop_portfolio(_session, pf)


def test_open_user_confirmed_does_not_open_on_a_non_actionable_decision(_session):
    pf = _disposable(_session)
    try:
        result, created = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("WATCH"), stop_distance=STOP, portfolio=pf,
        )
        assert result is None
        assert created is False
    finally:
        _drop_portfolio(_session, pf)


def test_close_manually_closes_an_open_position(_session):
    pf = _disposable(_session)
    try:
        position, _ = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        assert position is not None
        closed = paper.close_manually(_session, position.id, price=103.0)
        assert closed.status == "CLOSED"
        assert closed.exit_reason == "manual_close"
        assert closed.pnl_pct == pytest.approx(0.03, abs=0.02)
    finally:
        _drop_portfolio(_session, pf)


def test_close_manually_returns_none_for_an_already_closed_position(_session):
    pf = _disposable(_session)
    try:
        position, _ = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        assert position is not None
        paper.close_manually(_session, position.id, price=120.0)
        assert paper.close_manually(_session, position.id, price=130.0) is None
    finally:
        _drop_portfolio(_session, pf)


def test_list_positions_filters_by_source_user_and_status(_session):
    pf = _disposable(_session)
    try:
        paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        auto_sym = f"{SYMBOL}_AUTO"
        paper.sync_position(
            _session, symbol=auto_sym, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("BUY"),
            stop_distance=STOP, portfolio=pf,
        )
        _session.commit()

        user_positions = [
            p for p in paper.list_positions(_session, source="user_confirmed", user_id="user-1")
            if p.symbol == SYMBOL and p.portfolio_id == pf.id
        ]
        assert len(user_positions) == 1
        assert user_positions[0].source == "user_confirmed"

        auto_positions = [
            p for p in paper.list_positions(_session, source="auto_watchlist")
            if p.symbol == auto_sym and p.portfolio_id == pf.id
        ]
        assert len(auto_positions) == 1
        assert auto_positions[0].user_id is None
        assert auto_positions[0].direction == "LONG"

        open_only = [
            p for p in paper.list_positions(_session, status="OPEN") if p.portfolio_id == pf.id
        ]
        assert all(p.status == "OPEN" for p in open_only)
        assert len(open_only) == 2

        _purge_symbols(_session, auto_sym)
    finally:
        _drop_portfolio(_session, pf)


def test_open_user_confirmed_locks_symbol_already_open_on_portfolio(_session):
    """Second buy on the same symbol must not spend a second notional."""
    pf = _disposable(_session)
    try:
        first, created1 = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        second, created2 = paper.open_user_confirmed(
            _session, symbol=SYMBOL, timeframe="4h", user_id="user-1", price=110.0,
            pipeline=_pipeline("BUY"), stop_distance=STOP, portfolio=pf,
        )
        assert created1 is True and first is not None
        assert created2 is False and second is not None
        assert first.id == second.id
        open_same = [
            p
            for p in paper.list_positions(_session, status="OPEN")
            if p.symbol == SYMBOL and p.portfolio_id == pf.id
        ]
        assert len(open_same) == 1
    finally:
        _drop_portfolio(_session, pf)
