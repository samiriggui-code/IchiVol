from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.rvol import AnomalyLevel, RvolParams, compute_rvol

PARAMS = RvolParams()


def _candles_with_volumes(volumes: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=100, high=101, low=99, close=100, volume=v)
        for i, v in enumerate(volumes)
    ]


def test_constant_volume_is_rvol_one_and_normal():
    candles = _candles_with_volumes([50.0] * 40)
    states = compute_rvol(candles, PARAMS)
    last = states[-1]
    assert last.rvol == 1.0
    assert last.rvol5 == last.rvol10 == last.rvol20 == 1.0
    assert last.anomaly_level == AnomalyLevel.NORMAL
    assert last.confirmed is False
    assert last.spike is False
    assert last.vol_accel == 0.0


def test_first_bar_has_no_lookback_but_rvol_is_defined():
    candles = _candles_with_volumes([80.0])
    states = compute_rvol(candles, PARAMS)
    first = states[0]
    # With only one bar of history, avg == that bar's own volume -> rvol 1.0.
    assert first.avg_volume == 80.0
    assert first.rvol == 1.0
    assert first.percentile is None  # need >= 2 points for a percentile to mean anything


def test_volume_spike_is_classified_as_anomaly_and_confirmed_and_spike():
    volumes = [50.0] * 30 + [200.0]  # last bar is 4x the trailing average
    candles = _candles_with_volumes(volumes)
    states = compute_rvol(candles, PARAMS)
    last = states[-1]
    assert last.rvol is not None and last.rvol > PARAMS.anomaly_threshold
    assert last.anomaly_level == AnomalyLevel.ANOMALY
    assert last.confirmed is True
    assert last.spike is True


def test_low_participation_is_classified_as_low_and_not_confirmed():
    volumes = [100.0] * 30 + [20.0]  # last bar well below trailing average
    candles = _candles_with_volumes(volumes)
    states = compute_rvol(candles, PARAMS)
    last = states[-1]
    assert last.rvol is not None and last.rvol < PARAMS.low_threshold
    assert last.anomaly_level == AnomalyLevel.LOW
    assert last.confirmed is False
    assert last.spike is False


def test_monotonic_increasing_volume_gives_top_percentile():
    volumes = [float(v) for v in range(1, 51)]  # strictly increasing
    candles = _candles_with_volumes(volumes)
    states = compute_rvol(candles, PARAMS)
    last = states[-1]
    assert last.percentile == 1.0  # current bar is the highest volume seen so far
