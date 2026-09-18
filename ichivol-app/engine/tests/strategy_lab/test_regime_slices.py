"""Tests — Strategy Lab Phase 6 regime slices."""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.strategy_lab.regime import (
    DirectionRegime,
    StructureRegime,
    VolRegime,
    classify_regimes,
)
from app.strategy_lab.regime_slices import run_regime_slices_on_candles
from app.strategy_lab.ruleset import parse_ruleset


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def test_classify_regimes_length():
    candles = [
        _c(i, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100.5 + i * 0.1)
        for i in range(60)
    ]
    tags = classify_regimes(candles)
    assert len(tags) == 60
    assert all(isinstance(t.structure, StructureRegime) for t in tags)
    assert all(isinstance(t.volatility, VolRegime) for t in tags)
    assert all(isinstance(t.direction, DirectionRegime) for t in tags)


def test_regime_slices_includes_global():
    candles = []
    for i in range(120):
        base = 100 + i * 0.4
        candles.append(
            _c(i, base, base + 2, base - 1, base + 1, 90 + (150 if i % 16 == 0 else 0))
        )
    rs = parse_ruleset(
        {
            "id": "IV_REGIME_TEST",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.1},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    report = run_regime_slices_on_candles(
        candles, rs, symbol="TEST", timeframe="1h", persist=False
    )
    assert report.n_bars == 120
    assert report.slices[0].regime == "GLOBAL"
    assert "GLOBAL" in report.regime_bar_counts
    labels = {s.regime for s in report.slices}
    assert "GLOBAL" in labels
