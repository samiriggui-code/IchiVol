"""Correlate anomaly ↔ external candidates → EventContextBundle.

EVENT ≠ SIGNAL. Promotes UNKNOWN_EVENT → EVENT_MARKET only when a causal
match clears ``min_match_confidence``. Never touches pipeline/combiner.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from app.events.types import (
    DISCLAIMER,
    EventContextBundle,
    ExternalEventRef,
    MarketAnomalyObservation,
    MarketRegime,
)

DEFAULT_MAX_LAG_S = 48 * 3600
DEFAULT_MIN_MATCH_CONFIDENCE = 0.45


def _temporal_weight(lag_s: int, max_lag_s: int) -> float:
    if lag_s < 0:
        return 0.0
    if max_lag_s <= 0:
        return 1.0 if lag_s == 0 else 0.0
    if lag_s > max_lag_s:
        return 0.0
    # Linear decay: same-bar ≈ 1.0, at max_lag ≈ 0.15 floor if still in window
    return max(0.15, 1.0 - (lag_s / max_lag_s) * 0.85)


def score_match(
    anomaly: MarketAnomalyObservation,
    candidate: ExternalEventRef,
    *,
    max_lag_s: int = DEFAULT_MAX_LAG_S,
) -> ExternalEventRef | None:
    """Return candidate with match_confidence, or None if future / out of lag."""
    if candidate.published_at > anomaly.bar_time:
        return None
    lag = anomaly.bar_time - candidate.published_at
    if lag > max_lag_s:
        return None
    tw = _temporal_weight(lag, max_lag_s)
    # Symbol relevance dominates; temporal is a multiplier.
    conf = float(min(1.0, max(0.0, candidate.symbol_relevance * tw)))
    if conf <= 0.0:
        return None
    return replace(
        candidate,
        temporal_proximity_s=lag,
        match_confidence=conf,
        relation="CORRELATED_EVENT",
    )


def correlate_events(
    anomaly: MarketAnomalyObservation,
    candidates: Sequence[ExternalEventRef],
    *,
    max_lag_s: int = DEFAULT_MAX_LAG_S,
    min_match_confidence: float = DEFAULT_MIN_MATCH_CONFIDENCE,
    max_matches: int = 5,
) -> EventContextBundle:
    """Build context bundle. Drops any candidate with published_at > bar_time."""
    scored: list[ExternalEventRef] = []
    for cand in candidates:
        hit = score_match(anomaly, cand, max_lag_s=max_lag_s)
        if hit is not None:
            scored.append(hit)
    scored.sort(key=lambda m: m.match_confidence, reverse=True)
    matches = tuple(scored[:max_matches])

    regime = anomaly.market_regime
    if (
        anomaly.event_suspected
        and matches
        and matches[0].match_confidence >= min_match_confidence
    ):
        regime = MarketRegime.EVENT_MARKET
    elif anomaly.event_suspected:
        regime = MarketRegime.UNKNOWN_EVENT
    else:
        regime = MarketRegime.NORMAL_MARKET

    # Keep anomaly.market_regime aligned for serializers that only read anomaly.
    aligned = (
        anomaly
        if anomaly.market_regime == regime
        else replace(anomaly, market_regime=regime)
    )
    return EventContextBundle(
        anomaly=aligned,
        market_regime=regime,
        matches=matches,
        disclaimer=DISCLAIMER,
    )


def event_context_dict(bundle: EventContextBundle | None) -> dict | None:
    if bundle is None:
        return None
    return bundle.to_dict()
