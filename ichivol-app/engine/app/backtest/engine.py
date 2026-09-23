"""Event-driven backtest engine.

Anti-lookahead by construction (mission brief §11), same execution
convention documented and admired in shikokuchuo/ichimoku's strat() (see
_research/ichimoku-reference analysis): a position decided from data known
through the close of bar i is only ever held starting at the *open* of bar
i+1, never earlier. Concretely:

    posn[i] = desired_positions[i - 1]   (posn[0] is always NEUTRAL)

So `posn[i]`, the position held over the interval [open[i], open[i+1]),
depends only on `desired_positions[i-1]`, which in turn must itself be a
causal function of candles[0..i-1] (guaranteed by the agents that produce
it -- see app/agents/*, already proven anti-lookahead-safe by truncation
tests). Combined with this engine's own one-bar delay, the realized return
at bar i can never depend on candles[j] for j > i.

This is verified directly in tests/backtest/test_engine_lookahead.py using
the same truncation method as the indicator/RVOL tests: results computed
over a candle prefix must match the same-index results computed over the
full history.

Deliberately NOT implemented: parameter optimization / grid search. Mission
brief §11 explicitly forbids optimizing parameters on the full dataset and
then testing on that same dataset -- when that's eventually added, it needs
an explicit train/test (or walk-forward) split, which does not exist here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

from app.agents.types import Direction
from app.indicators.ichimoku import Candle

_DIRECTION_SIGN = {Direction.LONG: 1.0, Direction.SHORT: -1.0, Direction.NEUTRAL: 0.0}


def one_way_cost_log(commission_bps: float, slippage_bps: float) -> float:
    """One-side fee in log space: ``(commission_bps + slippage_bps) / 10_000``."""
    return (float(commission_bps) + float(slippage_bps)) / 10_000.0


def round_trip_cost_log(commission_bps: float, slippage_bps: float) -> float:
    """Full round-trip fee in log space (entry + exit).

    Matches ``ruleset_backtest._apply_hold_returns`` (``2 * cost``) and the
    typical NEUTRAL→pos→NEUTRAL path in ``run_backtest`` (one ``one_way`` on
    open, one on close). See T0-METRICS handoff for engine flip / EOD caveats.
    """
    return 2.0 * one_way_cost_log(commission_bps, slippage_bps)


@dataclass(frozen=True)
class Trade:
    entry_time: int
    exit_time: int
    direction: Direction
    entry_price: float
    exit_price: float
    log_return: float  # gross (prices only)
    cost_log: float = 0.0  # log-space fees deducted in bar_returns for this trade

    @property
    def net_log_return(self) -> float:
        return self.log_return - self.cost_log


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    n_bars: int
    bar_returns: list[float] = field(repr=False)
    posn: list[Direction] = field(repr=False)
    trades: list[Trade] = field(repr=False)
    commission_bps: float
    slippage_bps: float


def run_backtest(
    candles: Sequence[Candle],
    desired_positions: Sequence[Direction],
    symbol: str = "",
    timeframe: str = "",
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> BacktestResult:
    """`desired_positions[i]` must be the position an agent/combiner would
    choose using only candles[0..i] (causal). This function applies the
    one-bar execution delay on top; callers must not pre-shift it
    themselves.
    """
    n = len(candles)
    if len(desired_positions) != n:
        raise ValueError("desired_positions must have exactly one entry per candle")
    if n < 2:
        return BacktestResult(symbol, timeframe, n, [], [], [], commission_bps, slippage_bps)

    posn: list[Direction] = [Direction.NEUTRAL] + list(desired_positions[:-1])
    # One-side fee charged on each position *change* (historically named
    # round_trip_cost in earlier revisions — still one-way in practice).
    one_way = one_way_cost_log(commission_bps, slippage_bps)

    bar_returns: list[float] = []
    trades: list[Trade] = []
    open_trade_direction: Direction | None = None
    open_trade_entry_time: int | None = None
    open_trade_entry_price: float | None = None
    open_cost_log = 0.0  # fees already applied in bar_returns for the open trade
    prev_posn = Direction.NEUTRAL  # posn[0] is always NEUTRAL by construction above

    for i in range(n - 1):
        market_logret = (
            math.log(candles[i + 1].open / candles[i].open) if candles[i].open > 0 else 0.0
        )
        sign = _DIRECTION_SIGN[posn[i]]
        r = sign * market_logret

        if posn[i] != prev_posn:
            r -= one_way
            closing = open_trade_direction is not None
            opening = posn[i] != Direction.NEUTRAL
            if closing:
                # Flip bar: a single one_way covers exit (+ entry of the next).
                # Attribute that bar's fee to the *closed* trade; the new trade
                # starts with open_cost_log=0 (entry fee already spent on flip).
                trades.append(
                    Trade(
                        entry_time=open_trade_entry_time,
                        exit_time=candles[i].time,
                        direction=open_trade_direction,
                        entry_price=open_trade_entry_price,
                        exit_price=candles[i].open,
                        log_return=math.log(candles[i].open / open_trade_entry_price)
                        * _DIRECTION_SIGN[open_trade_direction],
                        cost_log=open_cost_log + one_way,
                    )
                )
                open_trade_direction = None
                open_cost_log = 0.0
            if opening:
                open_trade_direction = posn[i]
                open_trade_entry_time = candles[i].time
                open_trade_entry_price = candles[i].open
                open_cost_log = 0.0 if closing else one_way

        bar_returns.append(r)
        prev_posn = posn[i]

    if open_trade_direction is not None:
        # EOD force-close: no exit fee is written into bar_returns (pre-existing).
        last = candles[-1]
        trades.append(
            Trade(
                entry_time=open_trade_entry_time,
                exit_time=last.time,
                direction=open_trade_direction,
                entry_price=open_trade_entry_price,
                exit_price=last.close,
                log_return=math.log(last.close / open_trade_entry_price)
                * _DIRECTION_SIGN[open_trade_direction],
                cost_log=open_cost_log,
            )
        )

    return BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=n,
        bar_returns=bar_returns,
        posn=posn[:-1],
        trades=trades,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


def direction_from_score(score: float | None, threshold: float = 0.0) -> Direction:
    """Small helper for building an 'Ichimoku only' desired-position series
    directly from IchimokuState.score, mirroring ichimoku_agent's own
    direction rule without needing a full StrategyAgentOutput."""
    if score is None:
        return Direction.NEUTRAL
    if score > threshold:
        return Direction.LONG
    if score < -threshold:
        return Direction.SHORT
    return Direction.NEUTRAL


ActionableDecisions = frozenset({"STRONG_BUY", "BUY", "STRONG_SELL", "SELL"})


def desired_position_from_decision(decision: str, direction: Direction) -> Direction:
    """Ichimoku+RVOL desired position: only take the trade when the combiner
    resolved to an actionable decision (RVOL confirmed enough conviction);
    WATCH/WAIT means stay flat even if Ichimoku alone would suggest a
    direction -- this is the whole point of the RVOL gate being tested."""
    return direction if decision in ActionableDecisions else Direction.NEUTRAL
