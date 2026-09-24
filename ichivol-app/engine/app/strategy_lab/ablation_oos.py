"""T9g — ablation × walk-forward OOS study (observation-only).

Compares BASELINE vs BASELINE+X (additive) or FULL vs NO_X (leave-one-layer)
across walk-forward OOS folds. Emits promote / reject / inconclusive
recommendations — never mutates FeatureStatus, pipeline, or live gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.strategy_lab.ablation import (
    ABLATION_LADDERS,
    build_cumulative_rulesets,
    build_leave_one_layer_out_rulesets,
)
from app.strategy_lab.ruleset import Ruleset
from app.strategy_lab.walk_forward import WalkForwardReport, run_walk_forward_on_candles

_DISCLAIMER = (
    "Ablation OOS study (T9g) — observation only; does not alter decision, "
    "confidence, FeatureStatus, fills, or gates; no auto-reject."
)


@dataclass(frozen=True)
class AblationOosCandidate:
    label: str
    compare_mode: str
    baseline_ruleset_id: str
    variant_ruleset_id: str
    added_conditions: list[str]
    is_expectancy_delta: float | None
    oos_expectancy_delta: float | None
    is_profit_factor_delta: float | None
    oos_profit_factor_delta: float | None
    oos_total_trades_baseline: int
    oos_total_trades_variant: int
    n_folds: int
    recommendation: str  # promote | reject | inconclusive
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "compare_mode": self.compare_mode,
            "baseline_ruleset_id": self.baseline_ruleset_id,
            "variant_ruleset_id": self.variant_ruleset_id,
            "added_conditions": list(self.added_conditions),
            "is_expectancy_delta": self.is_expectancy_delta,
            "oos_expectancy_delta": self.oos_expectancy_delta,
            "is_profit_factor_delta": self.is_profit_factor_delta,
            "oos_profit_factor_delta": self.oos_profit_factor_delta,
            "oos_total_trades_baseline": self.oos_total_trades_baseline,
            "oos_total_trades_variant": self.oos_total_trades_variant,
            "n_folds": self.n_folds,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AblationOosReport:
    symbol: str
    timeframe: str
    compare_mode: str
    ladder: str | None
    n_bars: int
    n_folds: int
    train_bars: int
    test_bars: int
    candidates: list[AblationOosCandidate] = field(default_factory=list)
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "compare_mode": self.compare_mode,
            "ladder": self.ladder,
            "n_bars": self.n_bars,
            "n_folds": self.n_folds,
            "train_bars": self.train_bars,
            "test_bars": self.test_bars,
            "candidates": [c.to_dict() for c in self.candidates],
            "disclaimer": self.disclaimer,
        }


def _mean_is_expectancy(report: WalkForwardReport) -> float | None:
    vals: list[float] = []
    for fold in report.folds:
        if fold.train is None or fold.train.backtest is None:
            continue
        e = fold.train.backtest.metrics.expectancy
        if e is not None and e == e:
            vals.append(float(e))
    return sum(vals) / len(vals) if vals else None


def _mean_is_pf(report: WalkForwardReport) -> float | None:
    vals: list[float] = []
    for fold in report.folds:
        if fold.train is None or fold.train.backtest is None:
            continue
        pf = fold.train.backtest.metrics.profit_factor
        if pf is None or pf != pf or pf == float("inf"):
            continue
        vals.append(float(pf))
    return sum(vals) / len(vals) if vals else None


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return b - a


def decide_recommendation(
    *,
    oos_expectancy_delta: float | None,
    oos_profit_factor_delta: float | None,
    is_expectancy_delta: float | None,
    total_oos_trades: int,
    n_folds: int,
    min_oos_trades: int,
) -> tuple[str, list[str]]:
    """Deterministic research gate — never writes FeatureStatus."""
    reasons: list[str] = []
    if n_folds < 2:
        return "inconclusive", ["fewer than 2 OOS folds"]
    if total_oos_trades < min_oos_trades:
        return "inconclusive", [
            f"total OOS trades {total_oos_trades} < min_oos_trades {min_oos_trades}"
        ]
    if oos_expectancy_delta is None:
        return "inconclusive", ["missing OOS expectancy"]

    if oos_expectancy_delta <= 0:
        reasons.append(f"OOS expectancy delta {oos_expectancy_delta:.6f} <= 0")
        return "reject", reasons

    reasons.append(f"OOS expectancy delta {oos_expectancy_delta:.6f} > 0")
    if oos_profit_factor_delta is not None and oos_profit_factor_delta < 0:
        reasons.append(f"OOS PF delta {oos_profit_factor_delta:.6f} < 0")
        return "reject", reasons
    if oos_profit_factor_delta is not None:
        reasons.append(f"OOS PF delta {oos_profit_factor_delta:.6f} >= 0")

    # Mild overfitting guard: strong IS lift but flat/negative already handled;
    # if IS was negative while OOS positive, still promote but note it.
    if is_expectancy_delta is not None and is_expectancy_delta < 0:
        reasons.append("IS expectancy delta negative while OOS positive — review")
    return "promote", reasons


def _layer_keys(conds: Mapping[str, bool | int | float | str]) -> list[str]:
    return sorted(conds.keys())


def _run_wf(
    candles: Sequence[Candle],
    ruleset: Ruleset,
    *,
    symbol: str,
    timeframe: str,
    mode: str,
    train_bars: int,
    test_bars: int,
    step_bars: int | None,
    warmup_bars: int,
) -> WalkForwardReport:
    return run_walk_forward_on_candles(
        candles,
        ruleset,
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
        include_train=True,
        persist=False,
    )


def run_ablation_oos_study_on_candles(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    compare_mode: str = "additive",
    ladder: str = "default",
    layers: Sequence[tuple[str, Mapping[str, bool | int | float | str]]] | None = None,
    direction: Direction = Direction.LONG,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    wf_mode: str = "rolling",
    train_bars: int = 100,
    test_bars: int = 40,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    min_oos_trades: int = 5,
) -> AblationOosReport:
    mode = compare_mode.lower().strip()
    if mode not in ("additive", "leave_one_layer_out"):
        raise ValueError("compare_mode must be 'additive' or 'leave_one_layer_out'")

    if layers is None:
        if ladder not in ABLATION_LADDERS:
            raise ValueError(f"unknown ladder: {ladder!r}")
        layer_seq = ABLATION_LADDERS[ladder]
        ladder_name: str | None = ladder
    else:
        layer_seq = list(layers)
        ladder_name = None
    if len(layer_seq) < 2:
        raise ValueError("need at least 2 layers for ablation OOS")

    if mode == "additive":
        rulesets = build_cumulative_rulesets(
            layer_seq,
            direction=direction,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )
        pairs: list[tuple[str, Ruleset, Ruleset, list[str]]] = []
        for i in range(1, len(rulesets)):
            label = layer_seq[i][0]
            added = _layer_keys(layer_seq[i][1])
            pairs.append((label, rulesets[i - 1], rulesets[i], added))
    else:
        rulesets = build_leave_one_layer_out_rulesets(
            layer_seq,
            direction=direction,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )
        full = rulesets[0]
        pairs = []
        for i, (label, conds) in enumerate(layer_seq):
            variant = rulesets[i + 1]  # NO_X
            # Compare FULL (baseline with X) vs NO_X (variant without X)
            # positive delta means X helps when present in FULL
            pairs.append((label, variant, full, _layer_keys(conds)))

    candidates: list[AblationOosCandidate] = []
    n_folds = 0
    for label, baseline_rs, variant_rs, added in pairs:
        base_wf = _run_wf(
            candles,
            baseline_rs,
            symbol=symbol,
            timeframe=timeframe,
            mode=wf_mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
        )
        var_wf = _run_wf(
            candles,
            variant_rs,
            symbol=symbol,
            timeframe=timeframe,
            mode=wf_mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
        )
        n_folds = max(n_folds, base_wf.oos_summary.get("n_folds", 0) or 0)
        is_exp_d = _delta(_mean_is_expectancy(base_wf), _mean_is_expectancy(var_wf))
        oos_exp_d = _delta(
            base_wf.oos_summary.get("mean_oos_expectancy"),
            var_wf.oos_summary.get("mean_oos_expectancy"),
        )
        is_pf_d = _delta(_mean_is_pf(base_wf), _mean_is_pf(var_wf))
        oos_pf_d = _delta(
            base_wf.oos_summary.get("mean_oos_profit_factor"),
            var_wf.oos_summary.get("mean_oos_profit_factor"),
        )
        trades_base = int(base_wf.oos_summary.get("total_oos_trades") or 0)
        trades_var = int(var_wf.oos_summary.get("total_oos_trades") or 0)
        rec, reasons = decide_recommendation(
            oos_expectancy_delta=oos_exp_d,
            oos_profit_factor_delta=oos_pf_d,
            is_expectancy_delta=is_exp_d,
            total_oos_trades=max(trades_base, trades_var),
            n_folds=int(base_wf.oos_summary.get("n_folds") or 0),
            min_oos_trades=min_oos_trades,
        )
        candidates.append(
            AblationOosCandidate(
                label=label,
                compare_mode=mode,
                baseline_ruleset_id=baseline_rs.id,
                variant_ruleset_id=variant_rs.id,
                added_conditions=added,
                is_expectancy_delta=is_exp_d,
                oos_expectancy_delta=oos_exp_d,
                is_profit_factor_delta=is_pf_d,
                oos_profit_factor_delta=oos_pf_d,
                oos_total_trades_baseline=trades_base,
                oos_total_trades_variant=trades_var,
                n_folds=int(base_wf.oos_summary.get("n_folds") or 0),
                recommendation=rec,
                reasons=reasons,
            )
        )

    return AblationOosReport(
        symbol=symbol,
        timeframe=timeframe,
        compare_mode=mode,
        ladder=ladder_name,
        n_bars=len(candles),
        n_folds=n_folds,
        train_bars=train_bars,
        test_bars=test_bars,
        candidates=candidates,
    )


__all__ = [
    "AblationOosCandidate",
    "AblationOosReport",
    "decide_recommendation",
    "run_ablation_oos_study_on_candles",
]
