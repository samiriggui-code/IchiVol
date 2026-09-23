"""T0-MANAGE-a — trailing / breakeven stop (Lab backtest only)."""

from __future__ import annotations

import random

import pytest

from app.agents.types import Direction
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.ruleset_backtest import simulate_ruleset_trades
from app.strategy_lab.stop_trail import (
    TrailSpec,
    atr_trail_candidate,
    breakeven_price,
    ratchet_stop,
    update_trailing_stop,
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


def test_parse_exit_trail_roundtrip():
    rs = parse_ruleset(
        {
            "id": "trail_parse",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5},
            "stop_atr": 1.0,
            "target_atr": 3.0,
            "exit": {"trail": {"breakeven_at_r": 1.0, "atr_trail_mult": 1.5}},
        }
    )
    assert rs.exit.trail is not None
    assert rs.exit.trail.breakeven_at_r == 1.0
    assert rs.exit.trail.atr_trail_mult == 1.5
    again = parse_ruleset(rs.to_dict())
    assert again.exit.trail == rs.exit.trail
    assert again.to_dict()["exit"]["trail"]["breakeven_at_r"] == 1.0


def test_parse_exit_trail_rejects_empty_and_bad():
    with pytest.raises(ValueError, match="breakeven_at_r"):
        parse_ruleset(
            {
                "id": "x",
                "direction": "LONG",
                "conditions": {"rvol_min": 1.0},
                "exit": {"trail": {}},
            }
        )
    with pytest.raises(ValueError, match="> 0"):
        parse_ruleset(
            {
                "id": "x",
                "direction": "LONG",
                "conditions": {"rvol_min": 1.0},
                "exit": {"trail": {"breakeven_at_r": 0}},
            }
        )


def test_ratchet_never_retreats_property():
    rng = random.Random(42)
    for _ in range(200):
        direction = Direction.LONG if rng.random() < 0.5 else Direction.SHORT
        entry = 100.0
        initial = entry - 10.0 if direction == Direction.LONG else entry + 10.0
        stop = initial
        trail = TrailSpec(breakeven_at_r=1.0, atr_trail_mult=1.2)
        for _bar in range(40):
            close = entry + rng.uniform(-8, 12) * (1 if direction == Direction.LONG else -1)
            high = close + rng.uniform(0, 5)
            low = close - rng.uniform(0, 5)
            atr = rng.uniform(1.0, 5.0)
            nxt = update_trailing_stop(
                direction,
                stop,
                entry=entry,
                initial_stop=initial,
                high=high,
                low=low,
                close=max(close, 1.0),
                atr=atr,
                trail=trail,
                commission_bps=5.0,
                slippage_bps=3.0,
            )
            if direction == Direction.LONG:
                assert nxt >= stop - 1e-12
            else:
                assert nxt <= stop + 1e-12
            stop = nxt


def test_breakeven_triggers_exactly_at_r_not_before():
    """Initial stop 90 (risk=10). breakeven_at_r=1 → need high >= 110."""
    # signal @0, entry @1 open 100, stop 90, target far
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 105, 99, 104),  # MFE 5 < 1R — no BE yet
        _c(2, 104, 109.9, 103, 108),  # still < 1R
        _c(3, 108, 110.0, 107, 109),  # exactly 1R on high → BE after checks
        _c(4, 109, 110, 100.16, 105),  # dips to BE zone (~100.16 with fees)
        _c(5, 105, 106, 104, 105),
    ]
    trail = TrailSpec(breakeven_at_r=1.0)
    be = breakeven_price(Direction.LONG, 100.0, commission_bps=5.0, slippage_bps=3.0)
    # With 5+3 bps RT: 100 * (1 + 0.0016) = 100.16
    assert be == pytest.approx(100.16)

    details, _, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(6, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=10.0,
        commission_bps=5.0,
        slippage_bps=3.0,
        trail=trail,
    )
    assert len(details) == 1
    d = details[0]
    # After bar 3 arms BE; bar 4 low 100.16 hits BE stop
    assert d.exit_reason == "stop"
    assert d.exit_index == 4
    assert d.trade.exit_price == pytest.approx(be)


def test_breakeven_not_armed_before_r():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 105, 99, 104),
        _c(2, 104, 109, 95, 100),  # dips to 95 — still initial stop 90 if BE not armed
        _c(3, 100, 101, 99, 100),
    ]
    details, _, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=10.0,
        commission_bps=0,
        slippage_bps=0,
        trail=TrailSpec(breakeven_at_r=1.0),
        max_hold_bars=10,
    )
    assert details[0].exit_reason == "eod" or details[0].exit_index == 3
    # Never stopped at 95 — BE not armed (MFE max 9 < 10)
    assert details[0].trade.exit_price != 95.0
    assert details[0].exit_reason != "stop" or details[0].trade.exit_price == 90.0


def test_atr_trail_ratchet_tightens_then_holds():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 102, 99, 101),
        _c(2, 101, 112, 100, 110),  # close 110 → trail candidate 110-10=100 (>90)
        _c(3, 110, 111, 99.5, 105),  # low through trailed stop 100
    ]
    details, _, _, _, _ = simulate_ruleset_trades(
        candles,
        _atr(4, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=10.0,
        commission_bps=0,
        slippage_bps=0,
        trail=TrailSpec(atr_trail_mult=1.0),
    )
    assert details[0].exit_reason == "stop"
    assert details[0].exit_index == 3
    assert details[0].trade.exit_price == pytest.approx(100.0)


def test_no_trail_matches_fixed_stop_behavior():
    candles = [
        _c(0, 100, 100, 100, 100),
        _c(1, 100, 105, 95, 102),
        _c(2, 102, 121, 100, 118),
    ]
    a = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
        trail=None,
    )
    b = simulate_ruleset_trades(
        candles,
        _atr(3, 10.0),
        [(0, Direction.LONG)],
        stop_atr=1.0,
        target_atr=2.0,
        commission_bps=0,
        slippage_bps=0,
        trail=TrailSpec(),  # empty
    )
    assert a[0][0].exit_reason == b[0][0].exit_reason == "target"
    assert a[0][0].trade.exit_price == b[0][0].trade.exit_price


def test_ratchet_helper_unit():
    assert ratchet_stop(Direction.LONG, 90.0, 95.0) == 95.0
    assert ratchet_stop(Direction.LONG, 95.0, 92.0) == 95.0
    assert ratchet_stop(Direction.SHORT, 110.0, 105.0) == 105.0
    assert ratchet_stop(Direction.SHORT, 105.0, 108.0) == 105.0
    assert atr_trail_candidate(Direction.LONG, 110.0, 10.0, 1.0) == 100.0
