"""T-EXP research-harness test: PPO / BEST Cloud as ENTRY FILTERS on variant A.

Pre-declared (before any P&L): PPO 12/26/9, BEST Cloud EMA20/EMA50, no tuning.
Filters only remove entries; exits/sizing/caps unchanged. Same fixed seed, same
costs. Evaluated on two disjoint windows (DEV then VAL) and two cost scenarios.
Nothing here touches paper/ or production.
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
sys.path.insert(0, r"C:\Users\samir\AppData\Local\Temp\claude\c--laragon-www-IchiVol\36cb2c9b-e117-46cb-828a-f350d653bd7a\scratchpad")
from indep_sim import load, run  # noqa: E402
from app.indicators.best_cloud import compute_best_cloud  # noqa: E402
from app.indicators.ppo import compute_ppo  # noqa: E402


def ts(y, m, d, h=0):
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())


DEV = (ts(2025, 6, 1), ts(2026, 1, 1))
VAL = (ts(2026, 1, 1), ts(2026, 9, 20, 16))

data = load()
feat = {}
for sym, series in data.items():
    ts_sorted = sorted(series)
    candles = [series[t][0] for t in ts_sorted]
    ppo = compute_ppo(candles)
    cloud = compute_best_cloud(candles)
    feat[sym] = {t: (p, b) for t, p, b in zip(ts_sorted, ppo, cloud)}


def is_long(sig):
    return sig.direction.value == "LONG"


def f_ppo_side(sym, t, sig, c):  # ppo on the trade side of zero AND histogram on trade side
    p, _ = feat[sym][t]
    return (p.ppo_above_zero and p.histogram_positive) if is_long(sig) else (p.ppo_below_zero and p.histogram_negative)


def f_ppo_strong(sym, t, sig, c):  # + histogram accelerating in trade direction
    p, _ = feat[sym][t]
    return p.momentum.value == ("STRONG_BULLISH" if is_long(sig) else "STRONG_BEARISH")


def f_cloud(sym, t, sig, c):
    _, b = feat[sym][t]
    return b.trend.value == ("BULLISH" if is_long(sig) else "BEARISH")


def f_ppo_and_cloud(sym, t, sig, c):
    return f_ppo_side(sym, t, sig, c) and f_cloud(sym, t, sig, c)


FILTERS = {
    "A (no filter)": None,
    "F1 PPO side (ppo & hist)": f_ppo_side,
    "F2 PPO STRONG (hist accel)": f_ppo_strong,
    "F3 BEST Cloud aligned": f_cloud,
    "F4 F1 + F3": f_ppo_and_cloud,
}
COSTS = {"base": dict(), "adverse": dict(comm_bps=10, spread_bps=4, slip_bps=8)}

if __name__ == "__main__":
    print(f"{'window':4s} {'cost':7s} {'filter':28s} {'n':>5s} {'net':>8s} {'gross':>8s} {'fees':>7s} {'net/tr':>7s} {'gross/tr':>8s} {'win':>5s} {'long':>7s} {'short':>7s}")
    for wname, win in (("DEV", DEV), ("VAL", VAL)):
        for cname, ck in COSTS.items():
            for fname, fn in FILTERS.items():
                r = run(data, window=win, filt=fn, **ck)
                n = max(r["n"], 1)
                print(f"{wname:4s} {cname:7s} {fname:28s} {r['n']:5d} {r['net']:8.1f} {r['gross']:8.1f} {r['fees']:7.1f} "
                      f"{r['net'] / n:7.2f} {r['gross'] / n:8.2f} {r['win']:5.2f} {r['net_long']:7.1f} {r['net_short']:7.1f}", flush=True)
