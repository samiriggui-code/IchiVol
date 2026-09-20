import json, sys
from datetime import datetime, timezone
from research_lab.build import build
from research_lab.funnel import DEV, VAL
from research_lab.metrics import summarize
from research_lab.sim import ADVERSE_COST, BASE_COST, scaled_cost, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A, RULES_B, RULES_C, RULES_E, with_breakout_persistence

def ts(y, m, d, h=0): return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())
WINDOWS = {"DEV": DEV, "VAL": VAL, "V1": (ts(2026,1,1), ts(2026,4,1)), "V2": (ts(2026,4,1), ts(2026,7,1)), "V3": (ts(2026,7,1), ts(2026,9,20,16))}

def subset(data, syms): return {s: data[s] for s in syms}

def main():
    data = build()
    dA = subset(data, A_UNIVERSE); dB = data
    dC = with_breakout_persistence(dA)
    setups = {"A": (RULES_A, dA), "B": (RULES_B, dB), "C": (RULES_C, dC), "E": (RULES_E, dA)}
    out = []
    for w, win in WINDOWS.items():
        for k, (rules, d) in setups.items():
            for cost in (BASE_COST, ADVERSE_COST):
                r = simulate(d, rules, cost, win)
                s = summarize(r); s["window_name"] = w; s["id"] = k
                out.append(s)
                print(w, k, cost.name, s["trades"], s["net_realized"], s["equity_end"], s["max_drawdown_pct"], flush=True)
    json.dump(out, open("research_lab/results_main.json", "w"), indent=1)

if __name__ == "__main__":
    main()
