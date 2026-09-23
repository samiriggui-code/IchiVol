"""Versioned anomaly thresholds — placeholders pending PHASE 6 calibration.

Defaults follow the causal rule baseline from stock-anomaly-detector
(|ret_z|>2.5, vol_z>2.5) plus ATR-normalized range/gap gates. They MUST be
re-estimated per (asset_class, timeframe) via walk-forward quantiles before
being treated as product truth.
"""

from __future__ import annotations

from dataclasses import dataclass

EVENT_ANOMALY_FEATURE_VERSION = "event_anomaly_v0_placeholder"


@dataclass(frozen=True)
class AnomalyThresholds:
    """Past-only feature gates. Positive thresholds; abs used for return/gap."""

    feature_version: str = EVENT_ANOMALY_FEATURE_VERSION
    z_window: int = 63
    vol_z_window: int = 21
    min_history: int = 64  # need z_window + 1
    return_z_abs: float = 2.5
    volume_z: float = 2.5
    volatility_z_abs: float = 2.5
    range_atr: float = 3.0
    gap_atr: float = 1.5
    rvol: float = 3.0


DEFAULT_THRESHOLDS = AnomalyThresholds()
