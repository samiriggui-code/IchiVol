"""Mesure d'un ancrage : range 6 h, balayage + retour, rendement signé 60 min (RS-05 §3–§4).

Lecture retenue pour le balayage des deux côtés (RS-05 §3, « confirmation avant
tout balayage de l'autre côté ») : si l'autre côté est balayé sur une barre
postérieure au premier balayage et au plus tard sur la barre de confirmation,
l'ancrage est `ambiguous`, sans événement.
"""

from __future__ import annotations

from dataclasses import dataclass

from rs.us_open import BAR_MS, HORIZON_BARS, RANGE_BARS, SWEEP_BARS, VOL_REF_BARS
from rs.us_open.data import Bars


@dataclass(frozen=True)
class Anchor:
    status: str  # excluded | none | ambiguous | sweep_no_return | event
    vol15: float | None = None
    volshare15: float | None = None
    side: int = 0  # +1 LONG (balayage bas), -1 SHORT (balayage haut)
    confirm_ms: int | None = None
    r_bps: float | None = None
    mae_r: float | None = None
    mfe_r: float | None = None


def _window(bars: Bars, start_ms: int, n: int) -> list[tuple[float, float, float, float, float]] | None:
    out = []
    for i in range(n):
        b = bars.get(start_ms + i * BAR_MS)
        if b is None:
            return None
        out.append(b)
    return out


def measure(bars: Bars, a_ms: int) -> Anchor:
    pre = _window(bars, a_ms - RANGE_BARS * BAR_MS, RANGE_BARS)
    win = _window(bars, a_ms, SWEEP_BARS)
    if pre is None or win is None:
        return Anchor("excluded")
    rh = max(b[1] for b in pre)
    rl = min(b[2] for b in pre)

    vol15 = (max(b[1] for b in win) - min(b[2] for b in win)) / win[0][0] * 1e4
    ref = [b[4] for i in range(1, VOL_REF_BARS + 1) if (b := bars.get(a_ms - i * BAR_MS)) is not None]
    ref_mean3 = sum(ref) / len(ref) * SWEEP_BARS if ref else 0.0
    volshare15 = sum(b[4] for b in win) / ref_mean3 if ref_mean3 > 0 else None

    first: str | None = None
    extreme = 0.0
    confirm_i: int | None = None
    for i, (_o, h, l, c, _v) in enumerate(win):
        up, dn = h > rh, l < rl
        if first is None:
            if up and dn:
                return Anchor("ambiguous", vol15, volshare15)
            if up:
                first, extreme = "up", h
            elif dn:
                first, extreme = "dn", l
            else:
                continue
        else:
            if (first == "up" and dn) or (first == "dn" and up):
                return Anchor("ambiguous", vol15, volshare15)
            extreme = max(extreme, h) if first == "up" else min(extreme, l)
        if (first == "up" and c < rh) or (first == "dn" and c > rl):
            confirm_i = i
            break

    if first is None:
        return Anchor("none", vol15, volshare15)
    if confirm_i is None:
        return Anchor("sweep_no_return", vol15, volshare15)

    c_ms = a_ms + confirm_i * BAR_MS
    path = _window(bars, c_ms + BAR_MS, HORIZON_BARS + 1)  # barres c+1 .. c+13
    if path is None:
        return Anchor("excluded", vol15, volshare15)
    side = -1 if first == "up" else 1
    entry, exit_ = path[0][0], path[-1][0]
    r_bps = side * (exit_ / entry - 1.0) * 1e4

    held = path[:HORIZON_BARS]  # c+1 .. c+12
    risk = abs(entry - extreme)
    mae_r = mfe_r = None
    if risk > 0:
        hi, lo = max(b[1] for b in held), min(b[2] for b in held)
        if side == 1:
            mfe_r, mae_r = (hi - entry) / risk, (entry - lo) / risk
        else:
            mfe_r, mae_r = (entry - lo) / risk, (hi - entry) / risk
    return Anchor("event", vol15, volshare15, side, c_ms, r_bps, mae_r, mfe_r)
