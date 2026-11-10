"""VP-BR — run pré-enregistré de l'entrée sur repli (docs/REPLI-KIJUN-PREENREGISTREMENT-2026-11-10.md).

BR, B7 (entrée actuelle) et B0 (buy & hold) sur BTC/ETH/SOL 1h, plis WF1–WF7, coûts base puis adverse.
DSR : N = 51 (T10b), σ = écart-type des Sharpe annualisés des 9 séries du run (même méthode que NT1/J1).
Verdict d'une hypothèse BR = §9 (1)–(6) sur BR seule, EDGE en base non confirmé en adverse → NON CONCLUANT.
Les comparaisons appariées BR vs B7 et BR vs B0 sont rapportées à côté, sans entrer dans le verdict.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vp3 import N_T10B_REPLI
from vp3.bootstrap import DEFAULT_BOOT_N, bootstrap_mean_ci, paired_block_delta_ci
from vp3.nt1_run import (
    SYMBOLS,
    concat_nets,
    concat_returns,
    concat_times,
    dsr_bar_scaled,
    hyp_trial_from_wf,
    sigma_and_sr_star,
    verdict_compare,
)
from vp3.wf import WfReport, run_wf

STRATEGIES = ("BR", "B7", "B0")
INTERVAL = "1h"
BASELINES = ("B7", "B0")


def run_profile(cost_profile: str, *, n_boot: int = DEFAULT_BOOT_N, root: Path | None = None) -> dict[str, Any]:
    cache: dict[tuple[str, str], WfReport] = {}
    trials = []
    for strategy in STRATEGIES:
        for symbol in SYMBOLS:
            print(f"WF {cost_profile} {strategy} {symbol} {INTERVAL}", flush=True)
            rep = run_wf(strategy, symbol=symbol, interval=INTERVAL, cost_profile=cost_profile, root=root)
            cache[(strategy, symbol)] = rep
            trials.append(hyp_trial_from_wf(rep))

    sigma, sr_star_ann = sigma_and_sr_star([t.sr_ann for t in trials if t.sr_ann is not None], N_T10B_REPLI)
    for t in trials:
        t.dsr = None if t.sr_bar is None else dsr_bar_scaled(
            sr_b=t.sr_bar, n_obs=t.n_obs, skew=t.skew, kurt=t.kurt, interval=t.interval, sr_star_ann=sr_star_ann
        )
    index = {(t.strategy, t.symbol): t for t in trials}

    hypotheses: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        br, rep = index[("BR", symbol)], cache[("BR", symbol)]
        nets = concat_nets(rep)
        exp_ci = bootstrap_mean_ci(nets, n_boot=n_boot) if nets else None
        verdict = verdict_compare(
            bi="BR",
            bi_beats_bj=True,  # verdict on BR alone; paired comparisons are reported below
            dsr_i=br.dsr,
            n_trades_i=br.n_trades,
            expectancy_i=br.expectancy,
            expectancy_ci_excludes_zero=bool(exp_ci and exp_ci.excludes_zero),
            n_positive_folds=br.n_positive_folds,
            fold_max_dds=br.fold_max_dds,
            fold_expectancies=br.fold_expectancies,
        )
        exits: dict[str, int] = {}
        for fold in rep.folds:
            for reason, n in fold.exit_reasons.items():
                exits[reason] = exits.get(reason, 0) + n
        paired = {}
        for baseline in BASELINES:
            other = cache[(baseline, symbol)]
            print(f"COMPARE {cost_profile} BR vs {baseline} {symbol}", flush=True)
            delta = paired_block_delta_ci(
                concat_returns(rep), concat_returns(other), interval=INTERVAL, n_boot=n_boot, metric="mean",
                times_a=concat_times(rep), times_b=concat_times(other),
            )
            paired[baseline] = {
                "delta_mean": asdict(delta),
                "br_beats": bool(delta.excludes_zero and delta.mean > 0 and br.dsr is not None and br.dsr >= 0.95),
            }
        hypotheses.append({
            "hypothesis_id": f"BR-{symbol}-{INTERVAL}-{cost_profile}",
            "symbol": symbol,
            "cost_profile": cost_profile,
            "verdict": verdict,
            "verdict_final": verdict,
            "expectancy_ci": asdict(exp_ci) if exp_ci else None,
            "exit_reasons": exits,
            "paired": paired,
        })

    return {
        "n_t10b": N_T10B_REPLI,
        "cost_profile": cost_profile,
        "sigma_sr_ann": sigma,
        "sr_star_ann": sr_star_ann,
        "trials": [asdict(t) for t in trials],
        "hypotheses": hypotheses,
    }


def apply_adverse(base: dict[str, Any], adverse: dict[str, Any]) -> None:
    """§9 : EDGE en base mais pas en adverse → NON CONCLUANT (les deux)."""
    adv = {h["symbol"]: h for h in adverse["hypotheses"]}
    for h in base["hypotheses"]:
        a = adv[h["symbol"]]
        if h["verdict"] == "EDGE" and a["verdict"] != "EDGE":
            h["verdict_final"] = a["verdict_final"] = "NON CONCLUANT"


def main() -> int:
    out_path = Path(sys.argv[1])
    n_boot = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BOOT_N
    base = run_profile("base", n_boot=n_boot)
    adverse = run_profile("adverse", n_boot=n_boot)
    apply_adverse(base, adverse)
    out_path.write_text(json.dumps([base, adverse], indent=2, default=str), encoding="utf-8")
    print(f"WROTE {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
