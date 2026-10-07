"""Fenêtres de décision ouvertures / fermetures des places : heure d'été, week-end, règle de bougie."""

from __future__ import annotations

from datetime import datetime, timezone

from app.paper.strategy_profiles import ALL_PROFILES, syncable_profile_codes
from app.sessions.decision_windows import DEFAULT_DECISION_WINDOWS, decision_event_for_bar

UTC = timezone.utc
ALL = DEFAULT_DECISION_WINDOWS


def _bar(y, m, d, h):
    return int(datetime(y, m, d, h, tzinfo=UTC).timestamp())


def _events_of_day(y, m, d):
    return {h: e for h in range(24) if (e := decision_event_for_bar(_bar(y, m, d, h), ALL)) is not None}


def test_summer_weekday_utc_bars():
    # Mardi 2026-07-07 : Londres BST (UTC+1), New York EDT (UTC-4), Tokyo sans heure d'été.
    assert _events_of_day(2026, 7, 7) == {
        1: "tokyo_open",     # 09:00 JST -> bougie 00:00-01:00 UTC
        7: "tokyo_close",    # 15:30 JST = 06:30 UTC -> bougie close 07:00
        8: "london_open",    # 08:00 BST = 07:00 UTC -> première bougie de séance close 08:00
        14: "ny_open",       # 09:30 EDT = 13:30 UTC -> bougie close 14:00
        16: "london_close",  # 16:30 BST = 15:30 UTC -> bougie close 16:00
        20: "ny_close",      # 16:00 EDT = 20:00 UTC -> dernière bougie de séance close 20:00
    }


def test_winter_weekday_utc_bars_shift_one_hour():
    # Mardi 2026-01-13 : Londres GMT, New York EST.
    assert _events_of_day(2026, 1, 13) == {
        1: "tokyo_open", 7: "tokyo_close", 9: "london_open", 15: "ny_open", 17: "london_close", 21: "ny_close",
    }


def test_us_and_uk_dst_gap_week():
    # 2026-03-10 : New York déjà en EDT (8 mars), Londres encore en GMT (29 mars).
    ev = _events_of_day(2026, 3, 10)
    assert ev[9] == "london_open" and ev[14] == "ny_open" and ev[20] == "ny_close"


def test_weekend_has_no_event():
    assert _events_of_day(2026, 7, 11) == {}  # samedi
    sunday = _events_of_day(2026, 7, 12)
    assert sunday == {}  # dimanche UTC : lundi Tokyo commence à 00:00 UTC lundi
    assert decision_event_for_bar(_bar(2026, 7, 13, 1), ALL) == "tokyo_open"


def test_subset_and_unknown_keys():
    assert decision_event_for_bar(_bar(2026, 7, 7, 14), ["london_open", "nope"]) is None
    assert decision_event_for_bar(_bar(2026, 7, 7, 14), ["nope", "ny_open"]) == "ny_open"


def test_sessions_profile_synced_next_to_baseline():
    assert ALL_PROFILES["ICHIVOL_SESSIONS_V1"]["decision_windows"] == list(ALL)
    assert "decision_windows" not in ALL_PROFILES["ICHIVOL_BASELINE_V1"]
    assert syncable_profile_codes()[:2] == ["ICHIVOL_BASELINE_V1", "ICHIVOL_SESSIONS_V1"]
