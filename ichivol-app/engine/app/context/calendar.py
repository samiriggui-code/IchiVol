"""Read-only economic calendar adapter (CDC 2026-09-16, same backlog item
as app/context/news.py). Free, keyless weekly JSON feed -- ForexFactory's
widely-used community feed (no official docs/SLA, but no key and no
signup, consistent with this project's "gratuit, sans clé" preference over
adding a paid/keyed calendar provider for an opt-in, non-critical context
source). Same guarantees as news.py: never raises, degrades to an empty
list on any failure, never touches the decision pipeline.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import httpx

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

_CACHE_TTL_SEC = 900.0  # 15 min -- a weekly calendar doesn't change fast
_cache: tuple[float, list["CalendarEvent"]] | None = None
_lock = threading.Lock()


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    country: str
    date: str  # ISO 8601, as given by the feed -- not reparsed/converted here
    impact: str  # "High" | "Medium" | "Low" | "Holiday" | "Unknown"
    forecast: str | None
    previous: str | None


def _parse(raw: object) -> list[CalendarEvent]:
    if not isinstance(raw, list):
        return []

    events: list[CalendarEvent] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        title, date = row.get("title"), row.get("date")
        if not title or not date:
            continue
        forecast = row.get("forecast")
        previous = row.get("previous")
        events.append(
            CalendarEvent(
                title=str(title),
                country=str(row.get("country") or ""),
                date=str(date),
                impact=str(row.get("impact") or "Unknown"),
                forecast=str(forecast) if forecast not in (None, "") else None,
                previous=str(previous) if previous not in (None, "") else None,
            )
        )
    return events


def fetch_calendar_events(limit: int | None = None) -> list[CalendarEvent]:
    """This week's macro calendar, most fields passed through as the feed
    gives them (no reinterpretation of impact/date). `limit=None` returns
    everything cached/fetched."""
    global _cache
    with _lock:
        if _cache is not None and time.monotonic() - _cache[0] < _CACHE_TTL_SEC:
            events = _cache[1]
            return list(events[:limit]) if limit else list(events)

    try:
        response = httpx.get(URL, timeout=10.0, headers={"User-Agent": "IchiVol/1.0 (context-adapter)"})
        response.raise_for_status()
        events = _parse(response.json())
    except (httpx.HTTPError, ValueError):
        events = []

    with _lock:
        _cache = (time.monotonic(), events)
    return list(events[:limit]) if limit else list(events)
