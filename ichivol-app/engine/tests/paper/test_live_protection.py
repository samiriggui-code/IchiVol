"""Stops / objectifs en temps réel (flux direct Binance) : règle bid / ask, saut de prix, clôture par le
chemin du broker, idempotence et concurrence avec le scan et un ordre manuel (vrai PostgreSQL)."""

from __future__ import annotations

import threading
import time
import uuid
from copy import deepcopy

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.brokerage import persistence as ledger_db
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
from app.market_data.binance_live import LivePriceCache, LiveQuote, now_ms
from app.paper import broker
from app.paper import engine as paper_engine
from app.paper.financing import financing_total_for_position
from app.paper.live_protection import (
    LiveProtector,
    LiveTrigger,
    close_lot_on_quote,
    evaluate_live_trigger,
    execution_price,
)
from app.paper.risk import apply_exit_friction
from app.paper.strategy_profiles import BASELINE_PROFILE

# --- règle de déclenchement (sans base) ----------------------------------------------------------------


def q(bid, ask, t=1000, sym="BTCUSDT", source="ws"):
    return LiveQuote(sym, float(bid), float(ask), received_ms=t, source=source)


def test_long_triggers_on_bid_only():
    # stop 95, objectif 110 : l'ask ne déclenche jamais un LONG
    assert evaluate_live_trigger("LONG", 95, 110, bid=95.01, ask=95.5) is None
    assert evaluate_live_trigger("LONG", 95, 110, bid=95.0, ask=95.5) == LiveTrigger("stop_hit", 95.0, "bid", 95.0)
    assert evaluate_live_trigger("LONG", 95, 110, bid=109.9, ask=110.5) is None  # ask >= objectif : pas assez
    assert evaluate_live_trigger("LONG", 95, 110, bid=110.0, ask=110.2) == LiveTrigger("take_profit_hit", 110.0, "bid", 110.0)


def test_short_triggers_on_ask_only():
    # stop 105, objectif 90
    assert evaluate_live_trigger("SHORT", 105, 90, bid=104.5, ask=104.99) is None
    assert evaluate_live_trigger("SHORT", 105, 90, bid=104.8, ask=105.0) == LiveTrigger("stop_hit", 105.0, "ask", 105.0)
    assert evaluate_live_trigger("SHORT", 105, 90, bid=89.9, ask=90.1) is None  # bid <= objectif : pas assez
    assert evaluate_live_trigger("SHORT", 105, 90, bid=89.7, ask=90.0) == LiveTrigger("take_profit_hit", 90.0, "ask", 90.0)


def test_missing_levels_never_trigger():
    assert evaluate_live_trigger("LONG", None, 110, 1, 2) is None
    assert evaluate_live_trigger("LONG", 95, None, 1, 2) is None


def test_gap_executes_at_market_never_at_ideal_stop():
    trig = evaluate_live_trigger("LONG", 95, 110, bid=90.0, ask=90.3)  # saut : bid bien sous le stop
    price, used = execution_price("LONG", trig, q(90, 90.3, t=1000), latest=None)
    assert price == 90.0 and price < 95  # pire que le stop
    # plus récent et plus bas : ordre au marché exécuté au dernier bid
    price, used = execution_price("LONG", trig, q(90, 90.3, t=1000), latest=q(89, 89.2, t=1500))
    assert price == 89.0 and used.received_ms == 1500
    # rebond après déclenchement : le lot ne profite pas du rebond
    price, _ = execution_price("LONG", trig, q(90, 90.3, t=1000), latest=q(96, 96.2, t=1500))
    assert price == 90.0
    # SHORT : saut au-dessus du stop, exécution à l'ask
    trig_s = evaluate_live_trigger("SHORT", 105, 90, bid=109.0, ask=109.5)
    assert execution_price("SHORT", trig_s, q(109, 109.5), latest=q(110, 110.4, t=2000))[0] == 110.4


def test_target_executes_at_the_triggering_side():
    trig = evaluate_live_trigger("LONG", 95, 110, bid=111.0, ask=111.2)
    assert execution_price("LONG", trig, q(111, 111.2), latest=q(109, 109.1, t=5000))[0] == 111.0


# --- vrai PostgreSQL ----------------------------------------------------------------------------------

try:
    with engine.connect() as _c:
        DB = _c.dialect.name == "postgresql"
except OperationalError:
    DB = False

pg = pytest.mark.skipif(not DB, reason="PostgreSQL not reachable")
INITIAL = 20_000.0


@pytest.fixture()
def pf_code():
    s = SessionLocal()
    code = f"LIVE_{uuid.uuid4().hex[:10]}"
    prof = deepcopy(BASELINE_PROFILE)
    prof.update(code=code, max_open_positions=10, max_notional_pct=0.9, allow_short=True)
    p = PaperPortfolio(code=code, label="live-protection", currency="EUR",
                       initial_cash=INITIAL, cash=INITIAL, realized_pnl=0.0, strategy_profile=prof)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    yield code, pid
    s = SessionLocal()
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))
    ).delete(synchronize_session=False)
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperEquitySnapshot, PaperPosition):
        s.query(m).filter_by(portfolio_id=pid).delete(synchronize_session=False)
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open(pid, *, symbol="LIVBTCUSDT", direction="LONG", price=100.0, stop_distance=5.0, signal=None) -> tuple[str, float, float]:
    s = SessionLocal()
    try:
        pos = broker.open_capital_position(
            s, portfolio=s.get(PaperPortfolio, pid), symbol=symbol, timeframe="1h", source="user_confirmed",
            user_id=None, direction=direction, price=price, decision="BUY" if direction == "LONG" else "SELL",
            stop_distance=stop_distance, manual_notional=4000.0, signal=signal,
        )
        assert pos is not None
        s.commit()
        return pos.id, float(pos.stop_price), float(pos.take_profit_price)
    finally:
        s.close()


def _books_balance(pid) -> PaperPortfolio:
    s = SessionLocal()
    try:
        pf = s.get(PaperPortfolio, pid)
        opens = s.execute(select(PaperPosition).where(PaperPosition.portfolio_id == pid,
                                                      PaperPosition.status == "OPEN")).scalars().all()
        tied = sum(float(p.notional or 0) + float(p.entry_fee or 0) + financing_total_for_position(s, p.id) for p in opens)
        assert pf.cash + tied == pytest.approx(pf.initial_cash + pf.realized_pnl, abs=1e-6)
        assert abs(ledger_db.reconcile_cash(s, pf)) < 1e-4
        s.expunge(pf)
        return pf
    finally:
        s.close()


def _exit_orders(pos_id) -> list[PaperOrder]:
    s = SessionLocal()
    try:
        rows = s.execute(select(PaperOrder).where(PaperOrder.position_id == pos_id)).scalars().all()
        out = [o for o in rows if o.reason != "open" and o.side in ("SELL", "BUY")]
        # l'ordre d'ouverture porte le motif de décision ; garder seulement les sorties
        out = [o for o in out if o.reason in ("stop_hit", "take_profit_hit", "manual_close")]
        for o in out:
            s.expunge(o)
        return out
    finally:
        s.close()


def _closed_events(pos_id) -> list[dict]:
    s = SessionLocal()
    try:
        return [e.payload for e in s.execute(select(PaperJournalEvent).where(
            PaperJournalEvent.position_id == pos_id, PaperJournalEvent.event_type == "CLOSED")).scalars()]
    finally:
        s.close()


def _friction(pid, symbol):
    s = SessionLocal()
    try:
        return broker.portfolio_friction_bps(s.get(PaperPortfolio, pid), symbol)
    finally:
        s.close()


@pg
def test_long_stop_closes_at_bid_through_the_broker(pf_code):
    _, pid = pf_code
    pos_id, stop, _tp = _open(pid)
    bid = stop - 0.01
    s = SessionLocal()
    try:
        res = close_lot_on_quote(s, pos_id, q(bid, bid + 0.2, t=now_ms()))
    finally:
        s.close()
    assert res["status"] == "closed" and res["reason"] == "stop_hit"
    orders = _exit_orders(pos_id)
    assert len(orders) == 1 and orders[0].side == "SELL"
    assert orders[0].requested_price == pytest.approx(bid)  # exécuté au bid…
    spread, slip = _friction(pid, "LIVBTCUSDT")
    # … avec la même friction de profil que le scan (chemin close_capital_position sans quote)
    assert orders[0].filled_price == pytest.approx(apply_exit_friction(bid, direction="LONG", spread_bps=spread, slippage_bps=slip))
    ev = _closed_events(pos_id)
    assert len(ev) == 1 and ev[0]["reason"] == "stop_hit" and ev[0]["trigger"] == "live"
    assert ev[0]["live"]["side"] == "bid" and ev[0]["live"]["bid"] == pytest.approx(bid)
    _books_balance(pid)


@pg
def test_long_gap_executes_below_the_stop(pf_code):
    _, pid = pf_code
    pos_id, stop, _ = _open(pid)
    gap_bid = stop * 0.97
    s = SessionLocal()
    try:
        res = close_lot_on_quote(s, pos_id, q(gap_bid, gap_bid * 1.001, t=now_ms()))
    finally:
        s.close()
    assert res["status"] == "closed" and res["gap"] is True
    o = _exit_orders(pos_id)[0]
    assert o.requested_price == pytest.approx(gap_bid) and o.requested_price < stop  # jamais au stop idéal
    assert _closed_events(pos_id)[0]["live"]["gap"] is True
    _books_balance(pid)


@pg
def test_short_target_closes_at_ask(pf_code):
    _, pid = pf_code
    pos_id, stop, tp = _open(pid, symbol="LIVEURUSD", direction="SHORT", price=100.0)
    assert stop > 100 > tp
    ask = tp - 0.01
    s = SessionLocal()
    try:
        res = close_lot_on_quote(s, pos_id, q(ask - 0.05, ask, t=now_ms(), sym="LIVEURUSD"))
    finally:
        s.close()
    assert res["status"] == "closed" and res["reason"] == "take_profit_hit"
    o = _exit_orders(pos_id)[0]
    assert o.side == "BUY" and o.requested_price == pytest.approx(ask)
    spread, slip = _friction(pid, "LIVEURUSD")
    assert o.filled_price == pytest.approx(apply_exit_friction(ask, direction="SHORT", spread_bps=spread, slippage_bps=slip))
    assert _books_balance(pid).realized_pnl > 0


@pg
def test_short_stop_triggers_on_ask(pf_code):
    _, pid = pf_code
    pos_id, stop, _ = _open(pid, symbol="LIVEURUSD", direction="SHORT", price=100.0)
    s = SessionLocal()
    try:
        # bid au-dessus du stop mais ask non : un vrai courtier rachète à l'ask… qui est ici au stop
        assert close_lot_on_quote(s, pos_id, q(stop - 0.2, stop - 0.01, sym="LIVEURUSD"))["status"] == "levels_changed"
        res = close_lot_on_quote(s, pos_id, q(stop - 0.1, stop + 0.05, t=now_ms(), sym="LIVEURUSD"))
    finally:
        s.close()
    assert res["status"] == "closed" and res["reason"] == "stop_hit"
    assert _exit_orders(pos_id)[0].requested_price == pytest.approx(stop + 0.05)
    _books_balance(pid)


def _run(*fns) -> list[BaseException]:
    errors: list[BaseException] = []

    def wrap(fn):
        def run():
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
        return run

    ts = [threading.Thread(target=wrap(f)) for f in fns]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=30)
    return errors


@pg
def test_two_live_messages_at_once_close_the_lot_once(pf_code):
    _, pid = pf_code
    pos_id, stop, _ = _open(pid)
    barrier = threading.Barrier(2)
    results: list[dict] = []

    def live(bid):
        def run():
            s = SessionLocal()
            try:
                s.get(PaperPosition, pos_id)  # chacun a vu le lot ouvert
                barrier.wait(timeout=10)
                results.append(close_lot_on_quote(s, pos_id, q(bid, bid + 0.1, t=now_ms())))
            finally:
                s.close()
        return run

    assert _run(live(stop - 0.1), live(stop - 0.2)) == []
    assert sorted(r["status"] for r in results) == ["already_closed", "closed"]
    assert len(_exit_orders(pos_id)) == 1 and len(_closed_events(pos_id)) == 1
    _books_balance(pid)


@pg
def test_live_and_scan_together_close_once(pf_code):
    """Le scan 5 min (sync_position → check_stop_or_tp) et le flux direct voient le stop au même moment."""
    _, pid = pf_code
    pos_id, stop, _ = _open(pid)
    barrier = threading.Barrier(2)

    def scan():
        s = SessionLocal()
        try:
            pf = s.get(PaperPortfolio, pid)
            s.get(PaperPosition, pos_id)
            barrier.wait(timeout=10)
            paper_engine.sync_position(
                s, symbol="LIVBTCUSDT", timeframe="1h", source="auto_watchlist", user_id=None,
                price=stop - 0.5, pipeline=PipelineResult(decision="BUY", direction=Direction.LONG, stages=[]),
                portfolio=pf,
            )
            time.sleep(0.2)  # transaction ouverte : fenêtre la plus large
            s.commit()
        finally:
            s.close()

    def live():
        s = SessionLocal()
        try:
            barrier.wait(timeout=10)
            close_lot_on_quote(s, pos_id, q(stop - 0.3, stop - 0.2, t=now_ms()))
        finally:
            s.close()

    assert _run(scan, live) == []
    assert len(_exit_orders(pos_id)) == 1 and len(_closed_events(pos_id)) == 1
    _books_balance(pid)


@pg
def test_live_and_manual_close_together_close_once(pf_code):
    _, pid = pf_code
    pos_id, stop, _ = _open(pid)
    barrier = threading.Barrier(2)

    def manual():
        s = SessionLocal()
        try:
            pos = s.get(PaperPosition, pos_id)
            barrier.wait(timeout=10)
            broker.close_capital_position(s, pos, price=stop - 0.4, reason="manual_close")
            time.sleep(0.2)
            s.commit()
        finally:
            s.close()

    def live():
        s = SessionLocal()
        try:
            barrier.wait(timeout=10)
            close_lot_on_quote(s, pos_id, q(stop - 0.3, stop - 0.2, t=now_ms()))
        finally:
            s.close()

    assert _run(manual, live) == []
    assert len(_exit_orders(pos_id)) == 1 and len(_closed_events(pos_id)) == 1
    _books_balance(pid)


@pg
def test_stale_scan_session_after_live_close_writes_nothing(pf_code):
    """Le scan a chargé le lot (OUVERT) avant la clôture par le flux : sa clôture tardive ne crédite rien."""
    _, pid = pf_code
    pos_id, stop, _ = _open(pid)
    scan = SessionLocal()
    try:
        stale = scan.get(PaperPosition, pos_id)
        assert stale.status == "OPEN"
        s = SessionLocal()
        try:
            assert close_lot_on_quote(s, pos_id, q(stop - 0.1, stop, t=now_ms()))["status"] == "closed"
        finally:
            s.close()
        broker.close_capital_position(scan, stale, price=stop - 0.1, reason="stop_hit")
        scan.commit()
    finally:
        scan.close()
    assert len(_exit_orders(pos_id)) == 1
    _books_balance(pid)


@pg
def test_protector_end_to_end_queues_once_and_closes(pf_code):
    code, pid = pf_code
    pos_id, stop, _tp = _open(pid)
    managed_id, _, _ = _open(pid, symbol="LIVETHUSDT", signal={"protection_trail": {"breakeven_at_r": 1.0}})
    cache = LivePriceCache()
    prot = LiveProtector(cache, symbol_map={"LIVBTCUSDT": "LIVBTCUSDT", "LIVETHUSDT": "LIVETHUSDT"},
                         portfolio_code=code, session_factory=SessionLocal)
    s = SessionLocal()
    try:
        n = prot.refresh_lots(s)
    finally:
        s.close()
    assert [lot.position_id for lot in prot.watched()] == [pos_id]
    assert n == 1
    assert managed_id != pos_id
    assert prot.status()["skipped_managed_lots"] == 1  # stop suiveur : laissé au moniteur 1m (protection.py)

    prot.on_quote(q(stop + 1, stop + 1.1, sym="LIVBTCUSDT"))  # rien
    assert prot.status()["pending_closes"] == 0
    trigger = q(stop - 0.1, stop, t=now_ms(), sym="LIVBTCUSDT")
    cache.put(trigger)
    prot.on_quote(trigger)
    prot.on_quote(q(stop - 0.2, stop - 0.1, t=now_ms(), sym="LIVBTCUSDT"))  # second message : pas de doublon
    assert prot.status()["pending_closes"] == 1
    res = prot.process_next(timeout=1)
    assert res["status"] == "closed"
    assert prot.process_next(timeout=0.05) is None
    assert prot.watched() == []
    assert prot.status()["closes"] == 1
    assert len(_exit_orders(pos_id)) == 1
    _books_balance(pid)
