"""Cumulative Volume Delta (CVD) -- V2 "participation avancée"
(docs/METHODS-ROADMAP.md: "+ CVD / Delta (trades)"). Enriches the
Participation stage's read of the market; it never votes LONG/SHORT and
never gates on its own (docs/TRADING_ARCHITECTURE_V2.md §7 rule 2: RVOL
stays the participation gate) -- app/decision/pipeline.py folds this in as
extra context on the Participation stage, same status as before.

Derived from each bar's taker buy volume, which Binance's own kline
response already carries (app/market_data/binance.py, index 9 --
"taker buy base asset volume") -- no separate trades-endpoint fetch needed:

    delta = taker_buy_volume - taker_sell_volume
          = taker_buy_volume - (volume - taker_buy_volume)
          = 2 * taker_buy_volume - volume

Only meaningful where the provider populates `Candle.taker_buy_volume`
(Binance spot today); everywhere else (Twelve Data, biquote -- no trade-tape
concept the same way) this reports UNKNOWN, gracefully, same convention as
MTF being optional elsewhere in this codebase.

Anti-lookahead by construction: delta/cumulative/rolling_delta at index i
depend only on candles[0..i]. See tests/indicators/test_cvd_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class CvdBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CvdParams:
    window: int = 20
    bias_threshold: float = 0.1
    """Rolling delta / rolling volume beyond +-this ratio -> BULLISH/BEARISH;
    inside it -> NEUTRAL (buy/sell pressure roughly balanced)."""


@dataclass(frozen=True)
class CvdState:
    time: int
    delta: float | None
    cumulative: float | None
    rolling_delta: float | None
    bias: CvdBias


def compute_cvd(candles: Sequence[Candle], params: CvdParams = CvdParams()) -> list[CvdState]:
    out: list[CvdState] = []
    deltas: list[float | None] = []
    cumulative = 0.0
    have_cumulative = False

    for i, c in enumerate(candles):
        if c.taker_buy_volume is None:
            deltas.append(None)
            out.append(
                CvdState(time=c.time, delta=None, cumulative=None, rolling_delta=None, bias=CvdBias.UNKNOWN)
            )
            continue

        delta = 2 * c.taker_buy_volume - c.volume
        deltas.append(delta)
        cumulative += delta
        have_cumulative = True

        start = max(0, i - params.window + 1)
        window_deltas = [d for d in deltas[start : i + 1] if d is not None]
        window_volume = sum(
            candles[j].volume for j in range(start, i + 1) if deltas[j] is not None
        )
        rolling_delta = sum(window_deltas) if window_deltas else None

        if rolling_delta is None or window_volume <= 0:
            bias = CvdBias.UNKNOWN
        else:
            ratio = rolling_delta / window_volume
            if ratio > params.bias_threshold:
                bias = CvdBias.BULLISH
            elif ratio < -params.bias_threshold:
                bias = CvdBias.BEARISH
            else:
                bias = CvdBias.NEUTRAL

        out.append(
            CvdState(
                time=c.time,
                delta=delta,
                cumulative=cumulative if have_cumulative else None,
                rolling_delta=rolling_delta,
                bias=bias,
            )
        )

    return out
