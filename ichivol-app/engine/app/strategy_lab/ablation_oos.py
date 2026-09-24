"""T9g — ablation × walk-forward OOS study (observation-only).

Compares BASELINE vs BASELINE+X (additive) or FULL vs NO_X (leave-one-layer)
across walk-forward OOS folds. Emits review_candidate / reject / inconclusive
recommendations — never mutates FeatureStatus, pipeline, or live gates.

T9g-fix: Lab never « promotes » — Claude + user decide (T10e).
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
    "confidence, FeatureStatus, fills, or gates; no auto-reject. "
    "review_candidate is not a promotion — Claude + user decide (T10e)."
)

# research_lab.sim BASE_COST / ADVERSE_COST (commission + slippage fields)
BASE_COMMISSION_BPS = 5.0
BASE_SLIPPAGE_BPS = 3.0
ADVERSE_COMMISSION_BPS = 10.0
ADVERSE_SLIPPAGE_BPS = 8.0

DEFAULT_MIN_OOS_TRADES = 30
ONE_YEAR_SECONDS = 365 * 86400


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
    recommendation: str  # review_candidate | reject | inconclusive
    reasons: list[str]
    fold_oos_expectancy_deltas: list[float | None] = field(default_factory=list)
    folds_positive_delta: int | None = None
    folds_compared: int | None = None
    adverse_oos_expectancy_delta: float | None = None

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
            "fold_oos_expectancy_deltas": list(self.fold_oos_expectancy_deltas),
            "folds_positive_delta": self.folds_positive_delta,
            "folds_compared": self.folds_compared,
            "adverse_oos_expectancy_delta": self.adverse_oos_expectancy_delta,
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
    hypothesis_id: str | None = None
    lineage_trial_count: int | None = None
    history_span_seconds: int | None = None
    history_warning: str | None = None
    min_oos_trades: int = DEFAULT_MIN_OOS_TRADES
    cost_base_bps: dict[str, float] = field(
        default_factory=lambda: {
            "commission_bps": BASE_COMMISSION_BPS,
            "slippage_bps": BASE_SLIPPAGE_BPS,
        }
    )
    cost_adverse_bps: dict[str, float] = field(
        default_factory=lambda: {
            "commission_bps": ADVERSE_COMMISSION_BPS,
            "slippage_bps": ADVERSE_SLIPPAGE_BPS,
        }
    )

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
            "hypothesis_id": self.hypothesis_id,
            "lineage_trial_count": self.lineage_trial_count,
            "history_span_seconds": self.history_span_seconds,
            "history_warning": self.history_warning,
            "min_oos_trades": self.min_oos_trades,
            "cost_base_bps": dict(self.cost_base_bps),
            "cost_adverse_bps": dict(self.cost_adverse_bps),
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


def _fold_oos_expectancies(report: WalkForwardReport) -> list[float | None]:
    out: list[float | None] = []
    for fold in report.folds:
        if fold.test is None or fold.test.backtest is None:
            out.append(None)
            continue
        e = fold.test.backtest.metrics.expectancy
        out.append(float(e) if e is not None and e == e else None)
    return out


def _fold_expectancy_deltas(
    base: WalkForwardReport, variant: WalkForwardReport
) -> list[float | None]:
    be = _fold_oos_expectancies(base)
    ve = _fold_oos_expectancies(variant)
    n = min(len(be), len(ve))
    return [_delta(be[i], ve[i]) for i in range(n)]


def decide_recommendation(
    *,
    oos_expectancy_delta: float | None,
    oos_profit_factor_delta: float | None,
    is_expectancy_delta: float | None,
    total_oos_trades: int,
    n_folds: int,
    min_oos_trades: int,
    fold_oos_expectancy_deltas: Sequence[float | None] | None = None,
    adverse_oos_expectancy_delta: float | None = None,
) -> tuple[str, list[str]]:
    """Deterministic research gate — never writes FeatureStatus.

    ``review_candidate`` (never ``promote``) requires all of:
    - enough OOS trades,
    - OOS expectancy delta > 0 in a strict majority of folds,
    - OOS expectancy delta > 0 under adverse costs,
    - OOS profit-factor not degraded.
    """
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

    # Strict majority of folds with positive expectancy delta.
    fold_deltas = list(fold_oos_expectancy_deltas or [])
    compared = [d for d in fold_deltas if d is not None]
    if not compared:
        return "inconclusive", ["no per-fold OOS expectancy deltas to majority-test"]
    positive = sum(1 for d in compared if d > 0)
    if not (positive * 2 > len(compared)):
        reasons.append(
            f"fold majority failed: {positive}/{len(compared)} folds with "
            f"OOS expectancy delta > 0 (need strict majority)"
        )
        return "reject", reasons
    reasons.append(
        f"fold majority ok: {positive}/{len(compared)} folds OOS expectancy delta > 0"
    )

    if adverse_oos_expectancy_delta is None:
        return "inconclusive", ["missing adverse-cost OOS expectancy delta"]
    if adverse_oos_expectancy_delta <= 0:
        reasons.append(
            f"adverse-cost OOS expectancy delta {adverse_oos_expectancy_delta:.6f} <= 0"
        )
        return "reject", reasons
    reasons.append(
        f"adverse-cost OOS expectancy delta {adverse_oos_expectancy_delta:.6f} > 0"
    )

    if oos_profit_factor_delta is not None and oos_profit_factor_delta < 0:
        reasons.append(f"OOS PF delta {oos_profit_factor_delta:.6f} < 0 (degraded)")
        return "reject", reasons
    if oos_profit_factor_delta is not None:
        reasons.append(f"OOS PF delta {oos_profit_factor_delta:.6f} >= 0")

    reasons.append(f"aggregate OOS expectancy delta {oos_expectancy_delta:.6f} > 0")
    if is_expectancy_delta is not None and is_expectancy_delta < 0:
        reasons.append("IS expectancy delta negative while OOS positive — review")
    return "review_candidate", reasons


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
    commission_bps: float,
    slippage_bps: float,
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
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


def _lineage_trial_count(hypothesis_id: str | None) -> int | None:
    if not hypothesis_id:
        return None
    try:
        from sqlalchemy import func, select

        from app.db.models import StrategyLabExperiment
        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            n = session.scalar(
                select(func.count())
                .select_from(StrategyLabExperiment)
                .where(StrategyLabExperiment.hypothesis_id == hypothesis_id)
            )
            return int(n or 0)
        finally:
            session.close()
    except Exception:
        return None


def _history_meta(candles: Sequence[Candle]) -> tuple[int | None, str | None]:
    if len(candles) < 2:
        return None, "historique < 1 an : indicatif (T12a absent)"
    span = int(candles[-1].time) - int(candles[0].time)
    if span < ONE_YEAR_SECONDS:
        return span, "historique < 1 an : indicatif (T12a absent)"
    return span, None


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
    min_oos_trades: int = DEFAULT_MIN_OOS_TRADES,
    hypothesis_id: str | None = None,
    commission_bps: float = BASE_COMMISSION_BPS,
    slippage_bps: float = BASE_SLIPPAGE_BPS,
    adverse_commission_bps: float = ADVERSE_COMMISSION_BPS,
    adverse_slippage_bps: float = ADVERSE_SLIPPAGE_BPS,
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
            pairs.append((label, variant, full, _layer_keys(conds)))

    candidates: list[AblationOosCandidate] = []
    n_folds = 0
    wf_kw = dict(
        symbol=symbol,
        timeframe=timeframe,
        mode=wf_mode,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
    )
    for label, baseline_rs, variant_rs, added in pairs:
        base_wf = _run_wf(
            candles,
            baseline_rs,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            **wf_kw,
        )
        var_wf = _run_wf(
            candles,
            variant_rs,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            **wf_kw,
        )
        base_adv = _run_wf(
            candles,
            baseline_rs,
            commission_bps=adverse_commission_bps,
            slippage_bps=adverse_slippage_bps,
            **wf_kw,
        )
        var_adv = _run_wf(
            candles,
            variant_rs,
            commission_bps=adverse_commission_bps,
            slippage_bps=adverse_slippage_bps,
            **wf_kw,
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
        adverse_exp_d = _delta(
            base_adv.oos_summary.get("mean_oos_expectancy"),
            var_adv.oos_summary.get("mean_oos_expectancy"),
        )
        fold_deltas = _fold_expectancy_deltas(base_wf, var_wf)
        compared = [d for d in fold_deltas if d is not None]
        positive = sum(1 for d in compared if d > 0)
        trades_base = int(base_wf.oos_summary.get("total_oos_trades") or 0)
        trades_var = int(var_wf.oos_summary.get("total_oos_trades") or 0)
        rec, reasons = decide_recommendation(
            oos_expectancy_delta=oos_exp_d,
            oos_profit_factor_delta=oos_pf_d,
            is_expectancy_delta=is_exp_d,
            total_oos_trades=max(trades_base, trades_var),
            n_folds=int(base_wf.oos_summary.get("n_folds") or 0),
            min_oos_trades=min_oos_trades,
            fold_oos_expectancy_deltas=fold_deltas,
            adverse_oos_expectancy_delta=adverse_exp_d,
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
                fold_oos_expectancy_deltas=fold_deltas,
                folds_positive_delta=positive if compared else None,
                folds_compared=len(compared) if compared else None,
                adverse_oos_expectancy_delta=adverse_exp_d,
            )
        )

    span, hist_warn = _history_meta(candles)
    hid = str(hypothesis_id).strip() if hypothesis_id else None
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
        hypothesis_id=hid or None,
        lineage_trial_count=_lineage_trial_count(hid),
        history_span_seconds=span,
        history_warning=hist_warn,
        min_oos_trades=min_oos_trades,
        cost_base_bps={
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
        },
        cost_adverse_bps={
            "commission_bps": adverse_commission_bps,
            "slippage_bps": adverse_slippage_bps,
        },
    )


__all__ = [
    "ADVERSE_COMMISSION_BPS",
    "ADVERSE_SLIPPAGE_BPS",
    "AblationOosCandidate",
    "AblationOosReport",
    "BASE_COMMISSION_BPS",
    "BASE_SLIPPAGE_BPS",
    "DEFAULT_MIN_OOS_TRADES",
    "decide_recommendation",
    "run_ablation_oos_study_on_candles",
]
