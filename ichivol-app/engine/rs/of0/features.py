"""Agrégation 1 s → 1h, grille causale et mesures F1–F5 (RS-07 §2–§4).

Toutes les fonctions sont pures. Les mesures de l'heure `t` dépendent seulement
des secondes de `t` et de `w[t]` (calculé sur les barres ≤ t−1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from rs.of0 import ATR_PERIOD, BUCKETS_PER_ATR, BURST_SECONDS, EXTREME_FRAC, RVOL_WINDOW
from rs.of0.data import Second


@dataclass(frozen=True)
class HourBar:
    t: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy: float
    n_seconds: int


def aggregate(t: int, secs: Sequence[Second]) -> HourBar:
    return HourBar(
        t=t,
        open=secs[0][1],
        high=max(s[2] for s in secs),
        low=min(s[3] for s in secs),
        close=secs[-1][4],
        volume=sum(s[5] for s in secs),
        taker_buy=sum(s[6] for s in secs),
        n_seconds=len(secs),
    )


def atr_series(bars: Sequence[HourBar], period: int = ATR_PERIOD) -> list[float | None]:
    """ATR moyenne **simple** du true range (définition moteur), en barres disponibles."""
    trs: list[float] = []
    out: list[float | None] = []
    for i, b in enumerate(bars):
        if i == 0:
            tr = b.high - b.low
        else:
            pc = bars[i - 1].close
            tr = max(b.high - b.low, abs(b.high - pc), abs(b.low - pc))
        trs.append(tr)
        out.append(sum(trs[-period:]) / period if len(trs) >= period else None)
    return out


def bucket_width(atr_prev: float | None) -> float | None:
    if atr_prev is None or atr_prev <= 0:
        return None
    return atr_prev / BUCKETS_PER_ATR


def _typical(s: Second) -> float:
    return (s[2] + s[3] + s[4]) / 3.0


def of_features(secs: Sequence[Second], w: float) -> dict[str, float | None]:
    """F1–F5 et l'indicateur C2 d'une heure, grille de largeur `w`."""
    hi = max(s[2] for s in secs)
    lo = min(s[3] for s in secs)
    rng = hi - lo
    vol = sum(s[5] for s in secs)
    out: dict[str, float | None] = {
        "F1_poc_loc": None,
        "F2_delta_top": None,
        "F3_delta_bot": None,
        "F4_delta_path": None,
        "F5_burst_share": None,
        "c2_multi_bucket_vol": 0.0,
        "volume": vol,
    }
    if vol <= 0:
        return out
    anchor = math.floor(lo / w) * w

    def idx(p: float) -> int:
        return int(math.floor((p - anchor) / w))

    buckets: dict[int, float] = {}
    top_thr, bot_thr = hi - EXTREME_FRAC * rng, lo + EXTREME_FRAC * rng
    d_top = d_bot = 0.0
    cd = cd_max = cd_min = 0.0
    first = True
    multi = 0.0
    for s in secs:
        v = s[5]
        d = 2.0 * s[6] - v
        tp = _typical(s)
        if v > 0:
            buckets[idx(tp)] = buckets.get(idx(tp), 0.0) + v
            if idx(s[2]) != idx(s[3]):
                multi += v
        if rng > 0:
            if tp >= top_thr:
                d_top += d
            if tp <= bot_thr:
                d_bot += d
        cd += d
        if first:
            cd_max = cd_min = cd
            first = False
        else:
            cd_max, cd_min = max(cd_max, cd), min(cd_min, cd)
    out["c2_multi_bucket_vol"] = multi

    if rng > 0:
        best = max(buckets.values())
        poc_i = min(i for i, v in buckets.items() if v == best)  # égalité → bucket le plus bas
        center = anchor + (poc_i + 0.5) * w
        out["F1_poc_loc"] = min(1.0, max(0.0, (center - lo) / rng))
        out["F2_delta_top"] = d_top / vol
        out["F3_delta_bot"] = d_bot / vol
    if cd_max > cd_min:
        out["F4_delta_path"] = (cd - (cd_max + cd_min) / 2.0) / ((cd_max - cd_min) / 2.0)
    vols = sorted((s[5] for s in secs), reverse=True)
    out["F5_burst_share"] = sum(vols[:BURST_SECONDS]) / vol
    return out


def baseline(bar: HourBar, atr_prev: float | None, prev_volumes: Sequence[float]) -> list[float] | None:
    """Les 7 références OHLCV + delta (RS-07 §4). None si non définies."""
    rng = bar.high - bar.low
    if rng <= 0 or bar.volume <= 0 or bar.open <= 0 or atr_prev is None or atr_prev <= 0:
        return None
    if len(prev_volumes) < RVOL_WINDOW:
        return None
    mean_v = sum(prev_volumes[-RVOL_WINDOW:]) / RVOL_WINDOW
    if mean_v <= 0:
        return None
    clv = (2 * bar.close - bar.high - bar.low) / rng
    ret = math.log(bar.close / bar.open)
    dr = (2 * bar.taker_buy - bar.volume) / bar.volume
    range_atr = rng / atr_prev
    uw = (bar.high - max(bar.open, bar.close)) / rng
    lw = (min(bar.open, bar.close) - bar.low) / rng
    lrvol = math.log(bar.volume / mean_v)
    return [clv, ret, dr, range_atr, uw, lw, lrvol]


def design_row(base: Sequence[float]) -> list[float]:
    """16 régresseurs : 7 + 7 carrés + clv·dr + ret·dr (la constante est ajoutée par l'OLS)."""
    clv, ret, dr = base[0], base[1], base[2]
    return list(base) + [x * x for x in base] + [clv * dr, ret * dr]
