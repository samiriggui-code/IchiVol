"""Unit tests for Strategy Lab Phase 1 — Event Study."""

from __future__ import annotations

import pytest

from app.agents.types import Direction
from app.indicators.atr import AtrParams, AtrState, VolatilityRegime, compute_atr
from app.indicators.ichimoku import Candle
from app.strategy_lab.event_study import (
    extract_entry_signals,
    observe_event,
    study_positions,
)


def _candle(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=1.0)


def _atr_fixed(n: int, atr: float = 10.0) -> list[AtrState]:
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


def test_extract_entry_signals_on_transitions_only():
    desired = [
        Direction.NEUTRAL,
        Direction.LONG,
        Direction.LONG,
        Direction.NEUTRAL,
        Direction.SHORT,
        Direction.SHORT,
        Direction.LONG,
    ]
    assert extract_entry_signals(desired) == [
        (1, Direction.LONG),
        (4, Direction.SHORT),
        (6, Direction.LONG),
    ]


def test_long_forward_returns_and_mfe_mae_atr():
    candles = [
        _candle(0, 100, 100, 100, 100),
        _candle(1, 100, 115, 95, 110),
        _candle(2, 110, 125, 90, 120),
        _candle(3, 120, 130, 100, 105),
        _candle(4, 105, 108, 102, 106),
    ]
    atr = 10.0
    obs = observe_event(candles, 0, Direction.LONG, atr, horizons=(1, 3), r_multiple=1.0)
    assert obs is not None
    assert obs.entry_price == 100.0
    assert obs.returns_atr[1] == pytest.approx(1.0)
    assert obs.returns_atr[3] == pytest.approx(0.5)
    assert obs.mfe_atr == pytest.approx(3.0)
    assert obs.mae_atr == pytest.approx(1.0)


def test_hit_plus_r_before_minus_r_long():
    candles = [
        _candle(0, 100, 100, 100, 100),
        _candle(1, 100, 108, 96, 105),
        _candle(2, 105, 112, 104, 111),
    ]
    obs = observe_event(candles, 0, Direction.LONG, 10.0, horizons=(2,), r_multiple=1.0)
    assert obs is not None
    assert obs.hit_plus_r_before_minus_r is True


def test_hit_minus_r_first_when_both_in_same_bar():
    candles = [
        _candle(0, 100, 100, 100, 100),
        _candle(1, 100, 110, 90, 100),
    ]
    obs = observe_event(candles, 0, Direction.LONG, 10.0, horizons=(1,), r_multiple=1.0)
    assert obs is not None
    assert obs.hit_plus_r_before_minus_r is False


def test_short_signed_returns():
    candles = [
        _candle(0, 100, 100, 100, 100),
        _candle(1, 100, 105, 90, 92),
    ]
    obs = observe_event(candles, 0, Direction.SHORT, 10.0, horizons=(1,))
    assert obs is not None
    assert obs.returns_atr[1] == pytest.approx(0.8)
    assert obs.mfe_atr == pytest.approx(1.0)
    assert obs.mae_atr == pytest.approx(0.5)


def test_study_positions_aggregates():
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 102, 99, 101),
        _candle(2, 101, 112, 100, 110),
        _candle(3, 110, 115, 108, 114),
        _candle(4, 114, 120, 110, 118),
        _candle(5, 118, 122, 116, 120),
        _candle(6, 120, 125, 118, 124),
        _candle(7, 124, 126, 120, 125),
        _candle(8, 125, 128, 122, 127),
        _candle(9, 127, 130, 125, 129),
        _candle(10, 129, 132, 126, 130),
        _candle(11, 130, 133, 128, 131),
    ]
    desired = [Direction.NEUTRAL, Direction.LONG] + [Direction.LONG] * (len(candles) - 2)
    atr_states = _atr_fixed(len(candles), atr=10.0)
    result = study_positions(
        candles,
        desired,
        atr_states,
        horizons=(1, 3, 5),
        symbol="TEST",
        timeframe="1h",
        variant="MANUAL",
    )
    assert result.n_events == 1
    assert result.horizon_stats[0].n == 1
    assert result.horizon_stats[0].mean_atr is not None
    assert result.mean_mfe_atr is not None
    assert result.mean_mae_atr is not None


def test_insufficient_forward_bars_yields_none_returns():
    candles = [
        _candle(0, 100, 100, 100, 100),
        _candle(1, 100, 101, 99, 100),
    ]
    obs = observe_event(candles, 0, Direction.LONG, 10.0, horizons=(1, 5))
    assert obs is not None
    assert obs.returns_atr[1] is not None
    assert obs.returns_atr[5] is None


def test_compute_atr_compatible_with_study():
    candles = [_candle(i, 100 + i, 102 + i, 98 + i, 101 + i) for i in range(40)]
    desired = [Direction.NEUTRAL] * 20 + [Direction.LONG] * 20
    atr_states = compute_atr(candles, AtrParams(period=5, regime_lookback=20))
    result = study_positions(candles, desired, atr_states, horizons=(1, 3))
    assert result.n_events == 1
    assert result.n_bars == 40
