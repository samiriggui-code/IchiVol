"""Provider capability model (V3 delta) — observation / routing honesty.

Does not invent feeds. Declares what each registered provider can supply
today so Lab / screener / UI can avoid assuming Forex has exchange volume
or that every venue has depth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    ohlcv: bool = True
    historical: bool = True
    streaming: bool = False
    quotes: bool = False
    trades: bool = False
    depth: bool = False
    open_interest: bool = False
    funding: bool = False
    real_volume: bool = False
    tick_volume: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Explicit declarations — keep in sync with what code actually wires.
_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "binance": ProviderCapabilities(
        provider_id="binance",
        ohlcv=True,
        historical=True,
        streaming=False,  # REST poll only today; WS unused
        quotes=True,  # bookTicker implemented (BinanceQuoteProvider); not default paper path
        trades=True,  # fetch_trades + aggTrades (protection); not Lab default
        depth=False,  # unused
        open_interest=True,  # futures hist via binance_futures
        funding=True,
        real_volume=True,  # EXCHANGE_VOLUME
        tick_volume=False,
        notes=(
            "Spot klines + taker_buy_volume; futures OI/funding; "
            "quotes/trades coded but not default screener path; no WS/depth yet."
        ),
    ),
    "biquote": ProviderCapabilities(
        provider_id="biquote",
        ohlcv=True,
        historical=True,  # via accumulator over time (~100 bars/call)
        streaming=False,
        quotes=False,
        trades=False,
        depth=False,
        open_interest=False,
        funding=False,
        real_volume=False,
        tick_volume=True,
        notes=(
            "Keyless FX/metals/indices/energy; ~100 bars per call; "
            "TICK_VOLUME; accumulate for depth."
        ),
    ),
    "twelve_data": ProviderCapabilities(
        provider_id="twelve_data",
        ohlcv=True,
        historical=True,
        streaming=False,
        quotes=False,
        trades=False,
        depth=False,
        open_interest=False,
        funding=False,
        real_volume=False,  # REPORTED_VOLUME when present else NONE
        tick_volume=False,
        notes="Equities; credit-budgeted; volume may be NONE.",
    ),
}


def get_capabilities(provider_id: str) -> ProviderCapabilities | None:
    return _CAPABILITIES.get(provider_id)


def list_capabilities() -> list[ProviderCapabilities]:
    return [_CAPABILITIES[k] for k in sorted(_CAPABILITIES)]


def capabilities_dict(provider_id: str) -> dict | None:
    caps = get_capabilities(provider_id)
    return None if caps is None else caps.to_dict()
