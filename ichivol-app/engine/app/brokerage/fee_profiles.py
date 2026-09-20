"""Registry of fee schedules by id. Every entry states its source.

Nothing here is presented as verified unless its ``source`` says so. The
Binance figure is an ASSUMPTION carried from general knowledge of the public
standard tier and was NOT checked against Binance's schedule in this project
yet -- verify at the exchange's fee page before trusting net results.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.brokerage.fees import FeeSchedule

BINANCE_SPOT_STANDARD_ASSUMED = FeeSchedule(
    id="BINANCE_SPOT_STANDARD_ASSUMED",
    version="2026-09-20.1",
    currency="USDT",
    source="ASSUMPTION: Binance spot standard tier taker 0.10% -- unverified, check binance.com fee schedule",
    effective_from=date(2026, 9, 20),
    proportional=Decimal("0.001"),
    assumptions="No BNB discount, no VIP tier, quote-currency fee; spread comes from bid/ask, not from this schedule.",
)

LEGACY_BASELINE_BPS = FeeSchedule(
    id="LEGACY_BASELINE_BPS",
    version="1",
    currency="EUR",
    source="ASSUMPTION: legacy paper broker flat 5 bps (ICHIVOL_BASELINE_V1)",
    effective_from=date(2026, 9, 15),
    proportional=Decimal("0.0005"),
)

_REGISTRY = {s.id: s for s in (BINANCE_SPOT_STANDARD_ASSUMED, LEGACY_BASELINE_BPS)}


def get_schedule(schedule_id: str) -> FeeSchedule:
    try:
        return _REGISTRY[schedule_id]
    except KeyError:
        raise KeyError(f"unknown fee schedule {schedule_id!r}") from None
