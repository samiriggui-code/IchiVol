from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.backtest.engine import run_backtest
from app.indicators.ichimoku import Candle


def _flat_candles(opens: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=o, low=o, close=o, volume=1.0) for i, o in enumerate(opens)
    ]


def test_neutral_throughout_has_no_trades_and_zero_return():
    candles = _flat_candles([100, 101, 99, 102, 98])
    desired = [Direction.NEUTRAL] * len(candles)
    result = run_backtest(candles, desired, symbol="TEST", timeframe="1h")
    assert result.trades == []
    assert all(r == 0.0 for r in result.bar_returns)


def test_long_position_delayed_one_bar_and_force_closed_at_end():
    opens = [100, 101, 102, 103, 104]
    candles = _flat_candles(opens)
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
    ]
    result = run_backtest(
        candles, desired, symbol="TEST", timeframe="1h", commission_bps=5.0, slippage_bps=3.0
    )

    cost = 8.0 / 10_000
    expected = [0.0, 0.0, math.log(103 / 102) - cost, math.log(104 / 103)]
    assert result.bar_returns == pytest.approx(expected)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.direction == Direction.LONG
    assert trade.entry_time == 2
    assert trade.entry_price == 102
    assert trade.exit_time == 4  # force-closed at the very last candle
    assert trade.exit_price == 104  # close, not open, for the forced final exit
    assert trade.log_return == pytest.approx(math.log(104 / 102))


def test_position_closed_mid_series_when_signal_returns_to_neutral():
    opens = [100, 101, 102, 103, 104, 105]
    candles = _flat_candles(opens)
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    result = run_backtest(candles, desired, symbol="TEST", timeframe="1h")

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == 2
    assert trade.entry_price == 102
    assert trade.exit_time == 4
    assert trade.exit_price == 104  # closed at the bar's open, not its close
    assert trade.log_return == pytest.approx(math.log(104 / 102))


def test_short_position_profits_when_price_falls():
    opens = [100, 100, 90, 80]
    candles = _flat_candles(opens)
    desired = [Direction.NEUTRAL, Direction.SHORT, Direction.SHORT, Direction.SHORT]
    result = run_backtest(candles, desired, symbol="TEST", timeframe="1h", commission_bps=0, slippage_bps=0)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.direction == Direction.SHORT
    assert trade.log_return > 0  # price fell, short profits


def test_no_lookahead_when_desired_length_mismatches_candles():
    candles = _flat_candles([100, 101, 102])
    with pytest.raises(ValueError):
        run_backtest(candles, [Direction.LONG, Direction.LONG])
