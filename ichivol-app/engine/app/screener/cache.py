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
from app.paper.strategy_profiles import (
    WIDE_EXTRA_SYMBOLS,
    profile_for,
    syncable_profile_codes,
    wants_wide_universe,
)
from app.screener.service import DEFAULT_WATCHLIST, ScreenerRow, scan_watchlist

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    rows: list[ScreenerRow]
    computed_at: float
    timeframe: str


# Providers whose rows the paper broker may trade. Equities (twelve_data) stay out: free-tier quota.
PAPER_EXCHANGES = ("binance", "biquote")
# USDJPY is quoted in JPY: sizing and cash are in EUR/USD-proxy units, so it needs a quote-currency
# conversion that does not exist yet. Excluded rather than mis-sized.
PAPER_EXCLUDED_SYMBOLS = frozenset({"USDJPY"})


def paper_tradable_rows(rows):
    return [r for r in rows if r.exchange in PAPER_EXCHANGES and r.symbol not in PAPER_EXCLUDED_SYMBOLS]


def _synced_profiles() -> list[dict]:
    return [profile_for(code) for code in syncable_profile_codes()]


def paper_timeframes() -> set[str]:
    """Every timeframe some synced paper account trades automatically."""
    return {tf for profile in _synced_profiles() for tf in paper_engine.auto_timeframes(profile)}


def wide_universe_wanted() -> bool:
    return any(wants_wide_universe(profile) for profile in _synced_profiles())


def _paper_sync(rows) -> None:
    paper_session = SessionLocal()
    try:
        paper_engine.sync_auto_watchlist(paper_session, rows)
    except Exception:
        logger.warning("screener cache: paper trading sync failed", exc_info=True)
        paper_session.rollback()
    finally:
        paper_session.close()


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
        marked = False
        while not self._stop.is_set():
            if not marked:
                marked = paper_engine.mark_auto_timeframes_change()
            try:
                # Only this background loop drives the automatic paper strategy (default timeframe).
                self.refresh(paper_sync=True)
            except Exception:
                logger.warning("screener cache: background refresh failed", exc_info=True)
            try:
                self._sync_other_paper_timeframes()
            except Exception:
                logger.warning("screener cache: paper sync on other timeframes failed", exc_info=True)
            self._stop.wait(self.refresh_interval_s)

    def _sync_other_paper_timeframes(self) -> None:
        """Parallel paper accounts on another timeframe (e.g. ICHIVOL_4H_V1): scanned here for paper only --
        never cached for the UI, never persisted -- and each account keeps only its own auto_timeframes rows."""
        for tf in sorted(paper_timeframes() - {self.default_timeframe}):
            rows = scan_watchlist(DEFAULT_WATCHLIST, timeframe=tf)
            if rows:
                _paper_sync(paper_tradable_rows(rows))

    def refresh(self, timeframe: str | None = None, persist: bool = True, paper_sync: bool = False) -> CacheEntry:
        """Scan + cache (+ persistence / evidence when ``persist``).

        ``paper_sync`` feeds the rows to the automatic paper strategy. Since 2026-09-28 only the background loop
        sets it, and only for the default timeframe: a screener view or refresh from the UI / agent channel
        (any timeframe) never opens or closes a paper position (docs/VP-P-PAPER-REEL.md §2)."""
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

        if persist and rows and paper_sync and tf == self.default_timeframe:
            # Paper trading's auto_watchlist track rides the background cycle only -- reuses `rows` as-is (no extra
            # provider calls). Multi-market since 2026-09-21: crypto (binance) AND forex / metals / indices /
            # energy (biquote), see `paper_tradable_rows`.
            crypto_rows = paper_tradable_rows(rows)
            if wide_universe_wanted():
                # Extra liquid pairs for the wide-universe account only (filtered per account in the paper engine).
                try:
                    crypto_rows += paper_tradable_rows(scan_watchlist(WIDE_EXTRA_SYMBOLS, timeframe=tf))
                except Exception:
                    logger.warning("screener cache: wide universe scan failed", exc_info=True)
            _paper_sync(crypto_rows)

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
