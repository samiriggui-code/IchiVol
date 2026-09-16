"""Anti-lookahead proof for the backtest engine's own execution loop --
independent from whether the *signal* feeding it is causal (that's proven
separately in tests/indicators and tests/agents). Same truncation method as
elsewhere: bar_returns/posn computed over a candle prefix must match the
same-index values computed over the full history, since the engine must
never use candles or desired-positions beyond the bar it's currently
settling.
"""

from __future__ import annotations

from app.agents import ichimoku_agent
from app.backtest.engine import run_backtest
from app.indicators.ichimoku import IchimokuParams
from tests.indicators.test_ichimoku_lookahead import _make_candles

PARAMS = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
N = 220
TRUNCATION_POINTS = [30, 60, 100, 150, N]


def test_backtest_bar_returns_and_posn_are_stable_under_truncation():
    candles = _make_candles(N, seed=99)
    full_desired = [o.direction for o in ichimoku_agent.analyze(candles, PARAMS)]
    full_result = run_backtest(candles, full_desired, symbol="TEST", timeframe="1h")

    for t in TRUNCATION_POINTS:
        truncated_candles = candles[:t]
        truncated_desired = [
            o.direction for o in ichimoku_agent.analyze(truncated_candles, PARAMS)
        ]
        truncated_result = run_backtest(
            truncated_candles, truncated_desired, symbol="TEST", timeframe="1h"
        )

        shared_len = len(truncated_result.bar_returns)
        assert shared_len == t - 1

        assert truncated_result.bar_returns == full_result.bar_returns[:shared_len], (
            f"bar_returns diverged at truncation T={t}: the engine must be reading "
            f"data beyond what's available at that point."
        )
        assert truncated_result.posn == full_result.posn[:shared_len], (
            f"posn diverged at truncation T={t}"
        )
