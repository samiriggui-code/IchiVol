"""Price structure: swing highs/lows, HH/HL vs LH/LL bias, and break-of-
structure (BOS) events. Mission realignment (docs/METHODS-ROADMAP.md §4
step 2, docs/TRADING_ARCHITECTURE_V2.md §1): this answers the "Structure"
half of the Direction/Structure question, alongside MTF alignment computed
separately at the screener layer (app/screener/service.py) and folded into
the same pipeline stage by app/decision/pipeline.py.

Anti-lookahead by construction, same pattern as ichimoku.py/rvol.py: a
swing at index j is only usable once `swing_lookback` bars have passed
(confirmed at bar j + swing_lookback), matching how a real chart reader
could never point at a swing high before enough bars exist on its right
to know it was one. See tests/indicators/test_structure_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.pivots import fractal_confirmed_at


class StructureBias(str, Enum):
    BULLISH = "BULLISH"  # last confirmed swing: higher high + higher low
    BEARISH = "BEARISH"  # last confirmed swing: lower high + lower low
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class BosEvent(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StructureParams:
    swing_lookback: int = 2
    """Bars required on each side of a candidate swing point before it is
    confirmed. Small default (2) for responsiveness on the timeframes this
    engine already screens (15m/1h/4h/1d); the classic 5-bar fractal is
    available by passing a larger value."""


@dataclass(frozen=True)
class StructureState:
    time: int
    last_swing_high: float | None
    last_swing_low: float | None
    bias: StructureBias
    bos: BosEvent


def compute_structure(
    candles: Sequence[Candle],
    params: StructureParams = StructureParams(),
) -> list[StructureState]:
    n = len(candles)
    k = params.swing_lookback

    last_high: float | None = None
    last_low: float | None = None
    prev_high: float | None = None
    prev_low: float | None = None
    bias = StructureBias.UNKNOWN

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    out: list[StructureState] = []

    for i in range(n):
        # Shared causal fractal (T9a): pivot at j confirmed only at i = j + k.
        hi = fractal_confirmed_at(highs, i, left=k, right=k, mode="max")
        if hi is not None:
            prev_high, last_high = last_high, hi[1]
        lo = fractal_confirmed_at(lows, i, left=k, right=k, mode="min")
        if lo is not None:
            prev_low, last_low = last_low, lo[1]

        if hi is not None or lo is not None:
            if prev_high is not None and prev_low is not None:
                higher_high = last_high > prev_high
                higher_low = last_low > prev_low
                lower_high = last_high < prev_high
                lower_low = last_low < prev_low
                if higher_high and higher_low:
                    bias = StructureBias.BULLISH
                elif lower_high and lower_low:
                    bias = StructureBias.BEARISH
                else:
                    bias = StructureBias.MIXED

        bos = BosEvent.UNKNOWN
        if last_high is not None and last_low is not None and i > 0:
            close = candles[i].close
            prev_close = candles[i - 1].close
            if prev_close <= last_high < close:
                bos = BosEvent.BULLISH
            elif prev_close >= last_low > close:
                bos = BosEvent.BEARISH
            else:
                bos = BosEvent.NONE

        out.append(
            StructureState(
                time=candles[i].time,
                last_swing_high=last_high,
                last_swing_low=last_low,
                bias=bias,
                bos=bos,
            )
        )

    return out
