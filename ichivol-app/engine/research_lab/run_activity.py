"""More activity with small positions: same E long-only rules, only sizing/slots change. Crypto, costs 7.5 bps + 5 bps friction."""
import json, statistics
from dataclasses import replace
from research_lab.build import build
from research_lab.run import WINDOWS, subset
from research_lab.metrics import summarize
from research_lab.sim import CostModel, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_E

COST = CostModel("real", 7.5, 2, 3)
ADV = CostModel("adverse", 10, 4, 8)
data = subset(build(), A_UNIVERSE)
base = replace(RULES_E, name="E_long", allow_short=False)
CONF = [
    ("actuel 5 pos / 1% risque / 25% max", dict(max_open=5, risk_pct=0.01, max_notional_pct=0.25, max_open_risk_pct=0.04)),
    ("10 pos / 0.5% / 10%", dict(max_open=10, risk_pct=0.005, max_notional_pct=0.10, max_open_risk_pct=0.04)),
    ("8 pos / 0.5% / 15%", dict(max_open=8, risk_pct=0.005, max_notional_pct=0.15, max_open_risk_pct=0.04)),
    ("10 pos / 0.25% / 10%", dict(max_open=10, risk_pct=0.0025, max_notional_pct=0.10, max_open_risk_pct=0.04)),
    ("15 pos / 0.25% / 6%", dict(max_open=15, risk_pct=0.0025, max_notional_pct=0.06, max_open_risk_pct=0.04)),
]
out = []
for label, kw in CONF:
    r = replace(base, name=label, **kw)
    row = {"conf": label}
    for w in ("DEV", "V1", "V2", "V3", "VAL"):
        nets = [summarize(simulate(data, r, COST, WINDOWS[w], seed=s))["net_realized"] for s in range(5)]
        s0 = summarize(simulate(data, r, COST, WINDOWS[w]))
        adv = summarize(simulate(data, r, ADV, WINDOWS[w]))["net_realized"]
        row[w] = {"net": round(statistics.mean(nets)), "trades": s0["trades"], "dd": s0["max_drawdown_pct"], "expo": s0["exposure_mean_pct"], "adv": adv}
    out.append(row)
    v = row["VAL"]; d = row["DEV"]
    print(label.ljust(36), "DEV", d["net"], d["trades"], d["dd"], "| VAL", v["net"], v["trades"], "dd", v["dd"], "expo", v["expo"], "adv", v["adv"], "| V1/V2/V3", row["V1"]["net"], row["V2"]["net"], row["V3"]["net"], flush=True)
json.dump(out, open("research_lab/results_activity.json", "w"), indent=1)
