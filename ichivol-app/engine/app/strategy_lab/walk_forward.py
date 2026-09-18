"""Walk-forward evaluation — Strategy Lab Phase 7.

Split a shared OHLCV history into train / test folds and measure the *same*
fixed ruleset in-sample vs out-of-sample. No parameter optimization here
(that is Phase 8) — this module only answers:

  "Does this hypothesis hold on unseen time windows?"

Features are computed once on the full series (causal per bar). Signals are
then filtered by fold index ranges so indicators are never reset mid-history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.agents.types import Direction
from app.backtest.engine import BacktestResult
from app.backtest.metrics import compute_metrics
from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.evaluator import extract_ruleset_signals
from app.strategy_lab.event_study import (
    DEFAULT_HORIZONS,
    EventObservation,
    aggregate_events,
    observe_event,
)
from app.strategy_lab.features import FeatureSeries, build_feature_series
from app.strategy_lab.perf_db import persist_study_result
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.ruleset_backtest import RulesetBacktestResult, simulate_ruleset_trades
from app.strategy_lab.run_ruleset import RulesetStudyResult, ruleset_study_dict


@dataclass(frozen=True)
class FoldSpec:
    fold_index: int
    train_start: int
    train_end: int  # exclusive
    test_start: int
    test_end: int  # exclusive


@dataclass(frozen=True)
class WalkForwardFoldResult:
    fold: FoldSpec
    train: RulesetStudyResult | None
    test: RulesetStudyResult
    train_experiment_id: str | None = None
    test_experiment_id: str | None = None


@dataclass(frozen=True)
class WalkForwardReport:
    symbol: str
    timeframe: str
    ruleset: Ruleset
    mode: str
    n_bars: int
    warmup_bars: int
    train_bars: int
    test_bars: int
    step_bars: int
    folds: list[WalkForwardFoldResult]
    oos_summary: dict


def generate_rolling_folds(
    n_bars: int,
    *,
    train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    warmup_bars: int = 52,
) -> list[FoldSpec]:
    if train_bars < 50 or test_bars < 20:
        raise ValueError("train_bars must be >= 50 and test_bars >= 20")
    step = step_bars if step_bars is not None else test_bars
    if step < 1:
        raise ValueError("step_bars must be >= 1")
    folds: list[FoldSpec] = []
    cursor = warmup_bars
    idx = 0
    while cursor + train_bars + test_bars <= n_bars:
        train_start = cursor
        train_end = cursor + train_bars
        test_start = train_end
        test_end = train_end + test_bars
        folds.append(
            FoldSpec(
                fold_index=idx,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        cursor += step
        idx += 1
    return folds


def generate_expanding_folds(
    n_bars: int,
    *,
    initial_train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    warmup_bars: int = 52,
) -> list[FoldSpec]:
    if initial_train_bars < 50 or test_bars < 20:
        raise ValueError("initial_train_bars must be >= 50 and test_bars >= 20")
    step = step_bars if step_bars is not None else test_bars
    folds: list[FoldSpec] = []
    train_end = warmup_bars + initial_train_bars
    idx = 0
    while train_end + test_bars <= n_bars:
        folds.append(
            FoldSpec(
                fold_index=idx,
                train_start=warmup_bars,
                train_end=train_end,
                test_start=train_end,
                test_end=train_end + test_bars,
            )
        )
        train_end += step
        idx += 1
    return folds


def _signals_in_range(
    signals: Sequence[tuple[int, Direction]],
    start: int,
    end: int,
) -> list[tuple[int, Direction]]:
    return [(i, d) for i, d in signals if start <= i < end]


def _study_from_signals(
    features: FeatureSeries,
    ruleset: Ruleset,
    signals: Sequence[tuple[int, Direction]],
    *,
    symbol: str,
    timeframe: str,
    horizons: Sequence[int],
    commission_bps: float,
    slippage_bps: float,
    variant_suffix: str,
) -> RulesetStudyResult:
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
        variant=f"{ruleset.id}@{variant_suffix}",
        n_bars=len(features.candles),
    )
    details, posn, bar_returns, skipped = simulate_ruleset_trades(
        features.candles,
        features.atr,
        signals,
        stop_atr=float(ruleset.stop_atr),
        target_atr=float(ruleset.target_atr),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
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
    bt = RulesetBacktestResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        backtest=backtest,
        metrics=compute_metrics(backtest),
        details=details,
        n_signals=len(signals),
        n_skipped_in_position=skipped,
    )
    return RulesetStudyResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(features.candles),
        n_matching_bars=len(signals),
        n_signals=len(signals),
        event_study=study,
        backtest=bt,
    )


def _oos_summary(folds: Sequence[WalkForwardFoldResult]) -> dict:
    oos = [f.test for f in folds if f.test.backtest is not None]
    if not oos:
        return {
            "n_folds": len(folds),
            "folds_with_trades": 0,
            "mean_oos_expectancy": None,
            "mean_oos_profit_factor": None,
            "mean_oos_sharpe": None,
            "pct_folds_pf_gt_1": None,
            "pct_folds_expectancy_gt_0": None,
            "total_oos_trades": 0,
        }

    def _mean(xs: list[float | None]) -> float | None:
        vals = [x for x in xs if x is not None and x == x]
        return sum(vals) / len(vals) if vals else None

    expectancies = [s.backtest.metrics.expectancy if s.backtest else None for s in oos]
    pfs = [
        (
            s.backtest.metrics.profit_factor
            if s.backtest and s.backtest.metrics.profit_factor != float("inf")
            else None
        )
        for s in oos
    ]
    sharpes = [s.backtest.metrics.sharpe if s.backtest else None for s in oos]
    trades = [s.backtest.metrics.num_trades if s.backtest else 0 for s in oos]
    pf_ok = [p for p in pfs if p is not None]
    exp_ok = [e for e in expectancies if e is not None]

    return {
        "n_folds": len(folds),
        "folds_with_trades": sum(1 for t in trades if t > 0),
        "mean_oos_expectancy": _mean(expectancies),
        "mean_oos_profit_factor": _mean(pfs),
        "mean_oos_sharpe": _mean(sharpes),
        "pct_folds_pf_gt_1": (sum(1 for p in pf_ok if p > 1) / len(pf_ok) if pf_ok else None),
        "pct_folds_expectancy_gt_0": (
            sum(1 for e in exp_ok if e > 0) / len(exp_ok) if exp_ok else None
        ),
        "total_oos_trades": sum(trades),
    }


def run_walk_forward_on_candles(
    candles: Sequence,
    ruleset: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    include_train: bool = True,
    persist: bool = False,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> WalkForwardReport:
    n = len(candles)
    mode_l = mode.lower().strip()
    if mode_l == "rolling":
        specs = generate_rolling_folds(
            n,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
        )
    elif mode_l == "expanding":
        specs = generate_expanding_folds(
            n,
            initial_train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
        )
    else:
        raise ValueError("mode must be 'rolling' or 'expanding'")

    if not specs:
        raise ValueError(
            f"not enough bars for walk-forward "
            f"(n={n}, train={train_bars}, test={test_bars}, warmup={warmup_bars})"
        )

    features = build_feature_series(candles)
    all_signals = extract_ruleset_signals(features, ruleset, rising_edge=True)

    fold_results: list[WalkForwardFoldResult] = []
    for spec in specs:
        train_study = None
        train_exp = None
        if include_train:
            train_sigs = _signals_in_range(all_signals, spec.train_start, spec.train_end)
            train_study = _study_from_signals(
                features,
                ruleset,
                train_sigs,
                symbol=symbol,
                timeframe=timeframe,
                horizons=horizons,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                variant_suffix=f"WF{spec.fold_index}_IS",
            )
            if persist:
                saved = persist_study_result(
                    train_study,
                    market_regime=f"WF{spec.fold_index}_IS",
                    parameters={
                        "walk_forward": True,
                        "fold": spec.fold_index,
                        "split": "IS",
                        "train_start": spec.train_start,
                        "train_end": spec.train_end,
                    },
                )
                train_exp = saved.get("experiment_id")

        test_sigs = _signals_in_range(all_signals, spec.test_start, spec.test_end)
        test_study = _study_from_signals(
            features,
            ruleset,
            test_sigs,
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            variant_suffix=f"WF{spec.fold_index}_OOS",
        )
        test_exp = None
        if persist:
            saved = persist_study_result(
                test_study,
                market_regime=f"WF{spec.fold_index}_OOS",
                parameters={
                    "walk_forward": True,
                    "fold": spec.fold_index,
                    "split": "OOS",
                    "test_start": spec.test_start,
                    "test_end": spec.test_end,
                },
            )
            test_exp = saved.get("experiment_id")

        fold_results.append(
            WalkForwardFoldResult(
                fold=spec,
                train=train_study,
                test=test_study,
                train_experiment_id=train_exp,
                test_experiment_id=test_exp,
            )
        )

    return WalkForwardReport(
        symbol=symbol,
        timeframe=timeframe,
        ruleset=ruleset,
        mode=mode_l,
        n_bars=n,
        warmup_bars=warmup_bars,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars if step_bars is not None else test_bars,
        folds=fold_results,
        oos_summary=_oos_summary(fold_results),
    )


def run_walk_forward(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str | None = None,
    ruleset: dict | Ruleset | None = None,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    include_train: bool = True,
    persist: bool = False,
    exchange: str = "binance",
) -> WalkForwardReport:
    if ruleset is not None:
        rs = ruleset if isinstance(ruleset, Ruleset) else parse_ruleset(ruleset)
    elif ruleset_id:
        rs = get_builtin_ruleset(ruleset_id)
    else:
        rs = get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001")

    _p, _s, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles for {symbol} {timeframe}")
    return run_walk_forward_on_candles(
        candles,
        rs,
        symbol=symbol.upper(),
        timeframe=timeframe,
        mode=mode,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
        include_train=include_train,
        persist=persist,
    )


def walk_forward_dict(report: WalkForwardReport) -> dict:
    def _fold_payload(fr: WalkForwardFoldResult) -> dict:
        f = fr.fold
        return {
            "fold_index": f.fold_index,
            "train_start": f.train_start,
            "train_end": f.train_end,
            "test_start": f.test_start,
            "test_end": f.test_end,
            "train_bars": f.train_end - f.train_start,
            "test_bars": f.test_end - f.test_start,
            "train_experiment_id": fr.train_experiment_id,
            "test_experiment_id": fr.test_experiment_id,
            "is": ruleset_study_dict(fr.train, include_events=False) if fr.train else None,
            "oos": ruleset_study_dict(fr.test, include_events=False),
        }

    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "ruleset": report.ruleset.to_dict(),
        "mode": report.mode,
        "n_bars": report.n_bars,
        "warmup_bars": report.warmup_bars,
        "train_bars": report.train_bars,
        "test_bars": report.test_bars,
        "step_bars": report.step_bars,
        "folds": [_fold_payload(fr) for fr in report.folds],
        "oos_summary": report.oos_summary,
        "note": (
            "Walk-forward on a fixed ruleset (no optimizer). "
            "OOS metrics are the anti-overfitting check; IS is diagnostic only."
        ),
    }
