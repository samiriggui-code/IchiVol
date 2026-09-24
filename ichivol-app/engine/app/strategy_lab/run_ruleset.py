"""Run a Ruleset through features → Event Study + ATR SL/TP backtest."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.backtest.metrics import Metrics
from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.evaluator import extract_ruleset_signals, matches_mask
from app.strategy_lab.event_study import (
    DEFAULT_HORIZONS,
    EventObservation,
    EventStudyResult,
    aggregate_events,
    event_study_dict,
    observe_event,
)
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.ruleset_backtest import (
    RulesetBacktestResult,
    run_ruleset_backtest_on_features,
)


def _metrics_dict(m: Metrics) -> dict:
    return {
        "n_bars": m.n_bars,
        "total_return": m.total_return,
        "cagr": m.cagr,
        "sharpe": m.sharpe,
        "sortino": m.sortino,
        "max_drawdown": m.max_drawdown,
        "num_trades": m.num_trades,
        "win_rate": m.win_rate,
        "profit_factor": m.profit_factor if m.profit_factor != float("inf") else None,
        "expectancy": m.expectancy,
        "exposure": m.exposure,
        "win_rate_gross": m.win_rate_gross,
        "profit_factor_gross": (
            m.profit_factor_gross if m.profit_factor_gross != float("inf") else None
        ),
        "expectancy_gross": m.expectancy_gross,
        "metrics_basis": "net_v1",
    }


@dataclass(frozen=True)
class RulesetStudyResult:
    ruleset: Ruleset
    symbol: str
    timeframe: str
    n_bars: int
    n_matching_bars: int
    n_signals: int
    event_study: EventStudyResult
    backtest: RulesetBacktestResult | None = None


def study_ruleset_on_candles(
    candles: Sequence,
    ruleset: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    rising_edge: bool = True,
    with_backtest: bool = True,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
) -> RulesetStudyResult:
    features = build_feature_series(candles)
    signals = extract_ruleset_signals(features, ruleset, rising_edge=rising_edge)
    matching = sum(1 for m in matches_mask(features, ruleset) if m)

    r_multiple = float(ruleset.stop_atr)
    events: list[EventObservation] = []
    for signal_index, direction in signals:
        atr_val = features.atr[signal_index].atr
        if atr_val is None or atr_val <= 0:
            continue
        obs = observe_event(
            features.candles,
            signal_index,
            direction,
            atr_val,
            horizons,
            r_multiple=r_multiple,
        )
        if obs is not None:
            events.append(obs)

    study = aggregate_events(
        events,
        horizons,
        r_multiple,
        symbol=symbol,
        timeframe=timeframe,
        variant=ruleset.id,
        n_bars=len(candles),
    )

    bt: RulesetBacktestResult | None = None
    if with_backtest:
        bt = run_ruleset_backtest_on_features(
            features,
            ruleset,
            symbol=symbol,
            timeframe=timeframe,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            max_hold_bars=max_hold_bars,
        )

    return RulesetStudyResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        n_matching_bars=matching,
        n_signals=len(signals),
        event_study=study,
        backtest=bt,
    )


def run_ruleset_event_study(
    ruleset: Ruleset | dict,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    exchange: str = "binance",
    with_backtest: bool = True,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int | None = None,
) -> RulesetStudyResult:
    rs = ruleset if isinstance(ruleset, Ruleset) else parse_ruleset(ruleset)
    _provider, _psym, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles returned for {symbol} {timeframe}")
    return study_ruleset_on_candles(
        candles,
        rs,
        symbol=symbol.upper(),
        timeframe=timeframe,
        horizons=horizons,
        with_backtest=with_backtest,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_hold_bars=max_hold_bars,
    )


def ruleset_backtest_dict(bt: RulesetBacktestResult) -> dict:
    exit_counts: dict[str, int] = {}
    for d in bt.details:
        exit_counts[d.exit_reason] = exit_counts.get(d.exit_reason, 0) + 1
    out = {
        "metrics": _metrics_dict(bt.metrics),
        "backtest": {
            "symbol": bt.backtest.symbol,
            "timeframe": bt.backtest.timeframe,
            "n_bars": bt.backtest.n_bars,
            "commission_bps": bt.backtest.commission_bps,
            "slippage_bps": bt.backtest.slippage_bps,
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "direction": t.direction.value,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": math.exp(t.log_return) - 1,
                }
                for t in bt.backtest.trades
            ],
        },
        "n_signals": bt.n_signals,
        "n_skipped_in_position": bt.n_skipped_in_position,
        "exit_reasons": exit_counts,
        "trades": [
            {
                "entry_time": d.trade.entry_time,
                "exit_time": d.trade.exit_time,
                "direction": d.trade.direction.value,
                "entry_price": d.trade.entry_price,
                "exit_price": d.trade.exit_price,
                "pnl_pct": math.exp(d.trade.log_return) - 1,
                "exit_reason": d.exit_reason,
                "stop_price": d.stop_price,
                "target_price": d.target_price,
                "atr_at_signal": d.atr_at_signal,
            }
            for d in bt.details
        ],
    }
    if bt.levier:
        out["levier"] = True
    return out


def ruleset_study_dict(result: RulesetStudyResult, *, include_events: bool = False) -> dict:
    payload = {
        "ruleset": result.ruleset.to_dict(),
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "n_bars": result.n_bars,
        "n_matching_bars": result.n_matching_bars,
        "n_signals": result.n_signals,
        "event_study": event_study_dict(result.event_study, include_events=include_events),
        "note": (
            "Ruleset rising-edge → Event Study + ATR stop/target backtest. "
            "Conservative same-bar: stop before target."
        ),
    }
    if result.backtest is not None:
        payload["backtest"] = ruleset_backtest_dict(result.backtest)
    return payload
