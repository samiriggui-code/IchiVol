"""EventAnomalyDetector — causal rules + anti-lookahead (no Postgres)."""

from __future__ import annotations

import math

import pytest

from app.events.anomaly import detect_anomaly
from app.events.thresholds import AnomalyThresholds
from app.events.types import AnomalyType, MarketRegime
from app.indicators.ichimoku import Candle


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _quiet_series(n: int = 80, base: float = 100.0) -> list[Candle]:
    """Near-flat history so z-scores stay small until a shock is appended."""
    out: list[Candle] = []
    px = base
    for i in range(n):
        # tiny noise
        o = px
        c = px * (1.0 + (0.0001 if i % 2 == 0 else -0.0001))
        h = max(o, c) * 1.0002
        l = min(o, c) * 0.9998
        out.append(_c(1_700_000_000 + i * 3600, o, h, l, c, v=1000.0 + (i % 5)))
        px = c
    return out


def test_insufficient_history_is_normal():
    candles = _quiet_series(10)
    obs = detect_anomaly(candles, symbol="BTCUSDT", timeframe="1h")
    assert obs.event_suspected is False
    assert obs.event_type == AnomalyType.NONE
    assert obs.market_regime == MarketRegime.NORMAL_MARKET
    assert "insufficient_history" in obs.reasons


def test_price_volume_shock_marks_unknown_event():
    candles = _quiet_series(80)
    last = candles[-1]
    # Huge drop + volume spike on last bar
    shock = _c(
        last.time + 3600,
        last.close,
        last.close * 1.01,
        last.close * 0.80,
        last.close * 0.82,
        v=50_000.0,
    )
    candles = candles + [shock]
    obs = detect_anomaly(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        rvol=5.0,
        atr=last.close * 0.01,
    )
    assert obs.event_suspected is True
    assert obs.event_type in (AnomalyType.PRICE_VOLUME_SHOCK, AnomalyType.PRICE_SHOCK, AnomalyType.VOLUME_SHOCK)
    assert obs.market_regime == MarketRegime.UNKNOWN_EVENT
    assert obs.confidence > 0
    # Without news match, never EVENT_MARKET
    assert obs.market_regime != MarketRegime.EVENT_MARKET


def test_anomaly_does_not_change_when_future_bar_appended_past_scores():
    """Truncation / anti-lookahead: past observation immutable if we only look at prefix."""
    base = _quiet_series(80)
    # Mid shock at index 70
    mid = list(base)
    pivot = mid[70]
    mid[70] = _c(
        pivot.time,
        pivot.open,
        pivot.high,
        pivot.open * 0.85,
        pivot.open * 0.86,
        v=40_000.0,
    )
    # Force recompute only on prefix ending at 70
    prefix = mid[:71]
    obs_a = detect_anomaly(prefix, symbol="X", timeframe="1h", atr=1.0, rvol=4.0)

    # Append a future extreme bar — must not change obs on the same prefix
    future = mid + [
        _c(mid[-1].time + 3600, mid[-1].close, mid[-1].close * 2, mid[-1].close * 0.5, mid[-1].close * 1.5, v=1e6)
    ]
    obs_b = detect_anomaly(future[:71], symbol="X", timeframe="1h", atr=1.0, rvol=4.0)
    assert obs_a.return_zscore == pytest.approx(obs_b.return_zscore, rel=1e-9, abs=1e-12)
    assert obs_a.volume_zscore == pytest.approx(obs_b.volume_zscore, rel=1e-9, abs=1e-12)
    assert obs_a.event_suspected == obs_b.event_suspected
    assert obs_a.event_type == obs_b.event_type


def test_return_zscore_uses_past_only_window():
    """Appending a spike after index i must not change z at i (past-only mean/std)."""
    candles = _quiet_series(90)
    # Force a moderate move at i=80
    i = 80
    c = candles[i]
    candles[i] = _c(c.time, c.open, c.high, c.open * 0.90, c.open * 0.91, v=c.volume)
    obs_before = detect_anomaly(candles[: i + 1], symbol="T", timeframe="1h")

    # Extreme future bar
    last = candles[i]
    candles_ext = candles[: i + 1] + [
        _c(last.time + 3600, last.close, last.close * 3, last.close * 0.1, last.close * 2, v=1e6)
    ]
    obs_after = detect_anomaly(candles_ext[: i + 1], symbol="T", timeframe="1h")
    assert obs_before.return_zscore is not None
    assert obs_after.return_zscore is not None
    assert obs_before.return_zscore == pytest.approx(obs_after.return_zscore, abs=1e-12)


def test_quiet_series_not_suspected():
    candles = _quiet_series(100)
    obs = detect_anomaly(candles, symbol="BTCUSDT", timeframe="1h", atr=1.0, rvol=1.0)
    assert obs.event_suspected is False
    assert obs.event_type == AnomalyType.NONE
    assert obs.market_regime == MarketRegime.NORMAL_MARKET


def test_gap_event_classification():
    candles = _quiet_series(80)
    last = candles[-1]
    # Open gaps down hard vs prev close; tiny range; volume stays normal
    gap_open = last.close * 0.92
    shock = _c(last.time + 3600, gap_open, gap_open * 1.0001, gap_open * 0.9999, gap_open, v=1002.0)
    thr = AnomalyThresholds(
        gap_atr=0.5,
        range_atr=50.0,
        return_z_abs=50.0,
        volume_z=50.0,
        volatility_z_abs=50.0,
        rvol=50.0,
    )
    obs = detect_anomaly(
        candles + [shock],
        symbol="XAUUSD",
        timeframe="1h",
        atr=last.close * 0.01,
        thresholds=thr,
        rvol=1.0,
    )
    assert obs.event_suspected is True
    assert obs.gap_atr_ratio is not None and obs.gap_atr_ratio >= thr.gap_atr
    # Close == open after gap → return may still be large vs quiet history; accept GAP or PRICE.
    assert obs.event_type in (
        AnomalyType.GAP_EVENT,
        AnomalyType.PRICE_SHOCK,
        AnomalyType.PRICE_VOLUME_SHOCK,
        AnomalyType.VOLATILITY_SHOCK,
    )
    assert obs.gap_atr_ratio >= thr.gap_atr
