"""Idempotent SHORT entry-fee recalc — two --apply = one correction."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import (
    PaperJournalEvent,
    PaperPortfolio,
    PaperPosition,
)
from app.db.session import SessionLocal, engine
from scripts.recalc_short_entry_fee import (
    EVENT_TYPE,
    FIX_ACTIVATED_AT,
    apply_corrections,
    select_candidates,
)

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
    code = f"SFR_{uuid.uuid4().hex[:10]}"
    p = PaperPortfolio(
        code=code,
        label="short-fee-recalc",
        currency="EUR",
        initial_cash=10_000.0,
        cash=10_000.0,
        realized_pnl=50.0,
        strategy_profile={"code": code},
    )
    s.add(p)
    s.flush()
    # Pre-fix CLOSED SHORT with inflated realized (missing entry_fee deduct).
    pos = PaperPosition(
        portfolio_id=p.id,
        symbol="EURUSD",
        timeframe="1h",
        source="test",
        direction="SHORT",
        status="CLOSED",
        entry_time=FIX_ACTIVATED_AT - timedelta(days=2),
        entry_price=1.10,
        entry_decision="SELL",
        qty=0.0,
        notional=1000.0,
        entry_fee=1.25,
        initial_entry_fee=1.25,
        exit_time=FIX_ACTIVATED_AT - timedelta(hours=1),
        exit_price=1.09,
        exit_fee=0.5,
        realized_pnl=10.0,  # should become 8.75 after deducting entry_fee
        updated_at=datetime.now(timezone.utc),
    )
    s.add(pos)
    s.commit()
    s.info["portfolio"] = p
    s.info["position"] = pos
    yield s
    pid = p.id
    s.rollback()
    s.query(PaperJournalEvent).filter_by(portfolio_id=pid).delete()
    s.query(PaperPosition).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def test_two_apply_passes_correct_once(session):
    pos = session.info["position"]
    pf = session.info["portfolio"]

    cands, total = select_candidates(session, activated_at=FIX_ACTIVATED_AT)
    assert total >= 1
    assert any(c.id == pos.id for c in cands)

    n1 = apply_corrections(session, cands, activated_at=FIX_ACTIVATED_AT)
    session.commit()
    assert n1 == 1

    session.refresh(pos)
    session.refresh(pf)
    assert pos.realized_pnl == pytest.approx(8.75)
    assert pf.realized_pnl == pytest.approx(48.75)  # 50 + (8.75 - 10)

    events = (
        session.query(PaperJournalEvent)
        .filter_by(position_id=pos.id, event_type=EVENT_TYPE)
        .all()
    )
    assert len(events) == 1

    # Second pass — idempotent
    cands2, _ = select_candidates(session, activated_at=FIX_ACTIVATED_AT)
    assert not any(c.id == pos.id for c in cands2)
    n2 = apply_corrections(session, cands2 or [pos], activated_at=FIX_ACTIVATED_AT)
    # Even if we force the same position, already_recalculated skips it
    n2b = apply_corrections(session, [pos], activated_at=FIX_ACTIVATED_AT)
    session.commit()
    assert n2 == 0
    assert n2b == 0

    session.refresh(pos)
    assert pos.realized_pnl == pytest.approx(8.75)
    events2 = (
        session.query(PaperJournalEvent)
        .filter_by(position_id=pos.id, event_type=EVENT_TYPE)
        .all()
    )
    assert len(events2) == 1


def test_post_fix_exit_excluded(session):
    pos = session.info["position"]
    pos.exit_time = FIX_ACTIVATED_AT + timedelta(minutes=1)
    session.commit()
    cands, _ = select_candidates(session, activated_at=FIX_ACTIVATED_AT)
    assert not any(c.id == pos.id for c in cands)
