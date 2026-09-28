"""AG-S1 — persistance des snapshots analystes par session (idempotente)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.analyst_cards import ENGINE_VERSION, build_analyst_cards
from app.db.models import AnalystSnapshot
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def upsert_analyst_snapshot(
    *,
    session_id: str,
    symbol: str,
    timeframe: str,
    as_of: int,
    cards: list[dict[str, Any]],
    engine_version: str = ENGINE_VERSION,
) -> tuple[dict[str, Any], bool]:
    """Insert or return existing row for (session_id, symbol, timeframe).

    Returns ``(row_dict, created)``. Idempotent : 2 déclenchements = 1 ligne.
    """
    sym = symbol.upper()
    tf = timeframe

    with SessionLocal() as db:
        existing = db.execute(
            select(AnalystSnapshot).where(
                AnalystSnapshot.session_id == session_id,
                AnalystSnapshot.symbol == sym,
                AnalystSnapshot.timeframe == tf,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _row_dict(existing), False

        row = AnalystSnapshot(
            session_id=session_id,
            as_of=int(as_of),
            symbol=sym,
            timeframe=tf,
            cards=cards,
            engine_version=engine_version,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raced = db.execute(
                select(AnalystSnapshot).where(
                    AnalystSnapshot.session_id == session_id,
                    AnalystSnapshot.symbol == sym,
                    AnalystSnapshot.timeframe == tf,
                )
            ).scalar_one()
            return _row_dict(raced), False
        db.refresh(row)
        return _row_dict(row), True


def take_session_snapshot(
    *,
    session_id: str,
    symbol: str,
    timeframe: str,
    limit: int = 500,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """Calcule les fiches + upsert (idempotent)."""
    built = build_analyst_cards(
        symbol,
        timeframe,
        limit=limit,
        x_twelve_data_key=x_twelve_data_key,
    )
    as_of = int(built.get("as_of") or 0)
    row, created = upsert_analyst_snapshot(
        session_id=session_id,
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        cards=list(built.get("cards") or []),
        engine_version=str(built.get("engine_version") or ENGINE_VERSION),
    )
    return {
        "created": created,
        "snapshot": row,
        "observe_only": True,
        "used_by_decision": False,
    }


def get_analyst_snapshot(
    *, session_id: str, symbol: str, timeframe: str
) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            select(AnalystSnapshot).where(
                AnalystSnapshot.session_id == session_id,
                AnalystSnapshot.symbol == symbol.upper(),
                AnalystSnapshot.timeframe == timeframe,
            )
        ).scalar_one_or_none()
        return _row_dict(row) if row is not None else None


def _row_dict(row: AnalystSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "as_of": row.as_of,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "cards": row.cards,
        "engine_version": row.engine_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
