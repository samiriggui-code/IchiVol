"""Resolves a screener/decisions/backtest input to a concrete
(provider, provider_symbol) pair.

Compat rule (HANDOFF-CLAUDE-UNIVERSE-SKELETON.md §3): the frontend still
sends symbols like "BTCUSDT", not catalog ids -- and every existing test
uses ad hoc fixture symbols (TESTUSDT, PERSISTTEST, ...) that were never
meant to be "real" instruments. So resolution is two-tiered:

1. If the input matches a catalog instrument id, resolve through the
   catalog. An instrument with no provider yet (forex/metal/index/equity)
   raises ProviderNotWiredError with a clear reason -- never a crash deep
   in an HTTP client.
2. Otherwise, fall back to the pre-universe behavior: treat the input as a
   raw symbol for `default_provider` (Binance unless told otherwise). This
   is what keeps every existing symbol -- real crypto pairs and made-up
   test fixtures alike -- working exactly as before.

T11a-bis: fallback is tagged ``resolution="raw_fallback"`` (catalog hits
use ``"catalog"``). Unpacking ``provider, symbol = resolve(...)`` still
works — ``ResolvedSymbol`` iterates only those two fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.indicators.ichimoku import Candle
from app.market_data.accumulator import fetch_with_accumulation, needs_accumulation
from app.market_data.provider import MarketDataProvider
from app.market_data.registry import get_provider
from app.universe.catalog import get_instrument

ResolutionKind = Literal["catalog", "raw_fallback"]


class ProviderNotWiredError(ValueError):
    def __init__(self, instrument_id: str, asset_class: str):
        super().__init__(f"provider_not_wired: {instrument_id} ({asset_class})")
        self.instrument_id = instrument_id
        self.asset_class = asset_class


@dataclass(frozen=True)
class ResolvedSymbol:
    provider: MarketDataProvider
    provider_symbol: str
    resolution: ResolutionKind

    def __iter__(self):
        """Back-compat: ``provider, symbol = resolve(...)``."""
        yield self.provider
        yield self.provider_symbol


def resolve(
    symbol_or_id: str, default_provider: str = "binance"
) -> ResolvedSymbol:
    instrument = get_instrument(symbol_or_id)
    if instrument is not None:
        provider = get_provider(instrument.provider) if instrument.provider else None
        if provider is None:
            raise ProviderNotWiredError(instrument.id, instrument.asset_class.value)
        return ResolvedSymbol(provider, instrument.provider_symbol, "catalog")

    provider = get_provider(default_provider)
    if provider is None:
        raise ValueError(
            f"unsupported exchange {default_provider!r} "
            f"(wired providers: binance, twelve_data, biquote)"
        )
    return ResolvedSymbol(provider, symbol_or_id, "raw_fallback")


def resolve_and_fetch(
    symbol: str, timeframe: str, limit: int = 300, default_provider: str = "binance"
) -> tuple[MarketDataProvider, str, list[Candle]]:
    """Same resolution as `resolve()`, plus the actual fetch -- routed
    through app/market_data/accumulator.py for providers whose single call
    hard-caps well below what's commonly asked for (biquote: ~100 bars
    regardless of `limit`), so depth can accumulate in this engine's own DB
    over repeated calls instead of every request silently getting whatever
    the provider felt like returning. Prefer this over calling
    `provider.fetch_ohlcv()` directly wherever the caller doesn't have a
    specific reason not to (a chart/decision/backtest almost never does)."""
    resolved = resolve(symbol, default_provider)
    provider, provider_symbol = resolved.provider, resolved.provider_symbol
    if needs_accumulation(provider.id):
        candles = fetch_with_accumulation(provider, symbol, provider_symbol, timeframe, limit)
    else:
        candles = provider.fetch_ohlcv(provider_symbol, timeframe, limit)
    return provider, provider_symbol, candles
