import sys, statistics
sys.path.insert(0, ".")
sys.path.insert(0, r"C:\Users\samir\AppData\Local\Temp\claude\c--laragon-www-IchiVol\36cb2c9b-e117-46cb-828a-f350d653bd7a\scratchpad")
from indep_sim import load, run

data = load()


def row(name, r):
    print(f"{name:38s} n={r['n']:5d} net={r['net']:9.1f} gross={r['gross']:8.1f} fees={r['fees']:8.1f} "
          f"long={r['net_long']:8.1f} short={r['net_short']:8.1f} win={r['win']:.2f}", flush=True)


row("base seed7 (= reference)", run(data))
nets = []
for s in range(1, 11):
    nets.append(run(data, seed=s)["net"])
print(f"10 seeds net: mean={statistics.mean(nets):.0f} sd={statistics.pstdev(nets):.0f} min={min(nets):.0f} max={max(nets):.0f}", flush=True)
row("alphabetical priority", run(data, seed=None))
row("causal liquidity cap (prev bar vol)", run(data, liq_mode="prev_bar_volume"))
row("shorts OFF", run(data, shorts=False))
row("half spread per side", run(data, half_spread=True))
row("stop extra slippage +10bps", run(data, stop_extra_slip_bps=10))
row("TP needs trade-through", run(data, tp_needs_trade_through=True))
row("no costs at all", run(data, comm_bps=0, spread_bps=0, slip_bps=0))
row("commission 0 (spread+slip kept)", run(data, comm_bps=0))
row("maker-like comm 2bps", run(data, comm_bps=2))
print("END", flush=True)
