"""The IchiVol instrument universe -- one flat catalog spanning every asset
class the product cares about, independent of exchange brands
(docs/HANDOFF-CLAUDE-UNIVERSE-SKELETON.md, docs/MARKET-DATA-STRATEGY.md).

Providers:
- ``binance`` — crypto spot (Binance Vision, data-only)
- ``twelve_data`` — equities only now (Phase 1b); real exchange volume
  matters more there than anywhere biquote covers, and narrowing it to
  AAPL/TSLA leaves its scarce ~7 credit/min budget almost idle
- ``biquote`` — FX / metals / indices / energy (Phase 1c). Free, keyless,
  no documented per-minute quota -- see app/market_data/biquote.py for the
  one real constraint (hard-capped at ~100 bars/call, so it's a live feed
  that accumulates depth over time via the collector, not a one-shot
  backfill source)

Crypto ids stay identical to Binance symbols (BTCUSDT…) for API/front compat.
Non-crypto ids use conventional tickers (EURUSD, XAUUSD…); ``provider_symbol``
holds each provider's native form (Twelve Data: EUR/USD, XAU/USD… ; biquote:
EURUSD, XAUUSD… unchanged, but SPX500/NAS100 for the index CFDs).

``enabled`` on non-crypto defaults True for /universe and on-demand decisions.
``default_watchlist()`` includes crypto plus every biquote-backed instrument
(no scarce budget to protect there) but excludes the twelve_data-backed
equities, so the background screener does not burn Twelve Data's free-tier
credits on every refresh.
"""

from __future__ import annotations

from app.universe.types import AssetClass, Instrument, ProductType

_CRYPTO_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
    "LTCUSDT", "ATOMUSDT", "UNIUSDT", "NEARUSDT", "APTUSDT",
    "ARBUSDT", "OPUSDT", "SUIUSDT", "PEPEUSDT", "TONUSDT",
)


def _crypto_instrument(symbol: str) -> Instrument:
    return Instrument(
        id=symbol,
        asset_class=AssetClass.CRYPTO,
        label=symbol.removesuffix("USDT"),
        provider="binance",
        provider_symbol=symbol,
        quote="USDT",
    )


def _twelve(
    instrument_id: str,
    asset_class: AssetClass,
    label: str,
    provider_symbol: str,
    quote: str = "USD",
) -> Instrument:
    return Instrument(
        id=instrument_id,
        asset_class=asset_class,
        label=label,
        provider="twelve_data",
        provider_symbol=provider_symbol,
        quote=quote,
        enabled=True,
    )


def _biquote(
    instrument_id: str,
    asset_class: AssetClass,
    label: str,
    provider_symbol: str,
    quote: str = "USD",
) -> Instrument:
    return Instrument(
        id=instrument_id,
        asset_class=asset_class,
        label=label,
        provider="biquote",
        provider_symbol=provider_symbol,
        quote=quote,
        enabled=True,
    )


UNIVERSE: list[Instrument] = [
    *(_crypto_instrument(s) for s in _CRYPTO_SYMBOLS),
    # forex — biquote (free, keyless; symbol is identical to the instrument id)
    _biquote("EURUSD", AssetClass.FOREX, "EUR/USD", "EURUSD"),
    _biquote("GBPUSD", AssetClass.FOREX, "GBP/USD", "GBPUSD"),
    _biquote("USDJPY", AssetClass.FOREX, "USD/JPY", "USDJPY", quote="JPY"),
    # metal — biquote (explicit provider_symbol, never naive guess)
    _biquote("XAUUSD", AssetClass.METAL, "Or / USD", "XAUUSD"),
    _biquote("XAGUSD", AssetClass.METAL, "Argent / USD", "XAGUSD"),
    # index — biquote (index CFD mirrors; native symbols differ from the id.
    # "SPX500"/"NAS100" are listed in biquote's /api/symbols catalog but
    # return empty bars live -- "US500"/"USTEC" are the tickers that
    # actually carry data, confirmed live 2026-09-15. /api/symbols'
    # `hasData` flag isn't reliable either way -- it reads false even for
    # US500/EURUSD/AAPL, which do return real bars -- so every biquote
    # provider_symbol below was verified against the live /ohlc endpoint,
    # never assumed from the symbols listing.)
    _biquote("SPX", AssetClass.INDEX, "S&P 500", "US500"),
    _biquote("NDX", AssetClass.INDEX, "Nasdaq 100", "USTEC"),
    # equity — Twelve Data (kept for real exchange volume; biquote's equity
    # mirrors are CFDs with volume=0, same tick-only caveat as forex/metal)
    _twelve("AAPL", AssetClass.EQUITY, "Apple", "AAPL"),
    _twelve("TSLA", AssetClass.EQUITY, "Tesla", "TSLA"),
    # energy — biquote ("WTI" itself returns empty bars live; "USOIL" is the
    # ticker that actually carries WTI crude data, confirmed live 2026-09-15)
    _biquote("WTI", AssetClass.ENERGY, "Pétrole WTI", "USOIL"),
    # Futures & Crypto portfolio only (app/paper/futures_crypto.py) -- never in the shared watchlist, so the
    # baseline and the other accounts never trade them. No free futures feed: YM is priced from the Dow Jones
    # CFD ("US30" confirmed live on biquote 2026-10-07), MGC from spot gold, BTCCME from Binance spot BTCUSDT.
    # BTCPERP has its own candles (Binance USD-M perpetual).
    Instrument(
        id="YM", asset_class=AssetClass.INDEX, label="E-mini Dow (YM)", provider="biquote",
        provider_symbol="US30", product_type=ProductType.FUTURE, exchange_timezone="America/Chicago",
        in_default_watchlist=False,
    ),
    Instrument(
        id="MGC", asset_class=AssetClass.METAL, label="Micro Gold (MGC)", provider="biquote",
        provider_symbol="XAUUSD", product_type=ProductType.FUTURE, exchange_timezone="America/Chicago",
        in_default_watchlist=False,
    ),
    Instrument(
        id="BTCPERP", asset_class=AssetClass.CRYPTO, label="BTC perpétuel", provider="binance_usdm",
        provider_symbol="BTCUSDT", quote="USDT", product_type=ProductType.FUTURE, in_default_watchlist=False,
    ),
    Instrument(
        id="BTCCME", asset_class=AssetClass.CRYPTO, label="BTC CME (MBT)", provider="binance",
        provider_symbol="BTCUSDT", quote="USD", product_type=ProductType.FUTURE,
        exchange_timezone="America/Chicago", in_default_watchlist=False,
    ),
]

_BY_ID: dict[str, Instrument] = {instrument.id: instrument for instrument in UNIVERSE}


def get_instrument(instrument_id: str) -> Instrument | None:
    return _BY_ID.get(instrument_id)


def by_class(asset_class: AssetClass) -> list[Instrument]:
    """Shared-watchlist instruments of one class (dedicated-portfolio instruments excluded)."""
    return [i for i in UNIVERSE if i.asset_class == asset_class and i.in_default_watchlist]


def dedicated_only_ids() -> frozenset[str]:
    """Instruments only a dedicated portfolio trades (never the baseline / shared accounts)."""
    return frozenset(i.id for i in UNIVERSE if not i.in_default_watchlist)


def wired_instruments() -> list[Instrument]:
    """Wired shared-watchlist instruments (dedicated-portfolio instruments excluded)."""
    return [i for i in UNIVERSE if i.is_wired and i.in_default_watchlist]


def default_watchlist() -> list[str]:
    """Screener default: crypto (binance) + FX/metal/index/energy (biquote) --
    both have no scarce per-minute budget to protect. Twelve Data-backed
    equities stay out so the background screener doesn't burn its free-tier
    credits on every refresh."""
    return [
        i.id
        for i in UNIVERSE
        if i.is_wired and i.enabled and i.in_default_watchlist and i.provider in ("binance", "biquote")
    ]
