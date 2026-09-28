"""RS-D1 paper live — behaviour of the runner, broker, monitor and guards (RS-09 §3–§8)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import PaperJournalEvent, PaperPortfolio, PaperPosition, RsBookState
from app.db.session import SessionLocal
from app.indicators.ichimoku import Candle
from app.main import app
from app.paper import broker as paper_broker
from app.paper import protection
from app.paper.portfolio import ensure_baseline_portfolio
from app.paper.rs_d1_runner import RsD1Runner
from app.paper.strategy_profiles import BASELINE_CODE, RS_D1_CODE, is_rs_engine, profile_for, syncable_profile_codes
from rs import BAR_SECONDS
from rs.book import Book
from rs.costs import cost_profile
from tests.rs_paper.helpers import FakeSource, at, no_klines, rs_portfolio

T0 = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp())  # aligned on 4h
MIN = 60_000


def flat_then_breakout(n_flat: int = 80, *, base: float = 100.0, extra: list[tuple[float, float, float, float]] = ()) -> list[Candle]:
    """n_flat quiet bars around ``base`` then the given (o, h, l, c) bars."""
    out = []
    for i in range(n_flat):
        o = base + (0.5 if i % 2 else -0.5)
        out.append(Candle(time=T0 + i * BAR_SECONDS, open=o, high=o + 1.0, low=o - 1.0, close=base))
    for k, (o, h, l, c) in enumerate(extra):
        out.append(Candle(time=T0 + (n_flat + k) * BAR_SECONDS, open=o, high=h, low=l, close=c))
    return out


def journal(session, pf, kind: str) -> list[PaperJournalEvent]:
    return list(session.execute(
        select(PaperJournalEvent).where(PaperJournalEvent.portfolio_id == pf.id, PaperJournalEvent.event_type == kind)
        .order_by(PaperJournalEvent.created_at)
    ).scalars())


def open_rs_positions(session, pf) -> list[PaperPosition]:
    return list(session.execute(
        select(PaperPosition).where(PaperPosition.portfolio_id == pf.id, PaperPosition.status == "OPEN")
    ).scalars())


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# --- profile / separation --------------------------------------------------------------------------------

def test_profile_is_separate_and_never_synced():
    p = profile_for(RS_D1_CODE)
    assert is_rs_engine(p) and p["label"] == "RS-D1 — validé 2025, holdout 2026 non ouvert"
    assert p["auto_timeframes"] == [] and p["sync_auto"] is False and p["allow_short"] is False
    assert RS_D1_CODE not in syncable_profile_codes()
    assert not is_rs_engine(profile_for(BASELINE_CODE))
    assert profile_for(BASELINE_CODE)["auto_timeframes"] == ["1h"]  # baseline untouched


def test_manual_orders_refused_for_rs_portfolio(session):
    pf = rs_portfolio(session)
    client = TestClient(app)
    r = client.get("/api/engine/paper/preview", params={"symbol": "BTCUSDT", "notional": 100, "portfolio_code": RS_D1_CODE})
    assert r.status_code == 403 and r.json()["detail"].startswith("manual_orders_disabled")
    r = client.get("/api/engine/paper/propose", params={"symbol": "BTCUSDT", "portfolio_code": RS_D1_CODE})
    assert r.status_code == 403
    c = cost_profile("paper")["BTCUSDT"]
    pos = paper_broker.open_presized_position(
        session, portfolio=pf, symbol="BTCUSDT", timeframe="4h", source="rs_d1", requested_price=100.0,
        entry_fill=c.fill(100.0, "buy"), qty=1.0, notional=c.fill(100.0, "buy"), fee=c.fee(c.fill(100.0, "buy")),
        stop_price=90.0, risk_amount=10.0, spread_bps=1.0,
    )
    session.commit()
    r = client.post(f"/api/engine/paper/positions/{pos.id}/close")
    assert r.status_code == 403
    session.refresh(pos)
    assert pos.status == "OPEN"


def test_locks_are_per_portfolio_both_ways(session):
    """Complément B: baseline kill switch never blocks RS, and RS never trips baseline locks."""
    base = ensure_baseline_portfolio(session)
    base_before = (base.kill_switch_armed, base.daily_loss_locked, base.cash)
    pf = rs_portfolio(session)
    bars = flat_then_breakout(extra=[(100, 112, 99, 111)])  # breakout close 111 > U55 = 101.5
    src = FakeSource({"BTCUSDT": bars})
    runner = RsD1Runner(src, code=pf.code, symbols=["BTCUSDT"], klines_1m_fn=no_klines, trades_fn=None,
                        history_start=T0, replay_score_start=T0)
    base.kill_switch_armed = True  # baseline locked by a human
    session.commit()
    try:
        last = bars[-1].time
        runner.cycle(session, now=at(last + BAR_SECONDS + 1))  # decide at close of breakout bar
        # the next bar has not started in the fake source -> add it so the entry can fill at its open
        src2 = FakeSource({"BTCUSDT": bars + [Candle(time=last + BAR_SECONDS, open=111, high=112, low=110, close=111)]})
        runner.source = src2
        runner.cycle(session, now=at(last + BAR_SECONDS + 2))
        assert len(open_rs_positions(session, pf)) == 1  # RS traded despite the baseline kill switch
    finally:
        session.refresh(base)
        base.kill_switch_armed = base_before[0]
        session.commit()
    session.refresh(base)
    assert (base.daily_loss_locked, base.cash) == base_before[1:]  # RS activity never touched baseline

    # RS kill switch armed -> RS takes no new entry, baseline unaffected
    pf.kill_switch_armed = True
    session.commit()
    runner.cycle(session, now=at(bars[-1].time + 2 * BAR_SECONDS + 1))
    assert any(e.payload.get("reason") == "kill_switch_armed" for e in journal(session, pf, "RS_REJECTED"))
    session.refresh(base)
    assert base.kill_switch_armed == base_before[0]


# --- broker / monitor ------------------------------------------------------------------------------------

def test_close_capital_position_net_equals_symbolcost(session):
    """Same net as SymbolCost on a numeric case (RS-09 §2)."""
    pf = rs_portfolio(session)
    c = cost_profile("paper")["SOLUSDT"]
    raw_in, raw_out, qty = 150.0, 171.3, 2.5
    fill_in = c.fill(raw_in, "buy")
    notional = qty * fill_in
    fee_in = c.fee(notional)
    pos = paper_broker.open_presized_position(
        session, portfolio=pf, symbol="SOLUSDT", timeframe="4h", source="rs_d1", requested_price=raw_in,
        entry_fill=fill_in, qty=qty, notional=notional, fee=fee_in, stop_price=140.0, risk_amount=25.0, spread_bps=1.5,
    )
    paper_broker.close_capital_position(session, pos, price=raw_out, reason="rs_channel")
    fill_out = c.fill(raw_out, "sell")
    expected = qty * fill_out - notional - fee_in - c.fee(qty * fill_out)
    assert pos.exit_price == pytest.approx(fill_out, rel=1e-15)
    assert pos.realized_pnl == pytest.approx(expected, rel=1e-12)
    assert pf.cash == pytest.approx(5000.0 + expected, rel=1e-12)
    assert pos.take_profit_price is None


def _kl(rows):
    def fn(symbol, start_ms, end_ms):
        return [r for r in rows if start_ms <= r[0] < end_ms]
    return fn


def test_rs_lot_without_tp_is_monitored_baseline_without_tp_is_not(session):
    pf = rs_portfolio(session)
    c = cost_profile("paper")["BTCUSDT"]
    entry = datetime(2026, 1, 5, 4, 0, 0, tzinfo=timezone.utc)
    pos = paper_broker.open_presized_position(
        session, portfolio=pf, symbol="BTCUSDT", timeframe="4h", source="rs_d1", requested_price=100.0,
        entry_fill=c.fill(100.0, "buy"), qty=1.0, notional=c.fill(100.0, "buy"), fee=0.0, stop_price=95.0,
        risk_amount=5.0, spread_bps=1.0, at=entry,
    )
    session.commit()
    t0 = int(entry.timestamp() * 1000)
    rows = [[t0 + k * MIN, "100", "101", "96", "100"] for k in range(10)] + [[t0 + 10 * MIN, "100", "100", "94", "95"]]
    row: dict = {}
    protection._process_position(session, pos, row, klines_fn=_kl(rows), trades_fn=None,
                                 now=entry, now_ms=t0 + 12 * MIN, dry_run=False, enforce_legacy=False)
    assert pos.status == "CLOSED" and row["status"] == "closed"
    assert pos.exit_price == pytest.approx(c.fill(95.0, "sell"))

    base = ensure_baseline_portfolio(session)
    legacy = PaperPosition(portfolio_id=base.id, symbol="BTCUSDT", timeframe="1h", source="auto_watchlist",
                           direction="LONG", status="OPEN", entry_time=entry, entry_price=100.0, entry_decision="BUY",
                           qty=1.0, notional=100.0, stop_price=95.0, take_profit_price=None)
    session.add(legacy)
    session.flush()
    row2: dict = {}
    protection._process_position(session, legacy, row2, klines_fn=_kl(rows), trades_fn=None,
                                 now=entry, now_ms=t0 + 12 * MIN, dry_run=True, enforce_legacy=False)
    assert row2["status"] == "unprotected_legacy_no_levels"  # unchanged behaviour outside RS
    session.rollback()


def test_stop_raised_at_close_k_is_never_applied_during_k(session):
    """Complément A: minutes of bar k are checked with the old stop, the raised stop applies from k+1."""
    pf = rs_portfolio(session)
    c = cost_profile("paper")["BTCUSDT"]
    k_open = datetime(2026, 1, 5, 4, 0, tzinfo=timezone.utc)
    k_close_ms = int(k_open.timestamp() * 1000) + BAR_SECONDS * 1000
    pos = paper_broker.open_presized_position(
        session, portfolio=pf, symbol="BTCUSDT", timeframe="4h", source="rs_d1", requested_price=100.0,
        entry_fill=c.fill(100.0, "buy"), qty=1.0, notional=c.fill(100.0, "buy"), fee=0.0, stop_price=90.0,
        risk_amount=10.0, spread_bps=1.0, at=k_open,
    )
    session.commit()
    t0 = int(k_open.timestamp() * 1000)
    # during k: lows at 93 (above the old stop 90, below the new stop 95); during k+1: lows at 96 then 94
    rows = [[t0 + i * MIN, "100", "101", "93" if i == 100 else "99", "100"] for i in range(240)]
    rows += [[k_close_ms + i * MIN, "100", "101", "96", "100"] for i in range(10)]
    rows += [[k_close_ms + 10 * MIN, "100", "100", "94", "95"]]
    fn = _kl(rows)
    # runner at the close of k: scan through the close with the stop in force during k (90) ...
    rep = protection.scan_position_through(session, pos, datetime.fromtimestamp(k_close_ms / 1000, timezone.utc), klines_fn=fn, trades_fn=None)
    assert pos.status == "OPEN" and rep["pinned_through_ms"] == k_close_ms
    # ... then raise the stop to 95 (after the close)
    pos.stop_price = 95.0
    session.commit()
    # the monitor later never re-reads minutes of k with the raised stop (low 93 at minute 100 of k)
    row: dict = {}
    protection._process_position(session, pos, row, klines_fn=fn, trades_fn=None,
                                 now=datetime.now(timezone.utc), now_ms=k_close_ms + 5 * MIN, dry_run=False, enforce_legacy=False)
    assert pos.status == "OPEN"
    row = {}
    protection._process_position(session, pos, row, klines_fn=fn, trades_fn=None,
                                 now=datetime.now(timezone.utc), now_ms=k_close_ms + 12 * MIN, dry_run=False, enforce_legacy=False)
    assert pos.status == "CLOSED" and pos.exit_price == pytest.approx(c.fill(95.0, "sell"))


# --- runner: start-up, trailing stop, stale / late ---------------------------------------------------------

def test_startup_is_empty_and_never_retroactive(session):
    pf = rs_portfolio(session)
    bars = flat_then_breakout(extra=[(100, 112, 99, 111)] + [(111, 113, 110, 112)] * 3)
    src = FakeSource({"BTCUSDT": bars})
    runner = RsD1Runner(src, code=pf.code, symbols=["BTCUSDT"], klines_1m_fn=no_klines, trades_fn=None, history_start=T0)
    # created in the middle of the last bar: the breakout bar and all earlier bars are history, never decided
    now = at(bars[-1].time + 60)
    rep = runner.cycle(session, now=now)
    assert rep.processed_bars == [] and open_rs_positions(session, pf) == []
    st = session.get(RsBookState, pf.code)
    assert st.last_bar_time == bars[-2].time
    assert journal(session, pf, "RS_CYCLE")[0].payload["event"] == "created"


def test_trailing_stop_written_after_close(session):
    pf = rs_portfolio(session)
    extra = [(100, 112, 99, 111), (111, 113, 110.5, 112), (112, 125, 111.5, 124), (124, 126, 123, 125)]
    bars = flat_then_breakout(extra=extra)
    src = FakeSource({"BTCUSDT": bars})
    runner = RsD1Runner(src, code=pf.code, symbols=["BTCUSDT"], klines_1m_fn=no_klines, trades_fn=None,
                        history_start=T0, replay_score_start=T0)
    for b in bars[:-1]:
        runner.cycle(session, now=at(b.time + BAR_SECONDS + 1))
    pos = open_rs_positions(session, pf)[0]
    book = runner._cache[2]
    assert pos.stop_price == pytest.approx(book.positions["BTCUSDT"].stop)
    moves = journal(session, pf, "RS_TRAIL_STOP")
    assert moves and all(m.payload["to"] >= m.payload["from"] for m in moves)
    # each move is recorded at the close of its bar (never inside it)
    assert all(m.created_at.timestamp() == m.payload["bar"] + BAR_SECONDS for m in moves)


def test_stale_entry_cancelled_and_late_exit_executed(session):
    pf = rs_portfolio(session)
    extra = [(100, 112, 99, 111), (111, 113, 110, 112), (112, 113, 111, 112)]
    bars = flat_then_breakout(extra=extra)
    src = FakeSource({"BTCUSDT": bars})
    runner = RsD1Runner(src, code=pf.code, symbols=["BTCUSDT"], klines_1m_fn=no_klines, trades_fn=None,
                        history_start=T0, replay_score_start=T0)
    brk = bars[80].time
    for b in bars[:80]:
        runner.cycle(session, now=at(b.time + BAR_SECONDS + 1))
    # close of the breakout bar processed, but the runner is "down" during the whole next bar:
    # the next cycle only happens after that bar has closed -> the entry is stale and cancelled
    runner._cache = None
    runner.source = FakeSource({"BTCUSDT": bars[:81]})
    runner.cycle(session, now=at(brk + BAR_SECONDS - 1))  # nothing closed yet at this instant
    runner.source = src
    runner.cycle(session, now=at(brk + 2 * BAR_SECONDS + 1))
    # the decision was taken at the close of the breakout bar, its execution bar then closed unfilled
    reasons = [e.payload.get("reason") for e in journal(session, pf, "RS_REJECTED")]
    assert "stale_entry" in reasons
    assert open_rs_positions(session, pf) == []
    assert [e.payload["order"] for e in journal(session, pf, "RS_DECISION")] == ["entry_ordered"]


def test_late_exit_executed_at_first_available_price(session):
    pf = rs_portfolio(session)
    extra = [(100, 112, 99, 111), (111, 113, 110.5, 112), (112, 113, 111, 112), (112, 113, 111, 112), (112, 113, 111, 112)]
    bars = flat_then_breakout(extra=extra)
    src = FakeSource({"BTCUSDT": bars})
    runner = RsD1Runner(src, code=pf.code, symbols=["BTCUSDT"], klines_1m_fn=no_klines, trades_fn=None,
                        history_start=T0, replay_score_start=T0)
    for b in bars[:82]:  # entry filled at the open of bar 81
        runner.cycle(session, now=at(b.time + BAR_SECONDS + 1))
    assert len(open_rs_positions(session, pf)) == 1
    # a channel exit decided at the close of bar 81 (forced in the persisted state), then the runner is down
    # for the whole execution bar 82
    st = session.get(RsBookState, pf.code)
    meta = dict(st.state_json)
    book = dict(meta["book"])
    book["pending_exit"] = {"BTCUSDT": 82}
    meta["book"] = book
    st.state_json = meta
    session.commit()
    runner._cache = None
    now = at(bars[82].time + BAR_SECONDS + 30)
    runner.cycle(session, now=now)
    assert open_rs_positions(session, pf) == []
    closed = session.execute(select(PaperPosition).where(PaperPosition.portfolio_id == pf.id)).scalars().one()
    c = cost_profile("paper")["BTCUSDT"]
    assert closed.exit_price == pytest.approx(c.fill(src.last_price("BTCUSDT", now), "sell"))
    assert closed.exit_signal["rs_d1"]["late_fill"] is True


def test_book_state_roundtrip_and_incremental_market_identical():
    bars = flat_then_breakout(extra=[(100, 112, 99, 111), (111, 113, 110.5, 112), (112, 125, 111.5, 124)])
    full = Book({"BTCUSDT": bars}, cost_profile("paper"), initial=5000.0, score_start=T0, seed=7)
    inc = Book({"BTCUSDT": bars[:60]}, cost_profile("paper"), initial=5000.0, score_start=T0, seed=7)
    inc.extend_market({"BTCUSDT": bars[60:70]})
    inc.extend_market({"BTCUSDT": bars[70:]})
    assert inc.upper == full.upper and inc.lower == full.lower and inc.atr == full.atr
    for t in [b.time for b in bars[:-1]]:
        full.step(t)
    clone = Book({"BTCUSDT": bars}, cost_profile("paper"), initial=0.0, score_start=T0, seed=1)
    clone.load_state(full.state_dict())
    t_last = bars[-1].time
    n_before = len(full.trades)
    full.step(t_last)
    clone.step(t_last)
    assert clone.state_dict() == full.state_dict()  # includes the random generator state
    assert clone.trades == full.trades[n_before:]
