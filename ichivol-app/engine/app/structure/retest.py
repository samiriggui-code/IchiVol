"""Retest engine — return to broken level after breakout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.structure.types import LevelSide, PriceZone


class RetestOutcome(str, Enum):
    HOLD = "HOLD"
    FAILURE = "FAILURE"
    PENDING = "PENDING"


@dataclass(frozen=True)
class RetestCandidate:
    zone: PriceZone
    """Former resistance becomes support after bullish breakout, etc."""
    outcome: RetestOutcome
    bar_index: int
    close: float
    reason: str


def evaluate_retest(
    candles: Sequence[Candle],
    zone: PriceZone,
    *,
    breakout_bar: int,
    broken_side: LevelSide,
    atr: float | None = None,
    lookforward: int = 30,
) -> RetestCandidate | None:
    """After breakout at ``breakout_bar``, look for return into the zone.

    ``broken_side`` = the zone side that was broken (RESISTANCE for bullish BO).
    """
    n = len(candles)
    if breakout_bar < 0 or breakout_bar >= n - 1:
        return None

    end = min(n, breakout_bar + 1 + lookforward)
    for i in range(breakout_bar + 1, end):
        c = candles[i]
        in_zone = zone.contains(c.low) or zone.contains(c.high) or zone.contains(c.close)
        if not in_zone:
            # Near-miss within small ATR fraction
            if atr and atr > 0:
                if zone.distance(c.close) > atr * 0.35:
                    continue
            else:
                continue

        # Role reversal expectations
        if broken_side == LevelSide.RESISTANCE:
            # Expect hold as support
            if c.close >= zone.low:
                return RetestCandidate(
                    zone=zone,
                    outcome=RetestOutcome.HOLD,
                    bar_index=i,
                    close=c.close,
                    reason="SETUP_BREAKOUT_RETEST_HOLD",
                )
            return RetestCandidate(
                zone=zone,
                outcome=RetestOutcome.FAILURE,
                bar_index=i,
                close=c.close,
                reason="retest_failed_close_below",
            )
        # Broken support → expect hold as resistance
        if c.close <= zone.high:
            return RetestCandidate(
                zone=zone,
                outcome=RetestOutcome.HOLD,
                bar_index=i,
                close=c.close,
                reason="SETUP_BREAKOUT_RETEST_HOLD",
            )
        return RetestCandidate(
            zone=zone,
            outcome=RetestOutcome.FAILURE,
            bar_index=i,
            close=c.close,
            reason="retest_failed_close_above",
        )

    return RetestCandidate(
        zone=zone,
        outcome=RetestOutcome.PENDING,
        bar_index=breakout_bar,
        close=candles[breakout_bar].close,
        reason="no_retest_yet",
    )
