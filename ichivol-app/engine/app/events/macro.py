"""Macro calendar → ExternalEventRef candidates (causal date ≤ as_of).

Wraps ``app.context.calendar.fetch_calendar_events``. Crypto symbols rarely
match country calendars tightly — relevance stays low unless impact is High
and within the lag window (correlate still decides).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.context.calendar import CalendarEvent, fetch_calendar_events
from app.events.types import EventCategory, ExternalEventRef


def _parse_calendar_unix(date_str: str) -> int | None:
    """ForexFactory ISO-ish strings → unix seconds (UTC)."""
    text = date_str.strip()
    if not text:
        return None
    # Normalize trailing Z
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _impact_relevance(impact: str) -> float:
    key = (impact or "").strip().lower()
    if key == "high":
        return 0.45
    if key == "medium":
        return 0.25
    if key == "low":
        return 0.1
    return 0.05


def calendar_event_to_ref(
    event: CalendarEvent,
    *,
    bar_time: int,
) -> ExternalEventRef | None:
    published = _parse_calendar_unix(event.date)
    if published is None or published > bar_time:
        return None
    impact = event.impact or "Unknown"
    category = (
        EventCategory.ECONOMIC_DATA
        if impact.lower() in ("high", "medium", "low")
        else EventCategory.MACRO_EVENT
    )
    return ExternalEventRef(
        source="macro_calendar",
        category=category,
        title=f"{event.country}: {event.title}".strip(": "),
        published_at=published,
        url=None,
        symbol_relevance=_impact_relevance(impact),
        temporal_proximity_s=max(0, bar_time - published),
        match_confidence=0.0,
    )


def fetch_macro_candidates(
    *,
    as_of: int,
    limit: int | None = None,
    min_relevance: float = 0.2,
) -> list[ExternalEventRef]:
    events = fetch_calendar_events(limit=limit)
    return candidates_from_calendar(events, as_of=as_of, min_relevance=min_relevance)


def candidates_from_calendar(
    events: Sequence[CalendarEvent],
    *,
    as_of: int,
    min_relevance: float = 0.2,
) -> list[ExternalEventRef]:
    out: list[ExternalEventRef] = []
    for ev in events:
        ref = calendar_event_to_ref(ev, bar_time=as_of)
        if ref is None or ref.symbol_relevance < min_relevance:
            continue
        out.append(ref)
    return out
