"""RS-D1 paper live — runner of the separate portfolio ``RS_D1_PAPER_V1`` (docs/RS-09-RS-D1-PAPER-DESIGN.md).

Contains **no trading rule**: every decision comes from ``rs.book.Book`` (the same code as the backtest,
RS-03). The runner only
- feeds closed 4h Binance spot bars (BTC / ETH / SOL) to the book, in time order;
- persists the book state (``rs_book_state``);
- mirrors the book's effects into the paper tables (pre-sized opens, closes, stop updates, journal).

Per closed bar ``t`` (same order as ``rs.donchian.simulate``):
  1. pending orders whose execution bar ``t`` is already closed (runner was down): entries are cancelled
     (``stale_entry``), exits are executed at the first available price (``late_fill``);
  2. intrabar stops: the 1-minute protection monitor is run on each RS lot **through the close of t with
     the stop in force during t**, its closes are reconciled into the book, then the book's own 4h-bar
     stop check runs as a fallback (same rule as the backtest);
  3. ``on_close(t)``: trailing stops (written to ``paper_positions.stop_price`` after the close, so they
     apply from t+1 only), channel exit decisions, daily-loss halt;
  4. ``decide(t)``: entries.
Then orders decided at the last close are filled at the **open of the bar in progress** (first price after
the close), exactly ``open(t+1)`` of the backtest.

Start-up: empty book, 5 000; the bar in progress at creation is never decided, no retroactive entry.
Never touches another portfolio, the Ichimoku pipeline, gates or screener; no LLM.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperJournalEvent, PaperOrder, PaperPortfolio, PaperPosition, RsBookState
from app.indicators.ichimoku import Candle
from app.paper import broker as paper_broker
from app.paper import protection
from app.paper.portfolio import ensure_portfolio
from app.paper.strategy_profiles import RS_D1_CODE
from rs import BAR_SECONDS, SEED, SYMBOLS
from rs.book import Book, Event
from rs.costs import cost_profile

logger = logging.getLogger(__name__)

TIMEFRAME = "4h"
SOURCE = "rs_d1"
HISTORY_BARS = 200  # >= Donchian 55 + ATR 14 warm-up
KLINES_URL = "https://data-api.binance.vision/api/v3/klines"


# --- market data ---------------------------------------------------------------------------------------

class BarSource(Protocol):
    def closed_bars(self, symbol: str, start_s: int, now: datetime) -> list[Candle]:
        """4h bars with open time >= start_s and **close time < now**, ascending."""

    def bar_open(self, symbol: str, t_s: int, now: datetime) -> float | None:
        """Open price of the 4h bar starting at t_s if that bar has started, else None."""

    def last_price(self, symbol: str, now: datetime) -> float | None:
        """First available price now (late fills)."""


class BinanceBarSource:
    """Binance spot REST (public data host)."""

    def _get(self, symbol: str, start_ms: int, limit: int = 1000) -> list[list[Any]]:
        r = httpx.get(
            KLINES_URL,
            params={"symbol": symbol, "interval": TIMEFRAME, "startTime": start_ms, "limit": limit},
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()

    def closed_bars(self, symbol: str, start_s: int, now: datetime) -> list[Candle]:
        now_ms = int(now.timestamp() * 1000)
        out: list[Candle] = []
        cursor = start_s * 1000
        while True:
            rows = self._get(symbol, cursor)
            for row in rows:
                if int(row[6]) < now_ms:  # close_time strictly before now: closed bar
                    out.append(Candle(time=int(row[0]) // 1000, open=float(row[1]), high=float(row[2]),
                                      low=float(row[3]), close=float(row[4]), volume=float(row[5])))
            if len(rows) < 1000:
                break
            cursor = int(rows[-1][0]) + 1
        return out

    def bar_open(self, symbol: str, t_s: int, now: datetime) -> float | None:
        if now.timestamp() < t_s:
            return None
        rows = self._get(symbol, t_s * 1000, limit=1)
        if rows and int(rows[0][0]) // 1000 == t_s:
            return float(rows[0][1])
        return None

    def last_price(self, symbol: str, now: datetime) -> float | None:
        t = int(now.timestamp()) // BAR_SECONDS * BAR_SECONDS
        rows = self._get(symbol, t * 1000, limit=1)
        return float(rows[-1][4]) if rows else None


# --- runner ---------------------------------------------------------------------------------------------

@dataclass
class CycleReport:
    processed_bars: list[int]
    filled: list[str]
    note: str = ""


def _dt(t_s: int) -> datetime:
    return datetime.fromtimestamp(t_s, tz=timezone.utc)


def _floor_bar(t_s: int) -> int:
    return t_s - t_s % BAR_SECONDS


class RsD1Runner:
    def __init__(
        self,
        source: BarSource | None = None,
        *,
        code: str = RS_D1_CODE,
        symbols: Sequence[str] = SYMBOLS,
        klines_1m_fn: Callable | None = None,
        trades_fn: Callable | None = protection.binance_agg_trades,
        history_start: int | None = None,
        replay_score_start: int | None = None,
    ) -> None:
        self.source = source or BinanceBarSource()
        self.code = code
        self.symbols = tuple(sorted(symbols))
        self.klines_1m_fn = klines_1m_fn or protection.binance_klines_1m
        self.trades_fn = trades_fn
        self._history_start = history_start  # tests / replay only
        # Replay (parity test only): process every bar from history_start like rs.simulate, same score_start.
        self._replay_score_start = replay_score_start
        # In-memory book reused between cycles of this process (valid only if the persisted state was
        # committed by the previous cycle); otherwise rebuilt from the persisted state and full history.
        self._cache: tuple[int, int, Book] | None = None  # (history_start, last_bar_time, book)

    # -- state ---------------------------------------------------------------------------------------

    def _journal(self, session: Session, pf: PaperPortfolio, event_type: str, payload: dict[str, Any],
                 position_id: str | None = None, at: datetime | None = None) -> None:
        session.add(PaperJournalEvent(portfolio_id=pf.id, position_id=position_id, event_type=event_type,
                                      payload=payload, created_at=at or datetime.now(timezone.utc)))

    def _load_or_create(self, session: Session, pf: PaperPortfolio, now: datetime) -> RsBookState:
        st = session.get(RsBookState, self.code)
        if st is not None:
            return st
        in_progress = _floor_bar(int(now.timestamp()))
        start = self._history_start if self._history_start is not None else in_progress - HISTORY_BARS * BAR_SECONDS
        if self._replay_score_start is not None:
            last_bar, score_start = start - BAR_SECONDS, self._replay_score_start
        else:
            # every bar closed before creation is history, never decided; the bar in progress is decided at
            # its close (score_start = its execution bar), no retroactive entry
            last_bar, score_start = in_progress - BAR_SECONDS, in_progress + BAR_SECONDS
        st = RsBookState(
            portfolio_code=self.code,
            history_start=start,
            last_bar_time=last_bar,
            state_json={"score_start": score_start, "initial": float(pf.initial_cash), "book": None},
            refs={},
        )
        session.add(st)
        session.flush()
        self._journal(session, pf, "RS_CYCLE", {"event": "created", "history_start": start,
                                                "first_decision_bar": in_progress, "note": "book vide, aucune entrée rétroactive"}, at=now)
        return st

    def _book(self, st: RsBookState, candles: dict[str, list[Candle]]) -> Book:
        meta = st.state_json
        book = Book(candles, cost_profile("paper"), initial=float(meta["initial"]),
                    score_start=int(meta["score_start"]), exec_delay=1, seed=SEED)
        if meta.get("book") is not None:
            book.load_state(meta["book"])
        return book

    # -- mirroring -----------------------------------------------------------------------------------

    def _mirror(self, session: Session, pf: PaperPortfolio, st: RsBookState, book: Book, at: datetime,
                extra: dict[str, Any] | None = None) -> list[str]:
        """Write the book's pending events into the paper tables; returns filled symbols."""
        refs: dict[str, str] = dict(st.refs or {})
        filled: list[str] = []
        prof = pf.strategy_profile or {}
        fr = prof.get("friction_bps_by_symbol") or {}
        for ev in book.events:
            s = ev.symbol
            payload = {"bar": ev.t, "bar_utc": _dt(ev.t).isoformat(), **ev.data, **(extra or {})}
            if ev.kind == "entry_filled":
                pos = paper_broker.open_presized_position(
                    session, portfolio=pf, symbol=s, timeframe=TIMEFRAME, source=SOURCE,
                    requested_price=ev.data["raw"], entry_fill=ev.data["fill"], qty=ev.data["qty"],
                    notional=ev.data["notional"], fee=ev.data["fee"], stop_price=ev.data["stop"],
                    risk_amount=book.positions[s].risk_amount if s in book.positions else 0.0,
                    spread_bps=float(fr.get(s, 0.0)),
                    signal={"rs_d1": payload, "rules": "RS-03"}, at=at,
                )
                if pos is None:  # cash mismatch between book and paper: never silent
                    self._journal(session, pf, "RS_REJECTED", {**payload, "reason": "paper_cash_mismatch"}, at=at)
                    continue
                refs[s] = pos.id
                filled.append(s)
            elif ev.kind == "exit_filled":
                pid = refs.pop(s, None)
                pos = session.get(PaperPosition, pid) if pid else None
                if pos is not None and pos.status == "OPEN":
                    paper_broker.close_capital_position(
                        session, pos, price=ev.data["raw"], reason=f"rs_{ev.data['reason']}",
                        signal={"rs_d1": payload}, at=at,
                    )
                filled.append(s)
            elif ev.kind == "stop_moved":
                pid = refs.get(s)
                pos = session.get(PaperPosition, pid) if pid else None
                if pos is not None and pos.status == "OPEN":
                    pos.stop_price = ev.data["to"]
                    self._journal(session, pf, "RS_TRAIL_STOP", payload, position_id=pid, at=at)
            elif ev.kind in ("entry_ordered", "exit_ordered"):
                self._journal(session, pf, "RS_DECISION", {**payload, "order": ev.kind}, position_id=refs.get(s), at=at)
            elif ev.kind == "rejected":
                self._journal(session, pf, "RS_REJECTED", payload, at=at)
        book.events.clear()
        st.refs = refs
        return filled

    def _reconcile_monitor_closes(self, session: Session, st: RsBookState, book: Book) -> None:
        """Lots closed by the 1m protection monitor: close them in the book with the monitor's raw price."""
        refs: dict[str, str] = dict(st.refs or {})
        for s, pid in list(refs.items()):
            pos = session.get(PaperPosition, pid)
            if pos is None or pos.status == "OPEN" or s not in book.positions:
                continue
            p = book.positions[s]
            sig = (pos.exit_signal or {}).get("protection") or {}
            raw = float(sig.get("trigger_price")) if sig.get("trigger_price") is not None else float(
                session.execute(select(PaperOrder.requested_price).where(
                    PaperOrder.position_id == pid, PaperOrder.side == "SELL")).scalars().first() or pos.exit_price)
            exit_s = int(pos.exit_time.timestamp()) if pos.exit_time else max(book.idx_of[s])
            bar_t = _floor_bar(exit_s)
            idx = book.idx_of[s].get(bar_t, len(book.bars[s]) - 1)
            reason = "stop_gap" if sig.get("reason") == "stop_gap" else (
                "stop_initial" if p.stop == p.initial_stop else "stop_trail")
            book.close(p, raw, bar_t, idx, reason)
            refs.pop(s)
        book.events.clear()  # already written by the monitor
        st.refs = refs

    def _scan_through(self, session: Session, st: RsBookState, until: datetime) -> None:
        for s, pid in (st.refs or {}).items():
            pos = session.get(PaperPosition, pid)
            if pos is not None and pos.status == "OPEN":
                protection.scan_position_through(session, pos, until, klines_fn=self.klines_1m_fn, trades_fn=self.trades_fn)

    # -- cycle ---------------------------------------------------------------------------------------

    def cycle(self, session: Session, now: datetime | None = None) -> CycleReport:
        now = now or datetime.now(timezone.utc)
        pf = ensure_portfolio(session, self.code)
        st = self._load_or_create(session, pf, now)
        last = int(st.last_bar_time or 0)
        cache, self._cache = self._cache, None  # invalid until this cycle commits
        if cache is not None and cache[0] == int(st.history_start) and cache[1] == last:
            book = cache[2]
            book.drop_stubs()
            fresh = {
                s: self.source.closed_bars(s, (book.bars[s][-1].time + BAR_SECONDS) if book.bars[s] else int(st.history_start), now)
                for s in self.symbols
            }
            book.extend_market(fresh)
        else:
            candles = {s: self.source.closed_bars(s, int(st.history_start), now) for s in self.symbols}
            book = self._book(st, candles)
        new_times = sorted({c.time for s in self.symbols for c in book.bars[s] if c.time > last})
        processed: list[int] = []
        filled: list[str] = []

        for t in new_times:
            close_dt = _dt(t + BAR_SECONDS)
            # 1) orders that should have been filled at the open of t (runner was down)
            stale = [s for s, (fi, _, _) in book.pending_entry.items() if t in book.idx_of[s] and book.idx_of[s][t] >= fi]
            for s in stale:
                book.pending_entry.pop(s)
                book._reject("stale_entry", s, t)
            late_exits = [s for s, fi in book.pending_exit.items() if t in book.idx_of[s] and book.idx_of[s][t] >= fi]
            if late_exits:
                prices = {s: self.source.last_price(s, now) for s in late_exits}
                book.fill_pending(t, open_of=lambda s, i: prices[s])
            filled += self._mirror(session, pf, st, book, now, {"late_fill": True} if late_exits else None)
            # 2) intrabar stops: 1m monitor with the stop in force during t, then book fallback on the 4h bar
            self._scan_through(session, st, close_dt)
            self._reconcile_monitor_closes(session, st, book)
            book.check_stops(t)
            filled += self._mirror(session, pf, st, book, close_dt, {"stop_source": "4h_fallback"})
            # 3) close of t, 4) decisions
            book.on_close(t)
            if pf.kill_switch_armed:
                self._journal(session, pf, "RS_REJECTED", {"bar": t, "reason": "kill_switch_armed", "note": "décisions d'entrée non évaluées"}, at=close_dt)
            else:
                book.decide(t)
            self._mirror(session, pf, st, book, close_dt)
            processed.append(t)
            st.last_bar_time = t

        # fill orders decided at the last close at the open of the bar in progress
        if book.pending_entry or book.pending_exit:
            nxt = int(st.last_bar_time) + BAR_SECONDS
            opens = {s: self.source.bar_open(s, nxt, now) for s in self.symbols}
            ready = {s: o for s, o in opens.items() if o is not None}
            if ready:
                for s, o in ready.items():
                    book.add_open_stub(s, nxt, o)
                book.fill_pending(nxt, open_of=lambda s, i: ready[s])
                filled += self._mirror(session, pf, st, book, now)

        if processed:
            self._journal(session, pf, "RS_CYCLE", {
                "bars": processed, "equity_cost": book.equity_cost(), "cash_book": book.cash, "cash_paper": pf.cash,
                "open": sorted(book.positions), "halted": book.halted,
            }, at=now)
            paper_broker.snapshot_equity(session, pf, marks=dict(book.last_close))
        meta = dict(st.state_json)
        meta["book"] = book.state_dict()
        st.state_json = meta
        session.commit()
        self._cache = (int(st.history_start), int(st.last_bar_time or 0), book)
        return CycleReport(processed, filled)


class RsD1Loop:
    """Background loop (like ProtectionMonitor): one cycle every ``interval_s``; a failed cycle never kills it."""

    def __init__(self, interval_s: float = 60.0) -> None:
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.runner = RsD1Runner()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="rs-d1-paper")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        from app.db.session import SessionLocal

        while not self._stop.is_set():
            session = SessionLocal()
            try:
                rep = self.runner.cycle(session)
                if rep.processed_bars or rep.filled:
                    logger.info("rs-d1 paper: bars=%s filled=%s", rep.processed_bars, rep.filled)
            except Exception:  # noqa: BLE001 -- a failed cycle must not kill the loop
                logger.warning("rs-d1 paper cycle failed", exc_info=True)
                session.rollback()
            finally:
                session.close()
            self._stop.wait(self.interval_s)


rs_d1_loop = RsD1Loop()
