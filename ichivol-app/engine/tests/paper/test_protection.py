"""Protection monitor: post-entry crossings only, prudent ordering, legacy safety."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.brokerage import persistence as ledger_db
from app.db.models import (
    LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperOrder, PaperPartialExit,
    PaperPortfolio, PaperPosition, PaperReinforceAdd,
)
from app.db.session import SessionLocal, engine
from app.paper import broker
from app.paper.protection import CHECK_EVENT, find_first_breach, find_breach_with_trail, run_protection_cycle
from app.paper.protection_partial_tp import PARTIAL_TP_KEY, resolve_paper_partial_tp
from app.paper.protection_reinforce import REINFORCE_KEY, resolve_paper_reinforce
from app.paper.protection_trail import (
    TRAIL_EVENT,
    TRAIL_KEY,
    PaperTrailConfig,
    resolve_paper_trail,
)
from app.strategy_lab.reinforce import open_risk
from app.strategy_lab.stop_trail import TrailSpec, breakeven_price

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
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperReinforceAdd, PaperPartialExit, PaperPosition):
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
    by_id = {r["id"]: r for r in rep}
    assert by_id[pos.id]["status"] == "closed"
    assert pos.status == "CLOSED" and pos.exit_reason == "take_profit_hit"
    assert int(pos.exit_time.timestamp() * 1000) == m1 + M  # timestamped at the breach, not at run time
    assert ledger_db.is_reconciled(session, p)
    # idempotent: a second run has nothing to do for this lot
    assert pos.id not in {r["id"] for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now)}


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
    dry_row = next(r for r in dry if r["id"] == pos.id)
    assert dry_row["status"] == "legacy_watermark_initialised" and dry_row["history_breach"]["reason"] == "take_profit_hit"
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=CHECK_EVENT).count() == 0  # dry run wrote nothing

    live = run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now)
    live_row = next(r for r in live if r["id"] == pos.id)
    assert live_row["status"] == "legacy_watermark_initialised"
    assert pos.status == "OPEN"  # history is reported, never acted on
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=CHECK_EVENT).count() == 1

    # from the watermark on, a NEW breach is enforced
    bars2 = [kline(int(now.timestamp() * 1000) - int(now.timestamp() * 1000) % M + 2 * M, 80000, 80100, 78900, 79000)]
    k2, t2 = _fetchers(bars2)
    later = datetime.fromtimestamp(now.timestamp() + 10 * 60, timezone.utc)
    r2 = next(r for r in run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=later) if r["id"] == pos.id)
    # legacy lots are report-only by default: a later breach is reported, never enforced
    assert r2["status"] == "legacy_report_only" and r2["breach"]["reason"] == "stop_hit" and pos.status == "OPEN"
    r3 = next(r for r in run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=later, enforce_legacy=True) if r["id"] == pos.id)
    assert r3["status"] == "closed" and pos.exit_reason == "stop_hit"


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
    rep = {r["id"]: r for r in run_protection_cycle(session, klines_fn=klines, trades_fn=lambda *a: [], now=now)}
    statuses = sorted(rep[pid]["status"] for pid in (btc.id, eth.id))
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
    rep = next(r for r in run_protection_cycle(session, klines_fn=lambda *a: [], trades_fn=lambda *a: [], now=now) if r["id"] == pos.id)
    assert rep["status"] == "no_data"
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


# ── T0-MANAGE-b — trailing / breakeven (opt-in, user_confirmed) ─────────────


def _trail_scan(klines, *, entry, stop, target, config, since, until, ticks=None):
    k = lambda s, a, b: [x for x in klines if a <= x[0] < b]
    t = (lambda s, a, b: [(ts, p) for ts, p in (ticks or []) if a <= ts < b]) if ticks is not None else (lambda *a: [])
    return find_breach_with_trail(
        "LONG", stop, target, entry=entry, config=config, symbol="X",
        since_ms=since, until_ms=until, klines_fn=k, trades_fn=t,
    )


def test_resolve_paper_trail_gates_user_confirmed_and_explicit_config():
    cfg_raw = {"breakeven_at_r": 1.0, "initial_stop": 79000.0, "atr_ref": 1000.0}
    pos = SimpleNamespace(
        source="user_confirmed",
        entry_price=80000.0,
        stop_price=79000.0,
        entry_signal={TRAIL_KEY: cfg_raw},
    )
    assert resolve_paper_trail(pos, None) is not None

    auto = SimpleNamespace(
        source="auto_watchlist",
        entry_price=80000.0,
        stop_price=79000.0,
        entry_signal={TRAIL_KEY: cfg_raw},
    )
    assert resolve_paper_trail(auto, None) is None

    bare = SimpleNamespace(
        source="user_confirmed",
        entry_price=80000.0,
        stop_price=79000.0,
        entry_signal={},
    )
    assert resolve_paper_trail(bare, SimpleNamespace(strategy_profile={})) is None

    from_pf = SimpleNamespace(
        source="user_confirmed",
        entry_price=80000.0,
        stop_price=79000.0,
        entry_signal={},
    )
    pf = SimpleNamespace(strategy_profile={TRAIL_KEY: {"breakeven_at_r": 1.0}})
    got = resolve_paper_trail(from_pf, pf)
    assert got is not None and got.trail.breakeven_at_r == 1.0


def test_find_breach_with_trail_arms_breakeven_next_bar_only():
    """1R on bar N arms BE after checks; same-bar dip to BE does not exit; next bar does."""
    entry, stop, target = 80000.0, 79000.0, 85000.0
    be = breakeven_price(Direction.LONG, entry, commission_bps=5.0, slippage_bps=3.0)
    cfg = PaperTrailConfig(
        trail=TrailSpec(breakeven_at_r=1.0),
        initial_stop=stop,
        atr_ref=1000.0,
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    since = T0 + M
    # Bar1: exactly 1R high, low dips through BE — must NOT close at BE same bar
    # Bar2: low through BE → stop at BE
    kl = [
        kline(since, 80000, 81000, be - 50, 80900),
        kline(since + M, 80900, 80950, be - 10, 80200),
    ]
    scan, final_stop = _trail_scan(
        kl, entry=entry, stop=stop, target=target, config=cfg,
        since=since, until=since + 3 * M,
    )
    assert scan.breach is not None
    assert scan.breach.reason == "stop_hit"
    assert scan.breach.time_ms == since + M
    assert scan.breach.price == pytest.approx(be)
    assert final_stop == pytest.approx(be)

    # Without trail the second-bar low never hits the initial stop
    plain = find_first_breach(
        "LONG", stop, target, symbol="X", since_ms=since, until_ms=since + 3 * M,
        klines_fn=lambda s, a, b: [x for x in kl if a <= x[0] < b],
        trades_fn=lambda *a: [],
    )
    assert plain.breach is None


def test_find_breach_with_trail_never_relaxes_stop():
    entry, stop, target = 80000.0, 79000.0, 85000.0
    cfg = PaperTrailConfig(
        trail=TrailSpec(atr_trail_mult=1.0),
        initial_stop=stop,
        atr_ref=1000.0,
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    since = T0 + M
    # Bar1 close 82000 → trail candidate 81000; bar2 close 80500 → candidate 79500 but ratchet keeps 81000
    kl = [
        kline(since, 80000, 82100, 79900, 82000),
        kline(since + M, 82000, 82100, 80400, 80500),
        kline(since + 2 * M, 80500, 80600, 80950, 80980),  # low 80950 < 81000 → stop
    ]
    scan, final_stop = _trail_scan(
        kl, entry=entry, stop=stop, target=target, config=cfg,
        since=since, until=since + 4 * M,
    )
    assert scan.breach is not None
    assert scan.breach.reason == "stop_hit"
    assert scan.breach.price == pytest.approx(81000.0)
    assert final_stop == pytest.approx(81000.0)


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_user_confirmed_portfolio_trail_ratchets_then_closes_at_breakeven(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        TRAIL_KEY: {"breakeven_at_r": 1.0, "commission_bps": 5.0, "slippage_bps": 3.0},
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    be = breakeven_price(Direction.LONG, entry, commission_bps=5.0, slippage_bps=3.0)
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M

    # Cycle 1: +1R bar arms BE and persists stop (watermark advanced)
    bars1 = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.9)]
    k1, t1 = _fetchers(bars1)
    now1 = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep1 = next(r for r in run_protection_cycle(session, klines_fn=k1, trades_fn=t1, now=now1) if r["id"] == pos.id)
    assert rep1["status"] == "ok"
    assert rep1["trail_stop"]["to"] == pytest.approx(be)
    assert float(pos.stop_price) == pytest.approx(be)
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=TRAIL_EVENT).count() == 1
    assert (pos.entry_signal or {}).get(TRAIL_KEY, {}).get("initial_stop") == pytest.approx(stop0)

    # Cycle 2: dip through BE → close at BE (no re-walk of bar1 against new stop)
    bars2 = [kline(m1 + M, entry + risk * 0.9, entry + risk * 0.95, be - 20, be + 10)]
    k2, t2 = _fetchers(bars2)
    now2 = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep2 = next(r for r in run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=now2) if r["id"] == pos.id)
    assert rep2["status"] == "closed"
    assert pos.status == "CLOSED" and pos.exit_reason == "stop_hit"
    assert rep2["breach"]["price"] == pytest.approx(be)
    # exit_price includes paper exit friction on top of the trigger level
    assert float(pos.exit_price) < be


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_auto_watchlist_ignores_portfolio_trail(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        TRAIL_KEY: {"breakeven_at_r": 1.0},
    }
    session.flush()
    pos = _open(session, source="auto_watchlist")
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    be = breakeven_price(Direction.LONG, entry, commission_bps=5.0, slippage_bps=3.0)
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [
        kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.9),
        kline(m1 + M, entry + risk * 0.9, entry + risk * 0.95, be - 20, be + 10),
    ]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = next(r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id)
    assert rep["status"] == "ok"
    assert pos.status == "OPEN"
    assert float(pos.stop_price) == pytest.approx(stop0)
    assert session.query(PaperJournalEvent).filter_by(position_id=pos.id, event_type=TRAIL_EVENT).count() == 0


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_user_confirmed_without_trail_config_unchanged(session):
    pos = _open(session, source="user_confirmed")
    stop0 = float(pos.stop_price)
    entry = float(pos.entry_price)
    risk = entry - stop0
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, entry, entry + risk, entry - 50, entry + 100)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = next(r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id)
    assert rep["status"] == "ok"
    assert float(pos.stop_price) == pytest.approx(stop0)
    assert "trail_stop" not in rep


# ── T0-MANAGE-d — partial take-profit (opt-in, user_confirmed) ──────────────


def test_resolve_paper_partial_tp_gates():
    steps = [{"r_multiple": 1.0, "fraction": 0.5}]
    pos = SimpleNamespace(
        source="user_confirmed",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        entry_signal={PARTIAL_TP_KEY: {"steps": steps}},
    )
    assert resolve_paper_partial_tp(pos, None) is not None
    auto = SimpleNamespace(
        source="auto_watchlist",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        entry_signal={PARTIAL_TP_KEY: {"steps": steps}},
    )
    assert resolve_paper_partial_tp(auto, None) is None
    bare = SimpleNamespace(
        source="user_confirmed",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        entry_signal={},
    )
    assert resolve_paper_partial_tp(bare, SimpleNamespace(strategy_profile={})) is None


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_partial_tp_scales_qty_then_final_close_settles_remainder(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        PARTIAL_TP_KEY: {"steps": [{"r_multiple": 1.0, "fraction": 0.5}]},
        "take_profit_r": 3.0,
    }
    session.flush()
    cash0 = float(p.cash)
    pos = _open(session, source="user_confirmed")
    entry_fee0 = float(pos.entry_fee or 0.0)
    assert float(pos.initial_entry_fee) == pytest.approx(entry_fee0)
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    initial_qty = float(pos.qty)
    target = float(pos.take_profit_price)
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M

    # Cycle 1: +1R → partial 50%
    bars1 = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k1, t1 = _fetchers(bars1)
    now1 = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep1 = next(r for r in run_protection_cycle(session, klines_fn=k1, trades_fn=t1, now=now1) if r["id"] == pos.id)
    assert rep1["status"] == "partialed"
    assert pos.status == "OPEN"
    assert float(pos.qty) == pytest.approx(initial_qty * 0.5)
    assert float(pos.qty) > 0
    assert float(pos.entry_fee) == pytest.approx(entry_fee0 * 0.5)
    exits = session.query(PaperPartialExit).filter_by(position_id=pos.id).order_by(PaperPartialExit.seq).all()
    assert len(exits) == 1
    assert exits[0].qty == pytest.approx(initial_qty * 0.5)
    assert exits[0].r_multiple == pytest.approx(1.0)
    partial_pnl = float(pos.realized_pnl or 0.0)
    assert partial_pnl != 0.0

    # Cycle 2: hit target on remainder
    bars2 = [kline(m1 + M, entry + risk * 0.8, target + 10, entry + risk * 0.7, target)]
    k2, t2 = _fetchers(bars2)
    now2 = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep2 = next(r for r in run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=now2) if r["id"] == pos.id)
    assert rep2["status"] == "closed"
    assert pos.status == "CLOSED"
    assert float(pos.initial_qty) == pytest.approx(initial_qty)
    assert float(pos.qty) == pytest.approx(initial_qty)  # restored entry size after CLOSE
    assert float(pos.initial_entry_fee) == pytest.approx(entry_fee0)
    assert float(pos.entry_fee) == pytest.approx(entry_fee0)  # restored like qty
    assert session.query(PaperPartialExit).filter_by(position_id=pos.id).count() == 1
    # LONG, no financing: cash delta from pre-open == cumulative realized.
    assert float(p.cash) - cash0 == pytest.approx(float(pos.realized_pnl))
    assert abs(float(pos.realized_pnl)) >= abs(partial_pnl) - 1e-6


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_partial_tp_steps_sum_one_deducts_financing_on_exhaustion(session):
    """Steps summing to 1 exhaust via close_capital_position; financing hits realized."""
    from datetime import date

    from app.paper.financing import apply_daily_financing, financing_total_for_position

    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        "financing_bps_per_day_crypto": 10.0,  # force non-zero on BTCUSDT
        PARTIAL_TP_KEY: {
            "steps": [
                {"r_multiple": 1.0, "fraction": 0.5},
                {"r_multiple": 2.0, "fraction": 0.5},
            ]
        },
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    entry_fee0 = float(pos.entry_fee or 0.0)
    remaining = float(pos.qty)
    entry = float(pos.entry_price)
    notional0 = float(pos.notional or 0.0)

    fin = apply_daily_financing(
        session,
        p,
        as_of=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc),
        force_day=date(2026, 9, 24),
    )
    session.flush()
    assert len(fin) == 1
    financed = financing_total_for_position(session, pos.id)
    assert financed > 0
    assert financed == pytest.approx(notional0 * (10.0 / 10_000.0))

    half = remaining * 0.5
    r1 = broker.partial_close_capital_position(
        session,
        pos,
        price=entry * 1.01,
        qty=half,
        fraction=0.5,
        r_multiple=1.0,
    )
    assert r1 is not None and pos.status == "OPEN"
    # First slice: no financing yet (deferred to final close).
    assert float(r1.realized_pnl) == pytest.approx(
        half * (entry * 1.01) - (notional0 * 0.5) - (entry_fee0 * 0.5)
    )

    r2 = broker.partial_close_capital_position(
        session,
        pos,
        price=entry * 1.02,
        qty=half,
        fraction=0.5,
        r_multiple=2.0,
    )
    assert r2 is not None and pos.status == "CLOSED"
    assert float(pos.entry_fee) == pytest.approx(entry_fee0)
    assert float(pos.qty) == pytest.approx(remaining)
    session.flush()
    assert session.query(PaperPartialExit).filter_by(position_id=pos.id).count() == 2
    # Exhausting slice settles via close_capital_position → financing deducted once.
    assert float(r2.realized_pnl) == pytest.approx(
        half * (entry * 1.02) - (notional0 * 0.5) - (entry_fee0 * 0.5) - financed
    )
    assert float(pos.realized_pnl) == pytest.approx(
        float(r1.realized_pnl) + float(r2.realized_pnl)
    )


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_partial_tp_never_negative_qty(session):
    pos = _open(session, source="user_confirmed")
    with pytest.raises(ValueError, match="exceeds remaining"):
        broker.partial_close_capital_position(
            session,
            pos,
            price=float(pos.entry_price) * 1.01,
            qty=float(pos.qty) + 1.0,
            fraction=0.5,
            r_multiple=1.0,
        )


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_auto_watchlist_ignores_portfolio_partial_tp(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        PARTIAL_TP_KEY: {"steps": [{"r_multiple": 1.0, "fraction": 0.5}]},
    }
    session.flush()
    pos = _open(session, source="auto_watchlist")
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    qty0 = float(pos.qty)
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = next(r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id)
    assert rep["status"] == "ok"
    assert float(pos.qty) == pytest.approx(qty0)
    assert session.query(PaperPartialExit).filter_by(position_id=pos.id).count() == 0


def test_resolve_paper_reinforce_gates():
    blob = {
        "add_fraction": 0.5,
        "at_r_multiple": 1.0,
        "max_adds": 1,
        "max_exposure": 2.0,
    }
    pos = SimpleNamespace(
        source="user_confirmed",
        direction="LONG",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        initial_qty=0.1,
        entry_signal={REINFORCE_KEY: blob},
    )
    cfg = resolve_paper_reinforce(pos, None)
    assert cfg is not None
    assert cfg.max_exposure == 2.0
    assert cfg.risk_policy == "tighten_stop"
    assert cfg.initial_risk == pytest.approx(100.0)  # (80000-79000)*0.1

    auto = SimpleNamespace(
        source="auto_watchlist",
        direction="LONG",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        initial_qty=0.1,
        entry_signal={REINFORCE_KEY: blob},
    )
    assert resolve_paper_reinforce(auto, None) is None

    # Mutual exclusion with partial_tp
    both = SimpleNamespace(
        source="user_confirmed",
        direction="LONG",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        initial_qty=0.1,
        entry_signal={
            REINFORCE_KEY: blob,
            PARTIAL_TP_KEY: {"steps": [{"r_multiple": 1.0, "fraction": 0.5}]},
        },
    )
    assert resolve_paper_reinforce(both, None) is None

    # Default max_exposure 1.0 still resolves (broker/cap blocks the add)
    bare = SimpleNamespace(
        source="user_confirmed",
        direction="LONG",
        entry_price=80000.0,
        stop_price=79000.0,
        qty=0.1,
        initial_qty=0.1,
        entry_signal={
            REINFORCE_KEY: {"add_fraction": 0.5, "at_r_multiple": 1.0},
        },
    )
    cfg2 = resolve_paper_reinforce(bare, None)
    assert cfg2 is not None and cfg2.max_exposure == 1.0


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_reinforce_adds_at_r_tightens_stop_keeps_risk_le_r0(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        REINFORCE_KEY: {
            "add_fraction": 0.5,
            "at_r_multiple": 1.0,
            "max_adds": 1,
            "max_exposure": 2.0,
            "risk_policy": "tighten_stop",
        },
        "take_profit_r": 3.0,
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    qty0 = float(pos.qty)
    r0 = open_risk(Direction.LONG, entry, stop0, qty0)
    risk = entry - stop0
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M

    bars = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep = next(
        r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id
    )
    assert rep["status"] == "reinforced"
    assert pos.status == "OPEN"
    assert float(pos.qty) == pytest.approx(qty0 * 1.5)
    assert float(pos.stop_price) > stop0  # tightened toward avg
    adds = session.query(PaperReinforceAdd).filter_by(position_id=pos.id).order_by(PaperReinforceAdd.seq).all()
    assert len(adds) == 1
    assert adds[0].r_multiple == pytest.approx(1.0)
    live_risk = open_risk(
        Direction.LONG, float(pos.entry_price), float(pos.stop_price), float(pos.qty)
    )
    assert live_risk <= r0 + 1e-6
    assert adds[0].open_risk_after == pytest.approx(live_risk)

    # Rising-edge latch: still above 1R next cycle → no second add
    bars2 = [kline(m1 + M, entry + risk * 0.8, entry + risk * 1.1, entry + risk * 0.7, entry + risk)]
    k2, t2 = _fetchers(bars2)
    now2 = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep2 = next(
        r for r in run_protection_cycle(session, klines_fn=k2, trades_fn=t2, now=now2) if r["id"] == pos.id
    )
    assert rep2["status"] == "ok"
    assert session.query(PaperReinforceAdd).filter_by(position_id=pos.id).count() == 1


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_reinforce_default_max_exposure_blocks_add(session):
    """max_exposure default 1.0 → headroom 0 when fully sized → refuse."""
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        REINFORCE_KEY: {
            "add_fraction": 0.5,
            "at_r_multiple": 1.0,
            "max_adds": 1,
            # max_exposure omitted → 1.0
        },
        "take_profit_r": 3.0,
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    qty0 = float(pos.qty)
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep = next(
        r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id
    )
    assert rep["status"] == "ok"
    assert float(pos.qty) == pytest.approx(qty0)
    assert session.query(PaperReinforceAdd).filter_by(position_id=pos.id).count() == 0


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_reinforce_refuses_when_cash_insufficient(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        REINFORCE_KEY: {
            "add_fraction": 0.5,
            "at_r_multiple": 1.0,
            "max_adds": 1,
            "max_exposure": 2.0,
        },
        "take_profit_r": 3.0,
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    qty0 = float(pos.qty)
    # Drain cash so add cannot fund.
    p.cash = 0.01
    session.flush()
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep = next(
        r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id
    )
    # Discover may list reinforce, but broker refuse → qty unchanged
    assert float(pos.qty) == pytest.approx(qty0)
    assert session.query(PaperReinforceAdd).filter_by(position_id=pos.id).count() == 0
    assert pos.status == "OPEN"
    assert rep.get("reinforces_applied", 0) == 0
    assert rep["status"] == "ok"


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_stop_beats_reinforce_same_bar(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "spread_bps": 0.0,
        REINFORCE_KEY: {
            "add_fraction": 0.5,
            "at_r_multiple": 1.0,
            "max_adds": 1,
            "max_exposure": 2.0,
        },
        "take_profit_r": 3.0,
    }
    session.flush()
    pos = _open(session, source="user_confirmed")
    qty0 = float(pos.qty)
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    # Same bar: high reaches +1R AND low pierces stop → stop wins, no add
    bars = [kline(m1, entry, entry + risk, stop0 - 10, entry)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 2 * M) / 1000, timezone.utc)
    rep = next(
        r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id
    )
    assert rep["status"] == "closed"
    assert pos.exit_reason in ("stop_hit", "stop_gap")
    assert session.query(PaperReinforceAdd).filter_by(position_id=pos.id).count() == 0
    # qty restored to entry size on CLOSE
    assert float(pos.qty) == pytest.approx(qty0)


@pytest.mark.skipif(not DB, reason="Postgres not reachable")
def test_auto_watchlist_ignores_portfolio_reinforce(session):
    p = session.info["p"]
    p.strategy_profile = {
        **p.strategy_profile,
        REINFORCE_KEY: {
            "add_fraction": 0.5,
            "at_r_multiple": 1.0,
            "max_exposure": 2.0,
        },
    }
    session.flush()
    pos = _open(session, source="auto_watchlist")
    entry = float(pos.entry_price)
    stop0 = float(pos.stop_price)
    risk = entry - stop0
    qty0 = float(pos.qty)
    entry_ms = int(pos.entry_time.timestamp() * 1000)
    m1 = entry_ms - entry_ms % M + M
    bars = [kline(m1, entry, entry + risk, entry - 50, entry + risk * 0.8)]
    k, t = _fetchers(bars)
    now = datetime.fromtimestamp((m1 + 5 * M) / 1000, timezone.utc)
    rep = next(
        r for r in run_protection_cycle(session, klines_fn=k, trades_fn=t, now=now) if r["id"] == pos.id
    )
    assert rep["status"] == "ok"
    assert float(pos.qty) == pytest.approx(qty0)
    assert session.query(PaperReinforceAdd).filter_by(position_id=pos.id).count() == 0
