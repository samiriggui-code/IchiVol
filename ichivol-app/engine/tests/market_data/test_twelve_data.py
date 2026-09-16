"""Unit tests for Twelve Data adapter (no live network required)."""

from __future__ import annotations

import httpx
import pytest

from app.indicators.ichimoku import Candle
from app.market_data import twelve_data


@pytest.fixture(autouse=True)
def _reset_api_key_override():
    # ContextVar.set() persists for the rest of whatever context it's set
    # in -- fine per-request under FastAPI (Starlette copies the context
    # fresh per request), but pytest runs test functions in one shared
    # context, so a leftover override from one test would otherwise leak
    # into the next. Reset around every test in this module.
    twelve_data.set_api_key_override(None)
    yield
    twelve_data.set_api_key_override(None)


def test_twelve_data_provider_id():
    assert twelve_data.TwelveDataProvider().id == "twelve_data"


def test_fetch_time_series_requires_api_key(monkeypatch):
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "")
    with pytest.raises(ValueError, match="twelve_data_api_key_missing"):
        twelve_data.fetch_time_series("EUR/USD", "1h", 10)


def test_api_key_override_takes_precedence_over_settings(monkeypatch):
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "operator-key")
    twelve_data.set_api_key_override("clients-own-key")
    assert twelve_data._resolve_api_key() == "clients-own-key"


def test_no_override_falls_back_to_operator_settings_key(monkeypatch):
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "operator-key")
    assert twelve_data._resolve_api_key() == "operator-key"


def test_blank_override_falls_back_to_operator_settings_key(monkeypatch):
    # "" (client cleared the field but didn't save yet, or a proxy bug sends
    # an empty header) must behave like "no override", not like "no key at
    # all" -- the operator's key should still work.
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "operator-key")
    twelve_data.set_api_key_override("")
    assert twelve_data._resolve_api_key() == "operator-key"


def test_fetch_time_series_maps_json(monkeypatch):
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "test-key")

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "ok",
                "values": [
                    {
                        "datetime": "2024-01-02 15:00:00",
                        "open": "1.10",
                        "high": "1.11",
                        "low": "1.09",
                        "close": "1.105",
                        "volume": "",
                    },
                    {
                        "datetime": "2024-01-02 16:00:00",
                        "open": "1.105",
                        "high": "1.12",
                        "low": "1.10",
                        "close": "1.11",
                        "volume": "100",
                    },
                ],
            }

    monkeypatch.setattr(twelve_data.httpx, "get", lambda *a, **k: FakeResp())
    candles = twelve_data.fetch_time_series("EUR/USD", "1h", 2)
    assert len(candles) == 2
    assert isinstance(candles[0], Candle)
    assert candles[0].open == 1.10
    assert candles[0].volume == 0.0
    assert candles[1].volume == 100.0
    assert candles[0].time < candles[1].time


def test_unsupported_timeframe(monkeypatch):
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "test-key")
    with pytest.raises(ValueError, match="unsupported timeframe"):
        twelve_data.fetch_time_series("AAPL", "2h", 10)


def test_fetch_time_series_raises_clean_value_error_on_real_http_404(monkeypatch):
    # Live-confirmed: Twelve Data does not always follow its own documented
    # "200 + status:error" convention. An invalid symbol, or one gated
    # behind a paid plan (SPX/NDX require Grow/Venture on the free tier),
    # comes back as a genuine HTTP 404 whose body still carries the useful
    # message -- the caller (routes.py) only catches ValueError, so this
    # must never surface as a raw httpx.HTTPStatusError.
    monkeypatch.setattr(twelve_data.settings, "twelve_data_api_key", "test-key")

    class FakeResp:
        status_code = 404

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("404", request=None, response=self)

        def json(self) -> dict:
            return {"code": 404, "message": "This symbol is available starting with the Grow plan.", "status": "error"}

    monkeypatch.setattr(twelve_data.httpx, "get", lambda *a, **k: FakeResp())
    with pytest.raises(ValueError, match="twelve_data_error"):
        twelve_data.fetch_time_series("SPX", "1d", 5)
