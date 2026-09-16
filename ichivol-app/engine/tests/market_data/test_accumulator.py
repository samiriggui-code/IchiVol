"""Real-DB tests for app/market_data/accumulator.py, same conventions as
tests/market_data/test_collector.py (skipped if ichivol_engine_dev isn't
reachable, explicit cleanup around each test).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import Asset
from app.db.models import Candle as CandleRow
from app.db.session import SessionLocal, engine
from app.indicators.ichimoku import Candle
from app.market_data.accumulator import fetch_with_accumulation, needs_accumulation

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")

SYMBOL = "ACCUMTEST"
EXCHANGE = "biquote"


def _cleanup(session):
    asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange=EXCHANGE).one_or_none()
    if asset is not None:
        session.query(CandleRow).filter_by(asset_id=asset.id).delete()
        session.delete(asset)
        session.commit()


def _candles(times: range, base: float = 100.0) -> list[Candle]:
    return [
        Candle(time=t, open=base, high=base + 1, low=base - 1, close=base, volume=10.0)
        for t in times
    ]


class _FakeCappedProvider:
    """Simulates biquote: always returns exactly its own fixed window,
    ignoring whatever `limit` the caller asked for."""

    id = "biquote"

    def __init__(self, window: list[Candle]):
        self.window = window
        self.calls = 0

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int) -> list[Candle]:
        self.calls += 1
        return list(self.window)


def test_needs_accumulation_is_true_only_for_biquote():
    assert needs_accumulation("biquote") is True
    assert needs_accumulation("binance") is False
    assert needs_accumulation("twelve_data") is False


def test_fetch_with_accumulation_never_persists_the_still_forming_last_bar():
    session = SessionLocal()
    try:
        _cleanup(session)
        provider = _FakeCappedProvider(_candles(range(0, 5 * 3600, 3600)))  # 5 bars: t=0..14400

        fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)

        asset = session.query(Asset).filter_by(symbol=SYMBOL, exchange=EXCHANGE).one()
        stored_times = sorted(
            row.timestamp.timestamp()
            for row in session.query(CandleRow).filter_by(asset_id=asset.id).all()
        )
        # 5 bars fetched, but the last (t=14400, still "forming") must never
        # be written -- only the first 4 are persisted.
        assert stored_times == [0.0, 3600.0, 7200.0, 10800.0]
    finally:
        _cleanup(session)
        session.close()


def test_fetch_with_accumulation_returns_the_live_bars_including_the_last_one():
    session = SessionLocal()
    try:
        _cleanup(session)
        window = _candles(range(0, 5 * 3600, 3600))
        provider = _FakeCappedProvider(window)

        result = fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)

        # The caller still gets every live bar back, including the
        # not-yet-persisted last one -- accumulation must never starve the
        # caller of the freshest data.
        assert [c.time for c in result] == [c.time for c in window]
    finally:
        _cleanup(session)
        session.close()


def test_fetch_with_accumulation_grows_depth_across_repeated_calls():
    session = SessionLocal()
    try:
        _cleanup(session)

        # Call 1: a provider "window" covering hours 0..9 (10 bars).
        first_window = _candles(range(0, 10 * 3600, 3600))
        provider = _FakeCappedProvider(first_window)
        first_result = fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)
        assert len(first_result) == 10

        # Call 2: the live feed has "moved on" -- its capped window now only
        # covers hours 5..14 (the older hours 0..4 have scrolled out of the
        # provider's own cap, exactly like biquote always serving only its
        # most recent ~100 bars). Accumulation should still return the full
        # 0..14 span by combining what's stored (0..8, since hour 9 was
        # never persisted as the previous call's still-forming last bar)
        # with this call's live 5..14.
        second_window = _candles(range(5 * 3600, 15 * 3600, 3600))
        provider.window = second_window

        second_result = fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)

        assert [c.time for c in second_result] == list(range(0, 15 * 3600, 3600))
    finally:
        _cleanup(session)
        session.close()


def test_fetch_with_accumulation_trims_to_the_requested_limit():
    session = SessionLocal()
    try:
        _cleanup(session)
        provider = _FakeCappedProvider(_candles(range(0, 10 * 3600, 3600)))
        fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)

        provider.window = _candles(range(9 * 3600, 20 * 3600, 3600))
        result = fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=5)

        assert len(result) == 5
        # Trimming keeps the most recent bars, never the oldest.
        assert result[-1].time == 19 * 3600
    finally:
        _cleanup(session)
        session.close()


def test_fetch_with_accumulation_handles_an_empty_live_response():
    session = SessionLocal()
    try:
        _cleanup(session)
        provider = _FakeCappedProvider([])
        result = fetch_with_accumulation(provider, SYMBOL, "PROV_SYM", "1h", limit=300)
        assert result == []
    finally:
        _cleanup(session)
        session.close()
