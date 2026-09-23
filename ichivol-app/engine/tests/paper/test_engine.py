"""Real-DB tests for app/paper/engine.py, same conventions as
tests/market_data/test_collector.py (skipped if ichivol_engine_dev isn't
reachable, explicit cleanup around each test).

Aligned with the 2026-09-21 baseline profile: ATR stop required, long-only,
exit_mode=direction. Short / decision-exit scenarios use disposable portfolios.
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


@pytest.fixture(autouse=True)
def _session():
    session = SessionLocal()
    base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    cash0 = base.cash if base is not None else None
    realized0 = base.realized_pnl if base is not None else None
    _purge_symbols(session, SYMBOL, f"{SYMBOL}2", f"{SYMBOL}_AUTO")
    yield session
    session.rollback()
    _purge_symbols(session, SYMBOL, f"{SYMBOL}2", f"{SYMBOL}_AUTO")
    if base is not None and cash0 is not None:
        base = session.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
        if base is not None:
            base.cash = cash0
            if realized0 is not None:
                base.realized_pnl = realized0
            session.commit()
    session.close()
    paper_gates.reset_run_memory()


def test_sync_position_opens_a_long_on_buy_with_no_existing_position(_session):
    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert result is not None
    assert result.direction == "LONG"
    assert result.status == "OPEN"
    assert result.entry_price == pytest.approx(100.0, rel=0.01)  # fill includes entry friction
    assert result.entry_decision == "BUY"


def test_sync_position_does_nothing_on_watch_with_no_existing_position(_session):
    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("WATCH"), stop_distance=STOP,
    )
    assert result is None
    assert paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    ) is None


def test_sync_position_holds_an_open_position_while_still_supported(_session):
    opened = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert opened is not None
    _session.commit()
    entry = opened.entry_price

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=105.0, pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert result is None  # nothing changed -- still open, untouched

    open_position = paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    )
    assert open_position is not None
    assert open_position.status == "OPEN"
    assert open_position.entry_price == entry


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
            user_id=None, price=110.0, pipeline=_pipeline("WATCH"),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is not None
        assert result.status == "CLOSED"
        assert result.exit_reason == "pipeline_downgraded"
        assert result.pnl_pct > 0.05  # rose; friction keeps it below raw 0.10
    finally:
        _drop_portfolio(_session, pf)


def test_sync_position_closes_when_pipeline_direction_flips(_session):
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    _session.commit()

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=90.0, pipeline=_pipeline("SELL", Direction.SHORT),
        stop_distance=STOP,
    )
    assert result is not None
    assert result.status == "CLOSED"
    assert result.exit_reason == "direction_flipped"
    # Never auto-reversed into the new side -- a fresh sync would open a
    # new SHORT position on its own next call, this one only ever closes.
    assert paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    ) is None


def test_short_position_pnl_is_positive_when_price_falls(_session):
    """Baseline is long-only; short PnL needs a disposable allow_short portfolio."""
    pf = _disposable(_session, allow_short=True)
    try:
        opened = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=100.0, pipeline=_pipeline("SELL", Direction.SHORT),
            stop_distance=STOP, portfolio=pf,
        )
        assert opened is not None and opened.direction == "SHORT"
        _session.flush()

        # exit_mode=direction: WATCH with LONG direction flips the short closed
        result = paper.sync_position(
            _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
            user_id=None, price=80.0, pipeline=_pipeline("WATCH", Direction.LONG),
            stop_distance=STOP, portfolio=pf,
        )
        assert result is not None and result.status == "CLOSED"
        assert result.exit_reason == "direction_flipped"
        assert result.pnl_pct == pytest.approx(0.25, abs=0.05)  # (100/80)-1 minus friction
    finally:
        _drop_portfolio(_session, pf)


def test_sync_auto_watchlist_processes_multiple_rows_and_commits(_session):
    """BUY opens across every syncable portfolio; WATCH opens none.

    Multi-portfolio seeding (STRUCTURE_*, CTX_*, …) means one BUY row can
    touch many PaperPosition rows — assert by symbol, not by count==1.
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

    watch_sym = f"{SYMBOL}2"
    rows = [_FakeRow(SYMBOL, 100.0, "BUY"), _FakeRow(watch_sym, 50.0, "WATCH")]
    try:
        touched = paper.sync_auto_watchlist(_session, rows)
        assert touched, "BUY should open at least on baseline"
        assert all(p.symbol == SYMBOL for p in touched)
        assert not any(p.symbol == watch_sym for p in touched)
    finally:
        _purge_symbols(_session, SYMBOL, watch_sym)


def test_open_user_confirmed_is_idempotent(_session):
    first, created1 = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    second, created2 = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=105.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert created1 is True
    assert created2 is False
    assert first is not None and second is not None
    assert first.id == second.id
    assert second.entry_price == first.entry_price  # not overwritten by the second call


def test_open_user_confirmed_does_not_open_on_a_non_actionable_decision(_session):
    result, created = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("WATCH"), stop_distance=STOP,
    )
    assert result is None
    assert created is False


def test_close_manually_closes_an_open_position(_session):
    position, _ = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert position is not None
    closed = paper.close_manually(_session, position.id, price=120.0)
    assert closed.status == "CLOSED"
    assert closed.exit_reason == "manual_close"
    assert closed.pnl_pct == pytest.approx(0.20, abs=0.05)  # friction on entry/exit fills


def test_close_manually_returns_none_for_an_already_closed_position(_session):
    position, _ = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert position is not None
    paper.close_manually(_session, position.id, price=120.0)
    assert paper.close_manually(_session, position.id, price=130.0) is None


def test_list_positions_filters_by_source_user_and_status(_session):
    paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    auto_sym = f"{SYMBOL}_AUTO"
    paper.sync_position(
        _session, symbol=auto_sym, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    _session.commit()

    # Filter results down to this test's own symbols before counting -- a
    # real background screener cache may be running concurrently (its
    # auto_watchlist sync rides the same table, see app/screener/cache.py)
    # and would otherwise pollute an unscoped count.
    user_positions = [
        p for p in paper.list_positions(_session, source="user_confirmed", user_id="user-1")
        if p.symbol == SYMBOL
    ]
    assert len(user_positions) == 1
    assert user_positions[0].source == "user_confirmed"

    auto_positions = [
        p for p in paper.list_positions(_session, source="auto_watchlist") if p.symbol == auto_sym
    ]
    assert len(auto_positions) == 1
    assert auto_positions[0].user_id is None
    assert auto_positions[0].direction == "LONG"

    open_only = paper.list_positions(_session, status="OPEN")
    assert all(p.status == "OPEN" for p in open_only)

    _purge_symbols(_session, auto_sym)


def test_open_user_confirmed_locks_symbol_already_open_on_portfolio(_session):
    """Second buy on the same symbol must not spend a second notional."""
    first, created1 = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    second, created2 = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe="4h", user_id="user-1", price=110.0,
        pipeline=_pipeline("BUY"), stop_distance=STOP,
    )
    assert created1 is True and first is not None
    assert created2 is False and second is not None
    assert first.id == second.id
    open_same = [
        p
        for p in paper.list_positions(_session, status="OPEN")
        if p.symbol == SYMBOL
    ]
    assert len(open_same) == 1
