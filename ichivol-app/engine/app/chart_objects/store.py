"""Persistence for USER / CLAUDE ChartObject overlays (T2b)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chart_objects.types import (
    ChartObject,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.db.models import ChartObjectOverlay

# Sources that may be stored (ENGINE is recomputed; STRATEGY/BACKTEST = T4/T5).
PERSISTABLE_SOURCES = frozenset(
    {ChartObjectSource.USER.value, ChartObjectSource.CLAUDE.value}
)


def _row_to_chart_object(row: ChartObjectOverlay) -> ChartObject:
    points = tuple(
        ChartPoint(time=int(p["time"]), price=float(p["price"]))
        for p in (row.points or [])
    )
    return ChartObject(
        id=row.id,
        type=ChartObjectType(row.type),
        source=ChartObjectSource(row.source),
        symbol=row.symbol,
        timeframe=row.timeframe,
        points=points,
        price_low=row.price_low,
        price_high=row.price_high,
        side=row.side,
        label=row.label,
        confidence=float(row.confidence),
        as_of=int(row.as_of),
        origin=dict(row.origin or {}),
        subtype=row.subtype,
    )


def upsert_chart_object(session: Session, obj: ChartObject) -> ChartObject:
    if obj.source.value not in PERSISTABLE_SOURCES:
        raise ValueError(
            f"source {obj.source.value!r} is not persistable "
            f"(allowed: {sorted(PERSISTABLE_SOURCES)})"
        )
    now = datetime.now(timezone.utc)
    row = session.get(ChartObjectOverlay, obj.id)
    payload = dict(
        type=obj.type.value,
        source=obj.source.value,
        symbol=obj.symbol,
        timeframe=obj.timeframe,
        points=[{"time": p.time, "price": p.price} for p in obj.points],
        price_low=obj.price_low,
        price_high=obj.price_high,
        side=obj.side,
        label=obj.label,
        confidence=obj.confidence,
        as_of=obj.as_of,
        origin=dict(obj.origin),
        subtype=obj.subtype,
        updated_at=now,
        deleted_at=None,
    )
    if row is None:
        row = ChartObjectOverlay(id=obj.id, created_at=now, **payload)
        session.add(row)
    else:
        for key, value in payload.items():
            setattr(row, key, value)
    session.flush()
    return _row_to_chart_object(row)


def soft_delete_chart_object(
    session: Session, object_id: str, *, source: str | None = None
) -> bool:
    row = session.get(ChartObjectOverlay, object_id)
    if row is None or row.deleted_at is not None:
        return False
    if source is not None and row.source != source:
        return False
    row.deleted_at = datetime.now(timezone.utc)
    row.updated_at = row.deleted_at
    session.flush()
    return True


def list_chart_objects(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    sources: list[str] | None = None,
) -> list[ChartObject]:
    stmt = select(ChartObjectOverlay).where(
        ChartObjectOverlay.symbol == symbol.upper(),
        ChartObjectOverlay.timeframe == timeframe,
        ChartObjectOverlay.deleted_at.is_(None),
    )
    if sources:
        allowed = [s for s in sources if s in PERSISTABLE_SOURCES]
        if not allowed:
            return []
        stmt = stmt.where(ChartObjectOverlay.source.in_(allowed))
    else:
        stmt = stmt.where(ChartObjectOverlay.source.in_(list(PERSISTABLE_SOURCES)))
    rows = session.scalars(stmt).all()
    return [_row_to_chart_object(r) for r in rows]


def chart_object_to_dict(obj: ChartObject) -> dict[str, Any]:
    return obj.to_dict()
