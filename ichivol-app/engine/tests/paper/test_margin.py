"""Compte sur marge : la caisse peut passer sous zéro, l'équité, la clôture et le registre restent justes."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import PaperPortfolio
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import broker as paper_broker
from app.paper import engine as paper
from app.paper.margin import buying_power
from app.paper.reconcile import reconcile_portfolio
from app.paper.strategy_profiles import MAIN_PROFILE
from tests.paper.test_engine import _drop_portfolio

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False

db = pytest.mark.skipif(not DB, reason="Postgres not reachable")
MARGIN = {"margin": {"crypto_max_exposure": 1.0, "other_max_exposure": 5.0}}


def _lot(symbol: str, notional: float) -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, notional=notional)


def test_without_margin_it_is_the_cash() -> None:
    assert buying_power({}, "EURUSD", cash=1_000.0, equity=50_000.0, open_lots=[]) == 1_000.0


def test_each_market_has_its_own_pocket() -> None:
    lots = [_lot("EURUSD", 100_000.0), _lot("BTCUSDT", 20_000.0)]
    assert buying_power(MARGIN, "GBPUSD", cash=-70_000.0, equity=50_000.0, open_lots=lots) == 150_000.0
    assert buying_power(MARGIN, "ETHUSDT", cash=-70_000.0, equity=50_000.0, open_lots=lots) == 30_000.0


def test_exhausted_pocket_is_zero_never_negative() -> None:
    assert buying_power(MARGIN, "EURUSD", cash=0.0, equity=10_000.0, open_lots=[_lot("EURUSD", 90_000.0)]) == 0.0


@pytest.fixture()
def session():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def book(session):
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(
        id=str(uuid.uuid4()), code=f"TEST_MARGIN_{uuid.uuid4().hex[:8]}", label="marge", currency="EUR",
        valuation_mode="mark_to_market", initial_cash=50_000.0, cash=50_000.0, realized_pnl=0.0,
        strategy_profile=deepcopy(MAIN_PROFILE), is_active=True, started_at=now, created_at=now, updated_at=now,
    )
    session.add(pf)
    session.commit()
    yield pf
    _drop_portfolio(session, pf)


def _open(session, book, symbol: str, stop: float, price: float, direction: str = "LONG", **kw):
    decision = "BUY" if direction == "LONG" else "SELL"
    pipeline = PipelineResult(decision=decision, direction=Direction[direction], stages=[])
    return paper.open_user_confirmed(
        session, symbol=symbol, timeframe="1h", user_id="eve_intelligence", price=price, pipeline=pipeline,
        stop_distance=stop, portfolio=book, **kw,
    )


@db
def test_leveraged_lot_borrows_then_gives_back_exact_pnl(session, book) -> None:
    position, created = _open(session, book, "EURUSD", 0.0015, 1.0, risk_pct=0.01, max_notional_pct=3.0)
    assert created and position is not None
    session.commit()
    # 1 % de risque sur un stop de 0,15 % voudrait 6,6× ; la poche CFD du profil s'arrête à 2× l'équité.
    assert position.notional == pytest.approx(100_000.0, rel=1e-3)
    assert book.cash < 0
    equity = paper_broker.estimate_equity(session, book)
    assert equity == pytest.approx(50_000.0, abs=1.0)

    target = position.take_profit_price
    paper_broker.close_capital_position(session, position, price=target, reason="take_profit_hit", signal={})
    session.commit()
    assert book.cash == pytest.approx(50_000.0 + position.realized_pnl, abs=0.01)
    assert position.realized_pnl > 0
    report = reconcile_portfolio(session, book)
    failing = [c for c in report["checks"] if not c.get("ok")]
    assert failing == []


@db
def test_leveraged_short_stays_exact(session, book) -> None:
    position, _ = _open(session, book, "NDX", 25.0, 25_000.0, "SHORT", risk_pct=0.01, max_notional_pct=3.0)
    session.commit()
    assert position is not None and book.cash < 0
    paper_broker.close_capital_position(session, position, price=position.stop_price, reason="stop_hit", signal={})
    session.commit()
    assert position.realized_pnl < 0
    assert book.cash == pytest.approx(50_000.0 + position.realized_pnl, abs=0.5)
    assert [c for c in reconcile_portfolio(session, book)["checks"] if not c.get("ok")] == []


@db
def test_crypto_stays_within_one_times_equity(session, book) -> None:
    first, _ = _open(session, book, "BTCUSDT", 80.0, 80_000.0, risk_pct=0.01, max_notional_pct=1.0)
    session.commit()
    assert first is not None and first.notional == pytest.approx(50_000.0, rel=1e-2)
    second, created = _open(session, book, "ETHUSDT", 2.0, 2_000.0, risk_pct=0.01, max_notional_pct=1.0)
    assert second is None and created is False


@db
def test_profile_amounts_apply_without_an_engagement(session, book) -> None:
    position, _ = _open(session, book, "EURUSD", 0.0015, 1.0)
    session.commit()
    assert position is not None
    assert position.notional == pytest.approx(5_000.0, rel=1e-3)  # 10 % de l'équité, comme avant
    assert book.cash > 0


@db
def test_open_risk_cap_still_holds_with_large_engagements(session, book) -> None:
    # Sans le plafond de paris corrélés (testé à part) : seul le risque ouvert doit arrêter la série.
    book.strategy_profile = {**book.strategy_profile, "correlation_groups": None}
    session.commit()
    opened = []
    for i, sym in enumerate(("EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "SPX", "NDX")):
        pos, _ = _open(session, book, sym, 5.0, 100.0, risk_pct=0.01, max_notional_pct=3.0)
        session.commit()
        if pos is not None:
            opened.append(pos)
    assert len(opened) == 4  # 4 × 1 % = plafond de risque ouvert de 4 %


@db
def test_latent_loss_of_a_leveraged_lot_trips_the_daily_lock(session, book) -> None:
    position, _ = _open(session, book, "EURUSD", 0.0015, 1.0, risk_pct=0.01, max_notional_pct=3.0)
    session.commit()
    assert position is not None
    paper.snapshot_and_guard(session, book, {"EURUSD:1h": 0.999})
    assert book.daily_loss_locked is False
    # -2 % sur 100 000 € de position : -4 % du capital, sans aucune clôture.
    paper.snapshot_and_guard(session, book, {"EURUSD:1h": 0.98})
    session.commit()
    assert book.daily_loss_locked is True
    assert position.status == "OPEN"


@db
def test_one_dollar_bet_at_a_time_but_a_hedge_is_allowed(session, book) -> None:
    first, _ = _open(session, book, "EURUSD", 5.0, 100.0, "SHORT")
    session.commit()
    assert first is not None
    # GBPUSD et l'or vendus = la même hausse du dollar que l'EURUSD déjà vendu.
    for sym in ("GBPUSD", "XAUUSD"):
        same, created = _open(session, book, sym, 5.0, 100.0, "SHORT")
        assert same is None and created is False
    hedge, _ = _open(session, book, "GBPUSD", 5.0, 100.0, "LONG")
    other, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    assert hedge is not None and other is not None


@db
def test_no_reentry_on_a_symbol_just_stopped(session, book) -> None:
    first, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    session.commit()
    paper_broker.close_capital_position(session, first, price=first.stop_price, reason="stop_hit", signal={})
    session.commit()
    for direction in ("SHORT", "LONG"):  # ni ré-entrée, ni retournement
        again, created = _open(session, book, "WTI", 5.0, 100.0, direction)
        assert again is None and created is False
    # Délai écoulé : le symbole redevient ouvrable. Un objectif atteint n'impose aucun délai.
    first.exit_time = first.exit_time - timedelta(hours=9)
    session.commit()
    later, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    session.commit()
    assert later is not None
    paper_broker.close_capital_position(session, later, price=later.take_profit_price, reason="take_profit_hit", signal={})
    session.commit()
    after_win, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    assert after_win is not None
