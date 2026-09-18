"""Relative Strength Index (Wilder) — momentum context only.

Never votes LONG/SHORT on its own. Used by optional paper profile gates
(docs/ARCHITECTURE-CONSOLIDEE-V2.md Phase 3). Causal: RSI at i uses only
closes[0..i].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class RsiBias(str, Enum):
    BULLISH = "BULLISH"  # RSI >= mid
    BEARISH = "BEARISH"  # RSI < mid
    OVERBOUGHT = "OVERBOUGHT"
    OVERSOLD = "OVERSOLD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RsiParams:
    period: int = 14
    overbought: float = 70.0
    oversold: float = 30.0
    mid: float = 50.0


@dataclass(frozen=True)
class RsiState:
    time: int
    rsi: float | None
    bias: RsiBias


def compute_rsi(
    candles: Sequence[Candle],
    params: RsiParams = RsiParams(),
) -> list[RsiState]:
    period = params.period
    out: list[RsiState] = []
    avg_gain: float | None = None
    avg_loss: float | None = None
    gains: list[float] = []
    losses: list[float] = []

    for i, c in enumerate(candles):
        if i == 0:
            out.append(RsiState(time=c.time, rsi=None, bias=RsiBias.UNKNOWN))
            continue

        change = c.close - candles[i - 1].close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if avg_gain is None:
            gains.append(gain)
            losses.append(loss)
            if len(gains) < period:
                out.append(RsiState(time=c.time, rsi=None, bias=RsiBias.UNKNOWN))
                continue
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        if rsi >= params.overbought:
            bias = RsiBias.OVERBOUGHT
        elif rsi <= params.oversold:
            bias = RsiBias.OVERSOLD
        elif rsi >= params.mid:
            bias = RsiBias.BULLISH
        else:
            bias = RsiBias.BEARISH

        out.append(RsiState(time=c.time, rsi=rsi, bias=bias))

    return out
