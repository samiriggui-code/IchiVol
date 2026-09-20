"""Stop / take-profit monitoring for open paper positions, independent of signals.

Why this exists: stops used to be evaluated only when the screener refreshed
(every few minutes) and only against one price sample, and manually confirmed
positions were not looked at at all. A protection must be watched between two
candle closes, whatever way the position was opened (auto, user-confirmed, any
portfolio).

Method (no look-ahead into the past of the position):
1. The remainder of the entry minute is checked tick by tick (aggregated
   trades from the exact entry time) -- a high/low of the entry candle that
   happened BEFORE the fill is never used.
2. Whole 1-minute bars strictly after the entry minute are checked with
   ``resolve_bar_exit`` (gap through a level fills at the open, not at the level).
3. If one 1-minute bar touches both levels the order is unknown: finer data
   (ticks of that minute) is used when available; otherwise the STOP is assumed
   first and the note says so.

Legacy positions (opened before monitoring existed) are NOT closed on the basis
of a reconstruction: they get a watermark "from now" and any historical breach
is only reported (see ``history_breach`` in the result).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokerage.execution import resolve_bar_exit
from app.db.models import PaperJournalEvent, PaperPosition
from app.market_data.binance import BASE_URL
from app.paper import broker as paper_broker
from app.universe.catalog import get_instrument

logger = logging.getLogger(__name__)

MINUTE_MS = 60_000
CHECK_EVENT = "PROTECTION_CHECKED"
CHECK_EVENT_EVERY_MS = 15 * MINUTE_MS

# (symbol, start_ms, end_ms) -> rows
KlinesFn = Callable[[str, int, int], Sequence[Sequence[Any]]]
# (symbol, start_ms, end_ms) -> [(time_ms, price)] ascending
TradesFn = Callable[[str, int, int], Sequence[tuple[int, float]]]


@dataclass(frozen=True)
class Breach:
    reason: str  # stop_hit | stop_gap | take_profit_hit | target_gap
    price: float
    time_ms: int
    granularity: str  # tick | 1m
    note: str = ""


@dataclass(frozen=True)
class ScanResult:
    breach: Breach | None
    checked_through_ms: int


def _hit(direction: str, stop: float, target: float, price: float) -> str | None:
    long = direction.upper() == "LONG"
    if (price <= stop) if long else (price >= stop):
        return "stop"
    if (price >= target) if long else (price <= target):
        return "target"
    return None


def _scan_ticks(direction: str, stop: float, target: float, ticks: Sequence[tuple[int, float]]) -> Breach | None:
    for t, p in ticks:
        h = _hit(direction, stop, target, p)
        if h == "stop":
            gapped = (p < stop) if direction.upper() == "LONG" else (p > stop)
            return Breach("stop_hit", p if gapped else stop, t, "tick",
                          "tick beyond stop: filled at that tick" if gapped else "")
        if h == "target":
            return Breach("take_profit_hit", target, t, "tick")
    return None


def find_first_breach(
    direction: str,
    stop: float,
    target: float,
    *,
    symbol: str,
    since_ms: int,
    until_ms: int,
    klines_fn: KlinesFn,
    trades_fn: TradesFn | None,
) -> ScanResult:
    """First stop/target crossing strictly after ``since_ms`` and before ``until_ms``.

    ``until_ms`` bounds the scan to CLOSED minutes (a still-forming 1m bar is
    left for the next cycle)."""
    minute0 = since_ms - since_ms % MINUTE_MS
    checked = since_ms

    if since_ms % MINUTE_MS:
        entry_minute_end = minute0 + MINUTE_MS
        if trades_fn is not None and entry_minute_end <= until_ms:
            ticks = [(t, p) for t, p in trades_fn(symbol, since_ms, entry_minute_end) if t >= since_ms]
            b = _scan_ticks(direction, stop, target, ticks)
            if b:
                return ScanResult(b, entry_minute_end)
            checked = entry_minute_end
        # Without tick data the entry minute is skipped (blind spot < 60 s) rather
        # than guessed from a candle that mixes pre- and post-entry prices.
        start = entry_minute_end
    else:
        start = minute0

    end_closed = until_ms - until_ms % MINUTE_MS
    if start >= end_closed:
        return ScanResult(None, max(checked, min(start, end_closed)))

    rows = klines_fn(symbol, start, end_closed)
    for k in rows:
        open_ms = int(k[0])
        if open_ms < start or open_ms + MINUTE_MS > end_closed:
            continue
        o, h, l = float(k[1]), float(k[2]), float(k[3])
        r = resolve_bar_exit(direction, stop, target, o, h, l)
        checked = open_ms + MINUTE_MS
        if r.reason is None:
            continue
        if "both inside bar" in r.note and trades_fn is not None:
            ticks = list(trades_fn(symbol, open_ms, open_ms + MINUTE_MS))
            b = _scan_ticks(direction, stop, target, ticks)
            if b:
                return ScanResult(
                    Breach(b.reason, b.price, b.time_ms, "tick", "both levels in one minute; order resolved from ticks"),
                    checked,
                )
        reason = {"target_hit": "take_profit_hit", "target_gap": "take_profit_hit"}.get(r.reason, r.reason)
        return ScanResult(Breach(reason, float(r.price), open_ms, "1m", r.note), checked)
    return ScanResult(None, max(checked, end_closed))


# ── Binance data access ─────────────────────────────────────────────────────

def binance_klines_1m(symbol: str, start_ms: int, end_ms: int) -> list[list[Any]]:
    out: list[list[Any]] = []
    cur = start_ms
    while cur < end_ms:
        r = httpx.get(
            f"{BASE_URL}/api/v3/klines",
            params={"symbol": symbol, "interval": "1m", "startTime": cur, "endTime": end_ms - 1, "limit": 1000},
            timeout=20.0,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend(rows)
        cur = int(rows[-1][0]) + MINUTE_MS
        if len(rows) < 1000:
            break
    return out


def binance_agg_trades(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    cur = start_ms
    for _ in range(20):  # a minute rarely exceeds a few thousand trades; hard cap
        r = httpx.get(
            f"{BASE_URL}/api/v3/aggTrades",
            params={"symbol": symbol, "startTime": cur, "endTime": end_ms - 1, "limit": 1000},
            timeout=20.0,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend((int(x["T"]), float(x["p"])) for x in rows)
        if len(rows) < 1000:
            break
        cur = int(rows[-1]["T"]) + 1
    return out


# ── Cycle over open positions ───────────────────────────────────────────────

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _events(session: Session, position: PaperPosition, event_type: str) -> list[PaperJournalEvent]:
    return list(
        session.execute(
            select(PaperJournalEvent)
            .where(PaperJournalEvent.position_id == position.id, PaperJournalEvent.event_type == event_type)
            .order_by(PaperJournalEvent.created_at)
        ).scalars()
    )


def _seed(session: Session, position: PaperPosition) -> tuple[int | None, bool]:
    """(since_ms, is_legacy). Positions whose OPENED event declares monitoring
    start at their entry time; older ones are legacy (no closing from history)."""
    checks = _events(session, position, CHECK_EVENT)
    if checks:
        return int(checks[-1].payload["through_ms"]), bool(checks[-1].payload.get("legacy", False))
    opened = _events(session, position, "OPENED")
    if opened and (opened[-1].payload or {}).get("protection_monitored"):
        return _ms(position.entry_time), False
    return None, True


def _write_check(session: Session, position: PaperPosition, through_ms: int, legacy: bool, now: datetime) -> None:
    session.add(
        PaperJournalEvent(
            portfolio_id=position.portfolio_id,
            position_id=position.id,
            event_type=CHECK_EVENT,
            payload={"through_ms": through_ms, "legacy": legacy},
            created_at=now,
        )
    )


def run_protection_cycle(
    session: Session,
    *,
    klines_fn: KlinesFn = binance_klines_1m,
    trades_fn: TradesFn | None = binance_agg_trades,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Check every open protected position. Returns one report row per position.

    ``dry_run`` performs the scans but writes nothing and closes nothing."""
    now = now or datetime.now(timezone.utc)
    now_ms = _ms(now)
    report: list[dict[str, Any]] = []
    session.flush()  # sessions here run with autoflush off
    opens = session.execute(
        select(PaperPosition).where(PaperPosition.status == "OPEN").order_by(PaperPosition.entry_time)
    ).scalars().all()

    for pos in opens:
        row: dict[str, Any] = {"id": pos.id, "symbol": pos.symbol, "source": pos.source, "status": "skipped"}
        report.append(row)
        if not pos.qty or pos.stop_price is None or pos.take_profit_price is None:
            row["status"] = "unprotected_legacy_no_levels"
            continue
        inst = get_instrument(pos.symbol)
        if inst is None or inst.provider != "binance" or not inst.provider_symbol:
            row["status"] = "unsupported_provider"
            continue

        since_ms, legacy = _seed(session, pos)
        if since_ms is None:
            # Legacy: report what history says, never act on it.
            hist = find_first_breach(
                pos.direction, pos.stop_price, pos.take_profit_price, symbol=inst.provider_symbol,
                since_ms=_ms(pos.entry_time), until_ms=now_ms, klines_fn=klines_fn, trades_fn=trades_fn,
            )
            row["status"] = "legacy_watermark_initialised"
            row["history_breach"] = None if hist.breach is None else {
                "reason": hist.breach.reason, "price": hist.breach.price,
                "at": datetime.fromtimestamp(hist.breach.time_ms / 1000, timezone.utc).isoformat(),
                "granularity": hist.breach.granularity, "note": hist.breach.note,
            }
            if not dry_run:
                _write_check(session, pos, now_ms - now_ms % MINUTE_MS, True, now)
            continue

        scan = find_first_breach(
            pos.direction, pos.stop_price, pos.take_profit_price, symbol=inst.provider_symbol,
            since_ms=since_ms, until_ms=now_ms, klines_fn=klines_fn, trades_fn=trades_fn,
        )
        row["checked_through_ms"] = scan.checked_through_ms
        if scan.breach is None:
            row["status"] = "ok"
            if not dry_run and now_ms - since_ms >= CHECK_EVENT_EVERY_MS:
                _write_check(session, pos, scan.checked_through_ms, legacy, now)
            continue

        b = scan.breach
        at = datetime.fromtimestamp(b.time_ms / 1000, timezone.utc)
        row.update(status="breach", breach={"reason": b.reason, "price": b.price, "at": at.isoformat(),
                                             "granularity": b.granularity, "note": b.note})
        if dry_run:
            continue
        paper_broker.close_capital_position(
            session, pos, price=b.price, reason=b.reason,
            signal={"protection": {"reason": b.reason, "trigger_price": b.price, "breach_at": at.isoformat(),
                                   "granularity": b.granularity, "note": b.note}},
            at=at,
        )
        row["status"] = "closed"
    if not dry_run:
        session.commit()
    return report


class ProtectionMonitor:
    """Background loop: checks protections every ``interval_s`` between candle closes."""

    def __init__(self, interval_s: float = 60.0) -> None:
        import threading

        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Any = None
        self._threading = threading

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = self._threading.Thread(target=self._loop, daemon=True, name="protection-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        from app.db.session import SessionLocal

        while not self._stop.is_set():
            session = SessionLocal()
            try:
                for row in run_protection_cycle(session):
                    if row["status"] in ("closed", "legacy_watermark_initialised"):
                        logger.info("protection: %s", row)
            except Exception:  # noqa: BLE001 -- a failed cycle must not kill the loop
                logger.warning("protection cycle failed", exc_info=True)
                session.rollback()
            finally:
                session.close()
            self._stop.wait(self.interval_s)


protection_monitor = ProtectionMonitor()


def _cli() -> None:
    """One-shot run: ``python -m app.paper.protection --dry-run`` (report only) or ``--apply``."""
    import argparse
    import json

    from app.db.session import SessionLocal

    ap = argparse.ArgumentParser(description="Check stops/targets of open paper positions once.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="scan and report, write/close nothing")
    mode.add_argument("--apply", action="store_true", help="enforce breaches and write watermarks")
    args = ap.parse_args()
    session = SessionLocal()
    try:
        print(json.dumps(run_protection_cycle(session, dry_run=args.dry_run), indent=1, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    _cli()
