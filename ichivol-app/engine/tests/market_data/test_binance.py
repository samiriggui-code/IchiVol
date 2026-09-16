"""Integration test against the real Binance public REST API (no mocking --
the mission explicitly requires real market data, never simulated). Skips
gracefully if the network/endpoint isn't reachable from this environment
rather than failing the whole suite on that account.
"""

from __future__ import annotations

import httpx
import pytest

from app.market_data.binance import fetch_klines

try:
    httpx.get("https://data-api.binance.vision/api/v3/ping", timeout=5.0).raise_for_status()
    NETWORK_AVAILABLE = True
except httpx.HTTPError:
    NETWORK_AVAILABLE = False

pytestmark = pytest.mark.skipif(not NETWORK_AVAILABLE, reason="data-api.binance.vision not reachable")


def test_fetch_klines_returns_real_recent_candles():
    candles = fetch_klines("BTCUSDT", "1h", limit=10)
    assert len(candles) == 10
    for c in candles:
        assert c.high >= c.low
        assert c.high >= c.open
        assert c.high >= c.close
        assert c.low <= c.open
        assert c.low <= c.close
        assert c.volume >= 0
    # Strictly increasing open-times, one hour apart.
    for a, b in zip(candles, candles[1:]):
        assert b.time - a.time == 3600
    # Taker buy volume (CVD input, app/indicators/cvd.py) comes from the
    # same kline response -- no separate endpoint -- and can never exceed
    # the bar's own total volume.
    for c in candles:
        assert c.taker_buy_volume is not None
        assert 0.0 <= c.taker_buy_volume <= c.volume
