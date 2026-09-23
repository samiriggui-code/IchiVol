"""Golden parity — classify_regimes via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.strategy_lab.regime import classify_regimes
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "classify_regimes_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_classify_regimes_matches_golden(seed: int):
    tags = classify_regimes(_make_candles(300, seed=seed))
    actual = [
        {
            "structure": t.structure.value,
            "volatility": t.volatility.value,
            "direction": t.direction.value,
        }
        for t in tags
    ]
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
