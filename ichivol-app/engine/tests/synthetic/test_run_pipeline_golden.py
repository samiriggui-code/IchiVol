"""Golden parity — synthetic run_pipeline_over_candles via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.synthetic.validation import run_pipeline_over_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "run_pipeline_over_candles_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_run_pipeline_over_candles_matches_golden(seed: int):
    results = run_pipeline_over_candles(_make_candles(300, seed=seed))
    actual = [{"decision": r.decision, "direction": r.direction.value} for r in results]
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
