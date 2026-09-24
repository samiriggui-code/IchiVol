"""T11b — observe_lab_context cache + TD credit helpers."""

from __future__ import annotations

from app.market_data import twelve_data
from app.strategy_lab.lab_context import (
    clear_lab_context_cache,
    lab_context_cache_stats,
    observe_lab_context,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_lab_context_cache_hit_same_bar():
    clear_lab_context_cache()
    candles = _make_candles(200, seed=3)
    a = observe_lab_context(candles)
    b = observe_lab_context(candles)
    assert a is not None and b is not None
    assert a.to_dict() == b.to_dict()
    stats = lab_context_cache_stats()
    assert stats["misses"] == 1
    assert stats["hits"] >= 1


def test_lab_context_cache_miss_on_new_last_bar():
    clear_lab_context_cache()
    c1 = _make_candles(200, seed=5)
    c2 = list(c1) + [
        type(c1[0])(
            time=c1[-1].time + 3600,
            open=c1[-1].close,
            high=c1[-1].close + 1,
            low=c1[-1].close - 1,
            close=c1[-1].close + 0.5,
            volume=1.0,
        )
    ]
    observe_lab_context(c1)
    observe_lab_context(c2)
    stats = lab_context_cache_stats()
    assert stats["misses"] == 2


def test_twelve_data_credit_helpers_do_not_break_limiter():
    twelve_data.reset_credit_window()
    twelve_data.clear_ohlcv_cache()
    assert twelve_data.credits_used_in_window() == 0
    assert twelve_data._try_acquire_credit_slot() is True
    assert twelve_data.credits_used_in_window() == 1
    twelve_data.reset_credit_window()
