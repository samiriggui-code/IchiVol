"""Anti-lookahead proof for app/indicators/location.py, same truncation-based
methodology as every other indicator in this codebase: compute over the full
history vs. a prefix, and every shared index must match exactly.
"""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.location import LocationParams, compute_location
from app.indicators.structure import BosEvent, StructureBias, compute_structure


def _wiggly_candles(n: int) -> list[Candle]:
    candles = []
    price = 100.0
    for i in range(n):
        # A deterministic wiggle with an overall drift, so real swing highs
        # and lows (and therefore real BOS events) actually occur.
        price += 3.0 if (i // 7) % 2 == 0 else -2.0
        high = price + 2.0
        low = price - 2.0
        volume = 10.0 + (i % 5) * 4.0
        candles.append(Candle(time=i, open=price, high=high, low=low, close=price, volume=volume))
    return candles


def test_location_is_stable_under_truncation():
    candles = _wiggly_candles(300)
    structure = compute_structure(candles)
    # Sanity: this fixture actually produces some BOS events, or the
    # AVWAP-anchoring half of this proof would be vacuous.
    assert any(s.bos in (BosEvent.BULLISH, BosEvent.BEARISH) for s in structure)
    assert any(s.bias != StructureBias.UNKNOWN for s in structure)

    full = compute_location(candles, structure, LocationParams())

    for cut in (50, 120, 200, 299):
        truncated_candles = candles[:cut]
        truncated_structure = structure[:cut]
        truncated = compute_location(truncated_candles, truncated_structure, LocationParams())
        assert truncated == full[:cut]
