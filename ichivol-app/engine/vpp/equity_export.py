"""Month-end equity of the pre-registered continuous runs (R4 = P2 BTC/ETH/SOL; R1 = P1 U20), same seed/costs.

Deterministic re-run of the SAME runs as vpp.run (no new hypothesis). Equity convention = research_lab.sim:
cash + open positions marked at the bar close (the value at the last hourly bar of each UTC month).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from research_lab.sim import BASE_COST, simulate

from vpp import INITIAL_CAPITAL, SEED, U3, U20
from vpp.data import load_candles
from vpp.paper import paper_costs, paper_rules
from vpp.run import ART, CONTINUOUS, _git_head
from vpp.signals import build_feed, compute_all


def month_end(equity: list[tuple[int, float, float]]) -> list[dict]:
    last: dict[str, tuple[int, float, float]] = {}
    for t, eq, g in equity:
        last[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")] = (t, eq, g)
    out, prev = [], INITIAL_CAPITAL
    for m in sorted(last):
        t, eq, g = last[m]
        out.append({"month": m, "last_bar_utc": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                    "equity": eq, "gross_exposure": g, "return_pct": 100 * (eq / prev - 1)})
        prev = eq
    return out


def export() -> dict:
    sigs = compute_all(list(U20))
    candles = {s: load_candles(s, "1h")[0] for s in U20}
    feeds = {s: build_feed(candles[s], sigs[s]) for s in U20}
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_head": _git_head(), "seed": SEED,
           "initial_capital": INITIAL_CAPITAL, "window": "2021-07-01 -> 2024-12-31",
           "equity_convention": "cash + open positions marked at bar close; value at the month's last 1h bar",
           "cost_profile": "paper: commission 7.5 bps/side + per-symbol friction (vpp.paper.paper_costs)"}
    for name, syms in (("R4_P2_U3", U3), ("R1_P1_U20", U20)):
        res = simulate({s: feeds[s] for s in syms}, paper_rules(), BASE_COST, CONTINUOUS, initial=INITIAL_CAPITAL,
                       seed=SEED, cost_by_symbol=paper_costs(syms))
        body = month_end(res.equity)
        out[name] = {"symbols": list(syms), "n_trades": len(res.trades), "final_equity": res.equity[-1][1],
                     "costs": {s: c.__dict__ for s, c in paper_costs(syms).items()},
                     "month_end": body,
                     "sha256_month_end": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()}
    (ART / "vpp_equity_monthly.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = export()
    print(o["R4_P2_U3"]["n_trades"], o["R4_P2_U3"]["final_equity"], o["R1_P1_U20"]["n_trades"], o["R1_P1_U20"]["final_equity"])
