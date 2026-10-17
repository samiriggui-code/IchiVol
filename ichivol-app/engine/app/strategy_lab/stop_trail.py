"""Trailing / breakeven stop updates for Strategy Lab (T0-MANAGE-a).

Shared pure helpers so paper (T0-MANAGE-b) can call the same math later.
No lookahead: callers pass only bar-N (or earlier) OHLC / ATR.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.types import Direction


@dataclass(frozen=True)
class TrailSpec:
    """Optional mobile stop. At least one field must be set when present."""

    breakeven_at_r: float | None = None
    atr_trail_mult: float | None = None

    def is_empty(self) -> bool:
        return self.breakeven_at_r is None and self.atr_trail_mult is None


def initial_risk(entry: float, initial_stop: float) -> float:
    return abs(entry - initial_stop)


def round_trip_cost_fraction(commission_bps: float, slippage_bps: float) -> float:
    """Fractional price cost for a round trip (entry + exit), same basis as Lab."""
    return 2.0 * (commission_bps + slippage_bps) / 10_000.0


def trailing_exit_locks_net_profit(
    direction: Direction,
    *,
    entry_price: float,
    exit_price: float,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    extra_buffer: float = 0.0,
) -> bool:
    """True when a trail exit price is beyond round-trip fee breakeven.

    QuantDinger ``risk_guard.trailing_exit_locks_net_profit`` — adapted to IchiVol
    bps costs. Prevents presenting a trail exit as profit-protecting when fees
    would still leave a net loss.
    """
    try:
        entry = float(entry_price or 0.0)
        exit_px = float(exit_price or 0.0)
        extra = max(0.0, float(extra_buffer or 0.0))
    except (TypeError, ValueError):
        return False
    if entry <= 0 or exit_px <= 0:
        return False
    min_move = max(0.0, round_trip_cost_fraction(commission_bps, slippage_bps) + extra)
    if direction == Direction.LONG:
        return exit_px >= entry * (1.0 + min_move)
    if direction == Direction.SHORT:
        return exit_px <= entry * (1.0 - min_move)
    return False


def breakeven_price(
    direction: Direction,
    entry: float,
    *,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> float:
    """Stop that covers entry+exit fees (flat after costs)."""
    rt = round_trip_cost_fraction(commission_bps, slippage_bps)
    if direction == Direction.LONG:
        return entry * (1.0 + rt)
    return entry * (1.0 - rt)


def atr_trail_candidate(
    direction: Direction,
    close: float,
    atr: float,
    mult: float,
) -> float:
    if atr <= 0 or mult <= 0 or close <= 0:
        raise ValueError("close, atr, and atr_trail_mult must be > 0")
    if direction == Direction.LONG:
        return close - mult * atr
    return close + mult * atr


def ratchet_stop(direction: Direction, current: float, candidate: float) -> float:
    """Never move stop against the position (LONG: only up; SHORT: only down)."""
    if direction == Direction.LONG:
        return max(current, candidate)
    return min(current, candidate)


def favorable_excursion(
    direction: Direction,
    entry: float,
    high: float,
    low: float,
) -> float:
    """Max favorable move in price units using this bar's range (no future bars)."""
    if direction == Direction.LONG:
        return max(0.0, high - entry)
    return max(0.0, entry - low)


def update_trailing_stop(
    direction: Direction,
    current_stop: float,
    *,
    entry: float,
    initial_stop: float,
    high: float,
    low: float,
    close: float,
    atr: float | None,
    trail: TrailSpec | None,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
) -> float:
    """Apply trail updates for one closed bar; ratchet-only.

    Call **after** exit checks against ``current_stop`` so the new level
    applies from the next bar (no same-bar stop relocation after a hit).
    """
    if trail is None or trail.is_empty():
        return current_stop

    stop = current_stop
    risk = initial_risk(entry, initial_stop)
    if risk <= 0:
        return stop

    if trail.breakeven_at_r is not None:
        r_hit = favorable_excursion(direction, entry, high, low) / risk
        if r_hit + 1e-12 >= trail.breakeven_at_r:
            be = breakeven_price(
                direction,
                entry,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            )
            stop = ratchet_stop(direction, stop, be)

    if trail.atr_trail_mult is not None and atr is not None and atr > 0 and close > 0:
        cand = atr_trail_candidate(direction, close, atr, trail.atr_trail_mult)
        stop = ratchet_stop(direction, stop, cand)

    return stop
