"""Rejection funnel per bar-close over a window. Multi-label counts are marked (M), exclusive ones (X)."""
import sys, json
from collections import Counter
from datetime import datetime, timezone
from research_lab.build import build
from research_lab.universe import A_UNIVERSE

def ts(y, m, d, h=0): return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())
DEV = (ts(2025, 6, 1), ts(2026, 1, 1))
VAL = (ts(2026, 1, 1), ts(2026, 9, 20, 16))

def funnel(data, syms, win):
    c = Counter(); regime_codes = Counter(); only_fail = Counter(); combo = Counter(); runs = []
    for s in syms:
        cur = None; n = 0
        for t in sorted(k for k in data[s] if win[0] <= k < win[1]):
            cd, g = data[s][t]
            c["bars"] += 1
            if g.direction.value == "NEUTRAL":
                c["ichimoku_neutral"] += 1
            else:
                c["ichimoku_directional"] += 1
                fs = set(g.failed)
                for st in fs: c[f"fail_{st}(M)"] += 1
                if not fs:
                    c["signal_BUY_SELL"] += 1
                else:
                    combo["+".join(sorted(fs))] += 1
                    if len(fs) == 1: only_fail[next(iter(fs))] += 1
                for st, code in g.fail_codes:
                    if st == "regime": regime_codes[code] += 1
            if g.stop_distance is None and g.decision in ("BUY", "SELL"): c["signal_without_atr_stop"] += 1
            d = g.decision if g.decision in ("BUY", "SELL") else None
            if d == cur and d is not None: n += 1
            else:
                if cur is not None: runs.append(n)
                cur, n = d, (1 if d else 0)
        if cur is not None: runs.append(n)
    return c, regime_codes, only_fail, combo, runs

if __name__ == "__main__":
    data = build()
    for name, syms in (("A(20)", A_UNIVERSE), ("ALL(40)", sorted(data))):
        for wn, win in (("DEV", DEV), ("VAL", VAL)):
            c, rc, of, cb, runs = funnel(data, syms, win)
            r1 = sum(1 for r in runs if r == 1)
            print(f"\n== {name} {wn}: bars={c['bars']} directional={c['ichimoku_directional']} signals={c['signal_BUY_SELL']} runs={len(runs)} runs_len1={r1} mean_run={sum(runs)/max(1,len(runs)):.2f}")
            print(" fails (M):", {k: v for k, v in c.items() if k.startswith('fail_')})
            print(" regime codes among directional:", dict(rc))
            print(" ONLY this stage fails (X):", dict(of))
            print(" top combos:", cb.most_common(6))
