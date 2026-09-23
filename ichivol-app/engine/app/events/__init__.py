"""Event Intelligence — quantitative market anomaly observations.

EVENT ≠ SIGNAL. Nothing in this package votes BUY/SELL or mutates the
pipeline. See docs/EVENT-INTELLIGENCE-LAYER-AUDIT.md.
"""

from app.events.anomaly import detect_anomaly, anomaly_observation_dict
from app.events.types import (
    AnomalyType,
    MarketAnomalyObservation,
    MarketRegime,
)

__all__ = [
    "AnomalyType",
    "MarketAnomalyObservation",
    "MarketRegime",
    "detect_anomaly",
    "anomaly_observation_dict",
]
