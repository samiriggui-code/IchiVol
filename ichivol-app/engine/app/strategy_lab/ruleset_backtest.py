"""Ruleset backtester — Phase 3 Strategy Lab (+ T3 exit conditions).

Rising-edge ruleset signals → enter at next open → exit at ATR stop/target
(or optional exit.conditions signal, end of series / max hold). One position
at a time. Conservative intra-bar priority:
``stop`` > ``partials`` (ascending R) > ``target`` > ``signal`` > ``reinforce`` >
``max_hold`` / ``eod`` (trail update after exit checks).

Produces a standard BacktestResult so compute_metrics() stays unchanged.
Exit fills: stop/target/partials at price levels; signal exit at bar close.
Reinforce fills: bar close when ConditionGroup rising-edge fires.
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
from app.strategy_lab.evaluator import (
    bar_matches_group,
    explain_group_dicts,
    extract_ruleset_signals,
)
from app.strategy_lab.features import FeatureBar, FeatureSeries, build_feature_series
from app.strategy_lab.partial_tp import (
    PartialExit,
    PartialTpStep,
    log_return_from_vwap,
    mfe_r,
    partial_level,
    vwap_exit,
)
from app.strategy_lab.reinforce import (
    ReinforceAdd,
    apply_reinforce_add,
    cap_add_by_exposure,
    open_risk,
)
from app.strategy_lab.ruleset import ConditionGroup, ReinforceSpec, Ruleset, parse_ruleset
from app.strategy_lab.stop_trail import TrailSpec, update_trailing_stop

_SIGN = {Direction.LONG: 1.0, Direction.SHORT: -1.0, Direction.NEUTRAL: 0.0}


@dataclass(frozen=True)
class RulesetTradeDetail:
    trade: Trade
    exit_reason: str  # stop | target | signal | eod | max_hold | partial
    stop_price: float
    target_price: float
    atr_at_signal: float
    signal_index: int
    entry_index: int
    exit_index: int
    # T4c — explainability only (empty when feature_bars unavailable).
    why_entered: tuple[dict, ...] = ()
    why_exited: tuple[dict, ...] = ()
    # T0-MANAGE-c — empty when no scale-out fired.
    partial_exits: tuple[PartialExit, ...] = ()
    # T0-MANAGE-e — empty when no scale-in fired.
    reinforce_adds: tuple[ReinforceAdd, ...] = ()

@dataclass(frozen=True)
class RejectedSignal:
    """Rising-edge signal skipped because a position was already open (T4c)."""

    signal_index: int
    direction: Direction
    reason: str  # currently only "in_position"
    why_entered: tuple[dict, ...] = ()


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
    rejected: tuple[RejectedSignal, ...] = ()


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


def _hit_stop(
    direction: Direction,
    high: float,
    low: float,
    stop: float,
) -> bool:
    if direction == Direction.LONG:
        return low <= stop
    return high >= stop


def _hit_target(
    direction: Direction,
    high: float,
    low: float,
    target: float,
) -> bool:
    if direction == Direction.LONG:
        return high >= target
    return low <= target


def _hit_stop_or_target(
    direction: Direction,
    high: float,
    low: float,
    stop: float,
    target: float,
) -> str | None:
    if _hit_stop(direction, high, low, stop):
        return "stop"
    if _hit_target(direction, high, low, target):
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
    size: float = 1.0,
) -> None:
    """Fill bar_returns for one sized exit path (indices 0..n-2).

    Assignments overwrite within this call (same as pre-partial behaviour when
    ``exit_index == n-1``). Callers that stack several fills must accumulate
    into separate buffers then sum.
    """
    n = len(candles)
    sign = _SIGN[direction]
    if size <= 0 or entry_index >= n - 1 or entry_price <= 0 or exit_price <= 0:
        return

    if exit_index == entry_index:
        bar_returns[entry_index] = (
            size * sign * math.log(exit_price / entry_price) - 2 * size * cost
        )
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
        r = size * sign * math.log(end_px / candles[j].open)
        if j == entry_index:
            r -= size * cost
        bar_returns[j] = r

    if exit_index < n - 1 and exit_index > entry_index:
        if candles[exit_index].open > 0:
            bar_returns[exit_index] = (
                size * sign * math.log(exit_price / candles[exit_index].open)
                - size * cost
            )
    elif exit_index == n - 1 and exit_index - 1 >= entry_index:
        j = exit_index - 1
        if candles[j].open > 0:
            r = size * sign * math.log(exit_price / candles[j].open) - size * cost
            if j == entry_index:
                r = (
                    size * sign * math.log(exit_price / entry_price)
                    - 2 * size * cost
                )
            bar_returns[j] = r


def _apply_fills_hold_returns(
    bar_returns: list[float],
    candles: Sequence[Candle],
    *,
    direction: Direction,
    entry_index: int,
    entry_price: float,
    fills: list[tuple[int, float, float]],
    cost: float,
    target_net_log: float,
) -> None:
    """Size-weighted path per fill, then soak VWAP↔path residual on last exit bar.

    Physical remaining-size accounting sums to Σ f·log (Jensen). Trade uses
    log(VWAP/entry); the difference is added on the final exit contribution so
    Σ bar_returns == target_net_log (T0-METRICS-2).
    """
    if not fills:
        return
    scratch = [0.0] * len(bar_returns)
    for exit_index, exit_price, frac in fills:
        piece = [0.0] * len(bar_returns)
        _apply_hold_returns(
            piece,
            candles,
            direction=direction,
            entry_index=entry_index,
            entry_price=entry_price,
            exit_index=exit_index,
            exit_price=exit_price,
            cost=cost,
            size=frac,
        )
        for j, v in enumerate(piece):
            if v:
                scratch[j] += v
    path_sum = sum(scratch)
    residual = target_net_log - path_sum
    n = len(candles)
    final_idx = fills[-1][0]
    soak_at = final_idx if final_idx < n - 1 else max(entry_index, n - 2)
    if 0 <= soak_at < len(scratch) and abs(residual) >= 1e-15:
        scratch[soak_at] += residual
    for j, v in enumerate(scratch):
        if v:
            bar_returns[j] += v


def _why_at(
    feature_bars: Sequence[FeatureBar] | None,
    index: int,
    group: ConditionGroup | None,
    direction: Direction,
) -> tuple[dict, ...]:
    if feature_bars is None or group is None or index < 0 or index >= len(feature_bars):
        return ()
    return explain_group_dicts(feature_bars[index], group, direction)


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
    entry_group: ConditionGroup | None = None,
    trail: TrailSpec | None = None,
    partial_tp: tuple[PartialTpStep, ...] | None = None,
    reinforce: ReinforceSpec | None = None,
) -> tuple[
    list[RulesetTradeDetail],
    list[Direction],
    list[float],
    int,
    list[RejectedSignal],
]:
    n = len(candles)
    if n < 2:
        return [], [Direction.NEUTRAL] * n, [], 0, []

    need_features = exit_group is not None or (
        reinforce is not None and reinforce.condition_group is not None
    )
    if need_features:
        if feature_bars is None or len(feature_bars) != n:
            raise ValueError(
                "feature_bars (len == candles) required when exit_group "
                "or reinforce is set"
            )

    cost = (commission_bps + slippage_bps) / 10_000
    posn = [Direction.NEUTRAL] * n
    bar_returns = [0.0] * (n - 1)
    details: list[RulesetTradeDetail] = []
    rejected: list[RejectedSignal] = []
    skipped = 0
    busy_until = -1
    steps = tuple(partial_tp or ())

    for signal_index, direction in signals:
        if signal_index <= busy_until:
            skipped += 1
            rejected.append(
                RejectedSignal(
                    signal_index=signal_index,
                    direction=direction,
                    reason="in_position",
                    why_entered=_why_at(
                        feature_bars, signal_index, entry_group, direction
                    ),
                )
            )
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
        initial_stop, target = _levels(
            direction, entry_price, atr_val, stop_atr, target_atr
        )
        stop = initial_stop
        avg_entry = entry_price
        open_qty = 1.0
        risk0 = open_risk(direction, entry_price, initial_stop, 1.0)
        entry_lots: list[tuple[int, float, float]] = [
            (entry_index, entry_price, 1.0)
        ]
        reinforce_adds: list[ReinforceAdd] = []
        adds_done = 0
        reinforce_prev_match = False

        hold_end = n - 1
        if max_hold_bars is not None and max_hold_bars > 0:
            hold_end = min(hold_end, entry_index + max_hold_bars - 1)

        exit_index = hold_end
        exit_price = candles[hold_end].close
        exit_reason = "eod" if hold_end == n - 1 else "max_hold"
        why_exited: tuple[dict, ...] = ()
        partial_exits: list[PartialExit] = []
        # ``remaining`` tracks un-exited fraction of the *original* unit (partials).
        remaining = 1.0
        next_step = 0
        closed = False

        for j in range(entry_index, hold_end + 1):
            posn[j] = direction

            # 1) Stop — always first (unknown intra-bar order → conservative).
            if _hit_stop(direction, candles[j].high, candles[j].low, stop):
                exit_index = j
                exit_price = stop
                exit_reason = "stop"
                closed = True
                for k in range(j + 1, hold_end + 1):
                    posn[k] = Direction.NEUTRAL
                break

            # 2) Partials — ascending R (limit resting before farther target).
            while next_step < len(steps) and remaining > 1e-12:
                step = steps[next_step]
                if (
                    mfe_r(
                        direction,
                        entry_price,
                        initial_stop,
                        candles[j].high,
                        candles[j].low,
                    )
                    + 1e-12
                    < step.r_multiple
                ):
                    break
                take = min(step.fraction, remaining)
                level = partial_level(
                    direction, entry_price, initial_stop, step.r_multiple
                )
                partial_exits.append(
                    PartialExit(
                        bar_index=j,
                        price=level,
                        fraction=take,
                        r_multiple=step.r_multiple,
                    )
                )
                remaining -= take
                open_qty = max(0.0, open_qty - take)
                next_step += 1
                if remaining <= 1e-12 and open_qty <= 1e-12:
                    remaining = 0.0
                    open_qty = 0.0
                    exit_index = j
                    exit_price = level
                    exit_reason = "partial"
                    closed = True
                    for k in range(j + 1, hold_end + 1):
                        posn[k] = Direction.NEUTRAL
                    break
            if closed:
                break

            # 3) Full target on remainder.
            if open_qty > 1e-12 and _hit_target(
                direction, candles[j].high, candles[j].low, target
            ):
                exit_index = j
                exit_price = target
                exit_reason = "target"
                closed = True
                for k in range(j + 1, hold_end + 1):
                    posn[k] = Direction.NEUTRAL
                break

            # 4) Signal exit on remainder.
            if (
                open_qty > 1e-12
                and exit_group is not None
                and feature_bars is not None
                and bar_matches_group(feature_bars[j], exit_group, direction)
            ):
                exit_index = j
                exit_price = candles[j].close
                exit_reason = "signal"
                why_exited = _why_at(feature_bars, j, exit_group, direction)
                closed = True
                for k in range(j + 1, hold_end + 1):
                    posn[k] = Direction.NEUTRAL
                break

            # 5) Reinforce (rising-edge ConditionGroup) — after exit checks.
            if (
                reinforce is not None
                and feature_bars is not None
                and open_qty > 1e-12
                and adds_done < reinforce.max_adds
                and j > entry_index
            ):
                matched = bar_matches_group(
                    feature_bars[j], reinforce.condition_group, direction
                )
                rising = matched and not reinforce_prev_match
                reinforce_prev_match = matched
                if rising:
                    add_px = float(candles[j].close)
                    if add_px > 0:
                        requested = cap_add_by_exposure(
                            open_qty=open_qty,
                            requested_add=reinforce.add_fraction,
                            initial_qty=1.0,
                            max_exposure=reinforce.max_exposure,
                        )
                        if requested <= 1e-15:
                            pass
                        else:
                            actual, avg_entry, stop, open_qty, clamped = apply_reinforce_add(
                                direction=direction,
                                avg_entry=avg_entry,
                                qty=open_qty,
                                stop=stop,
                                add_price=add_px,
                                requested_add=requested,
                                initial_risk=risk0,
                                policy=reinforce.risk_policy,
                            )
                            if actual > 1e-15:
                                entry_lots.append((j, add_px, actual))
                                reinforce_adds.append(
                                    ReinforceAdd(
                                        bar_index=j,
                                        price=add_px,
                                        fraction=actual,
                                        requested_fraction=reinforce.add_fraction,
                                        stop_after=stop,
                                        avg_entry_after=avg_entry,
                                        open_risk_after=open_risk(
                                            direction, avg_entry, stop, open_qty
                                        ),
                                        clamped=clamped
                                        or requested + 1e-12 < reinforce.add_fraction,
                                    )
                                )
                                adds_done += 1
            elif reinforce is not None and feature_bars is not None:
                reinforce_prev_match = bar_matches_group(
                    feature_bars[j], reinforce.condition_group, direction
                )

            # 6) Trail update after exit checks — new stop applies from next bar.
            bar_atr = atr_states[j].atr if j < len(atr_states) else None
            stop = update_trailing_stop(
                direction,
                stop,
                entry=avg_entry,
                initial_stop=initial_stop,
                high=candles[j].high,
                low=candles[j].low,
                close=candles[j].close,
                atr=bar_atr if bar_atr is not None else atr_val,
                trail=trail,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            )

        # Build exit fill list: partials + remainder (open_qty).
        fills: list[tuple[int, float, float]] = [
            (pe.bar_index, pe.price, pe.fraction) for pe in partial_exits
        ]
        if open_qty > 1e-12:
            fills.append((exit_index, exit_price, open_qty))
        elif not fills:
            fills.append((exit_index, exit_price, 1.0))

        entry_vwap = vwap_exit([(p, f) for _, p, f in entry_lots])
        exit_vwap = vwap_exit([(p, f) for _, p, f in fills])
        total_qty = sum(f for _, _, f in entry_lots)
        gross = log_return_from_vwap(direction, entry_vwap, exit_vwap)
        # Scale fees with total traded size (each unit pays a full round-trip).
        rt_cost = round_trip_cost_log(commission_bps, slippage_bps) * total_qty
        # Trade.log_return stays per-unit VWAP return; net scales via cost only
        # when size==1. With adds, express gross on full notional for metrics:
        if abs(total_qty - 1.0) > 1e-12:
            gross = total_qty * log_return_from_vwap(direction, entry_vwap, exit_vwap)
        target_net = gross - rt_cost

        if (
            len(fills) == 1
            and fills[0][2] >= 1.0 - 1e-12
            and len(entry_lots) == 1
            and abs(total_qty - 1.0) <= 1e-12
        ):
            _apply_hold_returns(
                bar_returns,
                candles,
                direction=direction,
                entry_index=entry_index,
                entry_price=entry_price,
                exit_index=exit_index,
                exit_price=exit_price,
                cost=cost,
                size=1.0,
            )
        else:
            # Per entry-lot → allocated exit share (proportional), then soak residual.
            scratch = [0.0] * len(bar_returns)
            exit_total = sum(f for _, _, f in fills)
            for lot_i, lot_px, lot_f in entry_lots:
                share = lot_f / exit_total if exit_total > 0 else 0.0
                for ex_i, ex_px, ex_f in fills:
                    piece_f = ex_f * share
                    if piece_f <= 1e-15:
                        continue
                    piece = [0.0] * len(bar_returns)
                    _apply_hold_returns(
                        piece,
                        candles,
                        direction=direction,
                        entry_index=lot_i,
                        entry_price=lot_px,
                        exit_index=ex_i,
                        exit_price=ex_px,
                        cost=cost,
                        size=piece_f,
                    )
                    for jj, v in enumerate(piece):
                        if v:
                            scratch[jj] += v
            path_sum = sum(scratch)
            residual = target_net - path_sum
            final_idx = fills[-1][0]
            soak_at = final_idx if final_idx < n - 1 else max(entry_index, n - 2)
            if 0 <= soak_at < len(scratch) and abs(residual) >= 1e-15:
                scratch[soak_at] += residual
            for jj, v in enumerate(scratch):
                if v:
                    bar_returns[jj] += v

        details.append(
            RulesetTradeDetail(
                trade=Trade(
                    entry_time=candles[entry_index].time,
                    exit_time=candles[exit_index].time,
                    direction=direction,
                    entry_price=entry_vwap,
                    exit_price=exit_vwap,
                    log_return=gross,
                    cost_log=rt_cost,
                ),
                exit_reason=exit_reason,
                stop_price=stop,
                target_price=target,
                atr_at_signal=atr_val,
                signal_index=signal_index,
                entry_index=entry_index,
                exit_index=exit_index,
                why_entered=_why_at(
                    feature_bars, signal_index, entry_group, direction
                ),
                why_exited=why_exited,
                partial_exits=tuple(partial_exits),
                reinforce_adds=tuple(reinforce_adds),
            )
        )
        busy_until = exit_index

    return details, posn, bar_returns, skipped, rejected


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
    details, posn, bar_returns, skipped, rejected = simulate_ruleset_trades(
        features.candles,
        features.atr,
        signals,
        stop_atr=float(ruleset.stop_atr),
        target_atr=float(ruleset.target_atr),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_hold_bars=_resolve_max_hold(ruleset, max_hold_bars),
        exit_group=exit_group,
        # Always pass bars so T4c WHY traces are available (match logic unchanged).
        feature_bars=features.bars,
        entry_group=ruleset.condition_group,
        trail=ruleset.exit.trail,
        partial_tp=ruleset.exit.partial_tp or None,
        reinforce=ruleset.exit.reinforce,
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
        rejected=tuple(rejected),
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
