"""Experiment 'cost per trade' (separate from entries/exits): same E and A rules, only the cost schedule changes.
Scenarios are documented HYPOTHESES, not measured execution:
  base      commission 5 + spread 2 + slippage 3 bps per side (current paper profile)
  bnb_taker 7.5 bps commission (standard 0.10% with 25% BNB discount), spread 2, slip 3
  maker     limit orders: 7.5 bps commission, spread 0 (posted, not crossed), slippage 1 bp; NOT modelling missed fills
  vip_maker 2 bps commission, spread 0, slip 1 (high-volume tier, unrealistic at this account size)"""
import json
from research_lab.build import build
from research_lab.run import WINDOWS, subset
from research_lab.metrics import summarize
from research_lab.sim import CostModel, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A, RULES_E

data = subset(build(), A_UNIVERSE)
SCEN = [CostModel("base", 5, 2, 3), CostModel("bnb_taker", 7.5, 2, 3), CostModel("maker", 7.5, 0, 1), CostModel("vip_maker", 2, 0, 1)]
out = []
for w in ("DEV", "V1", "V2", "V3", "VAL"):
    for rules in (RULES_A, RULES_E):
        for c in SCEN:
            s = summarize(simulate(data, rules, c, WINDOWS[w]))
            out.append({"window": w, "rules": rules.name, "cost": c.name, "trades": s["trades"], "net": s["net_realized"], "dd": s["max_drawdown_pct"]})
            print(w, rules.name[:1], c.name, s["trades"], s["net_realized"], s["max_drawdown_pct"], flush=True)
json.dump(out, open("research_lab/results_costs.json", "w"), indent=1)
