"""Event Intelligence types — observations only, never trade signals."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class MarketRegime(str, Enum):
    NORMAL_MARKET = "NORMAL_MARKET"
    EVENT_MARKET = "EVENT_MARKET"
    UNKNOWN_EVENT = "UNKNOWN_EVENT"


class AnomalyType(str, Enum):
    NONE = "NONE"
    PRICE_SHOCK = "PRICE_SHOCK"
    VOLUME_SHOCK = "VOLUME_SHOCK"
    GAP_EVENT = "GAP_EVENT"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    PRICE_VOLUME_SHOCK = "PRICE_VOLUME_SHOCK"


@dataclass(frozen=True)
class MarketAnomalyObservation:
    """Causal anomaly snapshot at the last *closed* bar.

    Without an external event match, a suspected anomaly maps to
    ``UNKNOWN_EVENT`` (never auto-promoted to a stronger trade label).
    """

    symbol: str
    timeframe: str
    bar_time: int
    event_suspected: bool
    event_type: AnomalyType
    market_regime: MarketRegime
    return_zscore: float | None
    volume_zscore: float | None
    range_atr_ratio: float | None
    gap_atr_ratio: float | None
    rvol: float | None
    volatility_zscore: float | None
    confidence: float
    feature_version: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["market_regime"] = self.market_regime.value
        d["reasons"] = list(self.reasons)
        return d
