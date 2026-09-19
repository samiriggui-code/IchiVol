"""Unit tests for the MT5 bridge client (no live terminal/network required).

Mirrors tests/market_data/test_biquote.py's shape: mock httpx, never touch
a real bridge or broker. The bridge itself (Wine + MetaTrader5 terminal)
cannot run in this test environment -- that's exactly why the seam is a
plain HTTP client on this side.
"""

from __future__ import annotations

import httpx
import pytest

from app.indicators.ichimoku import Candle
from app.market_data import mt5
from app.market_data.volume_semantics import VolumeType


def test_mt5_provider_id_and_default_volume_type():
    provider = mt5.MT5Provider()
    assert provider.id == "mt5"
    assert provider.volume_type == VolumeType.TICK_VOLUME


def test_unsupported_timeframe_raises_before_any_network_call():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        mt5.fetch_ohlcv("XAUUSD", "2h", 10)


def test_fetch_ohlcv_maps_json_and_marks_tick_volume(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "symbol": "XAUUSD",
                "resolved_symbol": "XAUUSD.a",
                "volume_type": "tick",
                "bars": [
                    {"time": 1704200400, "open": 2070.0, "high": 2075.0, "low": 2069.0, "close": 2074.0, "volume": 421},
                    {"time": 1704204000, "open": 2074.0, "high": 2078.0, "low": 2073.0, "close": 2077.0, "volume": 388},
                ],
            }

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    candles = mt5.fetch_ohlcv("XAUUSD", "1h", 2)
    assert len(candles) == 2
    assert isinstance(candles[0], Candle)
    assert candles[0].volume_type == VolumeType.TICK_VOLUME
    assert candles[0].time < candles[1].time


def test_fetch_ohlcv_marks_real_volume_when_bridge_says_so(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "volume_type": "real",
                "bars": [
                    {"time": 1704200400, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 1000},
                ],
            }

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    candles = mt5.fetch_ohlcv("MICRO_GOLD", "1h", 1)
    assert candles[0].volume_type == VolumeType.REPORTED_VOLUME


def test_fetch_ohlcv_dedupes_duplicate_timestamps_last_write_wins(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "volume_type": "tick",
                "bars": [
                    {"time": 1704200400, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                    {"time": 1704200400, "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2},
                    {"time": 1704204000, "open": 3.0, "high": 3.0, "low": 3.0, "close": 3.0, "volume": 3},
                ],
            }

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    candles = mt5.fetch_ohlcv("EURUSD", "1h", 3)
    assert len(candles) == 2
    assert candles[0].close == 2.0  # second duplicate row wins
    assert candles[1].close == 3.0


def test_fetch_ohlcv_raises_clean_value_error_on_empty_bars(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"bars": []}

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError, match="mt5_empty"):
        mt5.fetch_ohlcv("NOTASYMBOL", "1h", 5)


def test_fetch_ohlcv_raises_clean_value_error_on_error_body(monkeypatch):
    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"error": "invalid symbol: NOTASYMBOL"}

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError, match="mt5_error"):
        mt5.fetch_ohlcv("NOTASYMBOL", "1h", 5)


def test_fetch_ohlcv_raises_mt5_connection_error_when_bridge_not_logged_in(monkeypatch):
    class FakeResp:
        status_code = 503
        text = "terminal not connected to broker"

    monkeypatch.setattr(mt5.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(mt5.MT5ConnectionError, match="mt5_not_connected"):
        mt5.fetch_ohlcv("XAUUSD", "1h", 5)


def test_fetch_ohlcv_raises_mt5_connection_error_on_timeout(monkeypatch):
    def raise_timeout(*a, **k):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(mt5.httpx, "get", raise_timeout)
    with pytest.raises(mt5.MT5ConnectionError, match="mt5_bridge_timeout"):
        mt5.fetch_ohlcv("XAUUSD", "1h", 5)


def test_fetch_ohlcv_raises_mt5_connection_error_when_bridge_unreachable(monkeypatch):
    def raise_transport_error(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(mt5.httpx, "get", raise_transport_error)
    with pytest.raises(mt5.MT5ConnectionError, match="mt5_bridge_unreachable"):
        mt5.fetch_ohlcv("XAUUSD", "1h", 5)
