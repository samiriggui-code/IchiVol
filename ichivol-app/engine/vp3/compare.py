"""VP3 questions A / B / H / J — paired bar-return Δ + DSR scaffold."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vp3.bootstrap import BootstrapCI, bootstrap_mean_ci, paired_block_delta_ci
from vp3.dsr import deflated_sharpe_ratio
from vp3.metrics import N_YEAR, sharpe_ratio
from vp3.wf import WfReport, run_wf

# Provisional VP3 questions (§3)
COMPARE_QUESTIONS: dict[str, tuple[str, str]] = {
    "A": ("B1", "B0"),
    "B": ("B2", "B1"),
    "H": ("B5", "B2"),
    # J resolved after seeing best of B0–B6
}


@dataclass
class StrategyScore:
    strategy: str
    n_trades: int
    expectancy: float | None
    expectancy_ci: BootstrapCI | None
    n_positive_folds: int
    n_folds: int
    sharpe_agg: float | None
    dsr: float | None
    max_dd_worst_fold: float | None


@dataclass
class CompareReport:
    question: str
    bi: str
    bj: str
    symbol: str
    interval: str
    cost_profile: str
    score_i: StrategyScore
    score_j: StrategyScore
    delta_mean: BootstrapCI
    delta_sharpe: BootstrapCI
    bi_beats_bj: bool  # IC Δ mean excludes 0 in favor of Bi AND DSR(Bi)≥0.95

    def summary(self) -> dict[str, Any]:
        return asdict(self)


def _concat_returns(report: WfReport) -> list[float]:
    out: list[float] = []
    for f in report.folds:
        out.extend(f.bar_returns)
    return out


def _concat_nets(report: WfReport) -> list[float]:
    out: list[float] = []
    for f in report.folds:
        out.extend(f.trade_nets)
    return out


def _score(report: WfReport, *, n_trials: int = 1) -> StrategyScore:
    rets = _concat_returns(report)
    nets = _concat_nets(report)
    n_year = N_YEAR[report.interval]
    sr = sharpe_ratio(rets, n_year)
    # DSR uses non-annualised SR scale consistent with PSR se formula → use raw mean/std
    sr_raw = None
    if len(rets) >= 2:
        import math

        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        sr_raw = mu / math.sqrt(var) if var > 0 else None
    dsr = (
        deflated_sharpe_ratio(sr_raw, len(rets), n_trials=n_trials)
        if sr_raw is not None
        else None
    )
    exp_ci = bootstrap_mean_ci(nets) if nets else None
    mdds = [f.equity.max_drawdown for f in report.folds]
    return StrategyScore(
        strategy=report.strategy,
        n_trades=report.aggregate_trades,
        expectancy=report.aggregate_expectancy,
        expectancy_ci=exp_ci,
        n_positive_folds=report.n_positive_folds,
        n_folds=len(report.folds),
        sharpe_agg=sr,
        dsr=dsr,
        max_dd_worst_fold=min(mdds) if mdds else None,
    )


def compare_pair(
    bi: str,
    bj: str,
    *,
    symbol: str,
    interval: str,
    cost_profile: str = "base",
    root: Path | None = None,
    question: str = "",
    n_trials: int = 1,
    n_boot: int = 2000,
) -> CompareReport:
    """Run WF for Bi and Bj then paired Δ on concatenated bar returns."""
    ri = run_wf(bi, symbol=symbol, interval=interval, cost_profile=cost_profile, root=root)
    rj = run_wf(bj, symbol=symbol, interval=interval, cost_profile=cost_profile, root=root)
    ra = _concat_returns(ri)
    rb = _concat_returns(rj)
    d_mean = paired_block_delta_ci(ra, rb, interval=interval, n_boot=n_boot, metric="mean")
    d_sr = paired_block_delta_ci(ra, rb, interval=interval, n_boot=n_boot, metric="sharpe")
    score_i = _score(ri, n_trials=n_trials)
    score_j = _score(rj, n_trials=n_trials)
    beats = bool(
        d_mean.excludes_zero
        and d_mean.mean > 0
        and score_i.dsr is not None
        and score_i.dsr >= 0.95
    )
    return CompareReport(
        question=question or f"{bi}_vs_{bj}",
        bi=bi,
        bj=bj,
        symbol=symbol,
        interval=interval,
        cost_profile=cost_profile,
        score_i=score_i,
        score_j=score_j,
        delta_mean=d_mean,
        delta_sharpe=d_sr,
        bi_beats_bj=beats,
    )


def compare_question(
    question: str,
    *,
    symbol: str,
    interval: str,
    cost_profile: str = "base",
    root: Path | None = None,
    n_trials: int = 1,
    n_boot: int = 2000,
) -> CompareReport:
    if question not in COMPARE_QUESTIONS:
        raise ValueError(f"unknown question {question}; choose {sorted(COMPARE_QUESTIONS)}")
    bi, bj = COMPARE_QUESTIONS[question]
    return compare_pair(
        bi,
        bj,
        symbol=symbol,
        interval=interval,
        cost_profile=cost_profile,
        root=root,
        question=question,
        n_trials=n_trials,
        n_boot=n_boot,
    )
