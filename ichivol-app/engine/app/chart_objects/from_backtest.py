"""Ephemeral BACKTEST ChartObjects from a RulesetBacktestResult (T4a).

Not persisted — recomputed on demand (deterministic).

T0-METRICS: net return uses ``Trade.net_log_return`` (``cost_log`` filled by
the backtest) — no local fee formula.
"""

from __future__ import annotations

import math
from typing import Sequence

from app.agents.types import Direction
from app.chart_objects.types import (
    ChartObject,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.indicators.ichimoku import Candle
from app.strategy_lab.ruleset_backtest import RulesetBacktestResult, RulesetTradeDetail


def trade_return_pct_gross(detail: RulesetTradeDetail) -> float:
    """Gross simple return from ``Trade.log_return`` (prices only, no fees)."""
    return float(math.exp(detail.trade.log_return) - 1.0)


def trade_return_pct_net(detail: RulesetTradeDetail) -> float:
    """Net simple return from ``Trade.net_log_return`` (fees via ``cost_log``)."""
    return float(math.exp(detail.trade.net_log_return) - 1.0)


def trade_r_multiple_gross(detail: RulesetTradeDetail) -> float:
    """R from gross price move vs stop distance (prices only)."""
    entry = float(detail.trade.entry_price)
    exit_px = float(detail.trade.exit_price)
    stop = float(detail.stop_price)
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    if detail.trade.direction == Direction.LONG:
        move = exit_px - entry
    else:
        move = entry - exit_px
    return float(move / risk)


def trade_outcome(return_pct: float) -> str:
    if return_pct > 0:
        return "win"
    if return_pct < 0:
        return "loss"
    return "flat"


def backtest_to_chart_objects(
    result: RulesetBacktestResult,
    candles: Sequence[Candle],
) -> list[ChartObject]:
    """Four ChartObjects per trade: ENTRY, STOP, TARGET, exit MARKER."""
    if not candles:
        return []
    as_of = int(candles[-1].time)
    symbol = (result.symbol or "").upper()
    timeframe = result.timeframe or ""
    ruleset_id = result.ruleset.id
    ruleset_version = result.ruleset.version
    out: list[ChartObject] = []

    for trade_id, detail in enumerate(result.details):
        entry_i = detail.entry_index
        exit_i = detail.exit_index
        if entry_i < 0 or entry_i >= len(candles):
            continue
        if exit_i < 0 or exit_i >= len(candles):
            continue
        entry_time = int(candles[entry_i].time)
        exit_time = int(candles[exit_i].time)
        direction = detail.trade.direction
        side = direction.value  # LONG | SHORT
        ret_gross = trade_return_pct_gross(detail)
        ret_net = trade_return_pct_net(detail)
        r_mult = trade_r_multiple_gross(detail)
        outcome = trade_outcome(ret_net)
        origin_base = {
            "ruleset_id": ruleset_id,
            "ruleset_version": ruleset_version,
            "trade_id": trade_id,
            "direction": side,
            "exit_reason": detail.exit_reason,
            "return_pct_gross": ret_gross,
            "return_pct_net": ret_net,
            "r_multiple_gross": r_mult,
            "outcome": outcome,
            "signal_index": detail.signal_index,
            "entry_index": detail.entry_index,
            "exit_index": detail.exit_index,
            "via": "backtest_overlay",
        }

        def _obj(
            obj_type: ChartObjectType,
            *,
            time: int,
            price: float,
            label: str,
            kind: str,
        ) -> ChartObject:
            return ChartObject(
                type=obj_type,
                source=ChartObjectSource.BACKTEST,
                symbol=symbol,
                timeframe=timeframe,
                points=(ChartPoint(time=time, price=float(price)),),
                as_of=as_of,
                side=side,
                label=label,
                subtype=f"bt:{ruleset_id}:{trade_id}:{kind}",
                origin=dict(origin_base),
            )

        out.append(
            _obj(
                ChartObjectType.ENTRY,
                time=entry_time,
                price=detail.trade.entry_price,
                label="Entry",
                kind="entry",
            )
        )
        out.append(
            _obj(
                ChartObjectType.STOP,
                time=entry_time,
                price=detail.stop_price,
                label="Stop",
                kind="stop",
            )
        )
        out.append(
            _obj(
                ChartObjectType.TARGET,
                time=entry_time,
                price=detail.target_price,
                label="Target",
                kind="target",
            )
        )
        out.append(
            _obj(
                ChartObjectType.MARKER,
                time=exit_time,
                price=detail.trade.exit_price,
                label=detail.exit_reason,
                kind="exit",
            )
        )

    return out
