"""Renforcement (pyramiding) helpers for Strategy Lab — T0-MANAGE-e.

Pure math shared with a future paper path (T0-MANAGE-f). Invariant: after an
add, open risk ``|avg_entry − stop| × qty`` never exceeds the risk at the
original entry (before any reinforce).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.agents.types import Direction

RiskPolicy = Literal["reduce_qty", "tighten_stop"]


@dataclass(frozen=True)
class ReinforceAdd:
    """One realized scale-in fill."""

    bar_index: int
    price: float
    fraction: float
    """Actual added fraction (after clamp)."""
    requested_fraction: float
    stop_after: float
    avg_entry_after: float
    open_risk_after: float
    clamped: bool


def open_risk(avg_entry: float, stop: float, qty: float) -> float:
    """Open risk in price×qty units: ``|avg_entry − stop| × qty``."""
    if qty <= 0:
        return 0.0
    return abs(float(avg_entry) - float(stop)) * float(qty)


def avg_entry_after_add(
    avg_entry: float,
    qty: float,
    add_price: float,
    add_qty: float,
) -> float:
    total = float(qty) + float(add_qty)
    if total <= 0:
        return float(avg_entry)
    return (float(avg_entry) * float(qty) + float(add_price) * float(add_qty)) / total


def _risk_after(
    avg_entry: float,
    qty: float,
    stop: float,
    add_price: float,
    add_qty: float,
    new_stop: float | None = None,
) -> float:
    if add_qty <= 0:
        return open_risk(avg_entry, stop if new_stop is None else new_stop, qty)
    avg = avg_entry_after_add(avg_entry, qty, add_price, add_qty)
    st = stop if new_stop is None else new_stop
    return open_risk(avg, st, qty + add_qty)


def max_add_qty_under_risk(
    *,
    avg_entry: float,
    qty: float,
    stop: float,
    add_price: float,
    requested_add: float,
    initial_risk: float,
    eps: float = 1e-12,
) -> float:
    """Largest ``add_qty ∈ [0, requested]`` such that open risk ≤ ``initial_risk``."""
    if requested_add <= 0 or initial_risk <= 0 or qty <= 0:
        return 0.0
    if _risk_after(avg_entry, qty, stop, add_price, requested_add) <= initial_risk + eps:
        return float(requested_add)

    # Already at/over cap with zero add → cannot add.
    if open_risk(avg_entry, stop, qty) >= initial_risk - eps:
        # Still allow a tiny add only if it somehow reduces risk (add toward stop).
        if _risk_after(avg_entry, qty, stop, add_price, requested_add) >= open_risk(
            avg_entry, stop, qty
        ) - eps:
            return 0.0

    lo, hi = 0.0, float(requested_add)
    for _ in range(60):
        mid = (lo + hi) * 0.5
        if _risk_after(avg_entry, qty, stop, add_price, mid) <= initial_risk + eps:
            lo = mid
        else:
            hi = mid
    return lo


def tighten_stop_for_add(
    *,
    direction: Direction,
    avg_entry: float,
    qty: float,
    stop: float,
    add_price: float,
    add_qty: float,
    initial_risk: float,
) -> float:
    """New stop so open risk after add equals ``initial_risk`` (never widens)."""
    if add_qty <= 0:
        return float(stop)
    avg = avg_entry_after_add(avg_entry, qty, add_price, add_qty)
    total = float(qty) + float(add_qty)
    if total <= 0 or initial_risk <= 0:
        return float(stop)
    dist = initial_risk / total
    if direction == Direction.LONG:
        # Stop below avg; tightening raises the stop.
        candidate = avg - dist
        return max(float(stop), candidate)
    candidate = avg + dist
    return min(float(stop), candidate)


def apply_reinforce_add(
    *,
    direction: Direction,
    avg_entry: float,
    qty: float,
    stop: float,
    add_price: float,
    requested_add: float,
    initial_risk: float,
    policy: RiskPolicy = "reduce_qty",
) -> tuple[float, float, float, float, bool]:
    """Apply one add under the risk invariant.

    Returns ``(actual_add, new_avg, new_stop, new_qty, clamped)``.
    """
    req = max(0.0, float(requested_add))
    if req <= 0 or qty <= 0:
        return 0.0, float(avg_entry), float(stop), float(qty), False

    if policy == "tighten_stop":
        new_stop = tighten_stop_for_add(
            direction=direction,
            avg_entry=avg_entry,
            qty=qty,
            stop=stop,
            add_price=add_price,
            add_qty=req,
            initial_risk=initial_risk,
        )
        avg = avg_entry_after_add(avg_entry, qty, add_price, req)
        new_qty = qty + req
        # Guard: if tightening still cannot meet R0 (shouldn't), fall back to reduce.
        if open_risk(avg, new_stop, new_qty) > initial_risk + 1e-9:
            actual = max_add_qty_under_risk(
                avg_entry=avg_entry,
                qty=qty,
                stop=stop,
                add_price=add_price,
                requested_add=req,
                initial_risk=initial_risk,
            )
            if actual <= 1e-15:
                return 0.0, float(avg_entry), float(stop), float(qty), True
            avg = avg_entry_after_add(avg_entry, qty, add_price, actual)
            return actual, avg, float(stop), qty + actual, actual + 1e-12 < req
        clamped = abs(new_stop - stop) > 1e-12
        return req, avg, new_stop, new_qty, clamped

    # Default: reduce_qty
    actual = max_add_qty_under_risk(
        avg_entry=avg_entry,
        qty=qty,
        stop=stop,
        add_price=add_price,
        requested_add=req,
        initial_risk=initial_risk,
    )
    if actual <= 1e-15:
        return 0.0, float(avg_entry), float(stop), float(qty), req > 0
    avg = avg_entry_after_add(avg_entry, qty, add_price, actual)
    return actual, avg, float(stop), qty + actual, actual + 1e-12 < req
