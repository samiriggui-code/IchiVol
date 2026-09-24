"""Persist fetched candles into the engine's own database.

Candles are immutable once closed, so this only ever inserts rows that
don't already exist (by asset/timeframe/timestamp) -- never updates or
overwrites, and re-running a collection pass over overlapping ranges is
always safe (idempotent).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Asset
from app.db.models import Candle as CandleRow
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType


def fetch_stored_candles(
    session: Session, *, symbol: str, exchange: str, timeframe: str, limit: int
) -> list[Candle]:
    """The most recent `limit` candles already accumulated for (symbol,
    exchange, timeframe), oldest first -- the read half of the accumulation
    pattern app/market_data/accumulator.py builds on. Returns an empty list
    for an asset that has never been collected, never an error."""
    asset = session.execute(
        select(Asset).where(Asset.symbol == symbol, Asset.exchange == exchange)
    ).scalar_one_or_none()
    if asset is None:
        return []

    rows = session.execute(
        select(CandleRow)
        .where(CandleRow.asset_id == asset.id, CandleRow.timeframe == timeframe)
        .order_by(CandleRow.timestamp.desc())
        .limit(limit)
    ).scalars().all()

    out: list[Candle] = []
    for row in reversed(rows):
        vt_raw = getattr(row, "volume_type", None)
        try:
            vt = VolumeType(vt_raw) if vt_raw else VolumeType.NONE
        except ValueError:
            vt = VolumeType.NONE
        out.append(
            Candle(
                time=int(row.timestamp.timestamp()),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                taker_buy_volume=getattr(row, "taker_buy_volume", None),
                volume_type=vt,
            )
        )
    return out


def get_or_create_asset(session: Session, symbol: str, exchange: str) -> Asset:
    asset = session.execute(
        select(Asset).where(Asset.symbol == symbol, Asset.exchange == exchange)
    ).scalar_one_or_none()
    if asset is None:
        asset = Asset(symbol=symbol, exchange=exchange)
        session.add(asset)
        session.flush()
    return asset


def upsert_candles(
    session: Session,
    *,
    symbol: str,
    exchange: str,
    timeframe: str,
    candles: Sequence[Candle],
) -> int:
    """Insert candles not already stored. Returns the count actually
    inserted (0 on a fully-overlapping re-run)."""
    if not candles:
        return 0

    asset = get_or_create_asset(session, symbol, exchange)
    rows = [
        {
            "asset_id": asset.id,
            "timeframe": timeframe,
            "timestamp": datetime.fromtimestamp(c.time, tz=timezone.utc),
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "volume_type": (
                c.volume_type.value if getattr(c, "volume_type", None) is not None else None
            ),
            "taker_buy_volume": getattr(c, "taker_buy_volume", None),
        }
        for c in candles
    ]

    stmt = pg_insert(CandleRow).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["asset_id", "timeframe", "timestamp"]
    ).returning(CandleRow.id)
    # rowcount is unreliable for multi-row INSERT ... ON CONFLICT with some
    # DBAPI drivers (psycopg reports -1 here) -- RETURNING gives an exact
    # count of the rows actually inserted instead.
    inserted_ids = session.execute(stmt).fetchall()
    session.commit()
    return len(inserted_ids)
