"""Golden parity — ichimoku/rvol agents via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents import ichimoku_agent, rvol_agent
from tests.golden_compare import assert_golden_equal
from tests.indicators.test_ichimoku_lookahead import _make_candles

_ICHI = Path(__file__).resolve().parent / "fixtures" / "ichimoku_agent_golden.json"
_RVOL = Path(__file__).resolve().parent / "fixtures" / "rvol_agent_golden.json"


def _payload(out) -> dict:
    return {
        "agent": out.agent,
        "direction": out.direction.value,
        "probability": out.probability,
        "confidence": out.confidence,
        "expected_value": out.expected_value,
        "reasons": list(out.reasons),
        "invalidation": list(out.invalidation),
        "metadata": dict(out.metadata),
    }


@pytest.mark.parametrize("seed", [7, 42])
def test_ichimoku_agent_matches_golden(seed: int):
    golden = json.loads(_ICHI.read_text(encoding="utf-8"))[f"seed_{seed}"]
    actual = [_payload(o) for o in ichimoku_agent.analyze(_make_candles(300, seed=seed))]
    assert_golden_equal(actual, golden)


@pytest.mark.parametrize("seed", [7, 42])
def test_rvol_agent_matches_golden(seed: int):
    golden = json.loads(_RVOL.read_text(encoding="utf-8"))[f"seed_{seed}"]
    actual = [_payload(o) for o in rvol_agent.analyze(_make_candles(300, seed=seed))]
    assert_golden_equal(actual, golden)
