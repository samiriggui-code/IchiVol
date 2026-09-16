from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.backtest.engine import BacktestResult, Trade
from app.backtest.metrics import compute_metrics


def _result(bar_returns, posn, trades, timeframe="1h") -> BacktestResult:
    return BacktestResult(
        symbol="TEST",
        timeframe=timeframe,
        n_bars=len(bar_returns) + 1,
        bar_returns=bar_returns,
        posn=posn,
        trades=trades,
        commission_bps=0.0,
        slippage_bps=0.0,
    )


def test_empty_backtest_has_neutral_metrics():
    result = _result([], [], [])
    metrics = compute_metrics(result)
    assert metrics.n_bars == 0
    assert metrics.total_return == 0.0
    assert metrics.num_trades == 0
    assert metrics.win_rate is None
    assert metrics.exposure == 0.0


def test_total_return_matches_sum_of_log_returns():
    bar_returns = [0.01, -0.005, 0.02, 0.0]
    posn = [Direction.LONG] * 4
    result = _result(bar_returns, posn, [])
    metrics = compute_metrics(result)
    assert metrics.total_return == pytest.approx(math.exp(sum(bar_returns)) - 1)
    assert metrics.exposure == 1.0


def test_unknown_timeframe_skips_annualized_metrics_but_not_the_rest():
    bar_returns = [0.01, -0.01, 0.02]
    posn = [Direction.LONG] * 3
    result = _result(bar_returns, posn, [], timeframe="3m")  # not in PERIODS_PER_YEAR
    metrics = compute_metrics(result)
    assert metrics.cagr is None
    assert metrics.sharpe is None
    assert metrics.sortino is None
    assert metrics.total_return == pytest.approx(math.exp(sum(bar_returns)) - 1)


def test_max_drawdown_detects_a_known_peak_to_trough():
    # equity path: 1 -> 1.10 -> 0.99 -> 1.05  => drawdown from 1.10 to 0.99 = 10%
    bar_returns = [math.log(1.10), math.log(0.99 / 1.10), math.log(1.05 / 0.99)]
    posn = [Direction.LONG] * 3
    result = _result(bar_returns, posn, [])
    metrics = compute_metrics(result)
    assert metrics.max_drawdown == pytest.approx(0.10, abs=1e-6)


def test_win_rate_profit_factor_and_expectancy_from_trades():
    trades = [
        Trade(0, 1, Direction.LONG, 100, 110, math.log(110 / 100)),  # win +10%
        Trade(1, 2, Direction.LONG, 110, 99, math.log(99 / 110)),  # loss -10%
        Trade(2, 3, Direction.LONG, 99, 108.9, math.log(108.9 / 99)),  # win +10%
    ]
    bar_returns = [0.0, 0.0, 0.0]
    posn = [Direction.LONG] * 3
    result = _result(bar_returns, posn, trades)
    metrics = compute_metrics(result)

    assert metrics.num_trades == 3
    assert metrics.win_rate == pytest.approx(2 / 3)
    assert metrics.profit_factor > 1.0  # two +10% wins vs one -10% loss
    assert metrics.expectancy == pytest.approx(
        sum(math.exp(t.log_return) - 1 for t in trades) / 3
    )


def test_all_losing_trades_has_zero_profit_factor_not_a_crash():
    trades = [Trade(0, 1, Direction.LONG, 100, 90, math.log(90 / 100))]
    result = _result([0.0], [Direction.LONG], trades)
    metrics = compute_metrics(result)
    assert metrics.profit_factor == 0.0 or metrics.profit_factor == pytest.approx(0.0)
