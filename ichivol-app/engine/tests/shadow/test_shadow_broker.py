"""ShadowBroker unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, PaperPortfolio, ShadowPosition
from app.shadow.broker import mark_shadows, open_shadow, shadow_stats


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _portfolio(session: Session) -> PaperPortfolio:
    p = PaperPortfolio(
        code="STRUCTURE_MVPP",
        label="test",
        initial_cash=5000.0,
        cash=5000.0,
        realized_pnl=0.0,
        strategy_profile={
            "risk_pct": 0.01,
            "take_profit_r": 2.0,
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
            "shadow_on_block": True,
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(p)
    session.commit()
    return p


def test_open_shadow_no_cash_impact():
    session = _session()
    p = _portfolio(session)
    cash_before = p.cash
    sh = open_shadow(
        session,
        portfolio=p,
        symbol="BTCUSDT",
        timeframe="1h",
        raw_decision="BUY",
        price=100.0,
        stop_distance=2.0,
        block_source="structure",
        block_reason="opposing_zone",
    )
    session.commit()
    session.refresh(p)
    assert sh is not None
    assert sh.status == "OPEN"
    assert sh.direction == "LONG"
    assert p.cash == cash_before


def test_mark_shadow_hits_stop():
    session = _session()
    p = _portfolio(session)
    sh = open_shadow(
        session,
        portfolio=p,
        symbol="BTCUSDT",
        timeframe="1h",
        raw_decision="BUY",
        price=100.0,
        stop_distance=2.0,
        block_source="fibonacci",
        block_reason="fib_no_confluence",
    )
    session.commit()
    assert sh is not None
    closed = mark_shadows(session, marks={"BTCUSDT:1h": 97.0})
    session.commit()
    assert len(closed) == 1
    session.refresh(sh)
    assert sh.status == "CLOSED"
    assert sh.exit_reason == "stop_hit"
    assert sh.pnl_r is not None and sh.pnl_r < 0


def test_shadow_stats_verdict():
    session = _session()
    p = _portfolio(session)
    for i in range(6):
        sh = ShadowPosition(
            portfolio_id=p.id,
            symbol="ETHUSDT",
            timeframe="1h",
            direction="LONG",
            status="CLOSED",
            entry_time=datetime.now(timezone.utc),
            entry_price=100.0,
            stop_price=98.0,
            take_profit_price=104.0,
            stop_distance=2.0,
            risk_pct=0.01,
            exit_time=datetime.now(timezone.utc),
            exit_price=104.0,
            exit_reason="take_profit_hit",
            pnl_r=2.0,
            pnl_pct=0.04,
            block_source="structure",
            block_reason="test",
            raw_decision="BUY",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(sh)
    session.commit()
    stats = shadow_stats(session, portfolio_id=p.id)
    assert stats["n_closed"] == 6
    assert stats["filter_verdict"] == "filter_too_aggressive"
