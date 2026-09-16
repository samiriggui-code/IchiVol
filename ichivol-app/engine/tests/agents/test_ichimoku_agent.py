from __future__ import annotations

from app.agents.ichimoku_agent import AGENT_NAME, analyze
from app.agents.types import Direction
from app.indicators.ichimoku import Candle, IchimokuParams

PARAMS = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)


def _flat_candles(n: int, price: float = 50.0) -> list[Candle]:
    return [
        Candle(time=i, open=price, high=price, low=price, close=price, volume=1.0)
        for i in range(n)
    ]


def _uptrend_candles(n: int) -> list[Candle]:
    return [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=1.0)
        for i in range(n)
    ]


def test_insufficient_history_is_neutral_with_zero_confidence():
    outputs = analyze(_flat_candles(5), PARAMS)
    last = outputs[-1]
    assert last.agent == AGENT_NAME
    assert last.direction == Direction.NEUTRAL
    assert last.probability == 0.5
    assert last.confidence == 0.0
    assert last.expected_value == 0.0
    assert "insufficient_history" in last.reasons
    assert last.invalidation == []


def test_flat_market_is_neutral_but_fully_confident():
    outputs = analyze(_flat_candles(120), PARAMS)
    last = outputs[-1]
    assert last.direction == Direction.NEUTRAL
    assert last.probability == 0.5
    assert last.confidence == 1.0
    assert "insufficient_confluence" in last.reasons


def test_sustained_uptrend_is_long_with_high_confidence_and_probability():
    outputs = analyze(_uptrend_candles(160), PARAMS)
    last = outputs[-1]
    assert last.direction == Direction.LONG
    assert last.probability > 0.5
    assert last.confidence == 1.0
    assert "price_above_kumo" in last.reasons
    assert "bullish_future_kumo" in last.reasons
    assert "bearish_tk_cross" in last.invalidation
    assert last.metadata["score"] is not None and last.metadata["score"] > 0


def test_agent_output_is_json_serializable_shape():
    import json

    outputs = analyze(_uptrend_candles(160), PARAMS)
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
    # Must not raise -- every field is a plain JSON-compatible type.
    json.dumps(payload)
