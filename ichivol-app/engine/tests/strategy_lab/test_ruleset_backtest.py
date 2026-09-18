"""Tests — Strategy Lab Phase 3 ruleset backtester."""

from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.ruleset_backtest import (
    run_ruleset_backtest_on_candles,
    simulate_ruleset_trades,
)


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


def test_long_hits_target_before_stop():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 105, 95, 102),
        _c(2, 102, 121, 100, 118),
        _c(3, 118, 119, 117, 118),
    ]
    details, _posn, _rets, skipped = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
    )
    assert skipped == 0
    assert len(details) == 1
    d = details[0]
    assert d.exit_reason == "target"
    assert d.trade.exit_price == 120.0
    assert d.trade.log_return == pytest.approx(math.log(120 / 100))


def test_long_stop_wins_when_both_touched():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 120, 90, 100),
    ]
    details, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(2, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
    )
    assert details[0].exit_reason == "stop"
    assert details[0].trade.exit_price == 90.0


def test_skips_signal_while_in_position():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 101, 99, 100),
        _c(2, 100, 101, 99, 100),
        _c(3, 100, 101, 99, 100),
        _c(4, 100, 130, 99, 120),
    ]
    details, _, _, skipped = simulate_ruleset_trades(
        candles,
        _atr(5, 10.0),
        [(0, Direction.LONG), (1, Direction.LONG), (2, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
    )
    assert len(details) == 1
    assert skipped == 2


def test_short_hits_target():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 105, 80, 85),
    ]
    details, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(2, 10.0),
        [(0, Direction.SHORT)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
    )
    assert details[0].exit_reason == "target"
    assert details[0].trade.exit_price == 80.0
    assert details[0].trade.log_return == pytest.approx(math.log(100 / 80))


def test_run_ruleset_backtest_metrics_shape():
    candles = []
    for i in range(120):
        base = 100 + i * 0.4
        candles.append(
            _c(i, base, base + 3, base - 2, base + 1, 80 + (200 if i % 19 == 0 else 0))
        )
    rs = parse_ruleset(
        {
            "id": "IV_RVOL_SPIKE",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.2},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    result = run_ruleset_backtest_on_candles(
        candles, rs, symbol="TEST", timeframe="1h", commission_bps=0, slippage_bps=0
    )
    assert result.metrics.num_trades == len(result.details)
    assert result.backtest.n_bars == 120
    assert result.n_signals >= result.metrics.num_trades
