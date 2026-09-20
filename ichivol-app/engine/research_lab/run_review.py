"""Follow-up to ichivol-36's review: (1) liquidity on signal bar, (2) 10 RNG seeds, (3) long-only as ONE separate lever."""
import json, statistics
from dataclasses import replace
from research_lab.build import build
from research_lab.run import WINDOWS, subset
from research_lab.metrics import summarize
from research_lab.sim import BASE_COST, ADVERSE_COST, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A, RULES_E
d = subset(build(), A_UNIVERSE); out = []
for name, rules in (("A", RULES_A), ("E", RULES_E), ("A_longonly", replace(RULES_A, name="A_longonly", allow_short=False)), ("E_longonly", replace(RULES_E, name="E_longonly", allow_short=False))):
    for w in ("DEV", "V1", "V2", "V3", "VAL"):
        nets = [summarize(simulate(d, rules, BASE_COST, WINDOWS[w], seed=s))["net_realized"] for s in range(10)]
        adv = summarize(simulate(d, rules, ADVERSE_COST, WINDOWS[w]))
        b = summarize(simulate(d, rules, BASE_COST, WINDOWS[w]))
        out.append({"id": name, "window": w, "net_mean10": round(statistics.mean(nets), 0), "net_sd": round(statistics.pstdev(nets), 0), "seed7": nets[7], "trades": b["trades"], "dd": b["max_drawdown_pct"], "adverse": adv["net_realized"]})
        print(name, w, "mean", round(statistics.mean(nets)), "sd", round(statistics.pstdev(nets)), "n", b["trades"], "dd", b["max_drawdown_pct"], "adv", adv["net_realized"], flush=True)
json.dump(out, open("research_lab/results_review.json", "w"), indent=1)
