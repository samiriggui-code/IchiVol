"""Read-only activity endpoints: what the automated circuit did, and when.

Everything here already existed as rows (backtest_snapshots, paper journal,
shadow trades, decisions); the app just never showed it. No writes, no
order routing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.activity.logic import SnapshotLite, cluster_runs, humanize_journal_event, summarize_run
from app.config import settings
from app.db.models import (
    BacktestSnapshot,
    Decision,
    PaperJournalEvent,
    PaperPortfolio,
    PaperPosition,
    SignalEvidenceRecord,
)
from app.db.session import SessionLocal

router = APIRouter(prefix=settings.engine_api_prefix, tags=["activity"])

_SNAPSHOT_HORIZON_DAYS = 90


def _snapshots(session) -> list[SnapshotLite]:
    since = datetime.now(timezone.utc) - timedelta(days=_SNAPSHOT_HORIZON_DAYS)
    rows = session.execute(
        select(BacktestSnapshot).where(BacktestSnapshot.computed_at >= since)
    ).scalars()
    return [
        SnapshotLite(
            computed_at=r.computed_at,
            symbol=r.symbol,
            timeframe=r.timeframe,
            experiment=r.experiment,
            num_trades=r.num_trades,
            sharpe=r.sharpe,
            profit_factor=r.profit_factor,
            expectancy=r.expectancy,
            win_rate=r.win_rate,
        )
        for r in rows
    ]


@router.get("/backtest/runs")
def get_backtest_runs(limit: int = 30) -> dict:
    """Each automatic collection run (newest first) with per-method results."""
    session = SessionLocal()
    try:
        runs = cluster_runs(_snapshots(session))
        summaries = [summarize_run(r) for r in reversed(runs)]
        return {
            "runs": summaries[: max(1, min(limit, 100))],
            "total_runs": len(runs),
            "min_trades_per_pair": 30,
        }
    finally:
        session.close()


@router.get("/activity/feed")
def get_activity_feed(limit: int = 120) -> dict:
    """Automatic paper/shadow events, newest first, in plain language."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(PaperJournalEvent, PaperPortfolio.code, PaperPosition.symbol, PaperPosition.direction)
            .join(PaperPortfolio, PaperPortfolio.id == PaperJournalEvent.portfolio_id)
            .outerjoin(PaperPosition, PaperPosition.id == PaperJournalEvent.position_id)
            .where(PaperJournalEvent.event_type != "SHADOW_OPEN")
            .order_by(PaperJournalEvent.created_at.desc())
            .limit(max(1, min(limit, 500)))
        ).all()
        items = []
        for event, portfolio_code, symbol, direction in rows:
            item = humanize_journal_event(
                event.event_type, event.payload or {}, symbol=symbol, direction=direction
            )
            if item is None:
                continue
            items.append({**item, "time": event.created_at.isoformat(), "portfolio": portfolio_code})
        return {"items": items}
    finally:
        session.close()


@router.get("/activity/summary")
def get_activity_summary() -> dict:
    """Counters that show the circuit is alive -- and which link is not wired."""
    session = SessionLocal()
    try:
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        def count(model, *where) -> int:
            return session.execute(select(func.count()).select_from(model).where(*where)).scalar_one()

        def journal(event_type: str, since: datetime | None = None) -> int:
            conds = [PaperJournalEvent.event_type == event_type]
            if since is not None:
                conds.append(PaperJournalEvent.created_at >= since)
            return count(PaperJournalEvent, *conds)

        last_opened = session.execute(
            select(func.max(PaperJournalEvent.created_at)).where(PaperJournalEvent.event_type == "OPENED")
        ).scalar_one_or_none()
        last_decision = session.execute(select(func.max(Decision.created_at))).scalar_one_or_none()
        runs = cluster_runs(_snapshots(session))

        return {
            "decisions": {"total": count(Decision), "last_24h": count(Decision, Decision.created_at >= day_ago),
                          "last_at": last_decision.isoformat() if last_decision else None},
            "paper": {
                "opened_total": journal("OPENED"),
                "opened_24h": journal("OPENED", day_ago),
                "closed_total": journal("CLOSED"),
                "closed_24h": journal("CLOSED", day_ago),
                "open_now": count(PaperPosition, PaperPosition.status == "OPEN"),
                "last_opened_at": last_opened.isoformat() if last_opened else None,
            },
            "shadow": {
                "blocked_total": journal("SHADOW_BLOCKED"),
                "blocked_24h": journal("SHADOW_BLOCKED", day_ago),
                "judged_total": journal("SHADOW_CLOSE"),
            },
            "backtest": {
                "runs_total": len(runs),
                "last_at": runs[-1][-1].computed_at.isoformat() if runs else None,
            },
            # Signal -> outcome tracking. 0 rows means nothing feeds it automatically.
            "evidence": {"rows_total": count(SignalEvidenceRecord)},
        }
    finally:
        session.close()
