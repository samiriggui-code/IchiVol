"""Binance public REST client for OHLCV collection.

Same endpoint and time convention as the already-shipped TS client
(ichivol-app/src/lib/binance.ts): `data-api.binance.vision` (reachable from
more regions than api.binance.com, per that file's own comment), kline
open-time converted from milliseconds to whole seconds. Real market data
only -- no synthetic/mocked candles anywhere in this module.

A kline row also carries "taker buy base asset volume" (index 9) -- the
same call already made for OHLCV, no extra request needed -- which is
enough to derive Cumulative Volume Delta (app/indicators/cvd.py, V2
"participation avancée") without fetching raw trades.
"""

from __future__ import annotations

import httpx

from app.indicators.ichimoku import Candle

BASE_URL = "https://data-api.binance.vision"


def fetch_klines(symbol: str, interval: str, limit: int = 300) -> list[Candle]:
    response = httpx.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10.0,
    )
    response.raise_for_status()
    rows = response.json()
    return [
        Candle(
            time=int(row[0]) // 1000,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            taker_buy_volume=float(row[9]) if len(row) > 9 else None,
        )
        for row in rows
    ]


class BinanceSpotProvider:
    """Satisfies app.market_data.provider.MarketDataProvider. Deliberately a
    thin wrapper that calls the bare `fetch_klines` name above rather than
    reimplementing the HTTP call: `fetch_klines` stays the single façade
    tests patch (`monkeypatch.setattr(app.market_data.binance, "fetch_klines",
    ...)`), whether they go through this class or call it directly."""

    id = "binance"

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        return fetch_klines(provider_symbol, timeframe, limit)
