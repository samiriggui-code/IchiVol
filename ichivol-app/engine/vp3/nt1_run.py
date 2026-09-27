"""VP-NT1 — DSR with frozen N=24 (annualized σ across 24 hyps), then A/B/H compares.

Does NOT modify dsr.py / compare.py / B* rules. Uses expected_max_sr +
probabilistic_sharpe_ratio from vp3.dsr, and paired_block_delta_ci from bootstrap.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vp3.bootstrap import DEFAULT_BOOT_N, BootstrapCI, paired_block_delta_ci
from vp3.compare import COMPARE_QUESTIONS
from vp3.dsr import (
    empirical_sr_std,
    expected_max_sr,
    probabilistic_sharpe_ratio,
    sample_skew_kurtosis,
)
from vp3.metrics import N_YEAR
from vp3.wf import WfReport, run_wf

N_T10B = 24
STRATEGIES = ("B0", "B1", "B2", "B5")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
INTERVALS = ("1h", "4h")
QUESTIONS = ("A", "B", "H")
BPY: dict[str, float] = {"1h": float(N_YEAR["1h"]), "4h": float(N_YEAR["4h"])}  # 8760 / 2190


def bars_per_year(interval: str) -> float:
    return BPY[interval]


def sr_bar(returns: list[float]) -> float | None:
    """Per-bar Sharpe (rf=0): mean/std sample."""
    if len(returns) < 2:
        return None
    mu = sum(returns) / len(returns)
    var = sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)
    if var <= 0:
        return None
    return mu / math.sqrt(var)


def sr_ann_from_bar(sr_b: float, interval: str) -> float:
    return sr_b * math.sqrt(bars_per_year(interval))


def sr_bar_from_ann(sr_a: float, interval: str) -> float:
    return sr_a / math.sqrt(bars_per_year(interval))


def concat_returns(report: WfReport) -> list[float]:
    out: list[float] = []
    for f in report.folds:
        out.extend(f.bar_returns)
    return out


def concat_times(report: WfReport) -> list[int]:
    out: list[int] = []
    for f in report.folds:
        out.extend(f.bar_times)
    return out


@dataclass
class HypTrial:
    strategy: str
    symbol: str
    interval: str
    cost_profile: str
    n_obs: int
    sr_bar: float | None
    sr_ann: float | None
    skew: float
    kurt: float
    n_trades: int
    expectancy: float | None
    n_positive_folds: int
    n_folds: int
    max_dd_worst_fold: float | None
    dsr: float | None = None


def _worst_mdd(report: WfReport) -> float | None:
    mdds = [f.equity.max_drawdown for f in report.folds]
    return min(mdds) if mdds else None


def hyp_trial_from_wf(report: WfReport) -> HypTrial:
    rets = concat_returns(report)
    skew, kurt = sample_skew_kurtosis(rets)
    sb = sr_bar(rets)
    sa = sr_ann_from_bar(sb, report.interval) if sb is not None else None
    return HypTrial(
        strategy=report.strategy,
        symbol=report.symbol,
        interval=report.interval,
        cost_profile=report.cost_profile,
        n_obs=len(rets),
        sr_bar=sb,
        sr_ann=sa,
        skew=skew,
        kurt=kurt,
        n_trades=report.aggregate_trades,
        expectancy=report.aggregate_expectancy,
        n_positive_folds=report.n_positive_folds,
        n_folds=len(report.folds),
        max_dd_worst_fold=_worst_mdd(report),
    )


def dsr_ann_scaled(
    *,
    sr_b: float,
    n_obs: int,
    skew: float,
    kurt: float,
    interval: str,
    sr_star_ann: float,
) -> float | None:
    """DSR on the annualized scale (same σ / SR* space as the 24-trial ledger).

    SR_ann = SR_bar × √bpy ; SR*_ann = E[max SR]_ann.
    PSR is evaluated on (SR_ann, SR*_ann) so that the same SR_ann yields the
    same DSR at equal n_obs across 1h/4h (bar-scale PSR is not scale-invariant
    via SR*_bar = SR*_ann/√bpy because the SE term depends non-linearly on SR).
    """
    sr_a = sr_ann_from_bar(sr_b, interval)
    return probabilistic_sharpe_ratio(
        sr_a, n_obs, skew=skew, kurt=kurt, sr_benchmark=sr_star_ann
    )


def sigma_and_sr_star(sr_anns: list[float], n_trials: int = N_T10B) -> tuple[float, float]:
    """σ of annualized SRs + E[max SR]_ann."""
    sigma = empirical_sr_std(sr_anns)
    return sigma, expected_max_sr(n_trials, sigma)


def verdict_compare(
    *,
    bi: str,
    bi_beats_bj: bool,
    dsr_i: float | None,
    n_trades_i: int,
    expectancy_i: float | None,
    n_positive_folds: int,
    delta_excludes_zero: bool,
    delta_mean: float,
    max_dd_worst: float | None,
) -> str:
    """§9 verdict for a Bi≻Bj cell (reportable; no look at val/holdout)."""
    if bi == "B0":
        # B0 as Bi never in A/B/H (Bi is B1/B2/B5)
        pass
    n_ok = n_trades_i >= 40
    dsr_ok = dsr_i is not None and dsr_i >= 0.95
    folds_ok = n_positive_folds >= 5
    folds_fail = n_positive_folds < 3
    exp_ok = expectancy_i is not None and expectancy_i > 0
    mdd_ok = max_dd_worst is None or max_dd_worst > -0.35  # maxDD < 35% ⇒ dd > -0.35

    if bi_beats_bj and n_ok and exp_ok and folds_ok and mdd_ok and dsr_ok:
        return "EDGE"
    if not n_ok or not delta_excludes_zero:
        return "NON CONCLUANT"
    if n_ok and (not exp_ok or not dsr_ok or folds_fail or delta_mean <= 0):
        return "PAS D'EDGE"
    return "NON CONCLUANT"


def run_profile(
    cost_profile: str,
    *,
    n_boot: int = DEFAULT_BOOT_N,
    root: Path | None = None,
) -> dict[str, Any]:
    """Pass 1 (24 WF) + pass 2 (18 compares) for one cost profile."""
    cache: dict[tuple[str, str, str], WfReport] = {}
    trials: list[HypTrial] = []

    for strategy in STRATEGIES:
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                key = (strategy, symbol, interval)
                print(f"WF {cost_profile} {strategy} {symbol} {interval}", flush=True)
                rep = run_wf(
                    strategy,
                    symbol=symbol,
                    interval=interval,
                    cost_profile=cost_profile,
                    root=root,
                )
                cache[key] = rep
                trials.append(hyp_trial_from_wf(rep))

    assert len(trials) == N_T10B, f"expected {N_T10B} trials, got {len(trials)}"
    sr_anns = [t.sr_ann for t in trials if t.sr_ann is not None]
    if len(sr_anns) < 2:
        raise RuntimeError("need ≥2 finite SR_ann for σ")
    sigma, sr_star_ann = sigma_and_sr_star(sr_anns, N_T10B)

    for t in trials:
        if t.sr_bar is None:
            t.dsr = None
        else:
            t.dsr = dsr_ann_scaled(
                sr_b=t.sr_bar,
                n_obs=t.n_obs,
                skew=t.skew,
                kurt=t.kurt,
                interval=t.interval,
                sr_star_ann=sr_star_ann,
            )

    trial_index = {(t.strategy, t.symbol, t.interval): t for t in trials}
    compares: list[dict[str, Any]] = []

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            for q in QUESTIONS:
                bi, bj = COMPARE_QUESTIONS[q]
                ri = cache[(bi, symbol, interval)]
                rj = cache[(bj, symbol, interval)]
                ra, rb = concat_returns(ri), concat_returns(rj)
                ta, tb = concat_times(ri), concat_times(rj)
                print(f"COMPARE {cost_profile} {q} {symbol} {interval}", flush=True)
                d_mean = paired_block_delta_ci(
                    ra, rb, interval=interval, n_boot=n_boot, metric="mean", times_a=ta, times_b=tb
                )
                d_sr = paired_block_delta_ci(
                    ra, rb, interval=interval, n_boot=n_boot, metric="sharpe", times_a=ta, times_b=tb
                )
                ti = trial_index[(bi, symbol, interval)]
                tj = trial_index[(bj, symbol, interval)]
                beats = bool(
                    d_mean.excludes_zero
                    and d_mean.mean > 0
                    and ti.dsr is not None
                    and ti.dsr >= 0.95
                )
                verd = verdict_compare(
                    bi=bi,
                    bi_beats_bj=beats,
                    dsr_i=ti.dsr,
                    n_trades_i=ti.n_trades,
                    expectancy_i=ti.expectancy,
                    n_positive_folds=ti.n_positive_folds,
                    delta_excludes_zero=d_mean.excludes_zero,
                    delta_mean=d_mean.mean,
                    max_dd_worst=ti.max_dd_worst_fold,
                )
                compares.append(
                    {
                        "question": q,
                        "bi": bi,
                        "bj": bj,
                        "symbol": symbol,
                        "interval": interval,
                        "cost_profile": cost_profile,
                        "score_i": asdict(ti),
                        "score_j": asdict(tj),
                        "delta_mean": asdict(d_mean),
                        "delta_sharpe": asdict(d_sr),
                        "bi_beats_bj": beats,
                        "verdict": verd,
                    }
                )

    return {
        "n_t10b": N_T10B,
        "cost_profile": cost_profile,
        "sigma_sr_ann": sigma,
        "sr_star_ann": sr_star_ann,
        "trials": [asdict(t) for t in trials],
        "compares": compares,
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/vp3_nt1_results.jsonl")
    n_boot = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BOOT_N
    out_path.write_text("", encoding="utf-8")
    all_rows: list[dict[str, Any]] = []
    for profile in ("base", "adverse"):
        block = run_profile(profile, n_boot=n_boot)
        all_rows.append(block)
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(block, default=str) + "\n")
        print(
            f"DONE profile={profile} σ={block['sigma_sr_ann']:.6g} "
            f"SR*_ann={block['sr_star_ann']:.6g} compares={len(block['compares'])}",
            flush=True,
        )
    out_path.with_suffix(".json").write_text(
        json.dumps(all_rows, indent=2, default=str), encoding="utf-8"
    )
    print(f"WROTE {out_path} and {out_path.with_suffix('.json')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
