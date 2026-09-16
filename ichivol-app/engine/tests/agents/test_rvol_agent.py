from __future__ import annotations

import json

from app.agents.rvol_agent import AGENT_NAME, analyze
from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.indicators.rvol import RvolParams

PARAMS = RvolParams()


def _candles_with_volumes(volumes: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=100, high=101, low=99, close=100, volume=v)
        for i, v in enumerate(volumes)
    ]


def test_rvol_agent_never_votes_on_direction():
    volumes = [50.0] * 30 + [200.0]
    outputs = analyze(_candles_with_volumes(volumes), PARAMS)
    last = outputs[-1]
    assert last.agent == AGENT_NAME
    assert last.direction == Direction.NEUTRAL
    assert last.probability == 0.5
    assert last.expected_value == 0.0


def test_rvol_spike_produces_high_confidence():
    volumes = [50.0] * 30 + [200.0]
    outputs = analyze(_candles_with_volumes(volumes), PARAMS)
    last = outputs[-1]
    assert last.confidence == 1.0
    assert "volume_anomaly" in last.reasons


def test_low_participation_produces_low_confidence():
    volumes = [100.0] * 30 + [20.0]
    outputs = analyze(_candles_with_volumes(volumes), PARAMS)
    last = outputs[-1]
    assert last.confidence == 0.1
    assert "low_participation" in last.reasons


def test_agent_output_is_json_serializable_shape():
    volumes = [50.0] * 30 + [200.0]
    outputs = analyze(_candles_with_volumes(volumes), PARAMS)
    last = outputs[-1]
    payload = {
        "agent": last.agent,
        "direction": last.direction.value,
        "probability": last.probability,
        "confidence": last.confidence,
        "expected_value": last.expected_value,
        "reasons": last.reasons,
        "invalidation": last.invalidation,
        "metadata": last.metadata,
    }
    json.dumps(payload)
