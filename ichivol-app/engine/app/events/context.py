"""Assemble EventContextBundle for a scan (observation-only, fail-soft)."""

from __future__ import annotations

from app.events.correlate import correlate_events
from app.events.macro import fetch_macro_candidates
from app.events.news import fetch_symbol_news
from app.events.types import EventContextBundle, MarketAnomalyObservation


def build_event_context(
    anomaly: MarketAnomalyObservation,
    *,
    include_macro: bool = True,
    include_news: bool = True,
) -> EventContextBundle:
    """Fetch candidates and correlate. Network failures → empty candidates."""
    candidates = []
    if include_news:
        try:
            candidates.extend(
                fetch_symbol_news(anomaly.symbol, as_of=anomaly.bar_time)
            )
        except Exception:
            pass
    if include_macro:
        try:
            candidates.extend(fetch_macro_candidates(as_of=anomaly.bar_time))
        except Exception:
            pass
    return correlate_events(anomaly, candidates)
