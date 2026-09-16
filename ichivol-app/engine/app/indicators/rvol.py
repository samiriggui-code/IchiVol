"""Relative Volume (RVOL) engine.

Trailing-average convention (partial window from the start of history)
matches ichivol-app/src/lib/signals.ts::computeVolumePulse exactly, so this
Python engine and the already-shipped TS client agree on RVOL for the same
data. As in app/indicators/ichimoku.py, every field at index i is a pure
function of candles[0..i] -- see
tests/indicators/test_rvol_lookahead.py for the truncation-based proof.

Thresholds (mission brief §4) are parameters, never hardcoded universal
truths: they classify what this run considers "low/normal/significant/
strong/anomalous" participation, and are meant to be tuned and validated by
backtest, not trusted as-is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle


class AnomalyLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    SIGNIFICANT = "SIGNIFICANT"
    STRONG = "STRONG"
    ANOMALY = "ANOMALY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RvolParams:
    primary_window: int = 20
    percentile_lookback: int = 100
    low_threshold: float = 0.7
    significant_threshold: float = 1.5
    strong_threshold: float = 2.0
    anomaly_threshold: float = 3.0


@dataclass(frozen=True)
class RvolState:
    time: int
    volume: float
    avg_volume: float | None
    rvol: float | None
    rvol5: float | None
    rvol10: float | None
    rvol20: float | None
    vol_accel: float | None
    percentile: float | None
    anomaly_level: AnomalyLevel
    confirmed: bool
    spike: bool


def _trailing_avg(candles: Sequence[Candle], end: int, window: int) -> float | None:
    start = max(0, end - window + 1)
    values = [c.volume for c in candles[start : end + 1]]
    if not values:
        return None
    return sum(values) / len(values)


def _rvol(candles: Sequence[Candle], end: int, window: int) -> tuple[float | None, float | None]:
    avg = _trailing_avg(candles, end, window)
    if avg is None or avg <= 0:
        return avg, None
    return avg, candles[end].volume / avg


def _percentile(candles: Sequence[Candle], end: int, lookback: int) -> float | None:
    start = max(0, end - lookback + 1)
    window = [c.volume for c in candles[start : end + 1]]
    if len(window) < 2:
        return None
    current = candles[end].volume
    rank = sum(1 for v in window if v <= current)
    return rank / len(window)


def _anomaly_level(rvol: float | None, params: RvolParams) -> AnomalyLevel:
    if rvol is None:
        return AnomalyLevel.UNKNOWN
    if rvol < params.low_threshold:
        return AnomalyLevel.LOW
    if rvol < params.significant_threshold:
        return AnomalyLevel.NORMAL
    if rvol < params.strong_threshold:
        return AnomalyLevel.SIGNIFICANT
    if rvol < params.anomaly_threshold:
        return AnomalyLevel.STRONG
    return AnomalyLevel.ANOMALY


def compute_rvol(
    candles: Sequence[Candle],
    params: RvolParams = RvolParams(),
) -> list[RvolState]:
    n = len(candles)
    out: list[RvolState] = []

    for i in range(n):
        avg5, rvol5 = _rvol(candles, i, 5)
        avg10, rvol10 = _rvol(candles, i, 10)
        avg20, rvol20 = _rvol(candles, i, 20)

        windows = {5: (avg5, rvol5), 10: (avg10, rvol10), 20: (avg20, rvol20)}
        if params.primary_window in windows:
            avg_primary, rvol_primary = windows[params.primary_window]
        else:
            avg_primary, rvol_primary = _rvol(candles, i, params.primary_window)

        vol_accel = None
        if rvol5 is not None and rvol20 is not None and rvol20 != 0:
            vol_accel = rvol5 / rvol20 - 1

        percentile = _percentile(candles, i, params.percentile_lookback)
        anomaly_level = _anomaly_level(rvol_primary, params)
        confirmed = rvol_primary is not None and rvol_primary >= params.significant_threshold
        spike = rvol_primary is not None and rvol_primary >= params.strong_threshold

        out.append(
            RvolState(
                time=candles[i].time,
                volume=candles[i].volume,
                avg_volume=avg_primary,
                rvol=rvol_primary,
                rvol5=rvol5,
                rvol10=rvol10,
                rvol20=rvol20,
                vol_accel=vol_accel,
                percentile=percentile,
                anomaly_level=anomaly_level,
                confirmed=confirmed,
                spike=spike,
            )
        )

    return out
