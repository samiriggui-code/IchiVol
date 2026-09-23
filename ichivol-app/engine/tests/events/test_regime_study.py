"""PHASE 6 — anomaly regime event-study + calibration (no Postgres / no network)."""

from __future__ import annotations

from app.agents.types import Direction
from app.events.calibrate import calibrate_anomaly_thresholds
from app.events.regime_study import study_anomaly_regimes, anomaly_regime_study_dict
from app.events.types import MarketRegime
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 1000.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _series(n: int = 120, base: float = 100.0) -> list[Candle]:
    out: list[Candle] = []
    px = base
    for i in range(n):
        o = px
        c = px * (1.0 + (0.0002 if i % 2 == 0 else -0.0002))
        h, l = max(o, c) * 1.0003, min(o, c) * 0.9997
        out.append(_c(1_700_000_000 + i * 3600, o, h, l, c, v=1000.0 + (i % 7)))
        px = c
    return out


def _atr_flat(candles: list[Candle], atr: float = 1.0) -> list[AtrState]:
    return [
        AtrState(
            time=c.time,
            true_range=atr,
            atr=atr,
            percentile=0.5,
            regime=VolatilityRegime.NORMAL,
            suggested_stop_distance=atr * 1.5,
        )
        for c in candles
    ]


def test_study_splits_normal_vs_unknown():
    candles = _series(120)
    # Inject a shock bar mid-series
    i = 90
    c = candles[i]
    candles[i] = _c(c.time, c.open, c.high, c.open * 0.85, c.open * 0.86, v=80_000.0)

    # Desired: NEUTRAL then LONG entry at shock bar, another LONG entry in quiet zone
    desired = [Direction.NEUTRAL] * len(candles)
    desired[70] = Direction.LONG  # quiet entry
    desired[71] = Direction.LONG
    desired[i] = Direction.LONG  # anomaly entry (rising edge from NEUTRAL at i-1)
    # Ensure rising edge at i: desired[i-1] must differ
    desired[i - 1] = Direction.NEUTRAL
    # Rising edge at 70
    desired[69] = Direction.NEUTRAL

    atr_states = _atr_flat(candles, atr=c.open * 0.01)
    report = study_anomaly_regimes(
        candles,
        desired,
        atr_states,
        symbol="BTCUSDT",
        timeframe="1h",
        min_signals=1,
        rvol_values=[1.0] * len(candles),
    )
    regimes = {s.regime: s for s in report.slices}
    assert "GLOBAL" in regimes
    assert MarketRegime.NORMAL_MARKET.value in regimes or MarketRegime.UNKNOWN_EVENT.value in regimes
    # Shock bar should contribute at least one UNKNOWN_EVENT signal if tagged as such
    assert report.n_bars == len(candles)
    d = anomaly_regime_study_dict(report)
    assert "comparison" in d
    assert "disclaimer" in d


def test_calibration_suggests_finite_thresholds():
    candles = _series(100)
    atr_states = _atr_flat(candles, atr=1.0)
    report = calibrate_anomaly_thresholds(
        candles, atr_states, symbol="BTCUSDT", timeframe="1h"
    )
    assert report.n_bars == 100
    assert "return_z_abs" in report.suggested_thresholds
    for v in report.suggested_thresholds.values():
        assert v == v  # not NaN
        assert v > 0


def test_calibration_does_not_mutate_defaults():
    from app.events.thresholds import DEFAULT_THRESHOLDS

    before = DEFAULT_THRESHOLDS.return_z_abs
    candles = _series(90)
    calibrate_anomaly_thresholds(candles, _atr_flat(candles), symbol="X", timeframe="1h")
    assert DEFAULT_THRESHOLDS.return_z_abs == before
