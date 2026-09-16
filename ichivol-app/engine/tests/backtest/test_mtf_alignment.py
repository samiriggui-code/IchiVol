"""Validates the causal timestamp-based MTF alignment used to backtest the
staged pipeline (app/backtest/experiments.py::_align_mtf_directions): a
higher-timeframe bar may only inform a primary bar once it has fully
closed (open_time + duration <= primary bar's own time), never while still
"in progress" relative to the primary bar, and never a future HTF bar.
"""

from __future__ import annotations

from app.agents.types import Direction, StrategyAgentOutput
from app.backtest.experiments import _align_mtf_directions
from app.indicators.ichimoku import Candle

HTF_SECONDS = 14400  # 4h


def _candle_at(t: int) -> Candle:
    return Candle(time=t, open=1, high=1, low=1, close=1, volume=1.0)


def _htf_output(direction: Direction) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=direction,
        probability=0.5,
        confidence=1.0,
        expected_value=0.0,
        reasons=[],
        invalidation=[],
        metadata={},
    )


def test_alignment_only_uses_htf_bars_already_fully_closed():
    htf_candles = [_candle_at(0), _candle_at(14400), _candle_at(28800)]
    htf_outputs = [_htf_output(Direction.LONG), _htf_output(Direction.SHORT), _htf_output(Direction.LONG)]

    primary_times = [0, 3600, 7200, 10800, 14400, 18000, 21600, 25200, 28800, 32400]
    primary_candles = [_candle_at(t) for t in primary_times]

    result = _align_mtf_directions(primary_candles, htf_candles, htf_outputs, HTF_SECONDS)

    expected = [
        None,  # t=0     : htf bar0 (closes 14400) not yet closed
        None,  # t=3600
        None,  # t=7200
        None,  # t=10800
        Direction.LONG,  # t=14400 : htf bar0 just closed
        Direction.LONG,  # t=18000
        Direction.LONG,  # t=21600
        Direction.LONG,  # t=25200
        Direction.SHORT,  # t=28800 : htf bar1 just closed
        Direction.SHORT,  # t=32400
    ]
    assert result == expected


def test_alignment_never_reaches_into_a_future_htf_bar():
    # Only one HTF bar exists; primary bars far beyond it must not somehow
    # pick up a direction that doesn't exist yet.
    htf_candles = [_candle_at(0)]
    htf_outputs = [_htf_output(Direction.LONG)]
    primary_candles = [_candle_at(t) for t in [0, 14400, 100_000]]

    result = _align_mtf_directions(primary_candles, htf_candles, htf_outputs, HTF_SECONDS)
    assert result == [None, Direction.LONG, Direction.LONG]


def test_alignment_is_stable_under_truncation_of_primary_candles():
    """Same anti-lookahead proof style as the rest of the codebase: the
    function must never use a primary candle beyond the one it's currently
    resolving, so truncating the primary series can only ever drop trailing
    results, never change earlier ones."""
    htf_candles = [_candle_at(t) for t in range(0, 200_000, HTF_SECONDS)]
    htf_outputs = [_htf_output(Direction.LONG if i % 2 == 0 else Direction.SHORT) for i in range(len(htf_candles))]
    primary_candles = [_candle_at(t) for t in range(0, 200_000, 3600)]

    full = _align_mtf_directions(primary_candles, htf_candles, htf_outputs, HTF_SECONDS)
    for cut in (5, 17, 30, len(primary_candles) - 1):
        truncated = _align_mtf_directions(primary_candles[:cut], htf_candles, htf_outputs, HTF_SECONDS)
        assert truncated == full[:cut]
