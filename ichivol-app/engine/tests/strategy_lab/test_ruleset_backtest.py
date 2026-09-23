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


def test_parse_exit_max_hold_and_conditions():
    rs = parse_ruleset(
        {
            "id": "IV_EXIT",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.2},
            "stop_atr": 1.0,
            "target_atr": 3.0,
            "exit": {
                "max_hold_bars": 5,
                "conditions": {"any": {"tk_cross_bearish": True}},
            },
        }
    )
    assert rs.exit.max_hold_bars == 5
    assert rs.exit.condition_group is not None
    assert "tk_cross_bearish" in rs.exit.condition_group.any_of
    again = parse_ruleset(rs.to_dict())
    assert again.exit.max_hold_bars == 5
    assert again.to_dict()["exit"]["max_hold_bars"] == 5


def test_reject_exit_stop_atr_dual_source():
    with pytest.raises(ValueError, match="must not contain stop_atr"):
        parse_ruleset(
            {
                "id": "BAD",
                "direction": "LONG",
                "conditions": {"rvol_min": 1.0},
                "exit": {"stop_atr": 1.5},
            }
        )


def test_max_hold_from_ruleset_exit():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 101, 99, 100),
        _c(2, 100, 101, 99, 100),
        _c(3, 100, 101, 99, 100),
        _c(4, 100, 101, 99, 100),
        _c(5, 100, 101, 99, 100),
    ]
    rs = parse_ruleset(
        {
            "id": "HOLD",
            "direction": "LONG",
            "conditions": {"rvol_min": 0.0},  # will not fire — force signals manually
            "stop_atr": 10.0,
            "target_atr": 10.0,
            "exit": {"max_hold_bars": 2},
        }
    )
    # Wide ATR levels so max_hold wins; use simulate with hold from resolve path
    details, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(6, 1.0),
        [(0, Direction.LONG)],
        stop_atr=10.0,
        target_atr=10.0,
        commission_bps=0,
        slippage_bps=0,
        max_hold_bars=rs.exit.max_hold_bars,
    )
    assert details[0].exit_reason == "max_hold"
    assert details[0].exit_index == 2  # entry=1, hold 2 bars → exit at 1+2-1=2


def test_signal_exit_at_close_when_condition_hits():
    from app.strategy_lab.features import FeatureBar

    def bar(i: int, *, tk_cross_bearish: bool = False) -> FeatureBar:
        return FeatureBar(
            index=i,
            time=i,
            price_above_kumo=False,
            price_below_kumo=False,
            tenkan_above_kijun=False,
            tenkan_below_kijun=False,
            tk_cross_bullish=False,
            tk_cross_bearish=tk_cross_bearish,
            tk_cross_age_bullish=None,
            tk_cross_age_bearish=None,
            kumo_breakout_bullish=False,
            kumo_breakout_bearish=False,
            rvol=1.0,
            bos_bullish=False,
            bos_bearish=False,
            structure_bias_bullish=False,
            structure_bias_bearish=False,
            atr=1.0,
            atr_percentile=0.5,
            atr_expansion=False,
            cmf=None,
            rsi=None,
            kijun_slope_state="FLAT",
            kijun_slope_atr_normalized=None,
            price_kijun_distance_atr=None,
            kijun_break_bullish=False,
            kijun_break_bearish=False,
            kijun_retest_bullish=False,
            kijun_retest_bearish=False,
            kijun_bounce_bullish=False,
            kijun_bounce_bearish=False,
            kumo_orientation="BULLISH",
            kumo_twist=False,
            bars_since_kumo_twist=None,
            kumo_thickness_atr=None,
            kumo_thickness_pct=None,
        )

    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 101, 99, 100.5),
        _c(2, 100.5, 101, 99.5, 100.2),
        _c(3, 100.2, 101, 99, 100.8),
    ]
    features = [bar(0), bar(1), bar(2, tk_cross_bearish=True), bar(3)]
    rs = parse_ruleset(
        {
            "id": "SIG_EXIT",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
            "stop_atr": 10.0,
            "target_atr": 10.0,
            "exit": {"conditions": {"tk_cross_bearish": True}},
        }
    )
    details, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 1.0),
        [(0, Direction.LONG)],
        stop_atr=10.0,
        target_atr=10.0,
        commission_bps=0,
        slippage_bps=0,
        exit_group=rs.exit.condition_group,
        feature_bars=features,
    )
    assert details[0].exit_reason == "signal"
    assert details[0].exit_index == 2
    assert details[0].trade.exit_price == 100.2


def test_stop_beats_signal_same_bar():
    from app.strategy_lab.features import FeatureBar

    def bar(i: int, *, tk_cross_bearish: bool = False) -> FeatureBar:
        return FeatureBar(
            index=i,
            time=i,
            price_above_kumo=False,
            price_below_kumo=False,
            tenkan_above_kijun=False,
            tenkan_below_kijun=False,
            tk_cross_bullish=False,
            tk_cross_bearish=tk_cross_bearish,
            tk_cross_age_bullish=None,
            tk_cross_age_bearish=None,
            kumo_breakout_bullish=False,
            kumo_breakout_bearish=False,
            rvol=1.0,
            bos_bullish=False,
            bos_bearish=False,
            structure_bias_bullish=False,
            structure_bias_bearish=False,
            atr=10.0,
            atr_percentile=0.5,
            atr_expansion=False,
            cmf=None,
            rsi=None,
            kijun_slope_state="FLAT",
            kijun_slope_atr_normalized=None,
            price_kijun_distance_atr=None,
            kijun_break_bullish=False,
            kijun_break_bearish=False,
            kijun_retest_bullish=False,
            kijun_retest_bearish=False,
            kijun_bounce_bullish=False,
            kijun_bounce_bearish=False,
            kumo_orientation="BULLISH",
            kumo_twist=False,
            bars_since_kumo_twist=None,
            kumo_thickness_atr=None,
            kumo_thickness_pct=None,
        )

    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 120, 90, 95),  # stop 90 and signal both true
    ]
    features = [bar(0), bar(1, tk_cross_bearish=True)]
    rs = parse_ruleset(
        {
            "id": "PRIO",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
            "stop_atr": 1.0,
            "target_atr": 2.0,
            "exit": {"conditions": {"tk_cross_bearish": True}},
        }
    )
    details, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(2, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
        exit_group=rs.exit.condition_group,
        feature_bars=features,
    )
    assert details[0].exit_reason == "stop"
    assert details[0].trade.exit_price == 90.0


def test_apply_params_preserves_exit():
    from app.strategy_lab.optimization import apply_params

    base = parse_ruleset(
        {
            "id": "OPT_EXIT",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.1},
            "stop_atr": 1.0,
            "target_atr": 2.0,
            "exit": {
                "max_hold_bars": 10,
                "conditions": {"bos_bearish": True},
            },
        }
    )
    rs = apply_params(base, {"rvol_min": 2.0})
    assert rs.exit.max_hold_bars == 10
    assert rs.exit.condition_group is not None
    assert rs.exit.condition_group.all_of["bos_bearish"] is True
    assert rs.conditions["rvol_min"] == 2.0
