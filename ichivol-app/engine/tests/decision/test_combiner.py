"""Validates the mission's central worked example directly (brief §6):
the same strong Ichimoku bullish structure must resolve to STRONG_BUY when
RVOL confirms and WATCH when RVOL is weak -- RVOL must never flip direction,
only gate confidence.
"""

from __future__ import annotations

import pytest

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.decision.combiner import combine_ichimoku_rvol
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.rvol import RvolParams

ICHI_PARAMS = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
RVOL_PARAMS = RvolParams()


def _uptrend_candles_with_volume(n: int, volumes: list[float]) -> list[Candle]:
    return [
        Candle(
            time=i,
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=volumes[i],
        )
        for i in range(n)
    ]


def _bullish_ichimoku_output(n: int = 160):
    flat_volume = [50.0] * n
    candles = _uptrend_candles_with_volume(n, flat_volume)
    outputs = ichimoku_agent.analyze(candles, ICHI_PARAMS)
    assert outputs[-1].direction == Direction.LONG  # sanity check on the fixture
    return outputs[-1]


def test_strong_ichimoku_with_weak_rvol_is_watch_not_buy():
    ichi_output = _bullish_ichimoku_output()

    weak_volumes = [50.0] * 30 + [15.0]  # last bar well below trailing average
    rvol_outputs = rvol_agent.analyze(_uptrend_candles_with_volume(31, weak_volumes), RVOL_PARAMS)
    rvol_output = rvol_outputs[-1]

    result = combine_ichimoku_rvol(ichi_output, rvol_output)
    assert result.direction == Direction.LONG  # RVOL never flips direction
    assert result.decision == "WATCH"
    assert result.confidence < 0.4
    assert "low_relative_volume_participation" in result.risks


def test_strong_ichimoku_with_strong_rvol_is_strong_buy():
    ichi_output = _bullish_ichimoku_output()

    strong_volumes = [50.0] * 30 + [250.0]  # last bar far above trailing average
    rvol_outputs = rvol_agent.analyze(_uptrend_candles_with_volume(31, strong_volumes), RVOL_PARAMS)
    rvol_output = rvol_outputs[-1]

    result = combine_ichimoku_rvol(ichi_output, rvol_output)
    assert result.direction == Direction.LONG
    assert result.decision == "STRONG_BUY"
    assert result.confidence >= 0.75
    assert "low_relative_volume_participation" not in result.risks


def test_neutral_ichimoku_is_always_wait_regardless_of_rvol():
    flat_candles = [
        Candle(time=i, open=50, high=50, low=50, close=50, volume=200.0) for i in range(160)
    ]
    ichi_output = ichimoku_agent.analyze(flat_candles, ICHI_PARAMS)[-1]
    assert ichi_output.direction == Direction.NEUTRAL

    rvol_output = rvol_agent.analyze(flat_candles, RVOL_PARAMS)[-1]

    result = combine_ichimoku_rvol(ichi_output, rvol_output)
    assert result.decision == "WAIT"
    assert result.direction == Direction.NEUTRAL


def test_rejects_mismatched_agents():
    flat_candles = [
        Candle(time=i, open=50, high=50, low=50, close=50, volume=200.0) for i in range(30)
    ]
    ichi_output = ichimoku_agent.analyze(flat_candles, ICHI_PARAMS)[-1]

    with pytest.raises(ValueError):
        combine_ichimoku_rvol(ichi_output, ichi_output)  # wrong second agent on purpose
