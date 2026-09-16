"""Donchian channels -- V3 experimental candidate (docs/METHODS-ROADMAP.md:
"Donchian / Breakout | Vraie cassure de range ? | Détection | V3 | OHLCV").
Same "Régime" question as ATR/ADX (docs/METHODS-ROADMAP.md §6 rule 3:
"ATR / ADX / Wyckoff ne votent jamais") -- classifies whether the current
bar breaks a real N-bar range, never votes LONG/SHORT itself.

Classic turtle-trading definition: upper band = highest high over the
trailing `period` bars, lower band = lowest low over the trailing `period`
bars. The band used to classify bar i is built from the PRIOR `period`
bars (i-period .. i-1), never bar i itself -- a range that includes its
own extremes could never be "broken" by the bar that defines it. Anti-
lookahead by construction: the band at bar i depends only on
candles[..i-1] -- see tests/indicators/test_donchian_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class DonchianBreakout(str, Enum):
    UP = "UP"
    """Close breaks above the prior-period high -- a real upside breakout."""
    DOWN = "DOWN"
    """Close breaks below the prior-period low -- a real downside breakout."""
    INSIDE = "INSIDE"
    """Close stays within the prior range -- no breakout."""
    UNKNOWN = "UNKNOWN"
    """Not enough history yet to form a range."""


@dataclass(frozen=True)
class DonchianParams:
    period: int = 20
    """Classic turtle-trading window."""


@dataclass(frozen=True)
class DonchianState:
    time: int
    upper: float | None
    """Highest high of the prior `period` bars, excluding this one."""
    lower: float | None
    """Lowest low of the prior `period` bars, excluding this one."""
    breakout: DonchianBreakout


def compute_donchian(
    candles: Sequence[Candle], params: DonchianParams = DonchianParams()
) -> list[DonchianState]:
    n = len(candles)
    out: list[DonchianState] = []
    for i in range(n):
        start = i - params.period
        if start < 0:
            out.append(
                DonchianState(time=candles[i].time, upper=None, lower=None, breakout=DonchianBreakout.UNKNOWN)
            )
            continue

        window = candles[start:i]  # strictly the PRIOR `period` bars
        upper = max(c.high for c in window)
        lower = min(c.low for c in window)
        close = candles[i].close

        if close > upper:
            breakout = DonchianBreakout.UP
        elif close < lower:
            breakout = DonchianBreakout.DOWN
        else:
            breakout = DonchianBreakout.INSIDE

        out.append(DonchianState(time=candles[i].time, upper=upper, lower=lower, breakout=breakout))

    return out
