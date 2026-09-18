"""Tests — Strategy Lab Phase 5 ablation."""

from __future__ import annotations

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.strategy_lab.ablation import (
    build_cumulative_rulesets,
    build_leave_one_out_rulesets,
    run_ablation_on_candles,
)


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def test_build_cumulative_grows_conditions():
    layers = [
        ("A", {"price_above_kumo": True}),
        ("B", {"rvol_min": 1.5}),
        ("C", {"bos_bullish": True}),
    ]
    sets = build_cumulative_rulesets(layers, direction=Direction.LONG)
    assert len(sets) == 3
    assert list(sets[0].conditions) == ["price_above_kumo"]
    assert "rvol_min" in sets[1].conditions
    assert "bos_bullish" in sets[2].conditions
    assert sets[2].id.endswith("__C")


def test_leave_one_out_count():
    full = {"price_above_kumo": True, "rvol_min": 1.5, "cmf_min": 0.0}
    sets = build_leave_one_out_rulesets(full)
    assert len(sets) == 1 + 3
    assert sets[0].meta["ablation_label"] == "FULL"


def test_run_ablation_on_candles():
    candles = []
    for i in range(120):
        base = 100 + i * 0.35
        candles.append(
            _c(i, base, base + 2, base - 1, base + 1, 90 + (180 if i % 18 == 0 else 0))
        )
    result = run_ablation_on_candles(
        candles,
        symbol="TEST",
        timeframe="1h",
        mode="cumulative",
        layers=[
            ("A_ICHIMOKU", {"price_above_kumo": True, "tenkan_above_kijun": True}),
            ("B_RVOL", {"rvol_min": 1.2}),
        ],
        persist=False,
    )
    assert result.n_bars == 120
    assert len(result.steps) == 2
    assert len(result.deltas) == 1
    assert result.deltas[0].from_label == "A_ICHIMOKU"
    assert result.deltas[0].to_label == "B_RVOL"
    assert "rvol_min" in result.deltas[0].added_conditions
