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


class EventCategory(str, Enum):
    MACRO_EVENT = "MACRO_EVENT"
    EARNINGS = "EARNINGS"
    GUIDANCE = "GUIDANCE"
    M_AND_A = "M&A"
    REGULATORY = "REGULATORY"
    LEGAL = "LEGAL"
    PRODUCT = "PRODUCT"
    MANAGEMENT = "MANAGEMENT"
    ANALYST_RATING = "ANALYST_RATING"
    GEOPOLITICAL = "GEOPOLITICAL"
    CENTRAL_BANK = "CENTRAL_BANK"
    ECONOMIC_DATA = "ECONOMIC_DATA"
    CRYPTO_SPECIFIC = "CRYPTO_SPECIFIC"
    UNKNOWN = "UNKNOWN"


DISCLAIMER = "Contexte événementiel — n'est pas un signal d'achat/vente."


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


@dataclass(frozen=True)
class ExternalEventRef:
    """Candidate external event — never a trade vote.

    ``published_at`` MUST be ≤ anomaly.bar_time for any accepted match.
    ``relation`` is always CORRELATED_EVENT (never PROVEN_CAUSE).
    """

    source: str  # macro_calendar | symbol_news | corporate
    category: EventCategory
    title: str
    published_at: int
    url: str | None
    symbol_relevance: float
    temporal_proximity_s: int = 0
    match_confidence: float = 0.0
    relation: str = "CORRELATED_EVENT"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass(frozen=True)
class EventContextBundle:
    """Anomaly + optional external matches. EVENT ≠ SIGNAL."""

    anomaly: MarketAnomalyObservation
    market_regime: MarketRegime
    matches: tuple[ExternalEventRef, ...] = ()
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "anomaly": self.anomaly.to_dict(),
            "market_regime": self.market_regime.value,
            "matches": [m.to_dict() for m in self.matches],
            "disclaimer": self.disclaimer,
        }
