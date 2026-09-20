import sys
sys.path.insert(0, "."); sys.path.insert(0, r"C:\Users\samir\AppData\Local\Temp\claude\c--laragon-www-IchiVol\36cb2c9b-e117-46cb-828a-f350d653bd7a\scratchpad")
from indep_sim import load, run
tick_bps = {"PEPEUSDT": 25.25, "APTUSDT": 13.81, "DOTUSDT": 9.00, "OPUSDT": 8.06, "TONUSDT": 6.25, "ATOMUSDT": 5.71,
    "ARBUSDT": 4.90, "ADAUSDT": 4.45, "NEARUSDT": 2.56, "LTCUSDT": 1.74, "SUIUSDT": 1.18, "DOGEUSDT": 1.17,
    "UNIUSDT": 1.15, "SOLUSDT": 0.92, "AVAXUSDT": 0.88, "LINKUSDT": 0.81, "XRPUSDT": 0.72, "BNBUSDT": 0.13,
    "ETHUSDT": 0.04, "BTCUSDT": 0.00}
qvol = {"BTCUSDT": 38.9e6, "ETHUSDT": 20.3e6, "SOLUSDT": 7.2e6, "XRPUSDT": 4.4e6, "BNBUSDT": 2.7e6, "DOGEUSDT": 2.0e6,
    "SUIUSDT": 1.15e6, "PEPEUSDT": 0.91e6, "ADAUSDT": 0.94e6, "NEARUSDT": 0.81e6, "LINKUSDT": 0.73e6,
    "AVAXUSDT": 0.60e6, "LTCUSDT": 0.55e6, "UNIUSDT": 0.46e6, "TONUSDT": 0.35e6, "DOTUSDT": 0.24e6,
    "ARBUSDT": 0.21e6, "APTUSDT": 0.21e6, "OPUSDT": 0.12e6, "ATOMUSDT": 0.08e6}
table = {s: 0.5 * tick_bps[s] + (1.0 if qvol[s] >= 2e6 else 2.0 if qvol[s] >= 0.4e6 else 4.0) for s in tick_bps}
data = load()
for label, cb in (("table + comm 5 bps", 5), ("table + comm 7.5 bps (BNB)", 7.5), ("table + comm 10 bps (std)", 10), ("table + comm 2 bps (maker/VIP)", 2)):
    r = run(data, comm_bps=cb, sym_f=table)
    print(f"{label:32s} n={r['n']} net={r['net']:.0f} gross={r['gross']:.0f} fees={r['fees']:.0f} long={r['net_long']:.0f} short={r['net_short']:.0f}", flush=True)
r = run(data, comm_bps=7.5, sym_f=table, shorts=False)
print(f"{'table + 7.5bps, LONG ONLY':32s} n={r['n']} net={r['net']:.0f} gross={r['gross']:.0f}")
