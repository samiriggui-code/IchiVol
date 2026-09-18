"""Real-DB tests for app/paper/engine.py, same conventions as
tests/market_data/test_collector.py (skipped if ichivol_engine_dev isn't
reachable, explicit cleanup around each test).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import PaperPosition
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import engine as paper

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")

SYMBOL = "PAPERTEST"
TIMEFRAME = "1h"


def _pipeline(decision: str, direction: Direction = Direction.LONG) -> PipelineResult:
    return PipelineResult(decision=decision, direction=direction, stages=[])


def _cleanup(session):
    session.query(PaperPosition).filter_by(symbol=SYMBOL).delete()
    session.commit()


@pytest.fixture(autouse=True)
def _session():
    session = SessionLocal()
    _cleanup(session)
    yield session
    _cleanup(session)
    session.close()


def test_sync_position_opens_a_long_on_buy_with_no_existing_position(_session):
    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"),
    )
    assert result is not None
    assert result.direction == "LONG"
    assert result.status == "OPEN"
    assert result.entry_price == 100.0
    assert result.entry_decision == "BUY"


def test_sync_position_does_nothing_on_watch_with_no_existing_position(_session):
    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("WATCH"),
    )
    assert result is None
    assert paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    ) is None


def test_sync_position_holds_an_open_position_while_still_supported(_session):
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"),
    )
    _session.commit()

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=105.0, pipeline=_pipeline("BUY"),
    )
    assert result is None  # nothing changed -- still open, untouched

    open_position = paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    )
    assert open_position is not None
    assert open_position.status == "OPEN"
    assert open_position.entry_price == 100.0  # unchanged


def test_sync_position_closes_when_decision_downgrades_to_watch(_session):
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"),
    )
    _session.commit()

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=110.0, pipeline=_pipeline("WATCH"),
    )
    assert result is not None
    assert result.status == "CLOSED"
    assert result.exit_reason == "pipeline_downgraded"
    assert result.exit_price == 110.0
    assert result.pnl_pct == pytest.approx(0.10)  # (110/100) - 1


def test_sync_position_closes_when_pipeline_direction_flips(_session):
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("BUY"),
    )
    _session.commit()

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=90.0, pipeline=_pipeline("SELL", Direction.SHORT),
    )
    assert result is not None
    assert result.status == "CLOSED"
    assert result.exit_reason == "pipeline_flipped"
    # Never auto-reversed into the new side -- a fresh sync would open a
    # new SHORT position on its own next call, this one only ever closes.
    assert paper._get_open_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist", user_id=None
    ) is None


def test_short_position_pnl_is_positive_when_price_falls(_session):
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("SELL", Direction.SHORT),
    )
    _session.commit()

    result = paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=80.0, pipeline=_pipeline("WATCH"),
    )
    assert result.pnl_pct == pytest.approx(0.25)  # (100/80) - 1


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

    watch_sym = f"{SYMBOL}2"
    rows = [_FakeRow(SYMBOL, 100.0, "BUY"), _FakeRow(watch_sym, 50.0, "WATCH")]
    try:
        touched = paper.sync_auto_watchlist(_session, rows)
        assert touched, "BUY should open at least on baseline"
        assert all(p.symbol == SYMBOL for p in touched)
        assert not any(p.symbol == watch_sym for p in touched)
    finally:
        _session.query(PaperPosition).filter(
            PaperPosition.symbol.in_([SYMBOL, watch_sym])
        ).delete(synchronize_session=False)
        _session.commit()


def test_open_user_confirmed_is_idempotent(_session):
    first = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"),
    )
    second = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=105.0,
        pipeline=_pipeline("BUY"),
    )
    assert first.id == second.id
    assert second.entry_price == 100.0  # not overwritten by the second call


def test_open_user_confirmed_does_not_open_on_a_non_actionable_decision(_session):
    result = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("WATCH"),
    )
    assert result is None


def test_close_manually_closes_an_open_position(_session):
    position = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"),
    )
    closed = paper.close_manually(_session, position.id, price=120.0)
    assert closed.status == "CLOSED"
    assert closed.exit_reason == "manual_close"
    assert closed.pnl_pct == pytest.approx(0.20)


def test_close_manually_returns_none_for_an_already_closed_position(_session):
    position = paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"),
    )
    paper.close_manually(_session, position.id, price=120.0)
    assert paper.close_manually(_session, position.id, price=130.0) is None


def test_list_positions_filters_by_source_user_and_status(_session):
    paper.open_user_confirmed(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, user_id="user-1", price=100.0,
        pipeline=_pipeline("BUY"),
    )
    paper.sync_position(
        _session, symbol=SYMBOL, timeframe=TIMEFRAME, source="auto_watchlist",
        user_id=None, price=100.0, pipeline=_pipeline("SELL", Direction.SHORT),
    )
    _session.commit()

    # Filter results down to this test's own symbol before counting -- a
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
        p for p in paper.list_positions(_session, source="auto_watchlist") if p.symbol == SYMBOL
    ]
    assert len(auto_positions) == 1
    assert auto_positions[0].user_id is None

    open_only = paper.list_positions(_session, status="OPEN")
    assert all(p.status == "OPEN" for p in open_only)
