"""Does the crypto-validated pipeline do anything on gold / forex? (Twelve Data free history, 1h, closed bars, no volume)."""
import json
from datetime import datetime, timezone
from dataclasses import replace
from research_lab.data_td import fetch
from research_lab.signals import compute_bar_signals
from research_lab.indicators_util import td_to_candles
from research_lab.metrics import summarize
from research_lab.sim import CostModel, simulate
from research_lab.variants import RULES_A, RULES_E

def ts(y, m, d): return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())
data = {}
for sym in ("EUR/USD", "GBP/USD", "XAU/USD"):
    c1 = td_to_candles(fetch(sym, "1h"))[:-1]  # last bar is still forming
    c4 = td_to_candles(fetch(sym, "4h"))[:-1]
    sig = compute_bar_signals(c1, c4)
    data[sym] = {c.time: (replace(c, volume=1e12), s) for c, s in zip(c1, sig)}  # FX has no volume: neutral liquidity for the sim only
    from collections import Counter
    print(sym, len(c1), Counter(s.decision for s in sig), flush=True)
LIQ = dict(liquidity_cap_pct=1e12)
WIN = {"DEV": (ts(2026, 3, 15), ts(2026, 6, 15)), "VAL": (ts(2026, 6, 15), ts(2026, 9, 20))}
COSTS = [CostModel("paper_base", 5, 2, 3), CostModel("fx_realistic", 0, 1, 0.5), CostModel("zero", 0, 0, 0)]
out = []
for rn, rules in (("A", replace(RULES_A, **LIQ)), ("E", replace(RULES_E, **LIQ)), ("E_long", replace(RULES_E, allow_short=False, **LIQ))):
    for w, win in WIN.items():
        for c in COSTS:
            s = summarize(simulate(data, rules, c, win))
            out.append({"rules": rn, "win": w, "cost": c.name, "trades": s["trades"], "gross": s["gross_raw"], "net": s["net_realized"], "dd": s["max_drawdown_pct"], "wr": s["win_rate"], "hold": s["avg_hold_h"]})
            print(rn, w, c.name, s["trades"], s["gross_raw"], s["net_realized"], s["max_drawdown_pct"], s["win_rate"], s["avg_hold_h"], flush=True)
json.dump(out, open("research_lab/results_fx.json", "w"), indent=1)
