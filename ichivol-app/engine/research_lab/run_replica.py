import json, pickle
from datetime import datetime, timezone
from research_lab.build import build
from research_lab.data import CACHE
from research_lab.metrics import summarize
from research_lab.replica import R_START, R_END
from research_lab.sim import ADVERSE_COST, BASE_COST, Rules, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A

def ts(y, m, d, h=0, mi=0): return int(datetime(y, m, d, h, mi, tzinfo=timezone.utc).timestamp())
rep = pickle.load(open(CACHE / "replica_v1.pkl", "rb")); rep = {k: v for k, v in rep.items() if v}
data = build()
LEGACY = dict(one_entry_per_signal_run=False, max_open_risk_pct=99.0, daily_loss_limit_pct=0.0, max_symbol_notional_pct=99.0, liquidity_cap_pct=1e9)
L_LIVE = Rules(name="L_live_replica_intrabar_5min", immediate_fill=True, bar_seconds=300, **LEGACY)
L_CLOSED = Rules(name="L_legacy_rules_closed_candles", **LEGACY)
W14 = (R_START // 1000 + 300, R_END // 1000)
WLIVE = (ts(2026, 9, 18, 19, 23), R_END // 1000)
closed = {s: data[s] for s in rep}
out = []
for wn, win in (("REPLICA_14D", W14), ("LIVE_WINDOW", WLIVE)):
    for name, rules, d in (("L_live", L_LIVE, rep), ("L_closed", L_CLOSED, closed), ("A_corrected_closed", RULES_A, closed)):
        for cost in (BASE_COST, ADVERSE_COST):
            r = simulate(d, rules, cost, win)
            s = summarize(r); s["window_name"] = wn; s["id"] = name; out.append(s)
            print(wn, name, cost.name, s["trades"], s["gross_raw"], s["net_realized"], s["avg_hold_h"], s["max_drawdown_pct"], s["exit_reasons"], flush=True)
json.dump(out, open("research_lab/results_replica.json", "w"), indent=1)
