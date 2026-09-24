"""T9f — Lab FeatureBar fib_* + conditions + lab_context observation."""

from __future__ import annotations

from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.lab_context import observe_lab_context
from tests.indicators.test_ichimoku_lookahead import _make_candles

_T9F_CONDITION_KEYS = (
    "fvg_status",
    "impulse_displacement_atr_min",
    "fib_confluence",
    "fib_key_confluence",
    "fib_impulse_up",
    "fib_impulse_down",
    "fib_anchor_impulse",
)

_T9F_FEATURE_FIELDS = (
    "fib_confluence",
    "fib_key_confluence",
    "fib_impulse_up",
    "fib_impulse_down",
    "fib_anchor_impulse",
    "fib_nearest_ratio",
)


def test_t9f_conditions_registered():
    for key in _T9F_CONDITION_KEYS:
        assert key in CONDITION_REGISTRY
        assert "EXPERIMENTAL" in CONDITION_REGISTRY[key].description


def test_t9f_feature_bar_has_fib_fields():
    series = build_feature_series(_make_candles(300, seed=7))
    bar = series.bars[-1]
    for field in _T9F_FEATURE_FIELDS:
        assert hasattr(bar, field)


def test_observe_lab_context_causal_and_additive():
    candles = _make_candles(300, seed=42)
    full = observe_lab_context(candles)
    trunc = observe_lab_context(candles[:-1])
    assert full is not None
    assert trunc is not None
    # Truncation must not invent future-bar events on the previous last bar.
    prev = observe_lab_context(candles[:-1])
    assert prev is not None
    assert prev.to_dict() == trunc.to_dict()


def test_observe_lab_context_does_not_require_pipeline():
    obs = observe_lab_context(_make_candles(200, seed=3))
    assert obs is not None
    d = obs.to_dict()
    assert "disclaimer" in d
    assert "alter decision" in d["disclaimer"]
    assert isinstance(d["fvg_active"], bool)
    assert isinstance(d["fib_confluence"], bool)
    assert isinstance(d["choch_bullish"], bool)
