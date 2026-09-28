"""RS-D1 — run unique pré-enregistré (RS-03) → docs/rs-artifacts/rsd1_results.json + rsd1_trades.json.

Usage (depuis ichivol-app/engine) : ``python -m rs.run``
Aucun paramètre libre : règles, coûts, fenêtres et critères viennent de ``rs/__init__.py`` (RS-03).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rs import DATA_END_EXCL, HYPOTHESIS_ID, INITIAL_CAPITAL, PROTOCOL_VERSION, SCORE_START, SEED, SYMBOLS
from rs.baselines import passive
from rs.costs import cost_profile
from rs.data import load_symbol
from rs.donchian import simulate
from rs.metrics import boot_mean_ci, monthly_returns, summary, trade_stats, verdict

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "docs" / "rs-artifacts"
B7P_EQUITY = REPO / "docs" / "vpp-artifacts" / "vpp_equity_monthly.json"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # pragma: no cover
        return "unknown"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _b7p_monthly() -> tuple[dict[str, float], dict[str, Any]]:
    """B7-P = R4 de #159 (P2, BTC/ETH/SOL 1h, capital commun) : rendements de fin de mois."""
    d = json.loads(B7P_EQUITY.read_text(encoding="utf-8"))
    r4 = d["R4_P2_U3"]
    prev = float(d["initial_capital"])
    out: dict[str, float] = {}
    for row in r4["month_end"]:
        out[row["month"]] = row["equity"] / prev - 1.0
        prev = row["equity"]
    meta = {"source": str(B7P_EQUITY.relative_to(REPO)), "sha256": _sha(B7P_EQUITY), "git_head": d["git_head"],
            "final_equity": r4["final_equity"], "n_trades": r4["n_trades"]}
    return out, meta


def _yearly(eq) -> dict[str, float]:
    ends: dict[str, float] = {}
    for t, e, _ in eq:
        ends[datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y")] = e
    out, prev = {}, INITIAL_CAPITAL
    for y in sorted(ends):
        out[y] = ends[y] / prev - 1.0
        prev = ends[y]
    return out


def main() -> dict[str, Any]:
    data, digests = {}, {}
    for s in SYMBOLS:
        data[s], digests[s] = load_symbol(s)
        assert data[s][-1].time < DATA_END_EXCL

    paper, adverse = cost_profile("paper"), cost_profile("adverse")
    base = simulate(data, paper)
    adv = simulate(data, adverse)
    stress = simulate(data, paper, exec_delay=2)

    s_base = summary(base.equity, INITIAL_CAPITAL)
    s_adv = summary(adv.equity, INITIAL_CAPITAL)
    s_stress = summary(stress.equity, INITIAL_CAPITAL)
    t_base = trade_stats(base.trades)

    e = s_base["exposure_mean"]  # RS-03 §7 : e = exposition moyenne réalisée de RS-D1, calcul mécanique
    b0f = passive(data, paper, weight=1.0, rebalance_monthly=False)
    b0e = passive(data, paper, weight=e, rebalance_monthly=True)
    s_b0f = summary(b0f, INITIAL_CAPITAL)
    s_b0e = summary(b0e, INITIAL_CAPITAL)

    m_rs = monthly_returns(base.equity, INITIAL_CAPITAL)
    m_b0f = monthly_returns(b0f, INITIAL_CAPITAL)
    m_b0e = monthly_returns(b0e, INITIAL_CAPITAL)
    m_b7p, b7p_meta = _b7p_monthly()
    common = sorted(set(m_rs) & set(m_b7p))
    assert len(common) == len(m_rs) == len(m_b7p), (len(common), len(m_rs), len(m_b7p))

    monthly_ci = boot_mean_ci([m_rs[k] for k in sorted(m_rs)])
    delta_b7 = boot_mean_ci([m_rs[k] - m_b7p[k] for k in common])
    delta_b0e = boot_mean_ci([m_rs[k] - m_b0e[k] for k in common])

    v = verdict(base=s_base, adverse_net_return=s_adv["net_return"], monthly_ci=monthly_ci,
                delta_b7_ci=delta_b7, calmar_b0e=s_b0e["calmar"], trades=t_base)

    b7p_final = b7p_meta["final_equity"]
    result: dict[str, Any] = {
        "hypothesis_id": HYPOTHESIS_ID,
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "seed": SEED,
        "window": {"score_start": datetime.fromtimestamp(SCORE_START, tz=timezone.utc).isoformat(),
                   "data_end_excl": datetime.fromtimestamp(DATA_END_EXCL, tz=timezone.utc).isoformat()},
        "data": {s: {"sha256_manifest": digests[s], "bars": len(data[s]),
                     "first": datetime.fromtimestamp(data[s][0].time, tz=timezone.utc).isoformat(),
                     "last": datetime.fromtimestamp(data[s][-1].time, tz=timezone.utc).isoformat()}
                 for s in SYMBOLS},
        "rs_d1": {
            "base": {**s_base, "trades": t_base, "rejections": base.rejections, "halt_days": base.halt_days,
                     "yearly": _yearly(base.equity)},
            "adverse": {**s_adv, "trades": trade_stats(adv.trades)},
            "stress_exec_delay_2": {**s_stress, "trades": trade_stats(stress.trades)},
        },
        "references": {
            "B0_F": {**s_b0f, "yearly": _yearly(b0f)},
            "B0_E": {**s_b0e, "weight_e": e, "yearly": _yearly(b0e)},
            "B7_P": {**b7p_meta, "net_return": b7p_final / INITIAL_CAPITAL - 1.0},
            "cash": {"net_return": 0.0},
        },
        "monthly": {"months": common, "RS_D1": [m_rs[k] for k in common], "B7_P": [m_b7p[k] for k in common],
                    "B0_F": [m_b0f.get(k) for k in common], "B0_E": [m_b0e.get(k) for k in common]},
        "intervals": {"rs_monthly_mean": monthly_ci, "delta_vs_b7p": delta_b7, "delta_vs_b0e": delta_b0e},
        "verdict": v,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "rsd1_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    trades = {
        "base": [asdict(t) for t in base.trades],
        "adverse": [asdict(t) for t in adv.trades],
        "stress_exec_delay_2": [asdict(t) for t in stress.trades],
    }
    (OUT_DIR / "rsd1_trades.json").write_text(json.dumps(trades, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    r = main()
    b = r["rs_d1"]["base"]
    print(json.dumps({"verdict": r["verdict"], "net_return": b["net_return"], "max_dd": b["max_dd"],
                      "n_closed": b["trades"]["n_closed"]}, indent=2, ensure_ascii=False))
