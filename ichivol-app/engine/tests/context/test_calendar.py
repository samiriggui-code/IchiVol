from __future__ import annotations

import httpx
import pytest

from app.context import calendar


@pytest.fixture(autouse=True)
def _clear_cache():
    calendar._cache = None
    yield
    calendar._cache = None


_SAMPLE_EVENTS = [
    {
        "title": "CPI m/m",
        "country": "USD",
        "date": "2026-09-17T12:30:00Z",
        "impact": "High",
        "forecast": "0.2%",
        "previous": "0.1%",
    },
    {
        "title": "Bank Holiday",
        "country": "GBP",
        "date": "2026-09-18T00:00:00Z",
        "impact": "Holiday",
        "forecast": "",
        "previous": None,
    },
    {"title": "", "country": "EUR", "date": "2026-09-19T00:00:00Z"},  # no title -> dropped
]


class FakeResp:
    def __init__(self, payload, ok: bool = True):
        self._payload = payload
        self._ok = ok

    def raise_for_status(self) -> None:
        if not self._ok:
            raise httpx.HTTPError("boom")

    def json(self):
        return self._payload


def test_fetch_calendar_events_parses_and_drops_incomplete_rows(monkeypatch):
    monkeypatch.setattr(calendar.httpx, "get", lambda *a, **k: FakeResp(_SAMPLE_EVENTS))
    events = calendar.fetch_calendar_events()
    assert len(events) == 2  # the titleless row is dropped
    assert events[0].title == "CPI m/m"
    assert events[0].forecast == "0.2%"
    assert events[1].forecast is None  # "" normalized to None
    assert events[1].previous is None  # None stays None


def test_fetch_calendar_events_respects_limit(monkeypatch):
    monkeypatch.setattr(calendar.httpx, "get", lambda *a, **k: FakeResp(_SAMPLE_EVENTS))
    events = calendar.fetch_calendar_events(limit=1)
    assert len(events) == 1


def test_network_failure_degrades_to_empty_list(monkeypatch):
    def _raise(*a, **k):
        raise httpx.HTTPError("network down")

    monkeypatch.setattr(calendar.httpx, "get", _raise)
    assert calendar.fetch_calendar_events() == []


def test_non_list_payload_degrades_to_empty_list(monkeypatch):
    monkeypatch.setattr(calendar.httpx, "get", lambda *a, **k: FakeResp({"error": "not a list"}))
    assert calendar.fetch_calendar_events() == []


def test_result_is_cached_within_ttl(monkeypatch):
    calls = {"n": 0}

    def _fake_get(*a, **k):
        calls["n"] += 1
        return FakeResp(_SAMPLE_EVENTS)

    monkeypatch.setattr(calendar.httpx, "get", _fake_get)
    calendar.fetch_calendar_events()
    calendar.fetch_calendar_events()
    assert calls["n"] == 1
