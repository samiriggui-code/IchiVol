"""Anti-lookahead proof for app/indicators/wyckoff.py: compute over the
full history vs. a prefix, every shared index must match exactly -- same
truncation-based methodology as every other indicator here. Donchian
states are recomputed for each prefix too, since compute_wyckoff consumes
them -- if either step secretly peeked ahead, this would catch it.
"""

from __future__ import annotations

from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle
from app.indicators.wyckoff import WyckoffParams, compute_wyckoff


def _wiggly_candles(n: int) -> list[Candle]:
    candles = []
    price = 100.0
    for i in range(n):
        price += 3.0 if (i // 5) % 2 == 0 else -2.0
        volume = 10.0 + (i % 7) * 2.0
        candles.append(
            Candle(time=i, open=price, high=price + 1.5, low=price - 1.5, close=price, volume=volume)
        )
    return candles


def _wyckoff_for(candles: list[Candle]):
    donchian = compute_donchian(candles, DonchianParams(period=20))
    return compute_wyckoff(candles, donchian, WyckoffParams())


def test_wyckoff_is_stable_under_truncation():
    candles = _wiggly_candles(200)
    full = _wyckoff_for(candles)

    for cut in (5, 19, 20, 21, 45, 100, 199):
        truncated = _wyckoff_for(candles[:cut])
        assert truncated == full[:cut]
