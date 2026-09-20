"""What happened after each recorded signal -- forward returns, best and worst
excursion -- measured on CLOSED candles only, so nothing peeks at a bar that is
still forming.

Pure functions (`select_bars_after`, `compute_outcome`) are separated from the
DB/provider loop so they can be tested without either.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Sequence

from sqlalchemy import select

from app.config import settings
from app.db.models import SignalEvidenceRecord
from app.db.session import SessionLocal
from app.indicators.ichimoku import Candle
from app.market_data.timeframes import TF_SECONDS

logger = logging.getLogger(__name__)

HORIZONS: tuple[int, ...] = (1, 3, 5, 10, 20)

# The provider window we re-read per (symbol, timeframe). A signal older than this
# many bars can no longer be located, and is closed as "stale" rather than retried forever.
FETCH_BARS = 80


def select_bars_after(
    candles: Sequence[Candle], signal_ts: int, tf_seconds: int, now_ts: float
) -> list[Candle]:
    """Closed bars strictly after the signal bar, oldest first."""
    return sorted(
        (c for c in candles if c.time > signal_ts and c.time + tf_seconds <= now_ts),
        key=lambda c: c.time,
    )


def compute_outcome(
    direction: str,
    entry_price: float,
    bars_after: Sequence[Candle],
    horizons: Sequence[int] = HORIZONS,
) -> dict:
    """Signed by direction: a positive return always means the signal was right.

    `mfe_pct` / `mae_pct`: best and worst excursion from the entry over the
    bars observed so far (up to the longest horizon), as fractions."""
    sign = 1.0 if direction == "LONG" else -1.0
    longest = max(horizons)
    forward = {
        str(h): sign * (bars_after[h - 1].close / entry_price - 1.0)
        for h in horizons
        if len(bars_after) >= h
    }
    window = list(bars_after[:longest])
    if window:
        highs = max(b.high for b in window)
        lows = min(b.low for b in window)
        if direction == "LONG":
            mfe, mae = highs / entry_price - 1.0, lows / entry_price - 1.0
        else:
            mfe, mae = 1.0 - lows / entry_price, 1.0 - highs / entry_price
    else:
        mfe = mae = None
    return {
        "forward_returns": forward,
        "mfe_pct": mfe,
        "mae_pct": mae,
        "bars_observed": len(window),
        "complete": len(bars_after) >= longest,
        "direction": direction,
        "entry_price": entry_price,
    }


CandleFetcher = Callable[[str, str], Sequence[Candle]]


def update_pending_outcomes(session, fetch: CandleFetcher, now_ts: float | None = None) -> int:
    """Measure every recorded signal that has new closed bars since last time.
    Returns how many records were updated. Never raises for one bad symbol."""
    now = now_ts if now_ts is not None else time.time()
    pending = session.execute(
        select(SignalEvidenceRecord).where(SignalEvidenceRecord.outcome_recorded_at.is_(None))
    ).scalars().all()

    by_pair: dict[tuple[str, str], list[SignalEvidenceRecord]] = {}
    for rec in pending:
        by_pair.setdefault((rec.symbol, rec.timeframe), []).append(rec)

    updated = 0
    for (symbol, timeframe), records in by_pair.items():
        tf_s = TF_SECONDS.get(timeframe)
        if tf_s is None:
            continue
        try:
            candles = fetch(symbol, timeframe)
        except Exception:
            logger.warning("signal outcomes: cannot fetch %s %s", symbol, timeframe, exc_info=True)
            continue
        oldest_visible = min((c.time for c in candles), default=None)

        for rec in records:
            snapshot = rec.market_snapshot or {}
            entry, direction = snapshot.get("price"), snapshot.get("direction")
            if not isinstance(entry, (int, float)) or entry <= 0 or direction not in ("LONG", "SHORT"):
                continue
            stamp = rec.timestamp if rec.timestamp.tzinfo else rec.timestamp.replace(tzinfo=timezone.utc)
            signal_ts = int(stamp.timestamp())
            if oldest_visible is not None and signal_ts < oldest_visible:
                # Fell out of the provider window before it could be measured.
                rec.outcome_json = {**(rec.outcome_json or {}), "stale": True, "complete": True}
                rec.outcome_recorded_at = datetime.now(timezone.utc)
                updated += 1
                continue
            bars = select_bars_after(candles, signal_ts, tf_s, now)
            outcome = compute_outcome(direction, float(entry), bars)
            previous = (rec.outcome_json or {}).get("bars_observed", 0)
            if outcome["bars_observed"] == previous and not outcome["complete"]:
                continue
            outcome["updated_at"] = datetime.now(timezone.utc).isoformat()
            rec.outcome_json = outcome
            if outcome["complete"]:
                rec.outcome_recorded_at = datetime.now(timezone.utc)
            updated += 1
    if updated:
        session.commit()
    return updated


def _fetch_from_provider(symbol: str, timeframe: str) -> Sequence[Candle]:
    from app.market_data.resolve import resolve_and_fetch

    _provider, _sym, candles = resolve_and_fetch(symbol, timeframe, FETCH_BARS)
    return candles


class OutcomeTracker:
    """Background thread, same shape as the other schedulers (started by the
    FastAPI lifespan). Runs often because a 1h signal gains a new measurable bar
    every hour."""

    def __init__(self, interval_s: float = 900.0):
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="signal-outcomes")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        # First pass after a short delay: lets a fresh engine finish its first scan.
        if self._stop.wait(60.0):
            return
        while not self._stop.is_set():
            session = SessionLocal()
            try:
                n = update_pending_outcomes(session, _fetch_from_provider)
                if n:
                    logger.info("signal outcomes: %d record(s) updated", n)
            except Exception:
                logger.warning("signal outcomes: pass failed", exc_info=True)
                session.rollback()
            finally:
                session.close()
            self._stop.wait(self.interval_s)


outcome_tracker = OutcomeTracker(interval_s=settings.signal_outcome_interval_s)
