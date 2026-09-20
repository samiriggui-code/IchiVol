"""Experiment definitions. Fixed BEFORE looking at any P&L (see docs report §definitions).

A  reference   : current pipeline, closed candles, universe A (20 crypto), exit = decision no longer supports
B  extended    : A rules, universe A + 20 extra liquid pairs (point-in-time rule, universe.py)
C  more entries: A rules + ONE change: the Donchian breakout requirement is waived for up to K=3 closed bars
                 after a genuine same-direction pipeline signal, but ONLY when it is the sole failing filter
                 (regime FAIL with code regime_no_breakout, every other stage passing).
                 Motivation (dev-window counters): 74% of signal runs last a single bar, caused by the one-bar nature
                 of the Donchian breakout (2nd sole blocker of the regime stage after ADX); ADX/ATR/location/RVOL/structure stay untouched.
E  exits       : A entries, exit only on stop/target/Ichimoku-direction change (tested separately from entries)
"""
from dataclasses import replace

from research_lab.sim import Rules

K_PERSIST = 3

RULES_A = Rules(name="A_reference")
RULES_B = Rules(name="B_extended_universe")
RULES_C = Rules(name="C_breakout_persistence_k3")
RULES_E = Rules(name="E_exit_direction_flip", exit_mode="direction")


def with_breakout_persistence(data: dict, k: int = K_PERSIST) -> dict:
    out = {}
    for sym, series in data.items():
        new = {}
        last_sig: dict[str, int] = {}
        for i, t in enumerate(sorted(series)):
            cd, g = series[t]
            dname = g.direction.value
            if g.decision in ("BUY", "SELL"):
                last_sig[dname] = i
            elif (
                dname != "NEUTRAL"
                and g.failed == ("regime",)
                and dict(g.fail_codes).get("regime") == "regime_no_breakout"
                and dname in last_sig
                and 1 <= i - last_sig[dname] <= k
                and g.stop_distance is not None
            ):
                g = replace(g, decision="BUY" if dname == "LONG" else "SELL", failed=(), fail_codes=(), primary="signal_persist")
            new[t] = (cd, g)
        out[sym] = new
    return out
