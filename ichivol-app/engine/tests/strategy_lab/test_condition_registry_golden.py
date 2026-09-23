"""Golden CONDITION_SCHEMA + per-condition eval — captured BEFORE T3c registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.types import Direction
from app.strategy_lab.evaluator import _condition_holds
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import CONDITION_ENUMS, CONDITION_SCHEMA
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_SCHEMA = _FIXTURES / "condition_schema_golden.json"
_EVAL = _FIXTURES / "condition_eval_golden.json"

_FLOAT_SAMPLES = {
    "rvol_min": [1.0, 1.5, 2.0],
    "rvol_max": [1.0, 1.5, 2.0],
    "atr_percentile_min": [0.25, 0.5, 0.75],
    "atr_percentile_max": [0.25, 0.5, 0.75],
    "cmf_min": [-0.1, 0.0, 0.1],
    "cmf_max": [-0.1, 0.0, 0.1],
    "rsi_min": [30.0, 50.0, 70.0],
    "rsi_max": [30.0, 50.0, 70.0],
    "price_kijun_distance_atr_min": [0.5, 1.0, 2.0],
    "price_kijun_distance_atr_max": [0.5, 1.0, 2.0],
    "kumo_thickness_atr_min": [0.5, 1.0, 2.0],
    "kumo_thickness_atr_max": [0.5, 1.0, 2.0],
    "ppo_min": [-1.0, 0.0, 1.0],
    "ppo_max": [-1.0, 0.0, 1.0],
}
_INT_SAMPLES = {
    "tk_cross_age_max": [3, 10, 20],
    "kumo_twist_age_max": [3, 10, 20],
    "ppo_cross_age_max": [3, 10, 20],
    "best_cloud_cross_age_max": [3, 10, 20],
}


def _sample_values(key: str, typ: type) -> list:
    if typ is bool:
        return [True, False]
    if typ is int:
        return _INT_SAMPLES[key]
    if typ is float:
        return _FLOAT_SAMPLES[key]
    if typ is str:
        return sorted(CONDITION_ENUMS[key])
    raise TypeError(typ)


def _value_key(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def test_condition_schema_matches_pre_t3c_golden():
    expected = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    actual = {k: v.__name__ for k, v in CONDITION_SCHEMA.items()}
    assert actual == expected


@pytest.mark.parametrize("seed", [7, 42])
def test_condition_eval_matches_pre_t3c_golden(seed: int):
    golden = json.loads(_EVAL.read_text(encoding="utf-8"))
    expected = golden[f"seed_{seed}"]
    series = build_feature_series(_make_candles(300, seed=seed))
    actual: dict = {}
    for key, typ in sorted(CONDITION_SCHEMA.items()):
        key_payload: dict = {}
        for direction in (Direction.LONG, Direction.SHORT):
            dir_payload = {}
            for val in _sample_values(key, typ):
                hits = [
                    i
                    for i, bar in enumerate(series.bars)
                    if _condition_holds(bar, key, val, direction)
                ]
                dir_payload[_value_key(val)] = hits
            key_payload[direction.value] = dir_payload
        actual[key] = key_payload
    assert actual == expected
