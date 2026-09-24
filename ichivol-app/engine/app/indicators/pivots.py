"""Causal swing / fractal pivots — T9a single detector core.

A pivot centered at bar ``j`` with spans ``left`` / ``right`` is known only
when bar ``i = j + right`` is closed (the right-hand window is complete).
Callers must not emit or consume a pivot before that confirmation index.

Consumed by:
- ``app.indicators.structure`` (HH/HL/BOS — detector-specific bias/BOS on top)
- ``app.fibonacci.context`` (impulse / Fib levels — detector-specific)
- ``app.structure.adapters`` (MVPP adaptive prices, trendln clusters,
  pytrendline provisional anchors — adapter-specific post-processing)

Goldens for structure + fibonacci must stay bit-identical after wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

ExtremumMode = Literal["max", "min"]


@dataclass(frozen=True)
class CausalPivot:
    """One confirmed fractal pivot."""

    bar_index: int
    """Index ``j`` of the extremum candle (not the confirmation bar)."""
    price: float
    confirmed_bar: int
    """Index ``i = j + right`` at which the pivot becomes known."""
    kind: Literal["high", "low"]


def fractal_confirmed_at(
    series: Sequence[float],
    i: int,
    *,
    left: int,
    right: int,
    mode: ExtremumMode,
) -> tuple[int, float] | None:
    """If bar ``i`` confirms a fractal at ``j = i - right``, return ``(j, price)``.

    Returns ``None`` when the left window is incomplete or ``series[j]`` is not
    a strict window extremum (equality with ``max``/``min`` — same as legacy).
    """
    if left < 0 or right < 0:
        raise ValueError("left/right must be >= 0")
    j = i - right
    if j - left < 0:
        return None
    if i >= len(series) or j >= len(series):
        return None
    window = series[j - left : j + right + 1]
    if len(window) < left + right + 1:
        return None
    center = series[j]
    if mode == "max":
        if center != max(window):
            return None
    else:
        if center != min(window):
            return None
    return j, float(center)


def detect_causal_extrema(
    values: Sequence[float],
    *,
    left: int,
    right: int,
    mode: ExtremumMode,
) -> list[tuple[int, float, int]]:
    """All confirmed extrema as ``(bar_index, price, confirmed_bar)``.

    Emits at scan index ``i`` only when ``i == j + right`` (no lookahead).
    """
    n = len(values)
    out: list[tuple[int, float, int]] = []
    for i in range(n):
        hit = fractal_confirmed_at(values, i, left=left, right=right, mode=mode)
        if hit is None:
            continue
        j, price = hit
        out.append((j, price, j + right))
    return out


def detect_causal_ohlc_fractals(
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    left: int,
    right: int,
) -> tuple[list[CausalPivot], list[CausalPivot]]:
    """Causal high/low fractals on OHLC extremes (Fib / structure raw path)."""
    if len(highs) != len(lows):
        raise ValueError("highs and lows must have the same length")
    high_pivots: list[CausalPivot] = []
    low_pivots: list[CausalPivot] = []
    n = len(highs)
    for i in range(n):
        h = fractal_confirmed_at(highs, i, left=left, right=right, mode="max")
        if h is not None:
            j, price = h
            high_pivots.append(
                CausalPivot(bar_index=j, price=price, confirmed_bar=j + right, kind="high")
            )
        lo = fractal_confirmed_at(lows, i, left=left, right=right, mode="min")
        if lo is not None:
            j, price = lo
            low_pivots.append(
                CausalPivot(bar_index=j, price=price, confirmed_bar=j + right, kind="low")
            )
    return high_pivots, low_pivots
