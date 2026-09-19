"""Provider registry: one lookup table from provider id (matching
`Instrument.provider` in the catalog) to a MarketDataProvider instance.
Adding a real forex/equity/metal provider later is: write the class,
register it here under its id, done -- catalog entries just start
resolving instead of raising ProviderNotWiredError.
"""

from __future__ import annotations

from app.config import settings
from app.market_data.binance import BinanceSpotProvider
from app.market_data.biquote import BiquoteProvider
from app.market_data.provider import MarketDataProvider
from app.market_data.twelve_data import TwelveDataProvider

_PROVIDERS: dict[str, MarketDataProvider] = {
    "binance": BinanceSpotProvider(),
    "twelve_data": TwelveDataProvider(),
    "biquote": BiquoteProvider(),
}

# MT5 stays unregistered (get_provider("mt5") -> None, exactly like any
# other unwired id) unless explicitly turned on -- the engine must boot and
# serve every other provider identically whether or not the mt5-bridge
# service even exists (docs/TRADING_ARCHITECTURE_V2.md §11).
if settings.mt5_enabled:
    from app.market_data.mt5 import MT5Provider

    _PROVIDERS["mt5"] = MT5Provider()


def get_provider(provider_id: str) -> MarketDataProvider | None:
    return _PROVIDERS.get(provider_id)
