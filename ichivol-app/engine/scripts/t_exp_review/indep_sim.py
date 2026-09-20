"""Independent re-implementation of variant A from the *documented execution model*
(not a copy of research_lab/sim.py). Reads only the cached per-bar signals.

Knobs let us measure how much each modelling choice moves the result:
  liq_mode   : "entry_bar_volume" (as sim.py) | "prev_bar_volume" (causal)
  shorts     : allow SHORT entries
  seed       : tie-break order when capacity is scarce (None -> alphabetical)
  half_spread: spread counted as half per side instead of full
"""
from __future__ import annotations

import pickle
import random
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, ".")
from research_lab.universe import A_UNIVERSE  # noqa: E402

WIN = (1767225600, 1789920000)  # 2026-01-01 .. 2026-09-20 16:00 UTC


def load():
    with open("research_lab/cache/signals_v1.pkl", "rb") as fh:
        data = pickle.load(fh)
    return {s: data[s] for s in A_UNIVERSE}


def run(
    data,
    window=WIN,
    initial=5000.0,
    comm_bps=5.0,
    spread_bps=2.0,
    slip_bps=3.0,
    seed=7,
    liq_mode="entry_bar_volume",
    shorts=True,
    half_spread=False,
    stop_extra_slip_bps=0.0,
    tp_needs_trade_through=False,
    filt=None,
    sym_f=None,
    exit_mode="decision",
):
    """filt(sym, t, sig, candle) -> bool : extra entry filter (True = allow). Exit untouched."""
    f = ((spread_bps / 2 if half_spread else spread_bps) + slip_bps) / 1e4
    cf = comm_bps / 1e4
    syms = sorted(data)
    times = sorted({t for s in syms for t in data[s] if window[0] <= t < window[1]})
    rng = random.Random(seed) if seed is not None else None

    cash = initial
    pos = {}  # sym -> dict
    pend_in = {}  # sym -> (sig, dir, est_risk)
    pend_out = {}  # sym -> reason
    last_close = {}
    last_d, run_start, entered = {}, {}, set()
    trades = []
    rej = Counter()
    curve = []
    day = None
    day_eq0 = initial
    halted = False
    prev_vol = {}  # sym -> volume*close of previous bar (for causal liquidity cap)

    def equity():
        v = cash
        for p in pos.values():
            px = last_close.get(p["sym"], p["fill"])
            v += p["qty"] * px if p["dir"] == "LONG" else p["notional"] + p["qty"] * (p["fill"] - px)
        return v

    def px_fill(raw, direction, entering, sym=None):
        ff = sym_f[sym] / 1e4 if (sym_f is not None and sym in sym_f) else f
        buy = (direction == "LONG") == entering
        return raw * (1 + ff) if buy else raw * (1 - ff)

    def close(sym, raw, t, reason, extra_slip=0.0):
        nonlocal cash
        p = pos.pop(sym)
        ef = px_fill(raw, p["dir"], False, sym)
        if extra_slip:
            ef = ef * (1 - extra_slip) if p["dir"] == "LONG" else ef * (1 + extra_slip)
        out_notional = p["qty"] * ef
        fee = out_notional * cf
        if p["dir"] == "LONG":
            pnl = out_notional - p["notional"]
            cash += out_notional - fee
        else:
            pnl = p["qty"] * (p["fill"] - ef)
            cash += p["notional"] + pnl - fee
        gross = p["qty"] * ((raw - p["raw"]) if p["dir"] == "LONG" else (p["raw"] - raw))
        trades.append(
            dict(sym=sym, dir=p["dir"], t_in=p["t"], t_out=t, gross=gross, fees=p["fee"] + fee,
                 net=pnl - p["fee"] - fee, reason=reason, notional=p["notional"])
        )

    for t in times:
        # (1) exits decided at previous close -> this open
        for sym in list(pend_out):
            it = data[sym].get(t)
            if it is None:
                continue
            if sym in pos:
                close(sym, it[0].open, t, pend_out[sym])
            del pend_out[sym]
        # (2) entries decided at previous close -> this open
        for sym in list(pend_in):
            sig, direction, _ = pend_in.pop(sym)
            it = data[sym].get(t)
            if it is None:
                rej["no_bar"] += 1
                continue
            c = it[0]
            fill = px_fill(c.open, direction, True, sym)
            eq = equity()
            sd = sig.stop_distance
            qty = eq * 0.01 / sd
            if qty * fill > eq * 0.25:
                qty = eq * 0.25 / fill
            notional = qty * fill
            fee = notional * cf
            if notional + fee > cash:
                notional_aff = cash / (1 + cf)
                if notional_aff <= 0:
                    rej["cash"] += 1
                    continue
                qty = notional_aff / fill
                notional = qty * fill
                fee = notional * cf
            if notional < 10.0:
                rej["min_notional"] += 1
                continue
            vol_q = (c.volume * c.close) if liq_mode == "entry_bar_volume" else prev_vol.get(sym, 0.0)
            if notional > 0.02 * vol_q:
                rej["liquidity"] += 1
                continue
            stop = fill - sd if direction == "LONG" else fill + sd
            tp = fill + 2 * sd if direction == "LONG" else fill - 2 * sd
            if stop <= 0 or tp <= 0:
                rej["levels"] += 1
                continue
            cash -= notional + fee
            pos[sym] = dict(sym=sym, dir=direction, t=t, raw=c.open, fill=fill, qty=qty, notional=notional,
                            fee=fee, stop=stop, tp=tp, risk=qty * sd)
        # (3) protections on this bar
        for sym in list(pos):
            it = data[sym].get(t)
            if it is None:
                continue
            c, p = it[0], pos[sym]
            lg = p["dir"] == "LONG"
            if t != p["t"]:
                if (c.open <= p["stop"]) if lg else (c.open >= p["stop"]):
                    close(sym, c.open, t, "stop_gap")
                    continue
                if (c.open >= p["tp"]) if lg else (c.open <= p["tp"]):
                    close(sym, c.open, t, "tp_gap")
                    continue
            hs = (c.low <= p["stop"]) if lg else (c.high >= p["stop"])
            if tp_needs_trade_through:
                ht = (c.high > p["tp"]) if lg else (c.low < p["tp"])
            else:
                ht = (c.high >= p["tp"]) if lg else (c.low <= p["tp"])
            if hs:
                close(sym, p["stop"], t, "stop", extra_slip=stop_extra_slip_bps / 1e4)
            elif ht:
                close(sym, p["tp"], t, "tp")
        # (4) mark to market
        for sym in syms:
            it = data[sym].get(t)
            if it is not None:
                last_close[sym] = it[0].close
        eq = equity()
        curve.append((t, eq))
        dk = datetime.fromtimestamp(t + 3599, timezone.utc).date()
        if dk != day:
            day, day_eq0, halted = dk, eq, False
        if not halted and eq <= day_eq0 * 0.97:
            halted = True
        # (5) decisions at this close
        order = [s for s in syms if t in data[s]]
        if rng:
            rng.shuffle(order)
        for sym in order:
            c, sig = data[sym][t]
            d = sig.decision
            if last_d.get(sym) != d:
                last_d[sym], run_start[sym] = d, t
            prev_vol[sym] = c.volume * c.close
            if sym in pos:
                want = "BUY" if pos[sym]["dir"] == "LONG" else "SELL"
                if exit_mode == "direction":
                    if sig.direction.value != pos[sym]["dir"] and sym not in pend_out:
                        pend_out[sym] = "direction_flipped"
                elif d != want and sym not in pend_out:
                    pend_out[sym] = "downgraded" if d not in ("BUY", "SELL") else "flipped"
                continue
            if d not in ("BUY", "SELL"):
                continue
            direction = "LONG" if d == "BUY" else "SHORT"
            if sym in pend_in:
                continue
            if direction == "SHORT" and not shorts:
                rej["short_off"] += 1
                continue
            if (sym, run_start[sym]) in entered:
                rej["run_done"] += 1
                continue
            if sig.stop_distance is None:
                rej["no_stop"] += 1
                continue
            if filt is not None and not filt(sym, t, sig, c):
                rej["filter"] += 1
                continue
            if halted:
                rej["halt"] += 1
                continue
            if len(pos) + len(pend_in) >= 5:
                rej["max_pos"] += 1
                continue
            eq = equity()
            px = last_close[sym]
            est_qty = min(eq * 0.01 / sig.stop_distance, eq * 0.25 / px)
            est_risk = est_qty * sig.stop_distance
            cur_risk = sum(p["risk"] for p in pos.values()) + sum(v[2] for v in pend_in.values())
            if cur_risk + est_risk > eq * 0.04 + 1e-9:
                rej["risk_cap"] += 1
                continue
            if est_qty * px > cash:
                rej["cash_pre"] += 1
                continue
            entered.add((sym, run_start[sym]))
            pend_in[sym] = (sig, direction, est_risk)

    eq_end = curve[-1][1]
    n = len(trades)
    net = sum(x["net"] for x in trades)
    return dict(
        n=n, net=net, gross=sum(x["gross"] for x in trades), fees=sum(x["fees"] for x in trades),
        eq_end=eq_end, open_end=len(pos), win=(sum(1 for x in trades if x["net"] > 0) / n) if n else 0,
        longs=sum(1 for x in trades if x["dir"] == "LONG"), shorts=sum(1 for x in trades if x["dir"] == "SHORT"),
        net_long=sum(x["net"] for x in trades if x["dir"] == "LONG"),
        net_short=sum(x["net"] for x in trades if x["dir"] == "SHORT"),
        reasons=dict(Counter(x["reason"] for x in trades)), rej=dict(rej), trades=trades, curve=curve,
    )


if __name__ == "__main__":
    data = load()
    base = run(data)
    print("base seed7:", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in base.items() if k not in ("trades", "curve")})
