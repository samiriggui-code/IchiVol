import glob, json, sys
sys.path.insert(0, ".")
sys.path.insert(0, r"C:\Users\samir\AppData\Local\Temp\claude\c--laragon-www-IchiVol\36cb2c9b-e117-46cb-828a-f350d653bd7a\scratchpad")
from collections import defaultdict
from indep_sim import load, run
from research_lab.data import CACHE
from research_lab.signals import compute_bar_signals, to_candles

data = load()

# ---- 1) cache freshness: recompute signals with CURRENT engine code for 3 symbols
for sym in ("BTCUSDT", "PEPEUSDT", "APTUSDT"):
    c = to_candles(json.load(open(glob.glob(str(CACHE / f"{sym}_1h_*.json"))[0])))
    h = to_candles(json.load(open(glob.glob(str(CACHE / f"{sym}_4h_*.json"))[0])))
    sig = compute_bar_signals(c, h)
    bad = 0
    for cd, sg in zip(c, sig):
        old = data[sym][cd.time][1]
        if (old.decision, old.direction, old.stop_distance) != (sg.decision, sg.direction, sg.stop_distance):
            bad += 1
    print(f"cache check {sym}: {len(c)} bars, {bad} mismatches vs current pipeline", flush=True)

# ---- 2) per-instrument friction table (half quoted spread = 0.5 * 1 tick + slippage tier)
tick_bps = {  # tick / last price, from exchangeInfo + bookTicker snapshot 2026-09-20
    "PEPEUSDT": 25.25, "APTUSDT": 13.81, "DOTUSDT": 9.00, "OPUSDT": 8.06, "TONUSDT": 6.25, "ATOMUSDT": 5.71,
    "ARBUSDT": 4.90, "ADAUSDT": 4.45, "NEARUSDT": 2.56, "LTCUSDT": 1.74, "SUIUSDT": 1.18, "DOGEUSDT": 1.17,
    "UNIUSDT": 1.15, "SOLUSDT": 0.92, "AVAXUSDT": 0.88, "LINKUSDT": 0.81, "XRPUSDT": 0.72, "BNBUSDT": 0.13,
    "ETHUSDT": 0.04, "BTCUSDT": 0.00,
}
qvol = {  # median 1h quote volume (USDT) over 2026 window
    "BTCUSDT": 38.9e6, "ETHUSDT": 20.3e6, "SOLUSDT": 7.2e6, "XRPUSDT": 4.4e6, "BNBUSDT": 2.7e6, "DOGEUSDT": 2.0e6,
    "SUIUSDT": 1.15e6, "PEPEUSDT": 0.91e6, "ADAUSDT": 0.94e6, "NEARUSDT": 0.81e6, "LINKUSDT": 0.73e6,
    "AVAXUSDT": 0.60e6, "LTCUSDT": 0.55e6, "UNIUSDT": 0.46e6, "TONUSDT": 0.35e6, "DOTUSDT": 0.24e6,
    "ARBUSDT": 0.21e6, "APTUSDT": 0.21e6, "OPUSDT": 0.12e6, "ATOMUSDT": 0.08e6,
}


def slip(q):  # per-side slippage tier by liquidity (proposal)
    return 1.0 if q >= 2e6 else 2.0 if q >= 0.4e6 else 4.0


table = {s: 0.5 * max(tick_bps[s], 0.0) + slip(qvol[s]) for s in tick_bps}
print("\nproposed per-side friction (bps) = 0.5*tick_bps + slippage tier:")
for s, v in sorted(table.items(), key=lambda kv: -kv[1]):
    print(f"  {s:9s} {v:5.2f}  (flat baseline = 5.00)")

for name, kw in (
    ("flat 5 bps/side (reference)", {}),
    ("per-instrument table", dict(sym_f=table)),
):
    r = run(data, **kw)
    by = defaultdict(lambda: [0, 0.0])
    for t in r["trades"]:
        by[t["sym"]][0] += 1
        by[t["sym"]][1] += t["net"]
    print(f"\n{name}: n={r['n']} net={r['net']:.1f} gross={r['gross']:.1f} fees={r['fees']:.1f}", flush=True)
    if kw:
        worst = sorted(by.items(), key=lambda kv: kv[1][1])[:5]
        print("  worst 5 instruments (n, net):", [(k, v[0], round(v[1], 1)) for k, v in worst])
        tr_share = {k: v[0] for k, v in by.items()}
        top = sorted(tr_share.items(), key=lambda kv: -kv[1])[:6]
        print("  most traded:", top)
r = run(data)
cnt = defaultdict(int)
for t in r["trades"]:
    cnt[t["sym"]] += 1
print("\ntrade count by symbol (flat run):", dict(sorted(cnt.items(), key=lambda kv: -kv[1])))
print("END", flush=True)
