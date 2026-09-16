"""Provider registry: one lookup table from provider id (matching
`Instrument.provider` in the catalog) to a MarketDataProvider instance.
Adding a real forex/equity/metal provider later is: write the class,
register it here under its id, done -- catalog entries just start
resolving instead of raising ProviderNotWiredError.
"""

from __future__ import annotations

from app.market_data.binance import BinanceSpotProvider
from app.market_data.biquote import BiquoteProvider
from app.market_data.provider import MarketDataProvider
from app.market_data.twelve_data import TwelveDataProvider

_PROVIDERS: dict[str, MarketDataProvider] = {
    "binance": BinanceSpotProvider(),
    "twelve_data": TwelveDataProvider(),
    "biquote": BiquoteProvider(),
}


def get_provider(provider_id: str) -> MarketDataProvider | None:
    return _PROVIDERS.get(provider_id)
