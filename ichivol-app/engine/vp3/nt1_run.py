"""VP-NT1 — DSR with frozen N=24 (annualized σ across 24 hyps), then A/B/H compares.

Does NOT modify dsr.py / compare.py / B* rules.
σ / SR*_ann stay annualized; PSR is evaluated at BAR scale:
  SR*_bar = SR*_ann / √bpy ; DSR = PSR(SR_bar, n_obs, skew, kurt, SR*_bar).
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vp3.bootstrap import DEFAULT_BOOT_N, BootstrapCI, bootstrap_mean_ci, paired_block_delta_ci
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
MDD_LIMIT = -0.35  # maxDD < 35% ⇒ fold equity max_drawdown > -0.35


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


def concat_nets(report: WfReport) -> list[float]:
    out: list[float] = []
    for f in report.folds:
        out.extend(f.trade_nets)
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
    fold_max_dds: list[float] = field(default_factory=list)
    fold_expectancies: list[float | None] = field(default_factory=list)
    dsr: float | None = None


def hyp_trial_from_wf(report: WfReport) -> HypTrial:
    rets = concat_returns(report)
    skew, kurt = sample_skew_kurtosis(rets)
    sb = sr_bar(rets)
    sa = sr_ann_from_bar(sb, report.interval) if sb is not None else None
    mdds = [f.equity.max_drawdown for f in report.folds]
    fold_exps = [f.expectancy for f in report.folds]
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
        max_dd_worst_fold=min(mdds) if mdds else None,
        fold_max_dds=mdds,
        fold_expectancies=fold_exps,
    )


def dsr_bar_scaled(
    *,
    sr_b: float,
    n_obs: int,
    skew: float,
    kurt: float,
    interval: str,
    sr_star_ann: float,
) -> float | None:
    """DSR = PSR(SR_bar, SR*_bar) with SR*_bar = SR*_ann / √bpy.

    σ and SR*_ann stay annualized; PSR is evaluated at bar scale so n_obs
    (bar count) matches the SR units (no √bpy inflation of the z-score).
    """
    sr_star_bar = sr_bar_from_ann(sr_star_ann, interval)
    return probabilistic_sharpe_ratio(
        sr_b, n_obs, skew=skew, kurt=kurt, sr_benchmark=sr_star_bar
    )


# Back-compat alias removed intentionally — callers must use dsr_bar_scaled.


def sigma_and_sr_star(sr_anns: list[float], n_trials: int = N_T10B) -> tuple[float, float]:
    """σ of annualized SRs + E[max SR]_ann."""
    sigma = empirical_sr_std(sr_anns)
    return sigma, expected_max_sr(n_trials, sigma)


def fold_sign_instability(
    fold_expectancies: list[float | None],
    aggregate_expectancy: float | None,
) -> bool:
    """True if >3 folds have expectancy sign opposite to the aggregate."""
    if aggregate_expectancy is None or aggregate_expectancy == 0:
        return False
    agg_sign = 1 if aggregate_expectancy > 0 else -1
    opposite = 0
    for e in fold_expectancies:
        if e is None or e == 0:
            continue
        if (1 if e > 0 else -1) != agg_sign:
            opposite += 1
    return opposite > 3


def mdd_ok_all_folds(fold_max_dds: list[float], *, bi: str) -> bool:
    """§9 EDGE (6): maxDD < 35% on each WF fold; B0 exempted."""
    if bi == "B0":
        return True
    return all(dd > MDD_LIMIT for dd in fold_max_dds)


def verdict_compare(
    *,
    bi: str,
    bi_beats_bj: bool,
    dsr_i: float | None,
    n_trades_i: int,
    expectancy_i: float | None,
    expectancy_ci_excludes_zero: bool,
    n_positive_folds: int,
    fold_max_dds: list[float],
    fold_expectancies: list[float | None],
) -> str:
    """§9 verdict for a Bi≻Bj cell (no val/holdout look).

    EDGE = bi_beats_bj AND exp>0 AND IC trades excl.0 AND DSR≥0.95
           AND ≥5/7 positive folds AND N≥40 AND maxDD<35% each fold (B0 exempt).
    Else if instability (>3 folds opposite sign) → NON CONCLUANT (priority).
    Else if N<40 → NON CONCLUANT.
    Else → PAS D'EDGE.
    """
    n_ok = n_trades_i >= 40
    dsr_ok = dsr_i is not None and dsr_i >= 0.95
    folds_ok = n_positive_folds >= 5
    exp_ok = expectancy_i is not None and expectancy_i > 0
    mdd_ok = mdd_ok_all_folds(fold_max_dds, bi=bi)
    unstable = fold_sign_instability(fold_expectancies, expectancy_i)

    if (
        bi_beats_bj
        and exp_ok
        and expectancy_ci_excludes_zero
        and dsr_ok
        and folds_ok
        and n_ok
        and mdd_ok
    ):
        return "EDGE"
    if unstable:
        return "NON CONCLUANT"
    if not n_ok:
        return "NON CONCLUANT"
    return "PAS D'EDGE"


def apply_adverse_final(
    base_compares: list[dict[str, Any]],
    adverse_compares: list[dict[str, Any]],
) -> None:
    """EDGE in base but not EDGE in adverse → verdict_final = NON CONCLUANT (both)."""
    adv_by_key = {
        (c["question"], c["symbol"], c["interval"]): c for c in adverse_compares
    }
    for bc in base_compares:
        key = (bc["question"], bc["symbol"], bc["interval"])
        ac = adv_by_key[key]
        if bc["verdict"] == "EDGE" and ac["verdict"] != "EDGE":
            bc["verdict_final"] = "NON CONCLUANT"
            ac["verdict_final"] = "NON CONCLUANT"
        else:
            bc["verdict_final"] = bc["verdict"]
            ac["verdict_final"] = ac["verdict"]


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
    sr_star_bar = {tf: sr_bar_from_ann(sr_star_ann, tf) for tf in INTERVALS}

    for t in trials:
        if t.sr_bar is None:
            t.dsr = None
        else:
            t.dsr = dsr_bar_scaled(
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
                nets_i = concat_nets(ri)
                print(f"COMPARE {cost_profile} {q} {symbol} {interval}", flush=True)
                d_mean = paired_block_delta_ci(
                    ra, rb, interval=interval, n_boot=n_boot, metric="mean", times_a=ta, times_b=tb
                )
                d_sr = paired_block_delta_ci(
                    ra, rb, interval=interval, n_boot=n_boot, metric="sharpe", times_a=ta, times_b=tb
                )
                exp_ci = bootstrap_mean_ci(nets_i, n_boot=n_boot) if nets_i else BootstrapCI(
                    float("nan"), float("nan"), float("nan"), 0, False
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
                    expectancy_ci_excludes_zero=exp_ci.excludes_zero,
                    n_positive_folds=ti.n_positive_folds,
                    fold_max_dds=ti.fold_max_dds,
                    fold_expectancies=ti.fold_expectancies,
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
                        "expectancy_ci_i": asdict(exp_ci),
                        "bi_beats_bj": beats,
                        "verdict": verd,
                        "verdict_final": verd,  # overwritten after both profiles
                    }
                )

    return {
        "n_t10b": N_T10B,
        "cost_profile": cost_profile,
        "sigma_sr_ann": sigma,
        "sr_star_ann": sr_star_ann,
        "sr_star_bar": sr_star_bar,
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
        print(
            f"DONE profile={profile} σ={block['sigma_sr_ann']:.6g} "
            f"SR*_ann={block['sr_star_ann']:.6g} compares={len(block['compares'])}",
            flush=True,
        )
    apply_adverse_final(all_rows[0]["compares"], all_rows[1]["compares"])
    out_path.write_text("", encoding="utf-8")
    with out_path.open("a", encoding="utf-8") as f:
        for block in all_rows:
            f.write(json.dumps(block, default=str) + "\n")
    out_path.with_suffix(".json").write_text(
        json.dumps(all_rows, indent=2, default=str), encoding="utf-8"
    )
    print(f"WROTE {out_path} and {out_path.with_suffix('.json')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
