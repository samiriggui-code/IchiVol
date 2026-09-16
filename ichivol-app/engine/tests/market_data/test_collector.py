from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import Asset
from app.db.models import Candle as CandleRow
from app.db.session import SessionLocal, engine
from app.indicators.ichimoku import Candle
from app.market_data.collector import fetch_stored_candles, upsert_candles

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")

SYMBOL = "COLLECTORTEST"
EXCHANGE = "binance"


def _sample_candles(n: int, start: int = 1_700_000_000) -> list[Candle]:
    return [
        Candle(time=start + i * 3600, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=10 + i)
        for i in range(n)
    ]


def _cleanup(session):
    asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange=EXCHANGE).one_or_none()
    if asset is not None:
        session.query(CandleRow).filter_by(asset_id=asset.id).delete()
        session.delete(asset)
        session.commit()


def test_upsert_inserts_new_candles_and_is_idempotent():
    session = SessionLocal()
    try:
        _cleanup(session)
        candles = _sample_candles(5)

        inserted_first = upsert_candles(
            session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", candles=candles
        )
        assert inserted_first == 5

        inserted_second = upsert_candles(
            session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", candles=candles
        )
        assert inserted_second == 0

        asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange=EXCHANGE).one()
        stored = session.query(CandleRow).filter_by(asset_id=asset.id).all()
        assert len(stored) == 5
    finally:
        _cleanup(session)
        session.close()


def test_upsert_only_inserts_the_genuinely_new_tail():
    session = SessionLocal()
    try:
        _cleanup(session)
        first_batch = _sample_candles(3)
        upsert_candles(session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", candles=first_batch)

        overlapping_batch = _sample_candles(6)  # first 3 overlap, last 3 are new
        inserted = upsert_candles(
            session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", candles=overlapping_batch
        )
        assert inserted == 3

        asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange=EXCHANGE).one()
        stored = session.query(CandleRow).filter_by(asset_id=asset.id).all()
        assert len(stored) == 6
    finally:
        _cleanup(session)
        session.close()


def test_fetch_stored_candles_returns_empty_for_a_never_collected_asset():
    session = SessionLocal()
    try:
        _cleanup(session)
        assert fetch_stored_candles(
            session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", limit=100
        ) == []
    finally:
        _cleanup(session)
        session.close()


def test_fetch_stored_candles_returns_the_most_recent_ones_oldest_first():
    session = SessionLocal()
    try:
        _cleanup(session)
        candles = _sample_candles(10)
        upsert_candles(session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", candles=candles)

        result = fetch_stored_candles(
            session, symbol=SYMBOL, exchange=EXCHANGE, timeframe="1h", limit=3
        )

        assert [c.time for c in result] == [c.time for c in candles[-3:]]
    finally:
        _cleanup(session)
        session.close()
