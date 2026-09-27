"""VP-J1 — N=36 DSR (B0–B7) + A/B/H/J compares. Reuses vp3.nt1_run helpers.

Does NOT modify dsr.py / compare.py / B* rules (entries already fixed pre-run).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vp3.bootstrap import DEFAULT_BOOT_N, BootstrapCI, bootstrap_mean_ci, paired_block_delta_ci
from vp3.compare import COMPARE_QUESTIONS
from vp3.nt1_run import (
    INTERVALS,
    SYMBOLS,
    apply_adverse_final,
    concat_nets,
    concat_returns,
    concat_times,
    dsr_bar_scaled,
    hyp_trial_from_wf,
    sigma_and_sr_star,
    sr_bar_from_ann,
    verdict_compare,
)
from vp3.wf import WfReport, run_wf

N_T10B = 36
STRATEGIES = ("B0", "B1", "B2", "B5", "B6", "B7")
QUESTIONS_ABH = ("A", "B", "H")
BJ_POOL = ("B0", "B1", "B2", "B5", "B6")  # simplicity order for ties
BJ_RANK = {s: i for i, s in enumerate(BJ_POOL)}


def select_bj(trial_index: dict[tuple[str, str, str], Any], symbol: str, interval: str) -> str:
    """Bj = argmax DSR_i among BJ_POOL; ties → simplest (B0<B1<B2<B5<B6)."""
    best_s = "B0"
    best_dsr = float("-inf")
    best_rank = 999
    for s in BJ_POOL:
        t = trial_index[(s, symbol, interval)]
        d = t.dsr
        if d is None:
            d = float("-inf")
        rank = BJ_RANK[s]
        if d > best_dsr or (d == best_dsr and rank < best_rank):
            best_dsr = d
            best_rank = rank
            best_s = s
    return best_s


def _one_compare(
    *,
    question: str,
    bi: str,
    bj: str,
    symbol: str,
    interval: str,
    cost_profile: str,
    cache: dict[tuple[str, str, str], WfReport],
    trial_index: dict,
    n_boot: int,
) -> dict[str, Any]:
    ri = cache[(bi, symbol, interval)]
    rj = cache[(bj, symbol, interval)]
    ra, rb = concat_returns(ri), concat_returns(rj)
    ta, tb = concat_times(ri), concat_times(rj)
    nets_i = concat_nets(ri)
    print(f"COMPARE {cost_profile} {question} {bi}vs{bj} {symbol} {interval}", flush=True)
    d_mean = paired_block_delta_ci(
        ra, rb, interval=interval, n_boot=n_boot, metric="mean", times_a=ta, times_b=tb
    )
    d_sr = paired_block_delta_ci(
        ra, rb, interval=interval, n_boot=n_boot, metric="sharpe", times_a=ta, times_b=tb
    )
    exp_ci = (
        bootstrap_mean_ci(nets_i, n_boot=n_boot)
        if nets_i
        else BootstrapCI(float("nan"), float("nan"), float("nan"), 0, False)
    )
    ti = trial_index[(bi, symbol, interval)]
    tj = trial_index[(bj, symbol, interval)]
    beats = bool(
        d_mean.excludes_zero and d_mean.mean > 0 and ti.dsr is not None and ti.dsr >= 0.95
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
    return {
        "question": question,
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
        "verdict_final": verd,
    }


def run_profile(
    cost_profile: str,
    *,
    n_boot: int = DEFAULT_BOOT_N,
    root: Path | None = None,
    bj_map: dict[tuple[str, str], str] | None = None,
    build_bj_map: bool = False,
) -> dict[str, Any]:
    cache: dict[tuple[str, str, str], WfReport] = {}
    trials = []
    for strategy in STRATEGIES:
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                print(f"WF {cost_profile} {strategy} {symbol} {interval}", flush=True)
                rep = run_wf(
                    strategy,
                    symbol=symbol,
                    interval=interval,
                    cost_profile=cost_profile,
                    root=root,
                )
                cache[(strategy, symbol, interval)] = rep
                trials.append(hyp_trial_from_wf(rep))

    assert len(trials) == N_T10B, f"expected {N_T10B}, got {len(trials)}"
    sr_anns = [t.sr_ann for t in trials if t.sr_ann is not None]
    sigma, sr_star_ann = sigma_and_sr_star(sr_anns, N_T10B)
    sr_star_bar = {tf: sr_bar_from_ann(sr_star_ann, tf) for tf in INTERVALS}

    for t in trials:
        t.dsr = (
            None
            if t.sr_bar is None
            else dsr_bar_scaled(
                sr_b=t.sr_bar,
                n_obs=t.n_obs,
                skew=t.skew,
                kurt=t.kurt,
                interval=t.interval,
                sr_star_ann=sr_star_ann,
            )
        )

    trial_index = {(t.strategy, t.symbol, t.interval): t for t in trials}

    if build_bj_map:
        bj_map = {}
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                bj_map[(symbol, interval)] = select_bj(trial_index, symbol, interval)
                print(f"BJ {symbol} {interval} = {bj_map[(symbol, interval)]}", flush=True)
    assert bj_map is not None

    compares: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            for q in QUESTIONS_ABH:
                bi, bj = COMPARE_QUESTIONS[q]
                compares.append(
                    _one_compare(
                        question=q,
                        bi=bi,
                        bj=bj,
                        symbol=symbol,
                        interval=interval,
                        cost_profile=cost_profile,
                        cache=cache,
                        trial_index=trial_index,
                        n_boot=n_boot,
                    )
                )
            bj = bj_map[(symbol, interval)]
            compares.append(
                _one_compare(
                    question="J",
                    bi="B7",
                    bj=bj,
                    symbol=symbol,
                    interval=interval,
                    cost_profile=cost_profile,
                    cache=cache,
                    trial_index=trial_index,
                    n_boot=n_boot,
                )
            )

    return {
        "n_t10b": N_T10B,
        "cost_profile": cost_profile,
        "sigma_sr_ann": sigma,
        "sr_star_ann": sr_star_ann,
        "sr_star_bar": sr_star_bar,
        "bj_map": {f"{s}|{i}": bj for (s, i), bj in bj_map.items()},
        "trials": [asdict(t) for t in trials],
        "compares": compares,
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/vp3_j1_results.jsonl")
    n_boot = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BOOT_N
    out_path.write_text("", encoding="utf-8")
    base = run_profile("base", n_boot=n_boot, build_bj_map=True)
    bj_map = {tuple(k.split("|", 1)): v for k, v in base["bj_map"].items()}
    adv = run_profile("adverse", n_boot=n_boot, bj_map=bj_map, build_bj_map=False)
    apply_adverse_final(base["compares"], adv["compares"])
    all_rows = [base, adv]
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
