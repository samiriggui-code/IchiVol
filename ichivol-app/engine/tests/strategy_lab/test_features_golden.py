"""Golden FeatureBar parity — registry path must match pre-T1c fixture."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

import pytest

from app.strategy_lab.features import FeatureBar, build_feature_series
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "features_golden.json"


def _serialize(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


@pytest.mark.parametrize("seed", [7, 42])
def test_feature_bars_match_golden_fixture(seed: int):
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    expected = golden[f"seed_{seed}"]
    series = build_feature_series(_make_candles(300, seed=seed))
    actual = [_serialize(b) for b in series.bars]
    assert actual == expected
    assert all(isinstance(b, FeatureBar) for b in series.bars)
