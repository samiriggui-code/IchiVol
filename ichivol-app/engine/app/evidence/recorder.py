"""Automatic signal recording -- the missing link of the evidence circuit.

`persist_evidence` used to run only when a user confirmed a position by hand,
so `signal_evidence` stayed empty and nothing could ever be compared with what
happened next. This records, on every screener scan, each market where Ichimoku
holds a direction, with the full context (gates, RVOL, structure, regime) and
the pipeline's decision -- so signals can later be grouped by confluence and
their outcome measured (app/evidence/outcomes.py).

One row per (symbol, timeframe, candle). The last candle of a scan is still
forming, so the row is refreshed on each scan until that candle's outcome
starts being measured; the stored state is therefore the last one seen before
the bar closed, not a first tick.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.types import Direction
from app.db.models import SignalEvidenceRecord
from app.evidence.engine import evidence_report_dict
from app.evidence.persistence import persist_evidence
from app.market_data.timeframes import TF_SECONDS

logger = logging.getLogger(__name__)


def _utc(dt: datetime) -> datetime:
    """Postgres returns aware datetimes; SQLite (tests) returns naive ones."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _directional(row: Any) -> str | None:
    direction = row.pipeline.direction
    return direction.value if direction in (Direction.LONG, Direction.SHORT) else None


def _first_of_run(session: Session, symbol: str, timeframe: str, ts: datetime, direction: str) -> bool:
    """True when this candle starts a new directional run -- consecutive bars in
    the same direction describe one situation, not independent signals."""
    prev = session.execute(
        select(SignalEvidenceRecord)
        .where(
            SignalEvidenceRecord.symbol == symbol,
            SignalEvidenceRecord.timeframe == timeframe,
            SignalEvidenceRecord.timestamp < ts,
        )
        .order_by(SignalEvidenceRecord.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()
    if prev is None:
        return True
    tf_s = TF_SECONDS.get(timeframe)
    adjacent = tf_s is not None and (ts - _utc(prev.timestamp)).total_seconds() <= 2 * tf_s
    same_direction = (prev.market_snapshot or {}).get("direction") == direction
    return not (adjacent and same_direction)


def record_signal_evidence(session: Session, row: Any) -> str | None:
    """Returns "created", "updated", or None when nothing was written.

    Does not commit -- the caller owns the transaction."""
    report = row.evidence
    direction = _directional(row)
    if report is None or direction is None or not row.candles:
        return None

    last = row.candles[-1]
    ts = datetime.fromtimestamp(last.time, tz=timezone.utc)
    decision = row.pipeline.decision
    context = report.context.to_dict()

    existing = session.execute(
        select(SignalEvidenceRecord).where(
            SignalEvidenceRecord.symbol == row.symbol,
            SignalEvidenceRecord.timeframe == row.timeframe,
            SignalEvidenceRecord.timestamp == ts,
        )
    ).scalars().first()

    if existing is not None:
        if existing.outcome_json is not None:
            return None  # outcome already started: the record is frozen
        if existing.decision == decision and existing.context_json == context:
            return None
        snapshot = dict(existing.market_snapshot or {})
        snapshot.update(price=row.price, direction=direction)
        existing.decision = decision
        existing.context_json = context
        existing.evidence_json = evidence_report_dict(report)
        existing.market_snapshot = snapshot
        existing.sample_size = report.historical.sample_size
        existing.sample_quality = report.historical.sample_quality.value
        session.flush()
        return "updated"

    persist_evidence(
        session,
        report=report,
        decision=decision,
        market_snapshot={
            "price": row.price,
            "direction": direction,
            "volume_type": last.volume_type.value,
            "first_of_run": _first_of_run(session, row.symbol, row.timeframe, ts, direction),
        },
    )
    return "created"
