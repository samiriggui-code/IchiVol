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


# ---------------------------------------------------------------------------
# Overnight financing (CFD swap) — ASSUMPTIONS, not verified against a live broker.
# Formula: financing_bps_per_day = (benchmark_annual + markup_annual) / 365 * 10_000
# where annual rates are fractions (e.g. 0.043 = 4.3%).
# Source date: 2026-09-23. Typical multi-asset CFD long = reference + ~2.5% markup.
# Benchmarks are order-of-magnitude stand-ins for SOFR / €STR / SONIA — verify
# against your broker's swap schedule before trusting multi-day PnL.
# ---------------------------------------------------------------------------

# ~SOFR / €STR order of magnitude (ASSUMPTION, not a live fixings feed).
CFD_BENCHMARK_ANNUAL_ASSUMED = 0.043
# Typical retail CFD overnight markup on longs (ASSUMPTION).
CFD_MARKUP_ANNUAL_ASSUMED = 0.025


def financing_bps_per_day_from_annual(
    benchmark_annual: float, markup_annual: float
) -> float:
    """(benchmark + markup) as fractions → bps/day via /365 × 10_000."""
    return (float(benchmark_annual) + float(markup_annual)) / 365.0 * 10_000.0


# Long CFD pays benchmark + markup ≈ 1.86 bps/day at assumed rates.
FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED = financing_bps_per_day_from_annual(
    CFD_BENCHMARK_ANNUAL_ASSUMED, CFD_MARKUP_ANNUAL_ASSUMED
)
# Short CFD: broker may pay or charge (rate − markup). When markup > benchmark the
# short still pays. ASSUMPTION: short pays max(0, benchmark − markup)/365 in bps.
FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED = financing_bps_per_day_from_annual(
    CFD_BENCHMARK_ANNUAL_ASSUMED, -CFD_MARKUP_ANNUAL_ASSUMED
)
if FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED < 0:
    # Negative = short receives credit; keep sign for financing module.
    pass

FINANCING_ASSUMPTION_META = {
    "source": (
        "ASSUMPTION 2026-09-23: retail CFD overnight ≈ (SOFR/€STR≈4.3% + 2.5% markup) / 365 "
        "for longs; shorts use (benchmark − markup)/365 (may be credit). "
        "Not verified against a named broker swap grid."
    ),
    "benchmark_annual": CFD_BENCHMARK_ANNUAL_ASSUMED,
    "markup_annual": CFD_MARKUP_ANNUAL_ASSUMED,
    "long_bps_per_day": FINANCING_BPS_PER_DAY_LONG_CFD_ASSUMED,
    "short_bps_per_day": FINANCING_BPS_PER_DAY_SHORT_CFD_ASSUMED,
    "crypto_spot_bps_per_day": 0.0,
    "as_of": "2026-09-23",
}
