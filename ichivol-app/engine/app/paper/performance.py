"""Paper trading performance -- CDC V2 "Performance / calibration", built
ahead of having much data to compute it on (deliberately): the paper
portfolio (app/paper/engine.py) only started running 2026-09-16, so results
today will be thin/noisy. The code is ready now so numbers show up the
moment enough trades have actually closed, rather than building this later
under pressure to "prove something" with a sparse sample.

Trade-level metrics only (win rate, profit factor, expectancy, compounded
return) -- deliberately NOT Sharpe/Sortino/drawdown the way
app/backtest/metrics.py computes them. Those need a continuous, evenly-
spaced equity curve (bar-by-bar returns); paper trades close at irregular
real-world times, not fixed bar intervals, so forcing the same annualized-
Sharpe math here would be a fake precision this data can't support. If a
proper equity curve gets tracked later (periodic portfolio snapshots), that
would be the honest way to add Sharpe/Sortino/drawdown for paper trading --
not bolting them onto a bare list of trades.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.db.models import PaperPosition


@dataclass(frozen=True)
class PaperPerformance:
    num_closed_trades: int
    num_open_positions: int
    total_return: float | None
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_holding_hours: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None


_EMPTY = PaperPerformance(
    num_closed_trades=0, num_open_positions=0, total_return=None, win_rate=None,
    profit_factor=None, expectancy=None, avg_holding_hours=None,
    best_trade_pct=None, worst_trade_pct=None,
)


def compute_performance(positions: Sequence[PaperPosition]) -> PaperPerformance:
    closed = [p for p in positions if p.status == "CLOSED" and p.pnl_pct is not None]
    open_count = sum(1 for p in positions if p.status == "OPEN")

    if not closed:
        return _EMPTY if open_count == 0 else PaperPerformance(
            num_closed_trades=0, num_open_positions=open_count, total_return=None,
            win_rate=None, profit_factor=None, expectancy=None, avg_holding_hours=None,
            best_trade_pct=None, worst_trade_pct=None,
        )

    pnls = [p.pnl_pct for p in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    # Compounded, same convention as app/backtest/metrics.py: each trade
    # multiplies the running equity by (1 + pnl_pct), not a naive sum.
    total_return = math.prod(1 + p for p in pnls) - 1

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (math.inf if gross_profit > 0 else None)
    )

    holding_hours = [
        (p.exit_time - p.entry_time).total_seconds() / 3600.0
        for p in closed
        if p.exit_time is not None
    ]

    return PaperPerformance(
        num_closed_trades=len(closed),
        num_open_positions=open_count,
        total_return=total_return,
        win_rate=len(wins) / len(closed),
        profit_factor=profit_factor,
        expectancy=statistics.mean(pnls),
        avg_holding_hours=statistics.mean(holding_hours) if holding_hours else None,
        best_trade_pct=max(pnls),
        worst_trade_pct=min(pnls),
    )
