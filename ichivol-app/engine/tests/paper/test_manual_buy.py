"""User-chosen (discretionary) paper buy: preview numbers, refusals explained, and the real opening."""
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import broker as paper_broker
from app.paper import engine as paper_engine
from app.paper.manual import preview_manual_buy
from app.paper.strategy_profiles import BASELINE_CODE, profile_for

try:
    with engine.connect():
        pass
    OK = True
except OperationalError:
    OK = False
pytestmark = pytest.mark.skipif(not OK, reason="dev Postgres not reachable")
CODE = "MANUALTEST"


def _clean_baseline_user_rows(s, cash_to_restore=None):
    """open_user_confirmed always targets the baseline portfolio: remove what this test opened there, restore cash."""
    base = s.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    if base is None:
        return
    for p in s.query(PaperPosition).filter_by(portfolio_id=base.id, user_id="u1").all():
        s.query(PaperJournalEvent).filter_by(position_id=p.id).delete()
        ids = [t.id for t in s.query(LedgerTransaction).filter_by(ref=p.id)]
        if ids:
            s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(ids)).delete(synchronize_session=False)
            s.query(LedgerTransaction).filter(LedgerTransaction.id.in_(ids)).delete(synchronize_session=False)
        s.query(PaperOrder).filter_by(position_id=p.id).delete()
        s.delete(p)
    if cash_to_restore is not None:
        base.cash = cash_to_restore
    s.commit()


def _clean(s):
    s.rollback()
    _clean_baseline_user_rows(s)
    pf = s.query(PaperPortfolio).filter_by(code=CODE).first()
    if pf is not None:
        s.query(PaperJournalEvent).filter_by(portfolio_id=pf.id).delete()
        ids = [t.id for t in s.query(LedgerTransaction).filter_by(portfolio_id=pf.id)]
        if ids:
            s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(ids)).delete(synchronize_session=False)
            s.query(LedgerTransaction).filter(LedgerTransaction.id.in_(ids)).delete(synchronize_session=False)
        s.query(PaperOrder).filter_by(portfolio_id=pf.id).delete()
        s.query(PaperPosition).filter_by(portfolio_id=pf.id).delete()
        s.delete(pf)
    s.commit()


@pytest.fixture
def s():
    sess = SessionLocal()
    _clean(sess)
    base = sess.query(PaperPortfolio).filter_by(code=BASELINE_CODE).first()
    cash0 = base.cash if base is not None else None
    yield sess
    sess.rollback()
    _clean(sess)
    _clean_baseline_user_rows(sess, cash0)
    sess.close()


def portfolio(s, **profile):
    now = datetime.now(timezone.utc)
    p = profile_for(BASELINE_CODE) | profile
    pf = PaperPortfolio(code=CODE, label=CODE, currency="EUR", valuation_mode="X", initial_cash=5000.0, cash=5000.0,
                        realized_pnl=0.0, strategy_profile=p, is_active=True, started_at=now, created_at=now, updated_at=now)
    s.add(pf); s.flush()
    return pf


def row(symbol="BTCUSDT", price=100.0, decision="WATCH", atr=2.0, stale=False):
    return NS(symbol=symbol, price=price, timeframe="1h", pipeline=PipelineResult(decision=decision, direction=Direction.LONG, stages=[]),
              atr=NS(suggested_stop_distance=atr), signal_timing={"stale": stale})


def test_preview_numbers_include_every_cost_and_no_signal_is_needed(s):
    portfolio(s)
    p = preview_manual_buy(s, row(), notional=1000.0, stop_pct=0.02, portfolio_code=CODE)
    assert p["ok"] and p["engine_verdict"] == "WATCH"
    assert [w["code"] for w in p["warnings"]] == ["signal_not_buy"]
    o, c, out = p["order"], p["costs"], p["outcomes"]
    assert o["notional"] == pytest.approx(1000.0, rel=1e-6)
    assert out["net_loss_if_stop"] < -(o["qty"] * 2.0) + 1e-9  # loss at the stop is LARGER than the raw stop distance: costs added
    assert out["net_gain_if_target"] < o["qty"] * 2.0 * 2.0  # gain at target is SMALLER than the raw target: costs subtracted
    assert c["commission_bps"] == 7.5 and c["commission_entry"] == pytest.approx(0.75, rel=1e-3)
    assert p["portfolio"]["cash_after"] == pytest.approx(5000 - o["notional"] - c["commission_entry"])


def test_refusals_are_explained(s):
    pf = portfolio(s)
    assert preview_manual_buy(s, row(stale=True), notional=500, stop_pct=0.02, portfolio_code=CODE)["blocking"][0]["code"] == "stale_data"
    assert preview_manual_buy(s, row(), notional=9000, stop_pct=0.02, portfolio_code=CODE)["blocking"][0]["code"] == "insufficient_cash"
    assert preview_manual_buy(s, row(), notional=5, stop_pct=0.02, portfolio_code=CODE)["blocking"][0]["code"] == "below_minimum"
    assert preview_manual_buy(s, row(), notional=500, stop_pct=0.9, portfolio_code=CODE)["blocking"][0]["code"] == "bad_stop"
    # 4% cumulative-risk cap: 2500 EUR with a 10% stop risks ~250 EUR > 200 EUR
    big = preview_manual_buy(s, row(), notional=2500, stop_pct=0.10, portfolio_code=CODE)
    assert "open_risk_cap" in [b["code"] for b in big["blocking"]] and not big["ok"]


def test_manual_buy_opens_exactly_the_chosen_amount_and_is_journaled(s):
    cash_before = s.query(PaperPortfolio).filter_by(code=BASELINE_CODE).one().cash
    position, created = paper_engine.open_user_confirmed(
        s, symbol="BTCUSDT", timeframe="1h", user_id="u1", price=100.0,
        pipeline=PipelineResult(decision="BUY", direction=Direction.LONG, stages=[]), stop_distance=2.0,
        signal_extra={"discretionary": True}, manual_notional=800.0, take_profit_r=3.0,
    )
    assert created and position.status == "OPEN" and position.source == "user_confirmed"
    assert position.notional == pytest.approx(800.0, rel=1e-6)
    assert position.take_profit_price - position.entry_price == pytest.approx(3.0 * 2.0, rel=1e-6)
    base = s.query(PaperPortfolio).filter_by(code=BASELINE_CODE).one()
    assert position.portfolio_id == base.id
    assert cash_before - base.cash == pytest.approx(800.0 + position.entry_fee)
    assert s.query(LedgerTransaction).filter_by(ref=position.id).count() == 1
