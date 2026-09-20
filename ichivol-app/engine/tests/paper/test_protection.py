"""Protection monitor: post-entry crossings only, prudent ordering, legacy safety."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.brokerage import persistence as ledger_db
from app.db.models import (
    LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.paper import broker
from app.paper.protection import CHECK_EVENT, find_first_breach, run_protection_cycle

M = 60_000
T0 = int(datetime(2026, 9, 18, 20, 38, tzinfo=timezone.utc).timestamp() * 1000)
ENTRY = T0 + 49_456  # 20:38:49.456 -- mid-minute, like the real APT lot


def kline(open_ms, o, h, l, c):
    return [open_ms, str(o), str(h), str(l), str(c), "1", open_ms + M - 1]


def scan(klines, ticks=None, *, since=ENTRY, until=T0 + 60 * M, trades=True, stop=0.703, target=0.779, direction="LONG"):
    k = lambda s, a, b: [x for x in klines if a <= x[0] < b]
    t = (lambda s, a, b: [(ts, p) for ts, p in (ticks or []) if a <= ts < b]) if trades else None
    return find_first_breach(direction, stop, target, symbol="X", since_ms=since, until_ms=until, klines_fn=k, trades_fn=t)


def test_pre_entry_high_in_entry_minute_is_ignored():
    # The entry-minute candle's high (0.80) may have printed BEFORE the fill: only ticks after entry count.
    kl = [kline(T0, 0.728, 0.80, 0.727, 0.729)]
    ticks = [(T0 + 10_000, 0.80), (ENTRY + 1000, 0.728), (ENTRY + 5000, 0.729)]  # 0.80 tick is pre-entry
    assert scan(kl, ticks).breach is None


def test_target_after_entry_detected_with_time():
    kl = [kline(T0 + M * i, 0.729, 0.730, 0.728, 0.729) for i in range(1, 5)] + [kline(T0 + 5 * M, 0.775, 0.782, 0.766, 0.78)]
    r = scan(kl)
    assert r.breach.reason == "take_profit_hit" and r.breach.time_ms == T0 + 5 * M and r.breach.granularity == "1m"


def test_gap_through_stop_fills_at_open():
    kl = [kline(T0 + M, 0.729, 0.73, 0.728, 0.729), kline(T0 + 2 * M, 0.690, 0.692, 0.68, 0.685)]
    b = scan(kl).breach
    assert b.reason == "stop_gap" and b.price == 0.690


def test_both_levels_same_minute_uses_ticks_when_available_else_stop_first():
    kl = [kline(T0 + M, 0.73, 0.78, 0.70, 0.74)]
    ticks = [(T0 + M + 1000, 0.779), (T0 + M + 2000, 0.702)]  # target first
    assert scan(kl, ticks).breach.reason == "take_profit_hit"
    b = scan(kl, None, trades=False).breach
    assert b.reason == "stop_hit" and "conservative" in b.note


def test_forming_minute_is_not_scanned():
    kl = [kline(T0 + M, 0.73, 0.78, 0.73, 0.78)]
    assert scan(kl, until=T0 + M + 30_000).breach is None  # minute not closed yet


# ── DB cycle ────────────────────────────────────────────────────────────────

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False


@pytest.fixture()
def session():
    s = SessionLocal()
    p = PaperPortfolio(
        code=f"PROT_{uuid.uuid4().hex[:8]}", label="t", currency="EUR", initial_cash=5000.0, cash=5000.0,
        strategy_profile={"risk_pct": 0.01, "take_profit_r": 2.0, "max_notional_pct": 0.25, "max_open_positions": 5},
    )
    s.add(p)
    s.flush()
    s.info["p"] = p
    yield s
    pid = p.id
    s.rollback()
    s.query(LedgerLeg).filter(LedgerLeg.transaction_id.in_(s.query(LedgerTransaction.id).filter_by(portfolio_id=pid))).delete(synchronize_session=False)
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
        s.query(m).filter_by(portfolio_id=pid).delete()
    s.query(PaperPortfolio).filter_by(id=pid).delete()
    s.commit()
    s.close()


def _open(s, source="user_confirmed"):
    return broker.open_capital_position(
        s, portfolio=s.info["p"], symbol="BTCUSDT", timeframe="1h", source=source, user_id=None,
        direction="LONG", price=80000.0, decision="BUY", stop_distance=1000.0,
    )


def _fetchers(bars):
    k = lambda s, a, b: [x for x in bars if a <= x[0] < b]
    return k, (lambda s, a, b: [])


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_monitored_user_confirmed_position_closed_at_breach_time_and_reconciles(session):
    p = session.info["p"]
    pos = _open(session)  # source user_confirmed: protections apply regardless of source
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, 80000, 80100, 79900, 80050), kline(m1 + M, 80050, 82600, 80000, 82500)]  # target 82004ish
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now)
    assert [r["status"] for r in rep] == ["closed"]
    assert pos.status == "CLOSED" and pos.exit_reason == "take_profit_hit"
    assert int(pos.exit_time.timestamp() * 1000) == m1 + M  # timestamped at the breach, not at run time
    assert ledger_db.is_reconciled(session, p)
    # idempotent: a second run has nothing to do
    assert run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) == []


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_legacy_position_is_never_closed_from_history_but_breach_is_reported(session):
    p = session.info["p"]
    pos = _open(session)
    # make it legacy: strip the monitoring declaration from its OPENED event
    session.flush()
    ev = session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type="OPENED").one()
    ev.payload = {k: v for k, v in ev.payload.items() if k != "protection_monitored"}
    session.flush()
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, 80000, 83000, 79900, 82900)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)

    dry = run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now, dry_run=True)
    assert dry[0]["status"] == "legacy_watermark_initialised" and dry[0]["history_breach"]["reason"] == "take_profit_hit"
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=CHECK_EVENT).count() == 0  # dry run wrote nothing

    live = run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now)
    assert live[0]["status"] == "legacy_watermark_initialised"
    assert pos.status == "OPEN"  # history is reported, never acted on
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=CHECK_EVENT).count() == 1

    # from the watermark on, a NEW breach is enforced
    bars2 = [kline(int(now.timestamp() * 1000) - int(now.timestamp() * 1000) % M + 2 * M, 80000, 80100, 78900, 79000)]
    k2, t2 = _fetchers(bars2)
    later = datetime.fromtimestamp(now.timestamp() + 10 * 60, timezone.utc)
    r2 = run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=later)
    # legacy lots are report-only by default: a later breach is reported, never enforced
    assert r2[0]["status"] == "legacy_report_only" and r2[0]["breach"]["reason"] == "stop_hit" and pos.status == "OPEN"
    r3 = run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=later, enforce_legacy=True)
    assert r3[0]["status"] == "closed" and pos.exit_reason == "stop_hit"


def _open_sym(s, symbol):
    return broker.open_capital_position(
        s, portfolio=s.info["p"], symbol=symbol, timeframe="1h", source="auto_watchlist", user_id=None,
        direction="LONG", price=80000.0 if symbol == "BTCUSDT" else 2600.0, decision="BUY",
        stop_distance=1000.0 if symbol == "BTCUSDT" else 40.0,
    )


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_one_failing_symbol_does_not_abort_or_roll_back_the_others(session):
    btc, eth = _open_sym(session, "BTCUSDT"), _open_sym(session, "ETHUSDT")
    session.commit()
    m1 = int(btc.entry_time.timestamp() * 1000) // M * M + M
    ok_bars = [kline(m1, 2600, 2900, 2590, 2850)]  # ETH: target hit

    def klines(sym, a, b):
        if sym == "BTCUSDT":
            raise RuntimeError("HTTP 429")
        return [x for x in ok_bars if a <= x[0] < b]

    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = {r["symbol"] if "symbol" in r else r["id"]: r for r in run_protection_cycle(session, klines_fn=klines, trades_fn=lambda *a: [], now=now)}
    statuses = sorted(r["status"] for r in rep.values())
    assert statuses == ["closed", "error"], statuses
    session.expire_all()
    assert session.get(PaperPosition, eth.id).status == "CLOSED"  # committed despite the other failure
    assert session.get(PaperPosition, btc.id).status == "OPEN"


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_no_data_is_not_declared_safe_and_watermark_does_not_advance(session):
    pos = _open_sym(session, "BTCUSDT")
    session.commit()
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    now = datetime.fromtimestamp((entry_ms + 30 * 60_000) / 1000, timezone.utc)
    rep = run_protection_cycle(session, klines_fn=lambda *a: [], trades_fn=lambda *a: [], now=now)
    assert rep[0]["status"] == "no_data"
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=CHECK_EVENT).count() == 0


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_concurrent_close_of_the_same_position_credits_cash_once(session):
    """Regression (review H1): a stale object in another session must not credit cash a second time."""
    from app.db.session import SessionLocal as SL

    pos = _open_sym(session, "BTCUSDT")
    session.commit()
    pid, portfolio_id = pos.id, pos.portfolio_id
    s2 = SL()
    try:
        stale = s2.get(PaperPosition, pid)  # session 2 loads the lot while it is still OPEN
        assert stale.status == "OPEN"
        broker.close_capital_position(session, session.get(PaperPosition, pid), price=81000.0, reason="auto_loop")
        session.commit()
        def cash():  # scalar read: does not touch (or expire) the stale ORM object in s2
            return s2.execute(select(PaperPortfolio.cash).where(PaperPortfolio.id == portfolio_id)).scalar_one()

        cash_after_first = cash()
        broker.close_capital_position(s2, stale, price=81000.0, reason="monitor_late")  # stale OPEN object
        s2.commit()
        assert cash() == cash_after_first  # no second credit
        assert s2.execute(select(PaperPosition.exit_reason).where(PaperPosition.id == pid)).scalar_one() == "auto_loop"
        assert s2.query(PaperOrder).filter_by(position_id=pid, side="SELL").count() == 1
    finally:
        s2.close()
