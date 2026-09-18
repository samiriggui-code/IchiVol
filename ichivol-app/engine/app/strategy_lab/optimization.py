"""Parameter optimization — Strategy Lab Phase 8.

Grid-search numeric ruleset knobs on an in-sample window, then measure the
*winning* candidate out-of-sample. Never trust IS rank alone.

Walk-forward mode (primary): for each fold, pick best params on train,
evaluate once on test. Single-window mode: rank the whole grid on one span
(research / smoke only).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.evaluator import extract_ruleset_signals
from app.strategy_lab.event_study import DEFAULT_HORIZONS
from app.strategy_lab.features import FeatureSeries, build_feature_series
from app.strategy_lab.perf_db import persist_study_result
from app.strategy_lab.ruleset import CONDITION_SCHEMA, Ruleset, parse_ruleset
from app.strategy_lab.run_ruleset import RulesetStudyResult, ruleset_study_dict
from app.strategy_lab.walk_forward import (
    FoldSpec,
    generate_expanding_folds,
    generate_rolling_folds,
    _oos_summary,
    _signals_in_range,
    _study_from_signals,
)

# Cap combinatorial explosion (API / agent callers).
MAX_GRID_COMBINATIONS = 96

DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "rvol_min": [1.2, 1.5, 2.0],
    "tk_cross_age_max": [2, 3, 5],
    "stop_atr": [1.0, 1.5],
    "target_atr": [1.5, 2.0, 3.0],
}

_OBJECTIVES = frozenset({"expectancy", "profit_factor", "sharpe"})


@dataclass(frozen=True)
class CandidateResult:
    params: dict[str, Any]
    ruleset: Ruleset
    score: float | None
    study: RulesetStudyResult
    n_trades: int


@dataclass(frozen=True)
class OptimizeReport:
    symbol: str
    timeframe: str
    base_ruleset: Ruleset
    objective: str
    min_trades: int
    grid: dict[str, list[Any]]
    n_candidates: int
    ranking: list[CandidateResult]
    best: CandidateResult | None
    n_bars: int


@dataclass(frozen=True)
class WalkForwardOptFoldResult:
    fold: FoldSpec
    best_params: dict[str, Any]
    is_score: float | None
    is_n_trades: int
    train: RulesetStudyResult | None
    test: RulesetStudyResult
    n_candidates_scored: int
    train_experiment_id: str | None = None
    test_experiment_id: str | None = None


@dataclass(frozen=True)
class WalkForwardOptReport:
    symbol: str
    timeframe: str
    base_ruleset: Ruleset
    mode: str
    objective: str
    min_trades: int
    grid: dict[str, list[Any]]
    n_bars: int
    warmup_bars: int
    train_bars: int
    test_bars: int
    step_bars: int
    folds: list[WalkForwardOptFoldResult]
    oos_summary: dict
    param_stability: dict


def resolve_param_grid(
    base: Ruleset,
    grid: Mapping[str, Sequence[Any]] | None,
) -> dict[str, list[Any]]:
    """Keep only knobs that exist on the base ruleset (or stop/target)."""
    raw = dict(grid) if grid is not None else dict(DEFAULT_PARAM_GRID)
    resolved: dict[str, list[Any]] = {}
    for key, values in raw.items():
        key_s = str(key)
        vals = list(values)
        if not vals:
            continue
        if key_s in ("stop_atr", "target_atr"):
            resolved[key_s] = [float(v) for v in vals]
            continue
        if key_s not in CONDITION_SCHEMA:
            raise ValueError(f"unknown grid key {key_s!r}")
        if key_s not in base.conditions:
            continue  # skip knobs not present on this hypothesis
        expected = CONDITION_SCHEMA[key_s]
        if expected is bool or expected is str:
            raise ValueError(f"cannot grid-search non-numeric condition {key_s!r}")
        casted = [expected(v) for v in vals]
        resolved[key_s] = casted
    if not resolved:
        raise ValueError(
            "empty param grid after resolve — base ruleset has no overlapping knobs"
        )
    n = 1
    for vals in resolved.values():
        n *= len(vals)
    if n > MAX_GRID_COMBINATIONS:
        raise ValueError(
            f"grid has {n} combinations (max {MAX_GRID_COMBINATIONS}); shrink the grid"
        )
    return resolved


def expand_param_grid(grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    keys = list(grid.keys())
    if not keys:
        return [{}]
    combos = []
    for values in itertools.product(*(grid[k] for k in keys)):
        combos.append(dict(zip(keys, values)))
    return combos


def apply_params(base: Ruleset, params: Mapping[str, Any]) -> Ruleset:
    conditions = dict(base.conditions)
    stop = float(base.stop_atr)
    target = float(base.target_atr)
    for key, value in params.items():
        if key == "stop_atr":
            stop = float(value)
        elif key == "target_atr":
            target = float(value)
        else:
            conditions[key] = value
    payload = base.to_dict()
    payload["conditions"] = conditions
    payload["stop_atr"] = stop
    payload["target_atr"] = target
    # Distinct id so Perf DB / UI can tell candidates apart
    suffix = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
    if suffix:
        payload["id"] = f"{base.id}__opt"
        payload["meta"] = {**dict(base.meta), "opt_params": dict(params)}
    return parse_ruleset(payload)


def score_study(
    study: RulesetStudyResult,
    *,
    objective: str = "expectancy",
    min_trades: int = 5,
) -> float | None:
    if objective not in _OBJECTIVES:
        raise ValueError(f"objective must be one of {sorted(_OBJECTIVES)}")
    bt = study.backtest
    if bt is None:
        return None
    m = bt.metrics
    if m.num_trades < min_trades:
        return None
    if objective == "expectancy":
        return float(m.expectancy) if m.expectancy is not None else None
    if objective == "profit_factor":
        pf = m.profit_factor
        if pf is None or pf != pf or pf == float("inf"):
            return None
        return float(pf)
    if objective == "sharpe":
        return float(m.sharpe) if m.sharpe is not None else None
    raise ValueError(f"unhandled objective {objective!r}")


def _rank_key(c: CandidateResult) -> tuple:
    # None scores sort last; then prefer more trades, then higher score
    score = c.score if c.score is not None else float("-inf")
    return (c.score is not None, score, c.n_trades)


def optimize_on_range(
    features: FeatureSeries,
    base: Ruleset,
    *,
    start: int,
    end: int,
    grid: Mapping[str, Sequence[Any]],
    symbol: str = "",
    timeframe: str = "",
    objective: str = "expectancy",
    min_trades: int = 5,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    variant_prefix: str = "OPT",
) -> list[CandidateResult]:
    resolved = resolve_param_grid(base, grid)
    combos = expand_param_grid(resolved)
    ranking: list[CandidateResult] = []
    for params in combos:
        rs = apply_params(base, params)
        all_sigs = extract_ruleset_signals(features, rs, rising_edge=True)
        sigs = _signals_in_range(all_sigs, start, end)
        study = _study_from_signals(
            features,
            rs,
            sigs,
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            variant_suffix=f"{variant_prefix}",
        )
        n_trades = study.backtest.metrics.num_trades if study.backtest else 0
        ranking.append(
            CandidateResult(
                params=dict(params),
                ruleset=rs,
                score=score_study(study, objective=objective, min_trades=min_trades),
                study=study,
                n_trades=n_trades,
            )
        )
    ranking.sort(key=_rank_key, reverse=True)
    return ranking


def run_optimize_on_candles(
    candles: Sequence,
    base: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    grid: Mapping[str, Sequence[Any]] | None = None,
    objective: str = "expectancy",
    min_trades: int = 5,
    warmup_bars: int = 52,
    persist_best: bool = False,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> OptimizeReport:
    resolved = resolve_param_grid(base, grid)
    features = build_feature_series(candles)
    n = len(candles)
    if n <= warmup_bars + 50:
        raise ValueError(f"not enough bars for optimize (n={n}, warmup={warmup_bars})")
    ranking = optimize_on_range(
        features,
        base,
        start=warmup_bars,
        end=n,
        grid=resolved,
        symbol=symbol,
        timeframe=timeframe,
        objective=objective,
        min_trades=min_trades,
        horizons=horizons,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        variant_prefix="OPT_FULL",
    )
    best = ranking[0] if ranking and ranking[0].score is not None else None
    if persist_best and best is not None:
        persist_study_result(
            best.study,
            market_regime="OPT_BEST",
            parameters={"optimize": True, "params": best.params, "objective": objective},
        )
    return OptimizeReport(
        symbol=symbol,
        timeframe=timeframe,
        base_ruleset=base,
        objective=objective,
        min_trades=min_trades,
        grid=resolved,
        n_candidates=len(ranking),
        ranking=ranking,
        best=best,
        n_bars=n,
    )


def _param_stability(folds: Sequence[WalkForwardOptFoldResult]) -> dict:
    """How often each chosen param value repeats across folds."""
    if not folds:
        return {"n_folds": 0, "keys": {}}
    keys: dict[str, dict[str, int]] = {}
    for fr in folds:
        for k, v in fr.best_params.items():
            bucket = keys.setdefault(k, {})
            label = str(v)
            bucket[label] = bucket.get(label, 0) + 1
    return {
        "n_folds": len(folds),
        "keys": {
            k: {
                "mode": max(counts, key=counts.get),
                "counts": counts,
                "unique": len(counts),
            }
            for k, counts in keys.items()
        },
    }


def run_walk_forward_opt_on_candles(
    candles: Sequence,
    base: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    grid: Mapping[str, Sequence[Any]] | None = None,
    objective: str = "expectancy",
    min_trades: int = 5,
    persist: bool = False,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> WalkForwardOptReport:
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
            f"not enough bars for walk-forward-opt "
            f"(n={n}, train={train_bars}, test={test_bars}, warmup={warmup_bars})"
        )

    resolved = resolve_param_grid(base, grid)
    features = build_feature_series(candles)

    fold_results: list[WalkForwardOptFoldResult] = []
    for spec in specs:
        ranking = optimize_on_range(
            features,
            base,
            start=spec.train_start,
            end=spec.train_end,
            grid=resolved,
            symbol=symbol,
            timeframe=timeframe,
            objective=objective,
            min_trades=min_trades,
            horizons=horizons,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            variant_prefix=f"WFOPT{spec.fold_index}_IS",
        )
        # Fall back to base params if nothing meets min_trades
        if ranking and ranking[0].score is not None:
            winner = ranking[0]
            best_params = winner.params
            train_study = winner.study
            is_score = winner.score
            is_n_trades = winner.n_trades
        else:
            best_params = {}
            train_study = _study_from_signals(
                features,
                base,
                _signals_in_range(
                    extract_ruleset_signals(features, base, rising_edge=True),
                    spec.train_start,
                    spec.train_end,
                ),
                symbol=symbol,
                timeframe=timeframe,
                horizons=horizons,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                variant_suffix=f"WFOPT{spec.fold_index}_IS_BASE",
            )
            is_score = score_study(train_study, objective=objective, min_trades=0)
            is_n_trades = train_study.backtest.metrics.num_trades if train_study.backtest else 0

        chosen = apply_params(base, best_params) if best_params else base
        oos_sigs = _signals_in_range(
            extract_ruleset_signals(features, chosen, rising_edge=True),
            spec.test_start,
            spec.test_end,
        )
        test_study = _study_from_signals(
            features,
            chosen,
            oos_sigs,
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            variant_suffix=f"WFOPT{spec.fold_index}_OOS",
        )

        train_exp = test_exp = None
        if persist:
            if train_study is not None:
                saved = persist_study_result(
                    train_study,
                    market_regime=f"WFOPT{spec.fold_index}_IS",
                    parameters={
                        "walk_forward_opt": True,
                        "fold": spec.fold_index,
                        "split": "IS",
                        "params": best_params,
                        "objective": objective,
                    },
                )
                train_exp = saved.get("experiment_id")
            saved = persist_study_result(
                test_study,
                market_regime=f"WFOPT{spec.fold_index}_OOS",
                parameters={
                    "walk_forward_opt": True,
                    "fold": spec.fold_index,
                    "split": "OOS",
                    "params": best_params,
                    "objective": objective,
                },
            )
            test_exp = saved.get("experiment_id")

        fold_results.append(
            WalkForwardOptFoldResult(
                fold=spec,
                best_params=best_params,
                is_score=is_score,
                is_n_trades=is_n_trades,
                train=train_study,
                test=test_study,
                n_candidates_scored=len(ranking),
                train_experiment_id=train_exp,
                test_experiment_id=test_exp,
            )
        )

    oos_summary = _oos_summary(fold_results)  # type: ignore[arg-type]

    return WalkForwardOptReport(
        symbol=symbol,
        timeframe=timeframe,
        base_ruleset=base,
        mode=mode_l,
        objective=objective,
        min_trades=min_trades,
        grid=resolved,
        n_bars=n,
        warmup_bars=warmup_bars,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars if step_bars is not None else test_bars,
        folds=fold_results,
        oos_summary=oos_summary,
        param_stability=_param_stability(fold_results),
    )


def _resolve_base(
    ruleset_id: str | None,
    ruleset: dict | Ruleset | None,
) -> Ruleset:
    if isinstance(ruleset, Ruleset):
        return ruleset
    if isinstance(ruleset, dict):
        return parse_ruleset(ruleset)
    if ruleset_id:
        return get_builtin_ruleset(ruleset_id)
    raise ValueError("ruleset_id or ruleset is required")


def run_optimize(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001",
    ruleset: dict | Ruleset | None = None,
    grid: Mapping[str, Sequence[Any]] | None = None,
    objective: str = "expectancy",
    min_trades: int = 5,
    warmup_bars: int = 52,
    persist_best: bool = False,
) -> OptimizeReport:
    base = _resolve_base(ruleset_id, ruleset)
    _p, _s, candles = resolve_and_fetch(symbol, timeframe=timeframe, limit=limit)
    return run_optimize_on_candles(
        candles,
        base,
        symbol=symbol,
        timeframe=timeframe,
        grid=grid,
        objective=objective,
        min_trades=min_trades,
        warmup_bars=warmup_bars,
        persist_best=persist_best,
    )


def run_walk_forward_opt(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001",
    ruleset: dict | Ruleset | None = None,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    grid: Mapping[str, Sequence[Any]] | None = None,
    objective: str = "expectancy",
    min_trades: int = 5,
    persist: bool = False,
) -> WalkForwardOptReport:
    base = _resolve_base(ruleset_id, ruleset)
    _p, _s, candles = resolve_and_fetch(symbol, timeframe=timeframe, limit=limit)
    return run_walk_forward_opt_on_candles(
        candles,
        base,
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
        grid=grid,
        objective=objective,
        min_trades=min_trades,
        persist=persist,
    )


def optimize_dict(report: OptimizeReport, *, top_n: int = 10) -> dict:
    def _cand(c: CandidateResult) -> dict:
        return {
            "params": c.params,
            "score": c.score,
            "n_trades": c.n_trades,
            "ruleset": c.ruleset.to_dict(),
            "study": ruleset_study_dict(c.study, include_events=False),
        }

    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "base_ruleset": report.base_ruleset.to_dict(),
        "objective": report.objective,
        "min_trades": report.min_trades,
        "grid": report.grid,
        "n_candidates": report.n_candidates,
        "n_bars": report.n_bars,
        "best": _cand(report.best) if report.best else None,
        "ranking": [_cand(c) for c in report.ranking[:top_n]],
        "note": (
            "Single-window grid search — IS only. Prefer walk-forward-opt for "
            "anti-overfitting OOS validation."
        ),
    }


def walk_forward_opt_dict(report: WalkForwardOptReport) -> dict:
    def _fold(fr: WalkForwardOptFoldResult) -> dict:
        f = fr.fold
        return {
            "fold_index": f.fold_index,
            "train_start": f.train_start,
            "train_end": f.train_end,
            "test_start": f.test_start,
            "test_end": f.test_end,
            "train_bars": f.train_end - f.train_start,
            "test_bars": f.test_end - f.test_start,
            "best_params": fr.best_params,
            "is_score": fr.is_score,
            "is_n_trades": fr.is_n_trades,
            "n_candidates_scored": fr.n_candidates_scored,
            "train_experiment_id": fr.train_experiment_id,
            "test_experiment_id": fr.test_experiment_id,
            "is": ruleset_study_dict(fr.train, include_events=False) if fr.train else None,
            "oos": ruleset_study_dict(fr.test, include_events=False),
        }

    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "base_ruleset": report.base_ruleset.to_dict(),
        "mode": report.mode,
        "objective": report.objective,
        "min_trades": report.min_trades,
        "grid": report.grid,
        "n_bars": report.n_bars,
        "warmup_bars": report.warmup_bars,
        "train_bars": report.train_bars,
        "test_bars": report.test_bars,
        "step_bars": report.step_bars,
        "folds": [_fold(fr) for fr in report.folds],
        "oos_summary": report.oos_summary,
        "param_stability": report.param_stability,
        "note": (
            "Walk-forward optimization: params chosen on IS per fold, measured on OOS. "
            "OOS summary is the anti-overfitting check; param_stability shows drift."
        ),
    }



