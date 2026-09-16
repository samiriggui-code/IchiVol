"""Anti-lookahead proof for app/indicators/oi_funding.py: compute over the
full history vs. a prefix, every shared index must match exactly.
"""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.oi_funding import OiFundingParams, compute_oi_funding
from app.market_data.binance_futures import FundingPoint, OpenInterestPoint


def _candle(time: int) -> Candle:
    return Candle(time=time, open=100, high=101, low=99, close=100.5, volume=10.0)


def test_oi_funding_is_stable_under_truncation():
    candles = [_candle(i * 3600) for i in range(300)]
    oi_points = [
        OpenInterestPoint(time=i * 3600, open_interest=1000.0 + 5.0 * ((i % 11) - 5))
        for i in range(300)
    ]
    # Funding on a sparser, ~8h-like cadence, not aligned to every candle.
    funding_points = [
        FundingPoint(time=i * 8 * 3600, rate=0.0002 * ((-1) ** i)) for i in range(300 // 8 + 1)
    ]

    full = compute_oi_funding(candles, oi_points, funding_points, OiFundingParams())

    for cut in (5, 47, 130, 299):
        truncated = compute_oi_funding(candles[:cut], oi_points, funding_points, OiFundingParams())
        assert truncated == full[:cut]
