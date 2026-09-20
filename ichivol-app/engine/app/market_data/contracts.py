"""Provider-independent data contracts for analysis vs. execution simulation.

Candles feed the indicators (see ``MarketDataProvider`` in provider.py).
Quotes (bid/ask) and trades feed the virtual broker's fill model. A provider
may implement any subset; an instrument whose provider cannot supply quotes
runs in ``ExecutionMode.CANDLE_ONLY`` and the broker must then apply the
documented, conservative assumptions instead of pretending to have a book.

Every datum carries its provenance. Nothing here fabricates a value: a missing
quote is ``None`` / an exception, never a mid-price dressed up as bid/ask.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


class ExecutionMode(str, Enum):
    QUOTE_BASED = "quote_based"
    """Bid/ask (and ideally trades) available: fills use the real spread."""

    CANDLE_ONLY = "candle_only"
    """Only OHLCV bars: spread/slippage are configured assumptions."""

    NONE = "none"
    """No execution model validated: simulation is unavailable."""


@dataclass(frozen=True)
class Provenance:
    source: str
    """Provider id, e.g. ``binance``."""

    market_time: datetime
    """Timestamp of the observation according to the market/provider."""

    received_at: datetime
    """When IchiVol received it (UTC, tz-aware)."""

    delayed: bool | None = None
    """True = known delayed feed; None = delay unknown (never assume real-time)."""

    transforms: tuple[str, ...] = field(default_factory=tuple)
    """Ordered list of transformations applied (e.g. ``resampled:1m->15m``)."""

    @property
    def latency_seconds(self) -> float:
        return (self.received_at - self.market_time).total_seconds()


@dataclass(frozen=True)
class Quote:
    instrument_id: str
    bid: float
    ask: float
    provenance: Provenance
    bid_size: float | None = None
    ask_size: float | None = None

    def __post_init__(self) -> None:
        if not (self.bid > 0 and self.ask > 0):
            raise ValueError("quote prices must be positive")
        if self.ask < self.bid:
            raise ValueError("crossed quote: ask < bid")

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class Trade:
    instrument_id: str
    price: float
    size: float
    provenance: Provenance
    buyer_is_aggressor: bool | None = None


class QuoteProvider(Protocol):
    id: str

    def fetch_quote(self, provider_symbol: str) -> Quote:
        """Current bid/ask. Raise if unavailable -- never synthesize one."""
        ...


class TradeProvider(Protocol):
    id: str

    def fetch_trades(self, provider_symbol: str, limit: int) -> list[Trade]:
        ...
