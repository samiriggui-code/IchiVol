import json, statistics
from dataclasses import replace
from research_lab.build import build
from research_lab.run import WINDOWS, subset
from research_lab.metrics import summarize
from research_lab.sim import CostModel, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_E
COST = CostModel("real", 7.5, 2, 3); ADV = CostModel("adverse", 10, 4, 8)
data = subset(build(), A_UNIVERSE)
base = replace(RULES_E, name="E_long", allow_short=False)
for label, kw in [("10 pos / 0.5% / 10% / cap4%", dict(max_open=10, risk_pct=0.005, max_notional_pct=0.10, max_open_risk_pct=0.04)),
                  ("15 pos / 0.5% / 10% / cap6%", dict(max_open=15, risk_pct=0.005, max_notional_pct=0.10, max_open_risk_pct=0.06)),
                  ("15 pos / 0.4% / 8% / cap6%", dict(max_open=15, risk_pct=0.004, max_notional_pct=0.08, max_open_risk_pct=0.06))]:
    r = replace(base, name=label, **kw); row = {}
    for w in ("DEV", "V1", "V2", "V3", "VAL"):
        nets = [summarize(simulate(data, r, COST, WINDOWS[w], seed=s))["net_realized"] for s in range(5)]
        s0 = summarize(simulate(data, r, COST, WINDOWS[w]))
        row[w] = (round(statistics.mean(nets)), s0["trades"], s0["max_drawdown_pct"], simulate(data, r, ADV, WINDOWS[w]) and summarize(simulate(data, r, ADV, WINDOWS[w]))["net_realized"])
    print(label.ljust(30), "DEV", row["DEV"], "| VAL", row["VAL"], "| V1-3", row["V1"][0], row["V2"][0], row["V3"][0], flush=True)
