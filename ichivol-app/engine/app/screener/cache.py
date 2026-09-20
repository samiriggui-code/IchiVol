"""Background-refreshed screener cache (mission brief §7: "ne pas recalculer
inutilement tout l'historique a chaque requete").

A daemon thread periodically re-scans the watchlist and persists each row
(same traceability as an on-demand /decisions call), while GET /screener
reads the latest cached result instantly instead of triggering 20 live
Binance calls per request. `refresh(force=True)` (wired to the frontend's
"Rafraichir" button) bypasses the wait for an on-demand recompute.

Deliberately a plain `threading.Thread` + `time`-based loop rather than
pulling in APScheduler or Celery: one periodic job, no distributed workers,
no persistence-of-schedule needed -- a dependency would be solving a
problem this doesn't have.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from app.db.session import SessionLocal
from app.paper import engine as paper_engine
from app.config import settings
from app.evidence.recorder import record_signal_evidence
from app.screener.persistence import persist_scan
from app.screener.service import DEFAULT_WATCHLIST, ScreenerRow, scan_watchlist

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    rows: list[ScreenerRow]
    computed_at: float
    timeframe: str


class ScreenerCache:
    def __init__(self, refresh_interval_s: float = 300.0, default_timeframe: str = "1h"):
        self.refresh_interval_s = refresh_interval_s
        self.default_timeframe = default_timeframe
        self._lock = threading.Lock()
        self._entry: CacheEntry | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="screener-cache")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception:
                logger.warning("screener cache: background refresh failed", exc_info=True)
            self._stop.wait(self.refresh_interval_s)

    def refresh(self, timeframe: str | None = None, persist: bool = True) -> CacheEntry:
        tf = timeframe or self.default_timeframe
        rows = scan_watchlist(DEFAULT_WATCHLIST, timeframe=tf)

        if persist and rows:
            session = SessionLocal()
            try:
                for row in rows:
                    try:
                        persist_scan(session, row)
                    except Exception:
                        logger.warning(
                            "screener cache: failed to persist %s", row.symbol, exc_info=True
                        )
                        session.rollback()
                    if settings.enable_signal_tracking:
                        # Its own guard: a tracking failure must never cost the decision above.
                        try:
                            record_signal_evidence(session, row)
                            session.commit()
                        except Exception:
                            logger.warning(
                                "screener cache: failed to record evidence for %s",
                                row.symbol,
                                exc_info=True,
                            )
                            session.rollback()
            finally:
                session.close()

            # Paper trading's auto_watchlist track (CDC V2) rides this same
            # cycle, gated the same way as persistence above -- reuses
            # `rows` as-is (no extra Binance calls), and `persist=False`
            # callers (tests, on-demand recomputes that don't want DB
            # writes) get none of this either. Crypto-only for now
            # (docs/HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md §1.5: "Paper/watch
            # multi-classe = après paper crypto stable (V2)") -- `exchange`
            # is "binance" only for crypto in this catalog, biquote/
            # twelve_data-backed rows (forex/metal/index/equity) are
            # excluded until that's revisited.
            crypto_rows = [r for r in rows if r.exchange == "binance"]
            paper_session = SessionLocal()
            try:
                paper_engine.sync_auto_watchlist(paper_session, crypto_rows)
            except Exception:
                logger.warning("screener cache: paper trading sync failed", exc_info=True)
                paper_session.rollback()
            finally:
                paper_session.close()

        entry = CacheEntry(rows=rows, computed_at=time.time(), timeframe=tf)
        with self._lock:
            self._entry = entry
        return entry

    def get(self, timeframe: str | None = None) -> CacheEntry | None:
        tf = timeframe or self.default_timeframe
        with self._lock:
            entry = self._entry
        if entry is not None and entry.timeframe == tf:
            return entry
        return None


screener_cache = ScreenerCache()
