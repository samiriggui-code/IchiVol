"""Causal price impulse / displacement leg — T9c.

An impulse is a pivot-to-pivot leg whose |end − start| / ATR meets an
explicit threshold. Emitted only when the completing opposite pivot is
confirmed (T9a fractal) — no lookahead.

Does not rewrite Fib's naive ``_pick_impulse_swings`` (T9e), does not emit
FVG (T9d), and does not change the decision pipeline. Lab keys are
EXPERIMENTAL (same split as T9b CHoCH).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from app.indicators.atr import AtrParams, compute_atr
from app.indicators.ichimoku import Candle
from app.indicators.pivots import CausalPivot, fractal_confirmed_at
from app.indicators.rvol import RvolParams, compute_rvol

ImpulseDirection = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class ImpulseParams:
    swing_lookback: int = 2
    """Bars on each side of a fractal pivot before it is confirmed (T9a)."""

    min_displacement_atr: float = 1.0
    """Leg |end − start| / ATR(end_bar) must be >= this to qualify.
    Explicit parameter — not a magic constant inside the detector."""

    min_rvol: float | None = None
    """Optional participation gate on the confirmation bar. ``None`` = off."""


@dataclass(frozen=True)
class ImpulseEvent:
    """One qualified pivot-to-pivot displacement leg."""

    direction: ImpulseDirection
    start_bar: int
    end_bar: int
    start_price: float
    end_price: float
    bar: int
    """Bar index at which this impulse becomes known (= completing pivot
    confirmation bar)."""
    displacement_atr: float
    rvol: float | None


@dataclass(frozen=True)
class ImpulseState:
    time: int
    event: ImpulseEvent | None
    """Impulse that becomes known on this bar (else None)."""
    active: ImpulseEvent | None
    """Last completed qualified impulse still current."""


def compute_impulse(
    candles: Sequence[Candle],
    params: ImpulseParams | None = None,
) -> list[ImpulseState]:
    """Per-bar impulse series — causal, additive, no pipeline side effects."""
    p = params or ImpulseParams()
    n = len(candles)
    if n == 0:
        return []

    atr_states = compute_atr(candles, AtrParams())
    rvol_states = compute_rvol(candles, RvolParams())
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    k = int(p.swing_lookback)

    out: list[ImpulseState] = []
    # Chronological confirmed pivots (by confirmation order).
    pivots: list[CausalPivot] = []
    active: ImpulseEvent | None = None

    for i in range(n):
        new_pivots: list[CausalPivot] = []
        h = fractal_confirmed_at(highs, i, left=k, right=k, mode="max")
        if h is not None:
            j, price = h
            new_pivots.append(
                CausalPivot(bar_index=j, price=price, confirmed_bar=i, kind="high")
            )
        lo = fractal_confirmed_at(lows, i, left=k, right=k, mode="min")
        if lo is not None:
            j, price = lo
            new_pivots.append(
                CausalPivot(bar_index=j, price=price, confirmed_bar=i, kind="low")
            )

        event: ImpulseEvent | None = None
        for pv in new_pivots:
            # Pair with the most recent opposite-kind pivot already known.
            opposite = None
            for prev in reversed(pivots):
                if prev.kind != pv.kind:
                    opposite = prev
                    break
            pivots.append(pv)
            if opposite is None:
                continue

            if pv.kind == "high" and opposite.kind == "low":
                direction: ImpulseDirection = "bullish"
                start, end = opposite, pv
            elif pv.kind == "low" and opposite.kind == "high":
                direction = "bearish"
                start, end = opposite, pv
            else:
                continue

            atr_val = atr_states[i].atr
            if atr_val is None or atr_val <= 0:
                continue
            disp = abs(end.price - start.price) / atr_val
            if disp < p.min_displacement_atr:
                continue

            rvol_val = rvol_states[i].rvol
            if p.min_rvol is not None:
                if rvol_val is None or rvol_val < p.min_rvol:
                    continue

            event = ImpulseEvent(
                direction=direction,
                start_bar=start.bar_index,
                end_bar=end.bar_index,
                start_price=start.price,
                end_price=end.price,
                bar=i,
                displacement_atr=disp,
                rvol=rvol_val,
            )
            active = event

        out.append(ImpulseState(time=candles[i].time, event=event, active=active))

    return out


__all__ = [
    "ImpulseDirection",
    "ImpulseEvent",
    "ImpulseParams",
    "ImpulseState",
    "compute_impulse",
]
