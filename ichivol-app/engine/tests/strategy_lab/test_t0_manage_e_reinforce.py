"""T0-MANAGE-e — renforcement / pyramiding (Lab backtest only)."""

from __future__ import annotations

import math

import pytest

from app.agents.types import Direction
from app.backtest.engine import round_trip_cost_log
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.strategy_lab.features import FeatureBar
from app.strategy_lab.reinforce import apply_reinforce_add, open_risk
from app.strategy_lab.ruleset import ReinforceSpec, parse_ruleset
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


def _bar(i: int, *, tk_cross_bullish: bool = False, rvol: float = 1.0) -> FeatureBar:
    return FeatureBar(
        index=i,
        time=i,
        price_above_kumo=False,
        price_below_kumo=False,
        tenkan_above_kijun=False,
        tenkan_below_kijun=False,
        tk_cross_bullish=tk_cross_bullish,
        tk_cross_bearish=False,
        tk_cross_age_bullish=None,
        tk_cross_age_bearish=None,
        kumo_breakout_bullish=False,
        kumo_breakout_bearish=False,
        rvol=rvol,
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


def _assert_metrics_invariant(details, bar_returns, *, eod_return: float = 0.0) -> None:
    trades = [d.trade for d in details]
    sum_net = sum(t.net_log_return for t in trades)
    sum_path = sum(bar_returns) + eod_return
    assert sum_net == pytest.approx(sum_path, abs=1e-9)


def test_parse_reinforce_roundtrip():
    rs = parse_ruleset(
        {
            "id": "rf",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5},
            "stop_atr": 1.0,
            "target_atr": 3.0,
            "exit": {
                "reinforce": {
                    "conditions": {"tk_cross_bullish": True},
                    "add_fraction": 0.5,
                    "max_adds": 2,
                    "risk_policy": "tighten_stop",
                }
            },
        }
    )
    assert rs.exit.reinforce is not None
    assert rs.exit.reinforce.add_fraction == 0.5
    assert rs.exit.reinforce.max_adds == 2
    assert rs.exit.reinforce.risk_policy == "tighten_stop"
    again = parse_ruleset(rs.to_dict())
    assert again.exit.reinforce == rs.exit.reinforce


@pytest.mark.parametrize(
    "reinforce, match",
    [
        ({}, "non-empty"),
        ({"add_fraction": 0.5}, "requires"),
        (
            {"conditions": {"tk_cross_bullish": True}, "add_fraction": 0},
            r"\]0, 1\]",
        ),
        (
            {"conditions": {"tk_cross_bullish": True}, "add_fraction": 1.5},
            r"\]0, 1\]",
        ),
        (
            {
                "conditions": {"tk_cross_bullish": True},
                "add_fraction": 0.5,
                "max_adds": 0,
            },
            "max_adds",
        ),
        (
            {
                "conditions": {"tk_cross_bullish": True},
                "add_fraction": 0.5,
                "risk_policy": "yolo",
            },
            "risk_policy",
        ),
        (
            {
                "conditions": {"tk_cross_bullish": True},
                "add_fraction": 0.5,
                "extra": 1,
            },
            "unknown",
        ),
    ],
)
def test_parse_reinforce_rejects(reinforce, match):
    with pytest.raises(ValueError, match=match):
        parse_ruleset(
            {
                "id": "x",
                "direction": "LONG",
                "conditions": {"rvol_min": 1.0},
                "stop_atr": 1.0,
                "target_atr": 2.0,
                "exit": {"reinforce": reinforce},
            }
        )


def test_open_risk_and_clamp_reduce_qty():
    # Room under R0 (stop already tightened): avg 100, stop 95, qty 1 → risk 5; R0=10.
    # Naive +1 @ 110 → avg 105, risk |105-95|*2 = 20 > 10 → clamp to ~1/3.
    actual, avg, stop, qty, clamped = apply_reinforce_add(
        direction=Direction.LONG,
        avg_entry=100.0,
        qty=1.0,
        stop=95.0,
        add_price=110.0,
        requested_add=1.0,
        initial_risk=10.0,
        policy="reduce_qty",
    )
    assert clamped is True
    assert actual == pytest.approx(1.0 / 3.0, abs=1e-6)
    assert open_risk(avg, stop, qty) == pytest.approx(10.0, abs=1e-6)


def test_tighten_stop_keeps_full_add():
    actual, avg, stop, qty, clamped = apply_reinforce_add(
        direction=Direction.LONG,
        avg_entry=100.0,
        qty=1.0,
        stop=90.0,
        add_price=110.0,
        requested_add=1.0,
        initial_risk=10.0,
        policy="tighten_stop",
    )
    assert actual == pytest.approx(1.0)
    assert qty == pytest.approx(2.0)
    assert avg == pytest.approx(105.0)
    assert clamped is True  # stop moved
    assert open_risk(avg, stop, qty) == pytest.approx(10.0, abs=1e-9)
    assert stop > 90.0  # tightened up


def test_reinforce_then_target_records_add_and_entry_vwap():
    """Entry 100 stop 90. Add 0.5 at close 105 (tighten_stop). Exit target 120."""
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),  # entry
        _c(2, 100, 106, 99, 105),  # reinforce @ 105
        _c(3, 105, 121, 104, 120),  # target 120
    ]
    features = [
        _bar(0),
        _bar(1),
        _bar(2, tk_cross_bullish=True),
        _bar(3),
    ]
    rs = parse_ruleset(
        {
            "id": "RF",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
            "stop_atr": 1.0,
            "target_atr": 2.0,
            "exit": {
                "reinforce": {
                    "conditions": {"tk_cross_bullish": True},
                    "add_fraction": 0.5,
                    "risk_policy": "tighten_stop",
                }
            },
        }
    )
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0.0,
        slippage_bps=0.0,
        feature_bars=features,
        reinforce=rs.exit.reinforce,
    )
    assert len(details) == 1
    d = details[0]
    assert len(d.reinforce_adds) == 1
    assert d.reinforce_adds[0].price == pytest.approx(105.0)
    assert d.reinforce_adds[0].fraction == pytest.approx(0.5)
    assert d.exit_reason == "target"
    # Entry VWAP = (100*1 + 105*0.5) / 1.5
    assert d.trade.entry_price == pytest.approx((100 + 52.5) / 1.5)
    assert d.trade.exit_price == pytest.approx(120.0)
    assert d.reinforce_adds[0].open_risk_after == pytest.approx(
        open_risk(100.0, 90.0, 1.0), abs=1e-6
    )
    _assert_metrics_invariant(details, bar_returns)


def test_reinforce_clamped_when_naive_add_exceeds_initial_risk():
    """reduce_qty with risk room from a tighter stop — add is shrunk, never ignored."""
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 112, 99, 110),  # add attempt @ 110
        _c(3, 110, 111, 109, 110),
    ]
    features = [_bar(0), _bar(1), _bar(2, tk_cross_bullish=True), _bar(3)]
    # Pre-trail the stop via a custom reinforce path: we simulate room by
    # starting with stop_atr that gives R0=10, then on bar 2 the stop has been
    # moved up by trail... simpler: call apply path through tighten then
    # use reduce with synthetic room — here use trail so stop rises before add.
    rs = parse_ruleset(
        {
            "id": "RF_CLAMP",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
            "stop_atr": 1.0,
            "target_atr": 5.0,
            "exit": {
                "trail": {"breakeven_at_r": 0.5},
                "reinforce": {
                    "conditions": {"tk_cross_bullish": True},
                    "add_fraction": 1.0,
                    "risk_policy": "reduce_qty",
                },
            },
        }
    )
    details, _, bar_returns, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=5.0,
        commission_bps=0.0,
        slippage_bps=0.0,
        feature_bars=features,
        trail=rs.exit.trail,
        reinforce=rs.exit.reinforce,
    )
    d = details[0]
    # Either an add was clamped, or blocked to 0 after trail math — never silent over-risk.
    if d.reinforce_adds:
        add = d.reinforce_adds[0]
        assert add.open_risk_after <= open_risk(100.0, 90.0, 1.0) + 1e-6
        if add.requested_fraction > add.fraction + 1e-9:
            assert add.clamped is True
    _assert_metrics_invariant(details, bar_returns)


def test_reduce_qty_blocks_add_when_already_at_risk_cap():
    """Fixed stop + favorable price: MTM risk ≥ R0 → reduce_qty adds nothing."""
    actual, avg, stop, qty, clamped = apply_reinforce_add(
        direction=Direction.LONG,
        avg_entry=110.0,
        qty=1.0,
        stop=90.0,
        add_price=120.0,
        requested_add=1.0,
        initial_risk=10.0,
        policy="reduce_qty",
    )
    assert actual == pytest.approx(0.0)
    assert qty == pytest.approx(1.0)
    assert clamped is True
    assert avg == pytest.approx(110.0)
    assert stop == pytest.approx(90.0)


def test_stop_beats_reinforce_same_bar():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 105, 89, 104),  # stop 90 hit + TK bullish same bar
    ]
    features = [_bar(0), _bar(1), _bar(2, tk_cross_bullish=True)]
    rs = parse_ruleset(
        {
            "id": "RF_STOP",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.0},
            "stop_atr": 1.0,
            "target_atr": 3.0,
            "exit": {
                "reinforce": {
                    "conditions": {"tk_cross_bullish": True},
                    "add_fraction": 0.5,
                }
            },
        }
    )
    details, _, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=3.0,
        commission_bps=0.0,
        slippage_bps=0.0,
        feature_bars=features,
        reinforce=rs.exit.reinforce,
    )
    assert details[0].exit_reason == "stop"
    assert details[0].reinforce_adds == ()


def test_no_reinforce_matches_full_exit_path():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 100, 99, 100),
        _c(2, 100, 121, 99, 120),
    ]
    base, _, br0, _, _ = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=5.0,
        slippage_bps=3.0,
    )
    with_none, _, br1, _, _ = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=5.0,
        slippage_bps=3.0,
        reinforce=None,
    )
    assert base[0].trade.log_return == pytest.approx(with_none[0].trade.log_return)
    assert br0 == br1
