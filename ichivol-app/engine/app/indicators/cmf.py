"""Chaikin Money Flow — money-flow context (not a direction vote).

CMF = sum(MFV) / sum(volume) over ``period``. Causal on candles[0..i].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class CmfBias(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CmfParams:
    period: int = 20
    neutral_band: float = 0.05
    """|CMF| below this → NEUTRAL."""


@dataclass(frozen=True)
class CmfState:
    time: int
    cmf: float | None
    bias: CmfBias


def _money_flow_volume(c: Candle) -> float:
    hl = c.high - c.low
    if hl <= 0 or c.volume <= 0:
        return 0.0
    mfm = ((c.close - c.low) - (c.high - c.close)) / hl
    return mfm * c.volume


def compute_cmf(
    candles: Sequence[Candle],
    params: CmfParams = CmfParams(),
) -> list[CmfState]:
    period = params.period
    out: list[CmfState] = []
    mfv: list[float] = []
    vols: list[float] = []

    for i, c in enumerate(candles):
        mfv.append(_money_flow_volume(c))
        vols.append(max(c.volume, 0.0))
        if i + 1 < period:
            out.append(CmfState(time=c.time, cmf=None, bias=CmfBias.UNKNOWN))
            continue
        window_mfv = mfv[-period:]
        window_vol = vols[-period:]
        vol_sum = sum(window_vol)
        cmf = (sum(window_mfv) / vol_sum) if vol_sum > 0 else 0.0
        if abs(cmf) < params.neutral_band:
            bias = CmfBias.NEUTRAL
        elif cmf > 0:
            bias = CmfBias.POSITIVE
        else:
            bias = CmfBias.NEGATIVE
        out.append(CmfState(time=c.time, cmf=cmf, bias=bias))

    return out
