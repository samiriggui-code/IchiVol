"""Evidence DB — persist SignalContext + decision + evidence + later outcomes.

Complements StrategyLabExperiment / BacktestSnapshot: this table is the
per-signal audit trail (what IchiVol knew at t0, what it decided, what
happened after).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SignalEvidenceRecord
from app.evidence.context import SignalContext
from app.evidence.engine import EvidenceReport, evidence_report_dict


def persist_evidence(
    session: Session,
    *,
    report: EvidenceReport,
    decision: str,
    decision_id: str | None = None,
    paper_position_id: str | None = None,
    market_snapshot: dict[str, Any] | None = None,
) -> SignalEvidenceRecord:
    row = SignalEvidenceRecord(
        symbol=report.context.symbol,
        timeframe=report.context.timeframe,
        timestamp=datetime.fromtimestamp(report.context.timestamp, tz=timezone.utc)
        if report.context.timestamp
        else datetime.now(timezone.utc),
        provider=report.context.provider,
        volume_type=(report.context.volume.volume_type if report.context.volume else "NONE"),
        asset_class=report.context.asset_class,
        decision=decision,
        decision_id=decision_id,
        paper_position_id=paper_position_id,
        context_json=report.context.to_dict(),
        evidence_json=evidence_report_dict(report),
        market_snapshot=market_snapshot or {},
        strategy_version=report.strategy_version,
        feature_version=report.feature_version,
        rules_version=report.rules_version,
        evidence_engine_version=report.evidence_engine_version,
        sample_size=report.historical.sample_size,
        sample_quality=report.historical.sample_quality.value,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def attach_outcome(
    session: Session,
    evidence_id: str,
    *,
    forward_returns: dict[str, float | None],
    mfe_pct: float | None,
    mae_pct: float | None,
    target_hit: bool | None = None,
    invalidation_hit: bool | None = None,
    realized_pnl_pct: float | None = None,
) -> SignalEvidenceRecord | None:
    row = session.get(SignalEvidenceRecord, evidence_id)
    if row is None:
        return None
    row.outcome_json = {
        "forward_returns": forward_returns,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "target_hit": target_hit,
        "invalidation_hit": invalidation_hit,
        "realized_pnl_pct": realized_pnl_pct,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    row.outcome_recorded_at = datetime.now(timezone.utc)
    session.flush()
    return row


def list_evidence_catalog(
    session: Session,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    asset_class: str | None = None,
    feature_version: str | None = None,
    limit: int = 500,
) -> list[SignalContext]:
    """Load prior contexts for historical matching (no candle series)."""
    q = select(SignalEvidenceRecord).order_by(SignalEvidenceRecord.created_at.desc()).limit(limit)
    if symbol:
        q = q.where(SignalEvidenceRecord.symbol == symbol)
    if timeframe:
        q = q.where(SignalEvidenceRecord.timeframe == timeframe)
    if asset_class:
        q = q.where(SignalEvidenceRecord.asset_class == asset_class)
    if feature_version:
        q = q.where(SignalEvidenceRecord.feature_version == feature_version)
    rows = session.execute(q).scalars().all()
    out: list[SignalContext] = []
    for row in rows:
        try:
            out.append(SignalContext.from_dict(row.context_json or {}))
        except (KeyError, TypeError, ValueError):
            continue
    return out
