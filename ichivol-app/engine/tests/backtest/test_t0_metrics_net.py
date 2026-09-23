"""T0-METRICS — net trade stats + bar_returns invariant."""

from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.backtest.engine import BacktestResult, Trade, one_way_cost_log, run_backtest
from app.backtest.metrics import compute_metrics
from app.indicators.ichimoku import Candle
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _flat(opens: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=o, low=o, close=o, volume=1.0) for i, o in enumerate(opens)
    ]


def test_gross_win_net_loss_counts_as_loss_in_win_rate():
    """+5 bps price move, 16 bps RT cost → gross win, net loss → win_rate=0."""
    entry = 100.0
    exit_px = 100.0 * math.exp(0.0005)
    log_ret = math.log(exit_px / entry)
    cost = one_way_cost_log(5.0, 3.0) * 2  # 16 bps
    assert cost == pytest.approx(0.0016)
    trade = Trade(
        0,
        1,
        Direction.LONG,
        entry,
        exit_px,
        log_ret,
        cost_log=cost,
    )
    assert math.exp(trade.log_return) - 1 > 0
    assert math.exp(trade.net_log_return) - 1 < 0
    result = BacktestResult(
        "T",
        "1h",
        2,
        bar_returns=[trade.net_log_return],
        posn=[Direction.LONG],
        trades=[trade],
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    m = compute_metrics(result)
    assert m.win_rate == 0.0
    assert m.win_rate_gross == 1.0
    assert m.expectancy is not None and m.expectancy < 0
    assert m.expectancy_gross is not None and m.expectancy_gross > 0


def test_expectancy_gross_minus_net_approx_mean_simple_cost_gap():
    """expectancy_gross − expectancy ≈ mean gross−net gap (simple returns)."""
    cost = 0.0016
    trades = [
        Trade(0, 1, Direction.LONG, 100, 110, math.log(1.10), cost_log=cost),
        Trade(1, 2, Direction.LONG, 110, 99, math.log(99 / 110), cost_log=cost),
    ]
    result = BacktestResult(
        "T",
        "1h",
        3,
        [0.0, 0.0],
        [Direction.LONG, Direction.LONG],
        trades,
        5.0,
        3.0,
    )
    m = compute_metrics(result)
    assert m.expectancy is not None and m.expectancy_gross is not None
    gaps = [
        (math.exp(t.log_return) - 1) - (math.exp(t.net_log_return) - 1) for t in trades
    ]
    assert m.expectancy_gross - m.expectancy == pytest.approx(sum(gaps) / len(gaps))


def test_ruleset_invariant_sum_net_log_eq_sum_bar_returns():
    candles = _make_candles(400, seed=7)
    ruleset = get_builtin_ruleset("IV_EXP_A_KUMO_BO_001")
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="INV", timeframe="1h",
        commission_bps=5.0, slippage_bps=3.0,
    )
    # All ruleset trades are closed inside the window by construction.
    sum_net = sum(t.net_log_return for t in result.backtest.trades)
    sum_bars = sum(result.backtest.bar_returns)
    assert sum_net == pytest.approx(sum_bars, abs=1e-9)


def test_engine_invariant_mid_close_and_eod_flat():
    """Mid-close and EOD flat OHLC — full round-trip cost on each trade."""
    opens = [100, 101, 102, 103, 104, 105]
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    r = run_backtest(
        _flat(opens), desired, commission_bps=5.0, slippage_bps=3.0
    )
    assert sum(t.net_log_return for t in r.trades) == pytest.approx(
        sum(r.bar_returns), abs=1e-9
    )

    opens2 = [100, 101, 102, 103, 104]
    desired2 = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
    ]
    r2 = run_backtest(
        _flat(opens2), desired2, commission_bps=5.0, slippage_bps=3.0
    )
    assert len(r2.trades) == 1
    assert r2.trades[0].cost_log == pytest.approx(2 * one_way_cost_log(5.0, 3.0))
    assert sum(t.net_log_return for t in r2.trades) == pytest.approx(
        sum(r2.bar_returns), abs=1e-9
    )


@pytest.mark.parametrize("seed", [7, 42])
@pytest.mark.parametrize(
    "ruleset_id",
    ["IV_EXP_A_KUMO_BO_001", "IV_ICHIMOKU_ONLY_LONG_001"],
)
def test_ruleset_invariant_catalog_seeds(seed: int, ruleset_id: str):
    candles = _make_candles(300, seed=seed)
    ruleset = get_builtin_ruleset(ruleset_id)
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="INV", timeframe="1h"
    )
    if not result.backtest.trades:
        pytest.skip("no trades")
    assert sum(t.net_log_return for t in result.backtest.trades) == pytest.approx(
        sum(result.backtest.bar_returns), abs=1e-9
    )
