"""Macro calendar candidates — causal date parse."""

from __future__ import annotations

from app.context.calendar import CalendarEvent
from app.events.macro import candidates_from_calendar


def test_future_calendar_dropped():
    as_of = 1_700_000_000  # 2023-11-14 ~22:13 UTC
    early = CalendarEvent(
        title="NFP",
        country="USD",
        date="2023-11-10T08:30:00-05:00",
        impact="High",
        forecast="200K",
        previous="180K",
    )
    future = CalendarEvent(
        title="FOMC",
        country="USD",
        date="2023-11-20T14:00:00-05:00",
        impact="High",
        forecast=None,
        previous=None,
    )
    refs = candidates_from_calendar([early, future], as_of=as_of, min_relevance=0.2)
    assert len(refs) == 1
    assert "NFP" in refs[0].title
    assert refs[0].published_at <= as_of
