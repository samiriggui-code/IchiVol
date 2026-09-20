import sys, statistics
from datetime import datetime, timezone
sys.path.insert(0, "."); sys.path.insert(0, ".")
from indep_sim import load, run
def ts(y, m, d, h=0): return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())
W = {"DEV": (ts(2025,6,1), ts(2026,1,1)), "V1": (ts(2026,1,1), ts(2026,4,1)), "V2": (ts(2026,4,1), ts(2026,7,1)),
     "V3": (ts(2026,7,1), ts(2026,9,20,16)), "VAL": (ts(2026,1,1), ts(2026,9,20,16))}
COST = {"base": {}, "adverse": dict(comm_bps=10, spread_bps=4, slip_bps=8)}
data = load()
print(f"{'win':4s} {'cost':7s} {'variant':22s} {'n':>5s} {'net':>8s} {'gross':>8s} {'fees':>7s} {'win%':>5s} {'hold_h':>6s}", flush=True)
for w, win in W.items():
    for c, ck in COST.items():
        for name, kw in (("A decision-exit", {}), ("E direction-exit", dict(exit_mode="direction")),
                         ("E_LONG long-only", dict(exit_mode="direction", shorts=False))):
            r = run(data, window=win, **ck, **kw)
            hold = statistics.mean((t["t_out"] - t["t_in"]) / 3600 for t in r["trades"]) if r["trades"] else 0
            print(f"{w:4s} {c:7s} {name:22s} {r['n']:5d} {r['net']:8.1f} {r['gross']:8.1f} {r['fees']:7.1f} {r['win']*100:5.1f} {hold:6.1f}", flush=True)
