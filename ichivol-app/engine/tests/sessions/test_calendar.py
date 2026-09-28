"""AG-S0 — calendrier sessions : DST, ordre, week-end crypto 24/7."""

from __future__ import annotations

from datetime import datetime, timezone

from app.sessions.calendar import (
    SESSION_DEFS,
    build_session_calendar,
    next_daily_close_utc,
    next_session_open,
    open_sessions_at,
    wall_time_to_utc,
)


UTC = timezone.utc


def test_session_open_order_typical_weekday():
    # 2026-03-10 00:30 UTC — Asie déjà ouverte (Tokyo 09:30), Europe/US fermées.
    now = datetime(2026, 3, 10, 0, 30, tzinfo=UTC)
    open_keys = [w.key for w in open_sessions_at(now)]
    assert open_keys == ["asia"]

    nxt = next_session_open(now)
    assert nxt is not None
    assert nxt.key == "europe"
    # London 08:00 en hiver = 08:00 UTC
    assert nxt.open_utc == datetime(2026, 3, 10, 8, 0, tzinfo=UTC)


def test_dst_europe_march_forward():
    # UK passe à BST le 29 mars 2026 (01:00 UTC → 02:00 local).
    # Le 30 mars, London 08:00 locale = 07:00 UTC.
    open_utc = wall_time_to_utc(2026, 3, 30, 8, 0, SESSION_DEFS[1].tz)
    assert open_utc == datetime(2026, 3, 30, 7, 0, tzinfo=UTC)

    # Avant le changement (27 mars) : London 08:00 = 08:00 UTC.
    open_winter = wall_time_to_utc(2026, 3, 27, 8, 0, SESSION_DEFS[1].tz)
    assert open_winter == datetime(2026, 3, 27, 8, 0, tzinfo=UTC)


def test_dst_us_november_back():
    # US revient à EST le 1er nov 2026. Le 2 nov, NY 09:30 locale = 14:30 UTC.
    open_est = wall_time_to_utc(2026, 11, 2, 9, 30, SESSION_DEFS[2].tz)
    assert open_est == datetime(2026, 11, 2, 14, 30, tzinfo=UTC)

    # Avant (30 oct, encore EDT) : 09:30 = 13:30 UTC.
    open_edt = wall_time_to_utc(2026, 10, 30, 9, 30, SESSION_DEFS[2].tz)
    assert open_edt == datetime(2026, 10, 30, 13, 30, tzinfo=UTC)


def test_dst_europe_october_back():
    # UK revient à GMT le 25 oct 2026. Le 26 oct, London 08:00 = 08:00 UTC.
    open_gmt = wall_time_to_utc(2026, 10, 26, 8, 0, SESSION_DEFS[1].tz)
    assert open_gmt == datetime(2026, 10, 26, 8, 0, tzinfo=UTC)

    # Avant (23 oct, BST) : 08:00 locale = 07:00 UTC.
    open_bst = wall_time_to_utc(2026, 10, 23, 8, 0, SESSION_DEFS[1].tz)
    assert open_bst == datetime(2026, 10, 23, 7, 0, tzinfo=UTC)


def test_weekend_is_time_marker_not_market_close():
    # Samedi 2026-03-14 01:00 UTC = Tokyo 10:00 — session Asie « ouverte »
    # comme repère horaire (crypto 24/7, pas de skip week-end FX).
    saturday = datetime(2026, 3, 14, 1, 0, tzinfo=UTC)
    open_keys = [w.key for w in open_sessions_at(saturday)]
    assert "asia" in open_keys

    nxt = next_session_open(saturday)
    assert nxt is not None
    # Prochaine = Europe le même samedi (London 08:00 hiver = 08:00 UTC)
    assert nxt.key == "europe"
    assert nxt.open_utc.weekday() == 5  # Saturday


def test_next_daily_close_utc():
    assert next_daily_close_utc(datetime(2026, 3, 10, 12, 0, tzinfo=UTC)) == datetime(
        2026, 3, 11, 0, 0, tzinfo=UTC
    )
    assert next_daily_close_utc(datetime(2026, 3, 10, 0, 0, tzinfo=UTC)) == datetime(
        2026, 3, 11, 0, 0, tzinfo=UTC
    )


def test_calendar_snapshot_payload_shape():
    snap = build_session_calendar(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    d = snap.to_dict()
    assert d["crypto_24_7"] is True
    assert "open_sessions" in d
    assert "next_open" in d
    assert d["next_daily_close_utc"].endswith("Z")
    assert len(d["sessions"]) == 3
