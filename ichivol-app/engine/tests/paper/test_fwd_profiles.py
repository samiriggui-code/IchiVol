"""Forward-test profiles FWD_A_REF / FWD_A_LONG / FWD_E_LONG (docs/SPEC-FWD-E-LONG-2026-09-20.md, T1..T11).

Real dev DB, controlled decisions/prices fed straight to sync_position. Portfolios are throwaway (unique
codes) and removed afterwards; ICHIVOL_BASELINE_V1 is never touched.
"""

from __future__ import annotations

import random
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.brokerage import persistence as ledger_db
from app.db.models import (
    LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import engine as paper_engine
from app.paper import gates as paper_gates
from app.paper.counters import REJECT_EVENT
from app.paper.strategy_profiles import BASELINE_CODE, FWD_FRICTION_BPS_BY_SYMBOL, profile_for

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False

pytestmark = pytest.mark.skipif(not DB, reason="Postgres not reachable")

SYM = "FWDTEST"
L, S_, N = Direction.LONG, Direction.SHORT, Direction.NEUTRAL


def pipe(decision, direction):
    return PipelineResult(decision=decision, direction=direction, stages=[])


@pytest.fixture()
def factory():
    s = SessionLocal()
    made: list[str] = []

    def make(code):
        prof = profile_for(code)
        prof["code"] = f"T_{code}_{uuid.uuid4().hex[:6]}"
        pf = PaperPortfolio(code=prof["code"], label="t", currency="EUR", initial_cash=5000.0, cash=5000.0, strategy_profile=prof)
        s.add(pf)
        s.flush()
        made.append(pf.id)
        return pf

    yield s, make
    s.rollback()
    for pid in made:
        s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))).delete(synchronize_session=False)
        for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
            s.query(m).filter_by(portfolio_id=pid).delete()
        s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()
    paper_gates.reset_run_memory()


def step(s, pf, decision, direction, price, run_id=None, stop=2.0):
    r = paper_engine.sync_position(
        s, symbol=SYM, timeframe="1h", source="auto_watchlist", user_id=None, price=price,
        pipeline=pipe(decision, direction), stop_distance=stop, portfolio=pf, run_id=run_id,
    )
    s.flush()
    return r


def positions(s, pf, **kw):
    return s.query(PaperPosition).filter_by(portfolio_id=pf.id, **kw).order_by(PaperPosition.created_at).all()


def test_t1_decision_falling_to_watch_closes_A_but_not_E(factory):
    s, make = factory
    a, e = make("FWD_A_LONG"), make("FWD_E_LONG")
    for pf in (a, e):
        step(s, pf, "BUY", L, 100.0, run_id=1)
        step(s, pf, "WATCH", L, 100.5)
        step(s, pf, "WATCH", L, 100.6)
    assert positions(s, e)[0].status == "OPEN"
    pa = positions(s, a)[0]
    assert pa.status == "CLOSED" and pa.exit_reason == "pipeline_downgraded"


def test_t2_direction_neutral_closes_E_with_friction_and_no_new_position(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    step(s, e, "BUY", L, 100.0, run_id=1)
    step(s, e, "NO_TRADE", N, 101.0)
    ps = positions(s, e)
    assert len(ps) == 1 and ps[0].status == "CLOSED" and ps[0].exit_reason == "direction_flipped"
    assert ps[0].exit_price < 101.0  # exit friction applied (adverse for a long)


def test_t3_direction_short_closes_long_and_never_opens_a_short(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    step(s, e, "BUY", L, 100.0, run_id=1)
    step(s, e, "SELL", S_, 99.0, run_id=2)
    ps = positions(s, e)
    assert [p.exit_reason for p in ps] == ["direction_flipped"] and not positions(s, e, direction="SHORT")
    step(s, e, "SELL", S_, 98.0, run_id=2)  # flat now: SELL must be rejected, counted
    assert not positions(s, e, direction="SHORT")
    n = s.query(PaperJournalEvent).filter_by(portfolio_id=e.id, event_type=REJECT_EVENT).all()
    assert any(x.payload["reason"] == "short_not_allowed" for x in n)


def test_t4_sell_when_flat_no_order_counted_and_does_not_consume_the_signal_run(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    assert step(s, e, "SELL", S_, 100.0, run_id=5) is None
    assert not positions(s, e)
    rej = [x.payload["reason"] for x in s.query(PaperJournalEvent).filter_by(portfolio_id=e.id, event_type=REJECT_EVENT)]
    assert rej.count("short_not_allowed") == 1 and "signal_already_processed" not in rej
    assert step(s, e, "BUY", L, 100.0, run_id=5) is not None  # a BUY in that same run number is still openable


def test_t5_stop_has_priority_over_direction_change(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    step(s, e, "BUY", L, 100.0, run_id=1)
    pos = positions(s, e)[0]
    step(s, e, "NO_TRADE", N, pos.stop_price - 0.5)  # stop touched AND direction lost in the same cycle
    assert positions(s, e)[0].exit_reason == "stop_hit"


def test_t9_same_cycle_twice_closes_once_and_credits_cash_once(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    step(s, e, "BUY", L, 100.0, run_id=1)
    step(s, e, "NO_TRADE", N, 101.0)
    cash_after = e.cash
    step(s, e, "NO_TRADE", N, 101.0)  # replay of the same cycle
    assert e.cash == cash_after and len(positions(s, e)) == 1
    n_close = s.query(LedgerTransaction).filter(LedgerTransaction.portfolio_id == e.id, LedgerTransaction.key.like("close:%")).count()
    assert n_close == 1 and ledger_db.is_reconciled(s, e)


@pytest.mark.parametrize("code", ["FWD_E_LONG", "FWD_A_LONG"])
def test_t10_replay_200_bars_never_short_and_ledger_reconciles(factory, code):
    s, make = factory
    pf = make(code)
    rnd = random.Random(7)
    price = 100.0
    run = 0
    last = None
    for _ in range(200):
        price = max(5.0, price * (1 + rnd.uniform(-0.01, 0.01)))
        decision = rnd.choice(["BUY", "SELL", "WATCH", "NO_TRADE"])
        direction = {"BUY": L, "SELL": S_}.get(decision, rnd.choice([L, S_, N]))
        if decision != last:
            run += 1
            last = decision
        step(s, pf, decision, direction, price, run_id=run, stop=price * 0.02)
    assert not positions(s, pf, direction="SHORT")
    assert len(positions(s, pf)) > 0
    assert ledger_db.is_reconciled(s, pf)


def test_t11_default_profiles_unchanged_shorts_allowed_and_decision_exit(factory):
    s, make = factory
    base = make("FWD_A_REF")  # long+short, decision exit: the defaults of the engine
    assert step(s, base, "SELL", S_, 100.0, run_id=1) is not None  # short allowed
    assert positions(s, base, direction="SHORT")
    step(s, base, "WATCH", N, 99.0)
    assert positions(s, base)[0].exit_reason == "pipeline_downgraded"  # decision-based exit


def test_baseline_since_2026_09_21_is_long_only_with_direction_exit_and_class_costs(factory):
    s, make = factory
    b = profile_for(BASELINE_CODE)
    assert b["allow_short"] is False and b["exit_mode"] == "direction" and b["commission_bps"] == 7.5
    assert b["commission_bps_by_symbol"]["XAUUSD"] == 0.0 and b["friction_bps_by_symbol"]["EURUSD"] == 0.8
    pf = make(BASELINE_CODE)
    assert step(s, pf, "SELL", S_, 100.0, run_id=1) is None  # no short selling
    assert not positions(s, pf)


def test_profiles_are_frozen_definitions():
    for code in ("FWD_A_REF", "FWD_A_LONG", "FWD_E_LONG"):
        p = profile_for(code)
        assert p["commission_bps"] == 7.5 and p["log_rejections"] is True
        assert p["max_open_risk_pct"] == 0.04 and p["daily_loss_limit_pct"] == 0.03 and p["one_entry_per_signal_run"]
        assert p["friction_bps_by_symbol"] == FWD_FRICTION_BPS_BY_SYMBOL
    assert profile_for("FWD_A_REF").get("allow_short", True) is True
    assert profile_for("FWD_A_LONG")["allow_short"] is False and profile_for("FWD_A_LONG")["exit_mode"] == "decision"
    assert profile_for("FWD_E_LONG")["allow_short"] is False and profile_for("FWD_E_LONG")["exit_mode"] == "direction"


def test_direction_exit_only_from_the_lots_own_timeframe(factory):
    s, make = factory
    e = make("FWD_E_LONG")
    step(s, e, "BUY", L, 100.0, run_id=1)  # opens a 1h lot
    paper_engine.sync_position(  # a 4h row loses direction: must NOT close the 1h lot
        s, symbol=SYM, timeframe="4h", source="auto_watchlist", user_id=None, price=101.0,
        pipeline=pipe("NO_TRADE", N), stop_distance=2.0, portfolio=e,
    )
    s.flush()
    assert positions(s, e)[0].status == "OPEN"
