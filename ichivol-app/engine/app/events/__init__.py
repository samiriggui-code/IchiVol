"""Event Intelligence — quantitative market anomaly observations.

EVENT ≠ SIGNAL. Nothing in this package votes BUY/SELL or mutates the
pipeline. See docs/EVENT-INTELLIGENCE-LAYER-AUDIT.md.
"""

from app.events.anomaly import detect_anomaly, anomaly_observation_dict
from app.events.correlate import correlate_events, event_context_dict
from app.events.types import (
    AnomalyType,
    EventCategory,
    EventContextBundle,
    ExternalEventRef,
    MarketAnomalyObservation,
    MarketRegime,
)

__all__ = [
    "AnomalyType",
    "EventCategory",
    "EventContextBundle",
    "ExternalEventRef",
    "MarketAnomalyObservation",
    "MarketRegime",
    "correlate_events",
    "detect_anomaly",
    "anomaly_observation_dict",
    "event_context_dict",
]
