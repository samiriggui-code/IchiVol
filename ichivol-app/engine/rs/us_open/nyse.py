"""Jours de séance NYSE et conversion des ancrages NY → UTC (RS-05 §2, §7)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
PARIS = ZoneInfo("Europe/Paris")

# Fermetures complètes NYSE 2021-07 → 2024-12 (RS-05 §7).
NYSE_HOLIDAYS: frozenset[date] = frozenset(
    date.fromisoformat(d)
    for d in (
        "2021-07-05", "2021-09-06", "2021-11-25", "2021-12-24",
        "2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20",
        "2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26",
        "2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29",
        "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25",
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27",
        "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
    )
)


def nyse_days(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in NYSE_HOLIDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out


def anchor_ms(day: date, minute_of_day: int, tz: ZoneInfo = NY) -> int:
    """Instant UTC (ms) de `day` à `minute_of_day` en heure locale `tz`."""
    local = datetime(day.year, day.month, day.day, minute_of_day // 60, minute_of_day % 60, tzinfo=tz)
    return int(local.astimezone(timezone.utc).timestamp() * 1000)


def us_dst(day: date) -> bool:
    return bool(datetime(day.year, day.month, day.day, 12, tzinfo=NY).dst())
