"""Anti-lookahead proof for app/indicators/cvd.py: compute over the full
history vs. a prefix, every shared index must match exactly -- same
truncation-based methodology as every other indicator here.
"""

from __future__ import annotations

from app.indicators.cvd import CvdParams, compute_cvd
from app.indicators.ichimoku import Candle


def _wiggly_candles(n: int) -> list[Candle]:
    candles = []
    for i in range(n):
        volume = 50.0 + (i % 7) * 10.0
        taker_buy = volume * (0.3 + 0.4 * ((i % 5) / 4.0))  # oscillates 30%-70% buy share
        candles.append(
            Candle(time=i, open=100, high=101, low=99, close=100.5, volume=volume, taker_buy_volume=taker_buy)
        )
    return candles


def test_cvd_is_stable_under_truncation():
    candles = _wiggly_candles(200)
    full = compute_cvd(candles, CvdParams())

    for cut in (5, 30, 90, 199):
        truncated = compute_cvd(candles[:cut], CvdParams())
        assert truncated == full[:cut]
