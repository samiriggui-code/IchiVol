"""Instrument identity — owned by IchiVol, not by any exchange brand.

`instrument_id` is the stable key everywhere (screener, decisions, DB later).
Provider-specific symbols live only in `provider` / `provider_symbol`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"
    INDEX = "index"
    EQUITY = "equity"
    METAL = "metal"
    ENERGY = "energy"


@dataclass(frozen=True)
class Instrument:
    """One tradeable/analyzable series in the IchiVol universe."""

    id: str
    """Canonical id, e.g. ``EURUSD``, ``XAUUSD``, ``BTC-USD``."""

    asset_class: AssetClass
    label: str
    """Human label (EUR/USD, Or spot, Bitcoin…)."""

    provider: str | None
    """Registered MarketData provider id, or None if not wired yet."""

    provider_symbol: str | None
    """Symbol as understood by that provider (e.g. Binance ``BTCUSDT``)."""

    enabled: bool = True
    """Include in default screener when a provider is wired."""

    quote: str = "USD"
    """Quote currency / unit for display."""

    @property
    def is_wired(self) -> bool:
        return bool(self.provider and self.provider_symbol)
