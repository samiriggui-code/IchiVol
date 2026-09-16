"""Unit tests for the biquote adapter (no live network required)."""

from __future__ import annotations

import pytest

from app.indicators.ichimoku import Candle
from app.market_data import biquote


@pytest.fixture(autouse=True)
def _clear_cache():
    biquote._cache.clear()
    yield
    biquote._cache.clear()


def test_biquote_provider_id():
    assert biquote.BiquoteProvider().id == "biquote"


def test_unsupported_timeframe_raises_before_any_network_call():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        biquote.fetch_ohlc("EURUSD", "2h", 10)


def test_fetch_ohlc_maps_json_and_sorts_oldest_first(monkeypatch):
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            # biquote returns newest-first, exactly like the real API.
            return {
                "symbol": "EURUSD",
                "interval": "1h",
                "bars": [
                    {
                        "openTime": "2024-01-02T16:00:00Z",
                        "open": "1.105",
                        "high": "1.12",
                        "low": "1.10",
                        "close": "1.11",
                        "volume": 0,
                        "tickVolume": 100,
                    },
                    {
                        "openTime": "2024-01-02T15:00:00Z",
                        "open": "1.10",
                        "high": "1.11",
                        "low": "1.09",
                        "close": "1.105",
                        "volume": 0,
                        "tickVolume": 0,
                    },
                ],
            }

    monkeypatch.setattr(biquote.httpx, "get", lambda *a, **k: FakeResp())
    candles = biquote.fetch_ohlc("EURUSD", "1h", 2)
    assert len(candles) == 2
    assert isinstance(candles[0], Candle)
    # Sorted oldest-first regardless of the newest-first API order.
    assert candles[0].time < candles[1].time
    assert candles[0].close == 1.105
    assert candles[0].volume == 0.0  # tickVolume 0 on the oldest bar
    assert candles[1].volume == 100.0


def test_fetch_ohlc_raises_clean_value_error_on_empty_bars(monkeypatch):
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"symbol": "NOTASYMBOL", "interval": "1h", "bars": []}

    monkeypatch.setattr(biquote.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError, match="biquote_empty"):
        biquote.fetch_ohlc("NOTASYMBOL", "1h", 5)


def test_fetch_ohlc_raises_clean_value_error_on_message_body(monkeypatch):
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": "At least one symbol is required"}

    monkeypatch.setattr(biquote.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError, match="biquote_error"):
        biquote.fetch_ohlc("EURUSD", "1h", 5)


def test_fetch_ohlc_caps_requested_count_at_the_server_ceiling(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "bars": [
                    {
                        "openTime": "2024-01-02T15:00:00Z",
                        "open": "1.10",
                        "high": "1.11",
                        "low": "1.09",
                        "close": "1.105",
                        "tickVolume": 1,
                    }
                ]
            }

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResp()

    monkeypatch.setattr(biquote.httpx, "get", fake_get)
    biquote.fetch_ohlc("EURUSD", "1d", 5000)
    assert captured["params"]["count"] == biquote._MAX_BARS_PER_CALL


def test_fetch_ohlc_serves_from_cache_within_ttl(monkeypatch):
    calls = {"n": 0}

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            calls["n"] += 1
            return {
                "bars": [
                    {
                        "openTime": "2024-01-02T15:00:00Z",
                        "open": "1.10",
                        "high": "1.11",
                        "low": "1.09",
                        "close": "1.105",
                        "tickVolume": 1,
                    }
                ]
            }

    monkeypatch.setattr(biquote.httpx, "get", lambda *a, **k: FakeResp())
    biquote.fetch_ohlc("EURUSD", "1h", 1)
    biquote.fetch_ohlc("EURUSD", "1h", 1)
    assert calls["n"] == 1
