"""Deterministic fill simulation. Pure functions, no I/O, no wall clock.

Two models, always recorded on the result so a backtest can state exactly how
each fill was produced and what limits that puts on its representativeness:

- ``quote_based``: market buy fills at the ask, sell at the bid; the spread is
  therefore already in the price (do not add a spread fee on top). If the
  displayed top-of-book size is smaller than the order, only that size fills
  (partial) -- unless ``allow_partial`` is False, in which case nothing does.
- ``candle_only``: no book. The fill is the next bar's open moved against the
  taker by a configured half-spread plus slippage. Both are ASSUMPTIONS and are
  returned as such.

Randomness is opt-in and seeded (``jitter_bps`` with ``seed``) so a run is
reproducible bit for bit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.market_data.contracts import ExecutionMode, Quote


@dataclass(frozen=True)
class Fill:
    filled_qty: float
    price: float | None
    model: ExecutionMode
    requested_qty: float
    assumptions: tuple[str, ...] = ()
    reason: str = "filled"

    @property
    def is_partial(self) -> bool:
        return 0 < self.filled_qty < self.requested_qty

    @property
    def rejected(self) -> bool:
        return self.filled_qty <= 0


def _jitter(seed: int | None, jitter_bps: float) -> float:
    if not jitter_bps or seed is None:
        return 0.0
    return random.Random(seed).uniform(0.0, jitter_bps) / 10_000.0


def fill_at_quote(side: str, qty: float, quote: Quote, *, allow_partial: bool = True) -> Fill:
    """Market order against the top of book."""
    if qty <= 0:
        raise ValueError("qty must be positive")
    is_buy = side.upper() == "BUY"
    price = quote.ask if is_buy else quote.bid
    avail = quote.ask_size if is_buy else quote.bid_size
    notes = ("spread included in price via bid/ask", "top-of-book only: no deeper levels modelled")
    if avail is not None and qty > avail:
        if not allow_partial:
            return Fill(0.0, None, ExecutionMode.QUOTE_BASED, qty, notes, "insufficient_liquidity")
        return Fill(avail, price, ExecutionMode.QUOTE_BASED, qty, notes, "partial_top_of_book")
    return Fill(qty, price, ExecutionMode.QUOTE_BASED, qty, notes)


def fill_candle_only(
    side: str,
    qty: float,
    next_open: float,
    *,
    half_spread_bps: float,
    slippage_bps: float,
    jitter_bps: float = 0.0,
    seed: int | None = None,
) -> Fill:
    """Market order without a book: next bar open, adverse by configured costs."""
    if qty <= 0 or next_open <= 0:
        raise ValueError("qty and next_open must be positive")
    adverse = (half_spread_bps + slippage_bps) / 10_000.0 + _jitter(seed, jitter_bps)
    price = next_open * (1.0 + adverse) if side.upper() == "BUY" else next_open * (1.0 - adverse)
    notes = (
        f"ASSUMPTION half_spread={half_spread_bps}bps slippage={slippage_bps}bps (no bid/ask available)",
        "fill at next bar open; unlimited liquidity assumed",
    )
    return Fill(qty, price, ExecutionMode.CANDLE_ONLY, qty, notes)


@dataclass(frozen=True)
class BarExit:
    reason: str | None
    price: float | None
    note: str = ""


def resolve_bar_exit(
    direction: str, stop: float, target: float, bar_open: float, bar_high: float, bar_low: float
) -> BarExit:
    """Which protective level fills within one bar, with a conservative rule.

    - A gap through the stop fills at the OPEN (worse than the stop): a stop
      guarantees a trigger, not the trigger price.
    - If the bar spans both stop and target and the intrabar order is unknown,
      the STOP is assumed first.
    """
    long = direction.upper() == "LONG"
    if long:
        stop_hit = bar_low <= stop
        tgt_hit = bar_high >= target
        gapped_stop = bar_open <= stop
        gapped_tgt = bar_open >= target
    else:
        stop_hit = bar_high >= stop
        tgt_hit = bar_low <= target
        gapped_stop = bar_open >= stop
        gapped_tgt = bar_open <= target

    if gapped_stop:
        return BarExit("stop_gap", bar_open, "opened beyond stop; filled at open")
    if gapped_tgt:
        return BarExit("target_gap", bar_open, "opened beyond target; filled at open (favourable gap)")
    if stop_hit and tgt_hit:
        return BarExit("stop_hit", stop, "stop and target both inside bar; stop assumed first (conservative)")
    if stop_hit:
        return BarExit("stop_hit", stop, "stop filled at trigger price: optimistic, no intrabar slippage")
    if tgt_hit:
        return BarExit("target_hit", target)
    return BarExit(None, None)
