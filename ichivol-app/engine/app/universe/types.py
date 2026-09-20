"""Instrument identity — owned by IchiVol, not by any exchange brand.

`instrument_id` is the stable key everywhere (screener, decisions, DB later).
Provider-specific symbols live only in `provider` / `provider_symbol`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.market_data.contracts import ExecutionMode


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"
    INDEX = "index"
    EQUITY = "equity"
    METAL = "metal"
    ENERGY = "energy"


class ProductType(str, Enum):
    """What is actually traded. An index, an ETF on it, a future and a CFD are
    different products with different fees, sizing, margin and hours."""

    SPOT = "spot"
    STOCK = "stock"
    ETF = "etf"
    CFD = "cfd"
    FUTURE = "future"
    OPTION = "option"
    INDEX_REFERENCE = "index_reference"
    """Analysis-only underlying; not directly tradable."""


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

    product_type: ProductType | None = None
    """None = not yet documented (unknown, never assumed)."""

    execution_mode: ExecutionMode = ExecutionMode.CANDLE_ONLY
    """QUOTE_BASED only once a bid/ask source is wired and validated."""

    fee_profile_id: str | None = None
    """FeeSchedule id applicable to the traded product; None = simulation unavailable."""

    exchange_timezone: str | None = None
    quantity_step: str | None = None
    """Decimal string (e.g. '0.00001'); None = unknown."""

    @property
    def analysis_available(self) -> bool:
        return self.enabled and self.is_wired

    @property
    def simulation_available(self) -> bool:
        """Needs data, a documented product, an execution model and a fee profile."""
        return (
            self.analysis_available
            and self.product_type is not None
            and self.product_type is not ProductType.INDEX_REFERENCE
            and self.execution_mode is not ExecutionMode.NONE
            and self.fee_profile_id is not None
        )
