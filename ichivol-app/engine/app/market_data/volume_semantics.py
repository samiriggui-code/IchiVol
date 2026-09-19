"""Volume semantics — providers are not interchangeable on volume.

RVOL on Binance exchange volume is not the same measurement as RVOL on
biquote tickVolume or a flat-zero Twelve Data FX series. Every Candle and
every EvidenceReport must carry which semantics applied so consumers never
treat them as equivalent.
"""

from __future__ import annotations

from enum import Enum


class VolumeType(str, Enum):
    EXCHANGE_VOLUME = "EXCHANGE_VOLUME"
    """Centralized exchange traded base/quote volume (e.g. Binance spot)."""

    REPORTED_VOLUME = "REPORTED_VOLUME"
    """Exchange-reported equity/index volume (e.g. Twelve Data equities)."""

    TICK_VOLUME = "TICK_VOLUME"
    """Count of price updates / ticks (e.g. biquote CFD mirrors)."""

    SYNTHETIC_VOLUME = "SYNTHETIC_VOLUME"
    """Explicitly generated volume (tests / synthetic scenarios only)."""

    NONE = "NONE"
    """No usable volume; series is flat zero or absent."""


# Default volume semantics declared by each registered provider id.
# Asset-class nuance for twelve_data is applied at fetch time (equities
# → REPORTED_VOLUME; FX/indices with missing volume → NONE).
PROVIDER_VOLUME_TYPE: dict[str, VolumeType] = {
    "binance": VolumeType.EXCHANGE_VOLUME,
    "biquote": VolumeType.TICK_VOLUME,
    "twelve_data": VolumeType.REPORTED_VOLUME,
    # Safe default for MT5 CFD/forex brokers -- most report tick counts, not
    # real traded volume. app/market_data/mt5.py overrides per-candle
    # whenever the bridge explicitly reports "real" (some MT5 futures feeds
    # do), so this default only applies when nothing more specific is known.
    "mt5": VolumeType.TICK_VOLUME,
}


def resolve_volume_type(provider_id: str, volumes: list[float] | None = None) -> VolumeType:
    """Provider default, with NONE when the whole series is unusable."""
    base = PROVIDER_VOLUME_TYPE.get(provider_id, VolumeType.NONE)
    if volumes is not None and volumes and all(v == 0.0 for v in volumes):
        return VolumeType.NONE
    return base
