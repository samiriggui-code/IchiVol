"""Ruleset backtester — Phase 3 Strategy Lab (+ T3 exit conditions).

Rising-edge ruleset signals → enter at next open → exit at ATR stop/target
(or optional exit.conditions signal, end of series / max hold). One position
at a time. Conservative intra-bar priority:
``stop`` > ``target`` > ``signal`` > ``max_hold`` / ``eod``.

Produces a standard BacktestResult so compute_metrics() stays unchanged.
Exit fills: stop/target at price levels; signal exit at bar close.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.agents.types import Direction
from app.backtest.engine import BacktestResult, Trade, round_trip_cost_log
from app.backtest.metrics import Metrics, compute_metrics
from app.indicators.atr import AtrState
from app.indicators.ichimoku import Candle
from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.evaluator import bar_matches_group, extract_ruleset_signals
from app.strategy_lab.features import FeatureBar, FeatureSeries, build_feature_series
from app.strategy_lab.ruleset import ConditionGroup, Ruleset, parse_ruleset

_SIGN = {Direction.LONG: 1.0, Direction.SHORT: -1.0, Direction.NEUTRAL: 0.0}


@dataclass(frozen=True)
class RulesetTradeDetail:
    trade: Trade
    exit_reason: str  # stop | target | signal | eod | max_hold
    stop_price: float
    target_price: float
    atr_at_signal: float
    signal_index: int
    entry_index: int
    exit_index: int


@dataclass(frozen=True)
class RulesetBacktestResult:
    ruleset: Ruleset
    symbol: str
    timeframe: str
    backtest: BacktestResult
    metrics: Metrics
    details: list[RulesetTradeDetail]
    n_signals: int
    n_skipped_in_position: int


def _levels(
    direction: Direction,
    entry: float,
    atr: float,
    stop_atr: float,
    target_atr: float,
) -> tuple[float, float]:
    if direction == Direction.LONG:
        return entry - stop_atr * atr, entry + target_atr * atr
    return entry + stop_atr * atr, entry - target_atr * atr


def _hit_stop_or_target(
    direction: Direction,
    high: float,
    low: float,
    stop: float,
    target: float,
) -> str | None:
    if direction == Direction.LONG:
        hit_stop = low <= stop
        hit_target = high >= target
    else:
        hit_stop = high >= stop
        hit_target = low <= target
    if hit_stop:
        return "stop"
    if hit_target:
        return "target"
    return None


def _apply_hold_returns(
    bar_returns: list[float],
    candles: Sequence[Candle],
    *,
    direction: Direction,
    entry_index: int,
    entry_price: float,
    exit_index: int,
    exit_price: float,
    cost: float,
) -> None:
    """Fill bar_returns for one trade (indices 0..n-2)."""
    n = len(candles)
    sign = _SIGN[direction]
    if entry_index >= n - 1 or entry_price <= 0 or exit_price <= 0:
        return

    if exit_index == entry_index:
        bar_returns[entry_index] = sign * math.log(exit_price / entry_price) - 2 * cost
        return

    for j in range(entry_index, exit_index):
        if j >= n - 1 or candles[j].open <= 0:
            break
        if j < exit_index - 1:
            end_px = candles[j + 1].open
        else:
            end_px = candles[exit_index].open if exit_index < n else exit_price
        if end_px <= 0:
            continue
        r = sign * math.log(end_px / candles[j].open)
        if j == entry_index:
            r -= cost
        bar_returns[j] = r

    if exit_index < n - 1 and exit_index > entry_index:
        if candles[exit_index].open > 0:
            bar_returns[exit_index] = (
                sign * math.log(exit_price / candles[exit_index].open) - cost
            )
    elif exit_index == n - 1 and exit_index - 1 >= entry_index:
        j = exit_index - 1
        if candles[j].open > 0:
            r = sign * math.log(exit_price / candles[j].open) - cost
            if j == entry_index:
                r = sign * math.log(exit_price / entry_price) - 2 * cost
            bar_returns[j] = r


def simulate_ruleset_trades(
    candles: Sequence[Candle],
    atr_states: Sequence[AtrState],
    signals: Sequence[tuple[int, Direction]],
    *,
    stop_atr: float,
    target_atr: float,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
    exit_group: ConditionGroup | None = None,
    feature_bars: Sequence[FeatureBar] | None = None,
) -> tuple[list[RulesetTradeDetail], list[Direction], list[float], int]:
    n = len(candles)
    if n < 2:
        return [], [Direction.NEUTRAL] * n, [], 0

    if exit_group is not None:
        if feature_bars is None or len(feature_bars) != n:
            raise ValueError(
                "feature_bars (len == candles) required when exit_group is set"
            )

    cost = (commission_bps + slippage_bps) / 10_000
    posn = [Direction.NEUTRAL] * n
    bar_returns = [0.0] * (n - 1)
    details: list[RulesetTradeDetail] = []
    skipped = 0
    busy_until = -1

    for signal_index, direction in signals:
        if signal_index <= busy_until:
            skipped += 1
            continue

        entry_index = signal_index + 1
        if entry_index >= n:
            continue
        atr_val = atr_states[signal_index].atr
        if atr_val is None or atr_val <= 0:
            continue

        entry_price = candles[entry_index].open
        if entry_price <= 0:
            continue
        stop, target = _levels(direction, entry_price, atr_val, stop_atr, target_atr)

        hold_end = n - 1
        if max_hold_bars is not None and max_hold_bars > 0:
            hold_end = min(hold_end, entry_index + max_hold_bars - 1)

        exit_index = hold_end
        exit_price = candles[hold_end].close
        exit_reason = "eod" if hold_end == n - 1 else "max_hold"

        for j in range(entry_index, hold_end + 1):
            posn[j] = direction
            hit = _hit_stop_or_target(
                direction, candles[j].high, candles[j].low, stop, target
            )
            if hit is not None:
                exit_index = j
                exit_price = stop if hit == "stop" else target
                exit_reason = hit
                for k in range(j + 1, hold_end + 1):
                    posn[k] = Direction.NEUTRAL
                break
            if (
                exit_group is not None
                and feature_bars is not None
                and bar_matches_group(feature_bars[j], exit_group, direction)
            ):
                exit_index = j
                exit_price = candles[j].close
                exit_reason = "signal"
                for k in range(j + 1, hold_end + 1):
                    posn[k] = Direction.NEUTRAL
                break

        _apply_hold_returns(
            bar_returns,
            candles,
            direction=direction,
            entry_index=entry_index,
            entry_price=entry_price,
            exit_index=exit_index,
            exit_price=exit_price,
            cost=cost,
        )

        details.append(
            RulesetTradeDetail(
                trade=Trade(
                    entry_time=candles[entry_index].time,
                    exit_time=candles[exit_index].time,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    log_return=_SIGN[direction] * math.log(exit_price / entry_price),
                    # Exact same 2×cost deducted across bars in _apply_hold_returns.
                    cost_log=round_trip_cost_log(commission_bps, slippage_bps),
                ),
                exit_reason=exit_reason,
                stop_price=stop,
                target_price=target,
                atr_at_signal=atr_val,
                signal_index=signal_index,
                entry_index=entry_index,
                exit_index=exit_index,
            )
        )
        busy_until = exit_index

    return details, posn, bar_returns, skipped


def _resolve_max_hold(
    ruleset: Ruleset, max_hold_bars: int | None
) -> int | None:
    """Call-site override wins; else ruleset.exit.max_hold_bars."""
    if max_hold_bars is not None:
        return max_hold_bars
    return ruleset.exit.max_hold_bars


def run_ruleset_backtest_on_features(
    features: FeatureSeries,
    ruleset: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
) -> RulesetBacktestResult:
    signals = extract_ruleset_signals(features, ruleset, rising_edge=True)
    exit_group = ruleset.exit.condition_group
    details, posn, bar_returns, skipped = simulate_ruleset_trades(
        features.candles,
        features.atr,
        signals,
        stop_atr=float(ruleset.stop_atr),
        target_atr=float(ruleset.target_atr),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_hold_bars=_resolve_max_hold(ruleset, max_hold_bars),
        exit_group=exit_group,
        feature_bars=features.bars if exit_group is not None else None,
    )
    backtest = BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(features.candles),
        bar_returns=bar_returns,
        posn=posn[:-1] if len(posn) > 1 else posn,
        trades=[d.trade for d in details],
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    return RulesetBacktestResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        backtest=backtest,
        metrics=compute_metrics(backtest),
        details=details,
        n_signals=len(signals),
        n_skipped_in_position=skipped,
    )


def run_ruleset_backtest_on_candles(
    candles: Sequence[Candle],
    ruleset: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
) -> RulesetBacktestResult:
    return run_ruleset_backtest_on_features(
        build_feature_series(candles),
        ruleset,
        symbol=symbol,
        timeframe=timeframe,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_hold_bars=max_hold_bars,
    )


def run_ruleset_backtest(
    ruleset: Ruleset | dict,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    exchange: str = "binance",
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
) -> RulesetBacktestResult:
    rs = ruleset if isinstance(ruleset, Ruleset) else parse_ruleset(ruleset)
    _p, _s, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles returned for {symbol} {timeframe}")
    return run_ruleset_backtest_on_candles(
        candles,
        rs,
        symbol=symbol.upper(),
        timeframe=timeframe,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_hold_bars=max_hold_bars,
    )
