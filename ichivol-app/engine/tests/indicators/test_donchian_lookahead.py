"""Anti-lookahead proof for app/indicators/donchian.py: compute over the
full history vs. a prefix, every shared index must match exactly -- same
truncation-based methodology as every other indicator here.
"""

from __future__ import annotations

from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle


def _wiggly_candles(n: int) -> list[Candle]:
    candles = []
    price = 100.0
    for i in range(n):
        price += 3.0 if (i // 5) % 2 == 0 else -2.0
        candles.append(
            Candle(time=i, open=price, high=price + 1.5, low=price - 1.5, close=price, volume=10.0)
        )
    return candles


def test_donchian_is_stable_under_truncation():
    candles = _wiggly_candles(200)
    full = compute_donchian(candles, DonchianParams(period=20))

    for cut in (5, 19, 20, 21, 45, 100, 199):
        truncated = compute_donchian(candles[:cut], DonchianParams(period=20))
        assert truncated == full[:cut]
