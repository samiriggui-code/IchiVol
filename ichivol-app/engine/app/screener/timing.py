"""Timing facts behind a signal computed on closed candles.

Four distinct things, never to be conflated:
- ``signal_bar_close``  : close time of the last CLOSED candle used for the signal
- ``computed_at``       : when this scan ran
- ``live_price``        : last traded price now (may be inside the forming bar)
- execution price       : decided later by the broker (bid/ask or configured friction)

``lag_bars`` compares the last closed candle available with the one that should
exist at ``now`` -- >=1 means the provider has not delivered the latest close
(late data); >=2 means the signal is stale and must not be acted on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle

STALE_LAG_BARS = 2
# A close is allowed a short delivery delay before being called "late".
DELIVERY_GRACE_S = 120


@dataclass(frozen=True)
class SignalTiming:
    timeframe: str
    signal_bar_open: int
    signal_bar_close: int
    computed_at: int
    live_price: float
    expected_bar_close: int
    lag_bars: int
    data_late: bool
    stale: bool
    closed_only: bool

    def to_dict(self) -> dict:
        return asdict(self)


def compute_signal_timing(
    used: Sequence[Candle], tf_seconds: int, now: int, live_price: float, timeframe: str, closed_only: bool
) -> SignalTiming:
    last = used[-1]
    bar_close = last.time + tf_seconds
    expected = now - now % tf_seconds  # most recent boundary already passed
    lag = max(0, (expected - bar_close) // tf_seconds)
    # right after a boundary the new close is normally still arriving: grace, not "late"
    within_grace = lag == 1 and (now - expected) <= DELIVERY_GRACE_S
    return SignalTiming(
        timeframe=timeframe,
        signal_bar_open=last.time,
        signal_bar_close=bar_close,
        computed_at=now,
        live_price=live_price,
        expected_bar_close=expected,
        lag_bars=int(lag),
        data_late=lag >= 1 and not within_grace,
        stale=lag >= STALE_LAG_BARS,
        closed_only=closed_only,
    )
