"""Partial take-profit helpers for Strategy Lab (T0-MANAGE-c).

Shared pure math so paper (T0-MANAGE-d) can reuse the same levels / VWAP.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.agents.types import Direction


@dataclass(frozen=True)
class PartialTpStep:
    """One DSL scale-out: close ``fraction`` of original qty once R hits ``r_multiple``."""

    r_multiple: float
    fraction: float


@dataclass(frozen=True)
class PartialExit:
    """One realized partial fill (fraction of original entry qty)."""

    bar_index: int
    price: float
    fraction: float
    r_multiple: float


def initial_risk(entry: float, initial_stop: float) -> float:
    return abs(entry - initial_stop)


def partial_level(
    direction: Direction,
    entry: float,
    initial_stop: float,
    r_multiple: float,
) -> float:
    """Limit price at ``r_multiple`` × initial risk from entry."""
    risk = initial_risk(entry, initial_stop)
    if risk <= 0 or r_multiple <= 0:
        raise ValueError("entry/stop risk and r_multiple must be > 0")
    if direction == Direction.LONG:
        return entry + r_multiple * risk
    return entry - r_multiple * risk


def mfe_r(
    direction: Direction,
    entry: float,
    initial_stop: float,
    high: float,
    low: float,
) -> float:
    """Max favorable R on this bar vs initial stop (no future bars)."""
    risk = initial_risk(entry, initial_stop)
    if risk <= 0:
        return 0.0
    if direction == Direction.LONG:
        return max(0.0, high - entry) / risk
    return max(0.0, entry - low) / risk


def vwap_exit(fills: list[tuple[float, float]]) -> float:
    """Qty-weighted average exit price. ``fills`` = [(price, fraction), ...], Σ fraction = 1."""
    if not fills:
        raise ValueError("fills required")
    total = sum(f for _, f in fills)
    if total <= 0:
        raise ValueError("fill fractions must sum to > 0")
    return sum(p * f for p, f in fills) / total


def log_return_from_vwap(
    direction: Direction,
    entry: float,
    exit_vwap: float,
) -> float:
    if entry <= 0 or exit_vwap <= 0:
        raise ValueError("entry and exit_vwap must be > 0")
    sign = 1.0 if direction == Direction.LONG else -1.0
    return sign * math.log(exit_vwap / entry)
