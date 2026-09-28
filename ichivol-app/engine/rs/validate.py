"""RS-D1 — validation 2025, run unique (amendement VP0-2026-09-28d).

Usage (depuis ichivol-app/engine) : ``python -m rs.validate``
Règles RS-03 inchangées ; seules la fenêtre (2025) et la troncature (< 2026-01-01) changent.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rs import (
    HYPOTHESIS_ID,
    INITIAL_CAPITAL,
    SEED,
    SYMBOLS,
    VAL_B0E_WEIGHT,
    VAL_DATA_END_EXCL,
    VAL_MIN_TRADES,
    VAL_SCORE_START,
)
from rs.baselines import passive
from rs.costs import cost_profile
from rs.data import load_symbol
from rs.donchian import simulate
from rs.metrics import boot_mean_ci, monthly_returns, summary, trade_stats
from rs.run import OUT_DIR, _git_head

AMENDMENT = "VP0-2026-09-28d"


def validation_verdict(base: dict[str, Any], adverse: dict[str, Any], b0e: dict[str, Any], n_closed: int) -> dict[str, Any]:
    if b0e["cagr"] is not None and b0e["cagr"] > 0:
        v4 = base["calmar"] is not None and base["calmar"] > b0e["calmar"]
        v4_rule = "calmar"
    else:
        v4 = base["net_return"] > b0e["net_return"]
        v4_rule = "net_return (CAGR B0-E <= 0)"
    c = {
        "V1": base["net_return"] > 0,
        "V2": base["max_dd"] >= -0.15,
        "V3": adverse["net_return"] > 0,
        "V4": v4,
        "V5": n_closed >= VAL_MIN_TRADES,
    }
    if not c["V1"] or not c["V2"]:
        v = "ÉCHEC"
    elif all(c.values()):
        v = "VALIDÉ 2025"
    else:
        v = "NON CONCLUANT"
    return {"criteria": c, "v4_rule": v4_rule, "verdict": v}


def main() -> dict[str, Any]:
    data, digests = {}, {}
    for s in SYMBOLS:
        data[s], digests[s] = load_symbol(s, end_excl=VAL_DATA_END_EXCL)
        assert data[s][-1].time < VAL_DATA_END_EXCL

    paper, adverse = cost_profile("paper"), cost_profile("adverse")
    kw = dict(score_start=VAL_SCORE_START, data_end_excl=VAL_DATA_END_EXCL)
    base = simulate(data, paper, **kw)
    adv = simulate(data, adverse, **kw)
    stress = simulate(data, paper, exec_delay=2, **kw)
    # aucun trade ne peut précéder la fenêtre de score
    assert all(t.entry_time >= VAL_SCORE_START for t in base.trades)

    s_base = summary(base.equity, INITIAL_CAPITAL)
    s_adv = summary(adv.equity, INITIAL_CAPITAL)
    s_stress = summary(stress.equity, INITIAL_CAPITAL)
    t_base = trade_stats(base.trades)

    b0f = passive(data, paper, weight=1.0, rebalance_monthly=False, score_start=VAL_SCORE_START)
    b0e = passive(data, paper, weight=VAL_B0E_WEIGHT, rebalance_monthly=True, score_start=VAL_SCORE_START)
    s_b0f = summary(b0f, INITIAL_CAPITAL)
    s_b0e = summary(b0e, INITIAL_CAPITAL)

    m_rs = monthly_returns(base.equity, INITIAL_CAPITAL)
    m_b0e = monthly_returns(b0e, INITIAL_CAPITAL)
    months = sorted(m_rs)
    v = validation_verdict(s_base, s_adv, s_b0e, t_base["n_closed"])

    for d in (s_base, s_adv, s_stress, s_b0f, s_b0e):
        d.pop("folds", None)  # plis WF = développement, sans objet en 2025

    result: dict[str, Any] = {
        "hypothesis_id": HYPOTHESIS_ID,
        "amendment": AMENDMENT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "seed": SEED,
        "window": {"score_start": datetime.fromtimestamp(VAL_SCORE_START, tz=timezone.utc).isoformat(),
                   "data_end_excl": datetime.fromtimestamp(VAL_DATA_END_EXCL, tz=timezone.utc).isoformat()},
        "data": {s: {"sha256_manifest": digests[s], "bars": len(data[s]),
                     "last": datetime.fromtimestamp(data[s][-1].time, tz=timezone.utc).isoformat()} for s in SYMBOLS},
        "rs_d1": {
            "base": {**s_base, "trades": t_base, "rejections": base.rejections, "halt_days": base.halt_days},
            "adverse": {**s_adv, "trades": trade_stats(adv.trades)},
            "stress_exec_delay_2": {**s_stress, "trades": trade_stats(stress.trades)},
        },
        "references": {"B0_F": s_b0f, "B0_E": {**s_b0e, "weight_e_frozen": VAL_B0E_WEIGHT}, "cash": {"net_return": 0.0}},
        "monthly": {"months": months, "RS_D1": [m_rs[k] for k in months], "B0_E": [m_b0e.get(k) for k in months]},
        "descriptive": {
            "rs_monthly_mean": boot_mean_ci([m_rs[k] for k in months]),
            "delta_vs_b0e": boot_mean_ci([m_rs[k] - m_b0e[k] for k in months if k in m_b0e]),
        },
        "verdict": v,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "rsd1_val2025_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "rsd1_val2025_trades.json").write_text(
        json.dumps({"base": [asdict(t) for t in base.trades], "adverse": [asdict(t) for t in adv.trades]}, indent=1),
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    r = main()
    b = r["rs_d1"]["base"]
    print(json.dumps({"verdict": r["verdict"], "net_return": b["net_return"], "max_dd": b["max_dd"],
                      "n_closed": b["trades"]["n_closed"]}, indent=2, ensure_ascii=False))
