"""Replica of the OLD live behaviour: pipeline decided every 5 minutes on the still-forming 1h bar
(and the still-forming 4h bar for MTF), exactly what screener/service.scan_symbol does
(candles[-1] = forming bar, HTF direction = analyze(htf)[-1]). Built from public 5m klines.
Purpose: measure what closed-candle decisions change. Not a claim about every historical live decision:
the live pipeline decisions per cycle were never persisted (only positions/journal), so this is a
reconstruction, validated against the actual live trades in the report."""
from __future__ import annotations

import glob, json, pickle, sys
from concurrent.futures import ProcessPoolExecutor

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.decision.pipeline import build_pipeline
from app.indicators.adx import compute_adx
from app.indicators.atr import compute_atr
from app.indicators.cvd import compute_cvd
from app.indicators.donchian import compute_donchian
from app.indicators.ichimoku import Candle
from app.indicators.location import compute_location
from app.indicators.structure import compute_structure
from research_lab.data import CACHE, load_or_fetch, ms
from research_lab.signals import BarSignal, _fail_codes, _failed_stages, _primary, to_candles
from research_lab.universe import A_UNIVERSE

R_START, R_END = ms(2026, 9, 6, 16), ms(2026, 9, 20, 16)
PKL = CACHE / "replica_v1.pkl"


def _agg(rows5, lo_s, hi_s):
    part = [r for r in rows5 if lo_s <= r[0] // 1000 < hi_s]
    if not part:
        return None
    return Candle(time=lo_s, open=float(part[0][1]), high=max(float(r[2]) for r in part),
                  low=min(float(r[3]) for r in part), close=float(part[-1][4]),
                  volume=sum(float(r[5]) for r in part), taker_buy_volume=sum(float(r[9]) for r in part))


def live_like_signal(candles, htf) -> BarSignal:
    io = ichimoku_agent.analyze(candles)[-1]
    rv = rvol_agent.analyze(candles)[-1]
    st = compute_structure(candles)
    atr = compute_atr(candles)
    loc = compute_location(candles, st)
    cvd = compute_cvd(candles)
    adx = compute_adx(candles)
    don = compute_donchian(candles)
    mtf = ichimoku_agent.analyze(htf)[-1].direction if len(htf) >= 2 else None
    aligned = (mtf == io.direction) if mtf is not None and mtf != Direction.NEUTRAL and io.direction != Direction.NEUTRAL else None
    p = build_pipeline(io, rv, st[-1], atr[-1], aligned, loc[-1], cvd[-1], None, adx[-1], don[-1])
    sd = getattr(atr[-1], "suggested_stop_distance", None)
    rvv = rv.metadata.get("rvol")
    return BarSignal(candles[-1].time, p.decision, p.direction, sd if isinstance(sd, (int, float)) and sd > 0 else None,
                     rvv if isinstance(rvv, (int, float)) else None, _failed_stages(p), _fail_codes(p), _primary(p), aligned)


def one(sym):
    f1 = glob.glob(str(CACHE / f"{sym}_1h_*.json"))[0]
    f4 = glob.glob(str(CACHE / f"{sym}_4h_*.json"))[0]
    closed1 = to_candles(json.load(open(f1)))
    closed4 = to_candles(json.load(open(f4)))
    rows5 = load_or_fetch(sym, "5m", R_START - 3_600_000 * 8, R_END)
    out = {}
    for T in range(R_START // 1000 + 300, R_END // 1000 + 1, 300):
        h = T - (T - 1) % 3600 - 1 if False else ((T - 1) // 3600) * 3600  # hour containing the last 5m bar
        h4 = ((T - 1) // 14400) * 14400
        forming = _agg(rows5, h, T)
        if forming is None:
            continue
        c1 = [c for c in closed1 if c.time < h][-299:] + [forming]
        f4c = _agg(rows5, h4, T)
        c4 = [c for c in closed4 if c.time < h4][-299:] + ([f4c] if f4c else [])
        sig = live_like_signal(c1, c4)
        px = float(next(r for r in reversed(rows5) if r[0] // 1000 < T)[4])
        out[T] = (Candle(time=T, open=px, high=px, low=px, close=px, volume=10**12), sig)
    return sym, out


if __name__ == "__main__":
    syms = sys.argv[1:] or list(A_UNIVERSE)
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = dict(ex.map(one, syms))
    pickle.dump(res, open(PKL, "wb"))
    print("done", {k: len(v) for k, v in res.items()})
