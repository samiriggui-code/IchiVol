"""T0-MANAGE-c — partial take-profit (Lab backtest only)."""

from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.backtest.engine import BacktestResult, round_trip_cost_log
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.strategy_lab.partial_tp import PartialTpStep, vwap_exit
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.ruleset_backtest import simulate_ruleset_trades


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _atr(n: int, atr: float = 10.0) -> list[AtrState]:
    return [
        AtrState(
            time=i,
            true_range=atr,
            atr=atr,
            percentile=0.5,
            regime=VolatilityRegime.NORMAL,
            suggested_stop_distance=atr * 1.5,
        )
        for i in range(n)
    ]


def _assert_metrics_invariant(details, bar_returns, *, eod_return: float = 0.0) -> None:
    trades = [d.trade for d in details]
    sum_net = sum(t.net_log_return for t in trades)
    sum_path = sum(bar_returns) + eod_return
    assert sum_net == pytest.approx(sum_path, abs=1e-9)


def test_parse_partial_tp_roundtrip():
    rs = parse_ruleset(
        {
            "id": "ptp",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5},
            "stop_atr": 1.0,
            "target_atr": 3.0,
            "exit": {"partial_tp": [{"r_multiple": 1.0, "fraction": 0.5}]},
        }
    )
    assert len(rs.exit.partial_tp) == 1
    assert rs.exit.partial_tp[0] == PartialTpStep(r_multiple=1.0, fraction=0.5)
    again = parse_ruleset(rs.to_dict())
    assert again.exit.partial_tp == rs.exit.partial_tp


@pytest.mark.parametrize(
    "partial_tp, match",
    [
        ([], "non-empty"),
        ([{"r_multiple": True, "fraction": 0.5}], "r_multiple"),
        ([{"r_multiple": 1.0, "fraction": 0}], r"\]0, 1\["),
        ([{"r_multiple": 1.0, "fraction": 1.0}], r"\]0, 1\["),
        ([{"r_multiple": 1.0, "fraction": 0.6}, {"r_multiple": 1.5, "fraction": 0.5}], "sum"),
        ([{"r_multiple": 1.5, "fraction": 0.5}, {"r_multiple": 1.0, "fraction": 0.3}], "increasing"),
        ([{"r_multiple": 1.0, "fraction": 0.5, "extra": 1}], "unknown"),
        ([{"r_multiple": 2.5, "fraction": 0.5}], "target_atr/stop_atr"),
    ],
)
def test_parse_partial_tp_rejects(partial_tp, match):
    with pytest.raises(ValueError, match=match):
        parse_ruleset(
            {
                "id": "x",
                "direction": "LONG",
                "conditions": {"rvol_min": 1.0},
                "stop_atr": 1.0,
                "target_atr": 2.0,
                "exit": {"partial_tp": partial_tp},
            }
        )


def test_partial_then_target_records_vwap_and_fills():
    """Entry 100, stop 90 (1R=10), target 120 (3R). Half at 1R=110, rest at 120."""
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),  # entry
        _c(2, 100, 111, 99, 110),  # 1R touched → partial 50% @ 110
        _c(3, 110, 121, 109, 120),  # target 120 on remainder
    ]
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=5.0,
        slippage_bps=3.0,
        partial_tp=(PartialTpStep(1.0, 0.5),),
    )
    assert len(details) == 1
    d = details[0]
    assert len(d.partial_exits) == 1
    assert d.partial_exits[0].price == pytest.approx(110.0)
    assert d.partial_exits[0].fraction == pytest.approx(0.5)
    assert d.exit_reason == "target"
    vwap = vwap_exit([(110.0, 0.5), (120.0, 0.5)])
    assert vwap == pytest.approx(115.0)
    assert d.trade.exit_price == pytest.approx(115.0)
    assert d.trade.log_return == pytest.approx(math.log(115 / 100))
    # NOT the Jensen-biased weighted-log sum
    bad = 0.5 * math.log(110 / 100) + 0.5 * math.log(120 / 100)
    assert d.trade.log_return != pytest.approx(bad)
    _assert_metrics_invariant(details, bar_returns)


def test_metrics_invariant_with_partials_is_acceptance_gate():
    """Σ net_log_return(trades) == Σ bar_returns (+ eod) within 1e-9."""
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 111, 99, 110),  # partial @ 110
        _c(3, 110, 112, 109, 111),
        _c(4, 111, 112, 89, 90),  # stop 90 on remainder
    ]
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(5, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=4.0,
        commission_bps=5.0,
        slippage_bps=3.0,
        partial_tp=(PartialTpStep(1.0, 0.5),),
    )
    assert details[0].exit_reason == "stop"
    assert len(details[0].partial_exits) == 1
    vwap = 0.5 * 110 + 0.5 * 90
    assert details[0].trade.exit_price == pytest.approx(vwap)
    assert details[0].trade.log_return == pytest.approx(math.log(vwap / 100))
    _assert_metrics_invariant(details, bar_returns)
    bt = BacktestResult(
        symbol="T",
        timeframe="1h",
        n_bars=5,
        bar_returns=bar_returns,
        posn=[Direction.NEUTRAL] * 4,
        trades=[details[0].trade],
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    assert sum(t.net_log_return for t in bt.trades) == pytest.approx(
        sum(bt.bar_returns) + bt.eod_return, abs=1e-9
    )


def test_same_bar_stop_beats_partial():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 111, 89, 90),  # high 1R and low through stop
    ]
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=3.0,
        partial_tp=(PartialTpStep(1.0, 0.5),),
    )
    assert details[0].exit_reason == "stop"
    assert details[0].partial_exits == ()
    assert details[0].trade.exit_price == pytest.approx(90.0)
    _assert_metrics_invariant(details, bar_returns)


def test_same_bar_partial_before_target():
    """High reaches 1R and 3R: partial fills first, remainder at target."""
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 121, 99, 120),  # touches 110 and 120
    ]
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,  # target at 120 = 2R
        partial_tp=(PartialTpStep(1.0, 0.5),),
    )
    d = details[0]
    assert len(d.partial_exits) == 1
    assert d.partial_exits[0].price == pytest.approx(110.0)
    assert d.exit_reason == "target"
    assert d.trade.exit_price == pytest.approx(115.0)
    _assert_metrics_invariant(details, bar_returns)


def test_no_partial_tp_matches_full_exit_path():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 105, 99, 104),
        _c(3, 104, 121, 103, 120),
    ]
    kwargs = dict(
        candles=candles,
        atr_states=_atr(4, 10.0),
        signals=[(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    d0, _, br0, _, _ = simulate_ruleset_trades(**kwargs)
    d1, _, br1, _, _ = simulate_ruleset_trades(**kwargs, partial_tp=())
    assert d0[0].trade == d1[0].trade
    assert d0[0].exit_reason == d1[0].exit_reason == "target"
    assert br0 == br1
    assert d0[0].trade.cost_log == pytest.approx(round_trip_cost_log(5.0, 3.0))
