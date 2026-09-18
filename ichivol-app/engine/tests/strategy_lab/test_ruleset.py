"""Tests — Strategy Lab Phase 2 Rules Engine."""

from __future__ import annotations

import pytest

from app.indicators.ichimoku import Candle
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.evaluator import extract_ruleset_signals, matches_mask
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.run_ruleset import study_ruleset_on_candles


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def test_parse_ruleset_rejects_unknown_condition():
    with pytest.raises(ValueError, match="unknown condition"):
        parse_ruleset(
            {
                "id": "X",
                "direction": "LONG",
                "conditions": {"magic_sauce": True},
            }
        )


def test_parse_ruleset_ok():
    rs = parse_ruleset(
        {
            "id": "IV_TEST",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5, "price_above_kumo": True},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    assert rs.id == "IV_TEST"
    assert rs.conditions["rvol_min"] == 1.5


def test_builtin_catalog_nonempty():
    items = list_builtin_rulesets()
    assert len(items) >= 3
    assert get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001").id.startswith("IV_")


def test_rising_edge_signals():
    # Synthetic trending series with volume spike — enough bars for ichimoku
    candles = []
    for i in range(80):
        base = 100 + i * 0.5
        vol = 500.0 if 50 <= i <= 55 else 100.0
        candles.append(_c(i, base, base + 1, base - 0.5, base + 0.8, vol))

    features = build_feature_series(candles)
    rs = parse_ruleset(
        {
            "id": "IV_RVOL_ONLY",
            "direction": "LONG",
            "conditions": {"rvol_min": 2.0},
        }
    )
    mask = matches_mask(features, rs)
    signals = extract_ruleset_signals(features, rs, rising_edge=True)
    # Rising edge: fewer or equal signals than matching bars
    assert sum(mask) >= len(signals)
    assert all(mask[i] for i, _ in signals)
    # Previous bar should not match (except i==0)
    for i, _ in signals:
        if i > 0:
            assert not mask[i - 1]


def test_study_ruleset_on_candles_runs():
    candles = []
    for i in range(100):
        base = 100 + i * 0.3
        candles.append(_c(i, base, base + 2, base - 1, base + 1, 100 + (50 if i % 17 == 0 else 0)))

    rs = get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001")
    result = study_ruleset_on_candles(
        candles, rs, symbol="TEST", timeframe="1h", horizons=(1, 3, 5)
    )
    assert result.n_bars == 100
    assert result.event_study.variant == rs.id
    assert result.n_signals == result.event_study.n_events or result.n_signals >= result.event_study.n_events
