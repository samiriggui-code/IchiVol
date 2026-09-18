"""Automated backtest evidence collection (CDC 2026-09-17, "condition 1" of
the live-broker gate, docs/CAHIER-DES-CHARGES.md §5 V3: "un vrai edge de
rendement prouvé"). Runs the exact same `experiments.compare()` already
used by `GET /backtest/{symbol}` and the front's Backtests page, on a
schedule, and persists every run's metrics to `backtest_snapshots` -- so a
trend ("is PIPELINE's Sharpe advantage growing, shrinking, still a coin
flip?") becomes visible over weeks without anyone re-running scripts by
hand, the way every number in `ichivol-app/engine/README.md`'s backtest
tables was produced tonight.

Deliberately narrow: this module only LOGS evidence. It never promotes a
gate, never edits `app/decision/pipeline.py`, never flips a CDC checkbox --
deciding "this counts as proof" stays a reviewed human/Claude call, exactly
like ADX/Donchian/Wyckoff were each judged individually rather than by an
automatic threshold. Read the log, then decide -- the log doesn't decide
for you.
"""

from __future__ import annotations

import logging
import threading
from datetime import timedelta

from sqlalchemy import func, select

from app.backtest import experiments
from app.config import settings
from app.db.models import BacktestSnapshot
from app.db.session import SessionLocal
from app.decision.pipeline import STRATEGY_VERSION
from app.universe.catalog import by_class
from app.universe.types import AssetClass

logger = logging.getLogger(__name__)

# Crypto only (binance, no scarce per-minute budget to protect) -- same
# reasoning as the default screener watchlist. Timeframes match the
# "sweep élargi" methodology already used to judge Donchian/Wyckoff.
DEFAULT_SYMBOLS: tuple[str, ...] = tuple(i.id for i in by_class(AssetClass.CRYPTO))
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("1h", "4h")
DEFAULT_LIMIT = 500  # lighter than the 1000 used for one-off manual runs -- this repeats daily


def _snapshot_row(symbol: str, timeframe: str, experiment_name: str, exp) -> BacktestSnapshot:
    m = exp.metrics
    return BacktestSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        experiment=experiment_name,
        strategy_version=STRATEGY_VERSION,
        n_bars=m.n_bars,
        num_trades=m.num_trades,
        total_return=m.total_return,
        cagr=m.cagr,
        sharpe=m.sharpe,
        sortino=m.sortino,
        max_drawdown=m.max_drawdown,
        exposure=m.exposure,
        win_rate=m.win_rate,
        profit_factor=m.profit_factor if m.profit_factor != float("inf") else None,
        expectancy=m.expectancy,
    )


def snapshot_symbol(session, symbol: str, timeframe: str, limit: int = DEFAULT_LIMIT) -> int:
    """Runs experiments.compare() for one (symbol, timeframe) and persists
    one BacktestSnapshot row per experiment. Never raises -- insufficient
    history or an unreachable provider for one symbol must not stop the
    rest of the cycle (same convention as the screener's per-symbol
    try/except). Returns how many rows were written (0 on failure)."""
    try:
        results = experiments.compare(symbol, timeframe=timeframe, limit=limit)
    except Exception:
        logger.warning("backtest evidence: skipping %s %s", symbol, timeframe, exc_info=True)
        return 0

    rows = [_snapshot_row(symbol, timeframe, name, exp) for name, exp in results.items()]
    session.add_all(rows)
    session.commit()
    return len(rows)


def run_snapshot_cycle(
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, int]:
    """One full evidence-collection pass -- every (symbol, timeframe) pair,
    each isolated so one bad one doesn't sink the cycle. Returns
    {"symbol tf": rows_written} for logging/inspection."""
    written: dict[str, int] = {}
    session = SessionLocal()
    try:
        for symbol in symbols:
            for timeframe in timeframes:
                key = f"{symbol} {timeframe}"
                written[key] = snapshot_symbol(session, symbol, timeframe, limit=limit)
    finally:
        session.close()
    return written


class BacktestEvidenceScheduler:
    """Background thread that runs `run_snapshot_cycle()` on an interval --
    same start/stop/_loop shape as app/screener/cache.py::ScreenerCache, so
    it lives and dies with the FastAPI process (app/main.py's lifespan),
    no separate cron container needed."""

    def __init__(self, interval_s: float = 86400.0):
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="backtest-evidence")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                written = run_snapshot_cycle()
                logger.info("backtest evidence: cycle done, %d snapshot groups", len(written))
            except Exception:
                logger.warning("backtest evidence: cycle failed", exc_info=True)
            self._stop.wait(self.interval_s)


backtest_evidence_scheduler = BacktestEvidenceScheduler(interval_s=settings.backtest_evidence_interval_s)


def compute_evidence_summary(session) -> dict:
    """Read-only rollup for `GET /backtest/evidence` (Overview's "Preuve edge
    (C1)" tile): how much automated evidence exists, and -- among the most
    recent cycle's pairs -- how often PIPELINE's Sharpe beat plain Ichimoku.
    Purely descriptive: this never decides Option C, it just makes the raw
    material for that decision visible without a manual script."""
    total_rows = session.execute(select(func.count()).select_from(BacktestSnapshot)).scalar_one()

    base = {
        "enabled": settings.enable_backtest_evidence,
        "interval_s": settings.backtest_evidence_interval_s,
    }

    if total_rows == 0:
        return {
            **base,
            "total_rows": 0,
            "last_run_at": None,
            "first_run_at": None,
            "distinct_days": 0,
            "latest_pairs": 0,
            "pipeline_beats_ichimoku_sharpe": None,
            "note": (
                "Aucune collecte pour l'instant -- le premier cycle tourne au démarrage du "
                "moteur (ou attends l'intervalle configuré)."
            ),
        }

    first_run, last_run = session.execute(
        select(func.min(BacktestSnapshot.computed_at), func.max(BacktestSnapshot.computed_at))
    ).one()

    # Span in calendar days between the first and most recent snapshot --
    # "depuis combien de temps ça tourne", not "combien de jours ont
    # vraiment produit une ligne" (a missed cycle during downtime still
    # counts towards the elapsed history).
    distinct_days = max(1, (last_run.date() - first_run.date()).days + 1)

    # "Cycle la plus récente" = tout ce qui est tombé dans les 2h précédant
    # le dernier computed_at -- un cycle complet (aujourd'hui ~40 paires,
    # fetch + backtest séquentiels) termine largement dans cette fenêtre,
    # et les cycles sont espacées d'un jour par défaut.
    recent_cutoff = last_run - timedelta(hours=2)
    recent_rows = session.execute(
        select(
            BacktestSnapshot.symbol, BacktestSnapshot.timeframe,
            BacktestSnapshot.experiment, BacktestSnapshot.sharpe,
        ).where(BacktestSnapshot.computed_at >= recent_cutoff)
    ).all()

    pairs, edge = _score_pipeline_vs_ichimoku(recent_rows)

    return {
        **base,
        "total_rows": total_rows,
        "last_run_at": last_run.isoformat() if last_run else None,
        "first_run_at": first_run.isoformat() if first_run else None,
        "distinct_days": distinct_days,
        "latest_pairs": len(pairs),
        "pipeline_beats_ichimoku_sharpe": edge,
        "note": None,
    }


def _score_pipeline_vs_ichimoku(
    rows,
) -> tuple[set[tuple[str, str]], dict[str, int] | None]:
    """Pure -- no DB, no clock -- so it can be tested in isolation from
    whatever else happens to be in the shared `ichivol_engine_dev` table at
    test time. `rows` is any iterable of objects/tuples with
    `.symbol`/`.timeframe`/`.experiment`/`.sharpe` (a SQLAlchemy Row from
    `compute_evidence_summary`'s query, or a plain namedtuple in tests).
    Returns (distinct (symbol, timeframe) pairs seen, {beats, compared} or
    None if no pair had both experiments recorded)."""
    pairs = {(r.symbol, r.timeframe) for r in rows}
    by_pair: dict[tuple[str, str], dict[str, float | None]] = {}
    for r in rows:
        by_pair.setdefault((r.symbol, r.timeframe), {})[r.experiment] = r.sharpe

    beats = 0
    compared = 0
    for sharpes in by_pair.values():
        pipeline_sharpe = sharpes.get("PIPELINE")
        ichimoku_sharpe = sharpes.get("ICHIMOKU_ONLY")
        if pipeline_sharpe is None or ichimoku_sharpe is None:
            continue
        compared += 1
        if pipeline_sharpe > ichimoku_sharpe:
            beats += 1

    edge = {"beats": beats, "compared": compared} if compared > 0 else None
    return pairs, edge
