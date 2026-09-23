"""Backtest performance metrics.

Deliberately does NOT hardcode an annualization factor the way
_research/backtestbot's Sharpe calculation does (`sqrt(252)` regardless of
whether the strategy trades 4h or 1d bars, a bug flagged in that repo's
analysis) -- `PERIODS_PER_YEAR` is looked up from the actual timeframe of
the backtest.

T0-METRICS: win_rate / expectancy / profit_factor are **net of fees**
(``Trade.net_log_return``). Gross counterparts are exposed as ``*_gross``
for transparency.

T0-METRICS-2: ``total_return`` / max DD use ``sum(bar_returns) + eod_return``
(``bar_returns`` stay open→open; EOD mark-to-close lives on
``BacktestResult.eod_return``).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from app.agents.types import Direction
from app.backtest.engine import BacktestResult

PERIODS_PER_YEAR: dict[str, int] = {
    "15m": 4 * 24 * 365,
    "1h": 24 * 365,
    "4h": 6 * 365,
    "1d": 365,
}


@dataclass(frozen=True)
class Metrics:
    n_bars: int
    total_return: float
    cagr: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float
    num_trades: int
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    exposure: float
    win_rate_gross: float | None = None
    profit_factor_gross: float | None = None
    expectancy_gross: float | None = None


def _max_drawdown(bar_returns: list[float], eod_return: float = 0.0) -> float:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in bar_returns:
        equity *= math.exp(r)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    if eod_return != 0.0:
        equity *= math.exp(eod_return)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return max_dd


def _trade_stats(pnls: list[float]) -> tuple[float | None, float | None, float | None]:
    """win_rate, profit_factor, expectancy from a list of simple returns."""
    n = len(pnls)
    if n == 0:
        return None, None, None
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / n
    expectancy = statistics.mean(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        (gross_profit / gross_loss)
        if gross_loss > 0
        else (math.inf if gross_profit > 0 else None)
    )
    return win_rate, profit_factor, expectancy


def compute_metrics(result: BacktestResult) -> Metrics:
    bar_returns = result.bar_returns
    eod_return = float(result.eod_return)
    n = len(bar_returns)

    if n == 0 and eod_return == 0.0:
        return Metrics(0, 0.0, None, None, None, 0.0, 0, None, None, None, 0.0)

    total_log_return = sum(bar_returns) + eod_return
    total_return = math.exp(total_log_return) - 1

    periods_per_year = PERIODS_PER_YEAR.get(result.timeframe)
    cagr = None
    sharpe = None
    sortino = None
    # Annualized stats stay on open→open bars (eod is a single terminal mark).
    if periods_per_year is not None and n > 0:
        cagr = (1 + total_return) ** (periods_per_year / n) - 1

        mean_r = statistics.mean(bar_returns)
        if n >= 2:
            std_r = statistics.stdev(bar_returns)
            if std_r > 0:
                sharpe = (mean_r / std_r) * math.sqrt(periods_per_year)

        downside = [r for r in bar_returns if r < 0]
        if len(downside) >= 2:
            downside_std = statistics.stdev(downside)
            if downside_std > 0:
                sortino = (mean_r / downside_std) * math.sqrt(periods_per_year)
        elif len(downside) == 1 and downside[0] != 0:
            sortino = (mean_r / abs(downside[0])) * math.sqrt(periods_per_year)

    max_dd = _max_drawdown(bar_returns, eod_return=eod_return)

    trade_pnls_net = [math.exp(t.net_log_return) - 1 for t in result.trades]
    trade_pnls_gross = [math.exp(t.log_return) - 1 for t in result.trades]
    num_trades = len(trade_pnls_net)
    win_rate, profit_factor, expectancy = _trade_stats(trade_pnls_net)
    win_rate_gross, profit_factor_gross, expectancy_gross = _trade_stats(trade_pnls_gross)

    exposure = (
        sum(1 for p in result.posn if p != Direction.NEUTRAL) / n if n > 0 else 0.0
    )

    return Metrics(
        n_bars=n,
        total_return=total_return,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        num_trades=num_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        exposure=exposure,
        win_rate_gross=win_rate_gross,
        profit_factor_gross=profit_factor_gross,
        expectancy_gross=expectancy_gross,
    )
