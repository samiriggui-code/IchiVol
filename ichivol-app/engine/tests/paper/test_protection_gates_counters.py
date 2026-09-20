"""Optional entry gates and structured counters (protections live in app/paper/protection.py).

Pure tests need no database; the DB tests use the same skip convention as test_engine.py and clean up
their own rows (portfolio code GATETEST).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.paper import counters, gates
from app.paper import engine as paper

# --- counters ------------------------------------------------------------------------------------------
def _pipe(decision, direction, fails=(), regime_code=None):
    stages = []
    for sid in (StageId.DIRECTION, StageId.PARTICIPATION, StageId.STRUCTURE, StageId.LOCATION, StageId.REGIME):
        failing = sid.value in fails
        stages.append(PipelineStage(sid, StageStatus.FAIL if failing else StageStatus.PASS, "",
                                    [regime_code] if failing and sid == StageId.REGIME and regime_code else []))
    return PipelineResult(decision=decision, direction=direction, stages=stages)


def test_classify_row_primary_is_exclusive_and_stage_fail_is_multilabel():
    c = counters.classify_row(_pipe("NO_TRADE", Direction.LONG, ("location", "regime"), "regime_no_breakout"),
                              bar_forming=True, stale=False)
    assert c["primary"] == "regime" and set(c["failed"]) == {"location", "regime"}
    assert c["sole_blocker"] is None and c["regime_code"] == "regime_no_breakout" and c["bar_forming"]


def test_sole_blocker_and_signal_and_neutral():
    only = counters.classify_row(_pipe("WATCH", Direction.LONG, ("participation",)), bar_forming=False, stale=False)
    assert only["sole_blocker"] == "participation" and only["primary"] == "participation"
    sig = counters.classify_row(_pipe("BUY", Direction.LONG), bar_forming=False, stale=False)
    assert sig["primary"] == "signal" and sig["sole_blocker"] is None
    neutral = counters.classify_row(_pipe("WATCH", Direction.NEUTRAL), bar_forming=False, stale=False)
    assert neutral["primary"] == "ichimoku_neutral" and not neutral["directional"]


def test_funnel_primary_sums_to_rows():
    acc = counters.FunnelAccumulator()
    for p in (_pipe("BUY", Direction.LONG), _pipe("NO_TRADE", Direction.LONG, ("regime",)), _pipe("WATCH", Direction.NEUTRAL)):
        acc.add(counters.classify_row(p, bar_forming=True, stale=False))
    out = acc.payload("1h")
    assert sum(out["primary"].values()) == out["rows"] == 3 and out["bar_forming"] == 3
    assert "semantics" in out


# --- DB ------------------------------------------------------------------------------------------------
try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

db = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")
CODE = "GATETEST"


@pytest.fixture
def session():
    s = SessionLocal()
    _clean(s)
    yield s
    _clean(s)
    s.close()


def _clean(s):
    s.rollback()
    pf = s.query(PaperPortfolio).filter_by(code=CODE).first()
    if pf is not None:
        s.query(PaperJournalEvent).filter_by(portfolio_id=pf.id).delete()
        tx_ids = [t.id for t in s.query(LedgerTransaction).filter_by(portfolio_id=pf.id)]
        if tx_ids:
            s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(tx_ids)).delete(synchronize_session=False)
            s.query(LedgerTransaction).filter(LedgerTransaction.id.in_(tx_ids)).delete(synchronize_session=False)
        s.query(PaperOrder).filter_by(portfolio_id=pf.id).delete()
        s.query(PaperPosition).filter_by(portfolio_id=pf.id).delete()
        s.delete(pf)
    s.commit()


def make_portfolio(s, **profile):
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code=CODE, label=CODE, currency="EUR", valuation_mode="USDT_AS_EUR_PROXY", initial_cash=5000.0,
                        cash=5000.0, realized_pnl=0.0, strategy_profile={"risk_pct": 0.01, "max_open_positions": 5,
                                                                        "max_notional_pct": 0.25, **profile},
                        is_active=True, started_at=now, created_at=now, updated_at=now)
    s.add(pf)
    s.flush()
    return pf


def open_pos(s, pf, symbol, source, entry=100.0, stop=98.0, tp=104.0, qty=10.0, risk=20.0):
    p = PaperPosition(portfolio_id=pf.id, symbol=symbol, timeframe="1h", source=source, user_id=None, direction="LONG",
                      status="OPEN", entry_time=datetime.now(timezone.utc) - timedelta(hours=3), entry_price=entry,
                      entry_decision="BUY", qty=qty, notional=qty * entry, stop_price=stop, take_profit_price=tp,
                      risk_amount=risk, entry_fee=0.5)
    s.add(p)
    s.flush()
    return p


@db
def test_one_position_per_symbol_blocks_second_entry_from_another_source(session):
    pf = make_portfolio(session, one_position_per_symbol=True)
    open_pos(session, pf, "NEARTEST", "auto_watchlist")
    r = gates.entry_gate(session, pf, symbol="NEARTEST", timeframe="1h", price=4.0, stop_distance=0.16, equity=5000.0)
    assert r == "position_already_open"


@db
def test_baseline_style_profile_has_no_gates(session):
    pf = make_portfolio(session)
    assert gates.has_gates(pf.strategy_profile) is False


@db
def test_symbol_exposure_open_risk_and_daily_halt(session):
    pf = make_portfolio(session, max_symbol_notional_pct=0.25, daily_loss_limit_pct=0.03)
    open_pos(session, pf, "AAA", "auto_watchlist", qty=12.0, entry=100.0, risk=25.0)  # 1200 = 24% of 5000
    # a second AAA entry would exceed the 25% aggregate cap on that instrument
    assert gates.entry_gate(session, pf, symbol="AAA", timeframe="1h", price=100.0, stop_distance=2.0,
                            equity=5000.0) == "symbol_exposure_cap"
    pf.strategy_profile = {**pf.strategy_profile, "max_open_risk_pct": 0.008}
    # another instrument: cumulative risk 25 + 25 = 50 > 0.8% of 5000 (= 40)
    assert gates.entry_gate(session, pf, symbol="BBB", timeframe="1h", price=100.0, stop_distance=2.0,
                            equity=5000.0) == "open_risk_cap"
    # daily loss: equity 4800 vs 5000 at day start (no snapshot -> initial cash) = -4% <= -3%
    pf.strategy_profile = {**pf.strategy_profile, "max_open_risk_pct": None, "max_symbol_notional_pct": None}
    assert gates.entry_gate(session, pf, symbol="BBB", timeframe="1h", price=100.0, stop_distance=2.0,
                            equity=4800.0) == "daily_loss_halt"


@db
def test_signal_run_is_only_traded_once(session):
    gates.reset_run_memory()
    pf = make_portfolio(session, one_entry_per_signal_run=True)
    run = gates.observe_decision(pf.id, "CCC", "1h", "BUY")
    assert gates.entry_gate(session, pf, symbol="CCC", timeframe="1h", price=10.0, stop_distance=0.5, equity=5000.0,
                            run_id=run) is None
    gates.mark_run_traded(pf.id, "CCC", "1h", run)
    assert gates.observe_decision(pf.id, "CCC", "1h", "BUY") == run  # same run, still BUY
    assert gates.entry_gate(session, pf, symbol="CCC", timeframe="1h", price=10.0, stop_distance=0.5, equity=5000.0,
                            run_id=run) == "signal_already_processed"
    new_run = gates.observe_decision(pf.id, "CCC", "1h", "WATCH")
    new_run = gates.observe_decision(pf.id, "CCC", "1h", "BUY")
    assert gates.entry_gate(session, pf, symbol="CCC", timeframe="1h", price=10.0, stop_distance=0.5, equity=5000.0,
                            run_id=new_run) is None


@db
def test_rejection_is_journaled_only_when_the_profile_opts_in(session):
    pf = make_portfolio(session, one_position_per_symbol=True, log_rejections=True)
    open_pos(session, pf, "NEARTEST", "auto_watchlist", entry=4.0, stop=3.8, tp=4.4, qty=300.0, risk=48.0)
    pipeline = PipelineResult(decision="BUY", direction=Direction.LONG, stages=[])
    res = paper.sync_position(session, symbol="NEARTEST", timeframe="1h", source="user_confirmed", user_id=None,
                              price=4.0, pipeline=pipeline, stop_distance=0.16, portfolio=pf)
    assert res is None
    session.flush()
    ev = session.query(PaperJournalEvent).filter_by(portfolio_id=pf.id, event_type=counters.REJECT_EVENT).all()
    assert [e.payload["reason"] for e in ev] == ["position_already_open"]
