import json, sys, statistics, httpx, pickle
sys.path.insert(0, ".")
from research_lab.universe import A_UNIVERSE
B = "https://data-api.binance.vision"
syms = [s for s in A_UNIVERSE]
c = httpx.Client(timeout=30)
info = c.get(B + "/api/v3/exchangeInfo", params={"symbols": json.dumps(syms, separators=(",", ":"))}).json()
bt = {}
for sy in syms:
    r = c.get(B + "/api/v3/ticker/bookTicker", params={"symbol": sy})
    if r.status_code == 200:
        bt[sy] = r.json()
meta = {}
for s in info["symbols"]:
    f = {x["filterType"]: x for x in s["filters"]}
    meta[s["symbol"]] = dict(
        status=s["status"], tick=float(f["PRICE_FILTER"]["tickSize"]), step=float(f["LOT_SIZE"]["stepSize"]),
        min_notional=float(f.get("NOTIONAL", f.get("MIN_NOTIONAL", {})).get("minNotional", 0)),
    )
json.dump(meta, open("research_lab/_tmp_symbol_meta.json", "w"))
print(len(meta), "symbols from exchangeInfo;", len(bt), "bookTickers")
data = pickle.load(open("research_lab/cache/signals_v1.pkl", "rb"))
WIN = (1767225600, 1789920000)
rows = []
for s in syms:
    m = meta.get(s)
    if not m: print("missing", s); continue
    cs = sorted((t, v[0]) for t, v in data[s].items() if WIN[0] <= t < WIN[1])
    closes = [x.close for _, x in cs]
    med_px = statistics.median(closes)
    last_px = closes[-1]
    # Corwin-Schultz (2012) high-low spread estimator on consecutive 1h bars
    import math
    vals = []
    for (t0, a), (t1, b) in zip(cs, cs[1:]):
        if t1 - t0 != 3600 or min(a.low, b.low) <= 0: continue
        beta = math.log(a.high / a.low) ** 2 + math.log(b.high / b.low) ** 2
        gamma = math.log(max(a.high, b.high) / min(a.low, b.low)) ** 2
        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / (3 - 2 * math.sqrt(2)) - math.sqrt(gamma / (3 - 2 * math.sqrt(2)))
        sp = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
        vals.append(max(sp, 0.0))
    cs_bps = statistics.median(vals) * 1e4 if vals else None
    q = statistics.median(x.volume * x.close for _, x in cs)
    b = bt.get(s)
    snap = (float(b["askPrice"]) - float(b["bidPrice"])) / ((float(b["askPrice"]) + float(b["bidPrice"])) / 2) * 1e4 if b and float(b["askPrice"]) > 0 and float(b["bidPrice"]) > 0 else None
    rows.append((s, meta[s]["tick"], last_px, meta[s]["tick"] / last_px * 1e4, meta[s]["min_notional"], cs_bps, snap, q))
print(f"{'sym':9s} {'tick':>10s} {'last px':>11s} {'tick bps':>9s} {'minNot':>7s} {'CS spr bps':>10s} {'snap bps':>9s} {'med 1h qvol':>12s}")
for r in sorted(rows, key=lambda x: -x[3]):
    print(f"{r[0]:9s} {r[1]:10.8g} {r[2]:11.6g} {r[3]:9.2f} {r[4]:7.2f} {r[5]:10.2f} {(r[6] if r[6] is not None else float('nan')):9.2f} {r[7]:12.0f}")
