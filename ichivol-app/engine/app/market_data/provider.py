"""MarketDataProvider contract -- the seam between the engine's indicators
(which only ever see a list[Candle]) and wherever prices actually come
from. Implementations today: BinanceSpotProvider (crypto) and
TwelveDataProvider (FX / metals / equities / indices). Adding another
later means writing a class that satisfies this Protocol and registering
it in app/market_data/registry.py -- screener / combiner / backtest only
ever see Candle objects.
"""

from __future__ import annotations

from typing import Protocol

from app.indicators.ichimoku import Candle


class MarketDataProvider(Protocol):
    id: str

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int) -> list[Candle]:
        """Real market data only -- no synthetic/mocked candles, ever."""
        ...
