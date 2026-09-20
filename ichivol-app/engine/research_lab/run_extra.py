import csv, json, subprocess, hashlib, dataclasses
from research_lab.build import build, PKL
from research_lab.data import CACHE
from research_lab.metrics import summarize
from research_lab.run import WINDOWS, subset
from research_lab.sim import ADVERSE_COST, BASE_COST, scaled_cost, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A, RULES_B, RULES_C, RULES_E, with_breakout_persistence, K_PERSIST

data = build(); dA = subset(data, A_UNIVERSE); dC = with_breakout_persistence(dA)
setups = {"A": (RULES_A, dA), "B": (RULES_B, data), "C": (RULES_C, dC), "E": (RULES_E, dA)}

# 1) cost sensitivity (x0 = no friction/fees, x1 = current baseline schedule, x2, x3)
sweep = []
for w in ("DEV", "VAL"):
    for k in ("A", "E"):
        for m in (0.0, 0.5, 1.0, 2.0, 3.0):
            r = simulate(setups[k][1], setups[k][0], scaled_cost(m), WINDOWS[w])
            s = summarize(r); sweep.append({"window": w, "id": k, "cost_mult": m, "trades": s["trades"], "net": s["net_realized"], "gross": s["gross_raw"], "end_equity": s["equity_end"]})
            print(w, k, m, s["trades"], s["gross_raw"], s["net_realized"], flush=True)
json.dump(sweep, open("research_lab/results_costsweep.json", "w"), indent=1)

# 2) ledger exports + manifest for the three independent 5,000 EUR experiments on the validation window
import os
os.makedirs("research_lab/runs/2026-09-20", exist_ok=True)
manifest = {"created": "2026-09-20", "windows": {k: list(v) for k, v in WINDOWS.items()}, "k_persist": K_PERSIST,
            "code_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
            "git_dirty_files": subprocess.run(["git", "status", "--short", "research_lab", "app"], capture_output=True, text=True).stdout.count("\n"),
            "cost_models": {"base": dataclasses.asdict(BASE_COST), "adverse": dataclasses.asdict(ADVERSE_COST)},
            "rules": {k: {f.name: (getattr(v[0], f.name) if f.name != "decision_hook" else None) for f in dataclasses.fields(v[0])} for k, v in setups.items()},
            "universe_A": list(A_UNIVERSE), "universe_B_extra": json.load(open(CACHE / "universe_B.json"))["extra"],
            "signals_cache_sha256": hashlib.sha256(open(PKL, "rb").read()).hexdigest(),
            "kline_manifest": json.load(open(CACHE / "manifest.json")),
            "execution_model": "candle_only: decide at closed bar, fill next open, adverse friction, stop-first on ambiguous bar, gap at open"}
json.dump(manifest, open("research_lab/runs/2026-09-20/manifest.json", "w"), indent=1)
for k in ("A", "B", "C", "E"):
    r = simulate(setups[k][1], setups[k][0], BASE_COST, WINDOWS["VAL"])
    with open(f"research_lab/runs/2026-09-20/ledger_{k}_VAL_base.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["key", "ts", "ref", "currency", "amount", "cause", "memo"])
        for tx in r.ledger.transactions:
            for leg in tx.legs: w.writerow([tx.key, tx.ts.isoformat(), tx.ref, leg.currency, leg.amount, leg.cause.value, leg.memo])
    with open(f"research_lab/runs/2026-09-20/trades_{k}_VAL_base.csv", "w", newline="") as f:
        w = csv.writer(f); cols = list(dataclasses.asdict(r.trades[0]).keys()) if r.trades else []; w.writerow(cols)
        for t in r.trades: w.writerow([getattr(t, c) for c in cols])
    print(k, "ledger balance", r.ledger.balances(), "diff", r.ledger_diff, "commission ledger", r.ledger.total_by_cause(__import__("app.brokerage.ledger", fromlist=["Cause"]).Cause.COMMISSION, "EUR"))
