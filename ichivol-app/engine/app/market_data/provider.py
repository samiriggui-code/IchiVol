"""MarketDataProvider contract -- the seam between the engine's indicators
(which only ever see a list[Candle]) and wherever prices actually come
from. Implementations today: BinanceSpotProvider (crypto),
TwelveDataProvider (equities), BiquoteProvider (FX / metals / indices).
Adding another later means writing a class that satisfies this Protocol
and registering it in app/market_data/registry.py -- screener / combiner /
backtest only ever see Candle objects.

Providers MUST declare `volume_type` (see app/market_data/volume_semantics.py)
and stamp every Candle they return. Unavailable providers stay unregistered
(or raise) — never invent real-looking OHLCV.
"""

from __future__ import annotations

from typing import Protocol

from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType


class MarketDataProvider(Protocol):
    id: str
    volume_type: VolumeType

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int) -> list[Candle]:
        """Real market data only -- no synthetic/mocked candles, ever."""
        ...
