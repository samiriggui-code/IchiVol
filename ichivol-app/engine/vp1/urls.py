"""URL builders for data.binance.vision archives (VP1)."""

from __future__ import annotations

from datetime import date

from vp1 import VISION_BASE


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Inclusive (year, month) pairs covering [start, end]."""
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def day_range(start: date, end: date) -> list[date]:
    from datetime import timedelta

    out: list[date] = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def spot_klines_monthly_url(symbol: str, interval: str, year: int, month: int) -> str:
    name = f"{symbol}-{interval}-{year}-{month:02d}.zip"
    return (
        f"{VISION_BASE}/data/spot/monthly/klines/{symbol}/{interval}/{name}"
    )


def funding_monthly_url(symbol: str, year: int, month: int) -> str:
    name = f"{symbol}-fundingRate-{year}-{month:02d}.zip"
    return f"{VISION_BASE}/data/futures/um/monthly/fundingRate/{symbol}/{name}"


def metrics_daily_url(symbol: str, day: date) -> str:
    name = f"{symbol}-metrics-{day.isoformat()}.zip"
    return f"{VISION_BASE}/data/futures/um/daily/metrics/{symbol}/{name}"


def checksum_url(file_url: str) -> str:
    return f"{file_url}.CHECKSUM"
