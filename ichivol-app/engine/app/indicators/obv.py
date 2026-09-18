"""On-Balance Volume — cumulative flow + short slope bias.

OBV never votes direction alone; experimental gates may require slope
alignment with the pipeline decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class ObvBias(str, Enum):
    RISING = "RISING"
    FALLING = "FALLING"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ObvParams:
    slope_lookback: int = 10
    """Bars used to judge rising/falling OBV."""
    flat_pct: float = 0.002
    """Relative OBV change below this → FLAT."""


@dataclass(frozen=True)
class ObvState:
    time: int
    obv: float
    bias: ObvBias
    slope: float | None
    """(obv[i] - obv[i-lookback]) / lookback when available."""


def compute_obv(
    candles: Sequence[Candle],
    params: ObvParams = ObvParams(),
) -> list[ObvState]:
    out: list[ObvState] = []
    obv = 0.0
    series: list[float] = []

    for i, c in enumerate(candles):
        if i == 0:
            obv = c.volume
        else:
            prev = candles[i - 1].close
            if c.close > prev:
                obv += c.volume
            elif c.close < prev:
                obv -= c.volume
        series.append(obv)

        slope: float | None = None
        bias = ObvBias.UNKNOWN
        lb = params.slope_lookback
        if i >= lb:
            delta = series[i] - series[i - lb]
            slope = delta / lb
            base = abs(series[i - lb]) if series[i - lb] != 0 else 1.0
            rel = delta / base
            if abs(rel) < params.flat_pct:
                bias = ObvBias.FLAT
            elif delta > 0:
                bias = ObvBias.RISING
            else:
                bias = ObvBias.FALLING

        out.append(ObvState(time=c.time, obv=obv, bias=bias, slope=slope))

    return out
