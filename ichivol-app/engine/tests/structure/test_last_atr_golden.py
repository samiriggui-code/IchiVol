"""Golden parity — structure.last_atr via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.structure.atr_utils import last_atr
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "last_atr_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_last_atr_matches_golden(seed: int):
    actual = {"last_atr": last_atr(_make_candles(300, seed=seed), period=14)}
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
