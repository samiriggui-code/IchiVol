"""T0-METRICS-2 — engine fee accounting: flip, EOD exit, close alignment."""

from __future__ import annotations

import math
import random

import pytest

from app.agents.types import Direction
from app.backtest.engine import one_way_cost_log, run_backtest
from app.indicators.ichimoku import Candle
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _flat(opens: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=o, low=o, close=o, volume=1.0) for i, o in enumerate(opens)
    ]


def _assert_invariant(result, *, abs_tol: float = 1e-9) -> None:
    sum_net = sum(t.net_log_return for t in result.trades)
    sum_bars = sum(result.bar_returns)
    assert sum_net == pytest.approx(sum_bars, abs=abs_tol)


def test_engine_invariant_mid_close():
    opens = [100, 101, 102, 103, 104, 105]
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    r = run_backtest(_flat(opens), desired, commission_bps=5.0, slippage_bps=3.0)
    assert len(r.trades) == 1
    ow = one_way_cost_log(5.0, 3.0)
    assert r.trades[0].cost_log == pytest.approx(2 * ow)
    _assert_invariant(r)


def test_engine_invariant_eod_close_ne_open():
    """EOD: trade @ last.close; bar_returns includes open→close + exit fee."""
    candles = [
        Candle(time=i, open=o, high=o + 1, low=o - 1, close=c, volume=1.0)
        for i, (o, c) in enumerate(
            [(100.0, 100.0), (101.0, 101.0), (102.0, 102.0), (103.0, 103.0), (104.0, 110.0)]
        )
    ]
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
        Direction.LONG,
    ]
    r = run_backtest(candles, desired, commission_bps=5.0, slippage_bps=3.0)
    assert len(r.trades) == 1
    ow = one_way_cost_log(5.0, 3.0)
    assert r.trades[0].exit_price == 110.0
    assert r.trades[0].cost_log == pytest.approx(2 * ow)
    assert r.trades[0].log_return == pytest.approx(math.log(110 / 102))
    _assert_invariant(r)


def test_engine_invariant_flip_long_to_short():
    opens = [100, 100, 110, 90, 90, 95]
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.SHORT,
        Direction.SHORT,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    r = run_backtest(_flat(opens), desired, commission_bps=5.0, slippage_bps=3.0)
    assert len(r.trades) == 2
    ow = one_way_cost_log(5.0, 3.0)
    # Each trade: full round-trip (entry + exit)
    assert r.trades[0].cost_log == pytest.approx(2 * ow)
    assert r.trades[1].cost_log == pytest.approx(2 * ow)
    _assert_invariant(r)


def test_engine_invariant_flip_short_to_long():
    opens = [100, 100, 90, 110, 110, 105]
    desired = [
        Direction.NEUTRAL,
        Direction.SHORT,
        Direction.LONG,
        Direction.LONG,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    r = run_backtest(_flat(opens), desired, commission_bps=5.0, slippage_bps=3.0)
    assert len(r.trades) == 2
    _assert_invariant(r)


def test_engine_invariant_multiple_flips_in_a_row():
    opens = [100, 101, 102, 103, 104, 105, 106, 107]
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.SHORT,
        Direction.LONG,
        Direction.SHORT,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
        Direction.NEUTRAL,
    ]
    r = run_backtest(_flat(opens), desired, commission_bps=5.0, slippage_bps=3.0)
    assert len(r.trades) >= 3
    _assert_invariant(r)


def test_engine_invariant_property_200_random_sequences():
    """200 random NEUTRAL/LONG/SHORT desired series → invariant always holds."""
    rng = random.Random(20260923)
    dirs = [Direction.NEUTRAL, Direction.LONG, Direction.SHORT]
    for i in range(200):
        n = rng.randint(30, 120)
        candles = _make_candles(n, seed=1000 + i)
        # Mutate closes so open≠close often (EOD path).
        mutated = [
            Candle(
                time=c.time,
                open=c.open,
                high=max(c.high, c.close * 1.01),
                low=min(c.low, c.close * 0.99),
                close=c.close * (1.0 + rng.uniform(-0.02, 0.02)),
                volume=c.volume,
            )
            for c in candles
        ]
        desired = [rng.choice(dirs) for _ in range(n)]
        # Keep first bar neutral-ish for realism (posn[0] already forced NEUTRAL)
        desired[0] = Direction.NEUTRAL
        r = run_backtest(
            mutated, desired, commission_bps=5.0, slippage_bps=3.0
        )
        _assert_invariant(r)
