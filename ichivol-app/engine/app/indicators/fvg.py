"""Causal Fair Value Gap (3-candle ICT imbalance) — T9d.

On closed bar ``i``, candles ``c0=i-2``, ``c1=i-1``, ``c2=i``:

- Bullish FVG when ``c0.high < c2.low`` → gap ``[c0.high, c2.low]``
- Bearish FVG when ``c0.low > c2.high`` → gap ``[c2.high, c0.low]``

Known at bar ``i`` (no fractal lag). Fill / invalidation update causally on
later bars. Independent of T9c impulse by default.

No Fib rewrite (T9e), no decision pipeline, no broker. Lab keys EXPERIMENTAL.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Sequence

from app.indicators.atr import AtrParams, compute_atr
from app.indicators.ichimoku import Candle

FvgDirection = Literal["bullish", "bearish"]
FvgStatus = Literal["open", "partial", "filled", "invalidated"]


@dataclass(frozen=True)
class FvgParams:
    min_gap_atr: float = 0.0
    """Gap height / ATR must be >= this. Explicit; ``0`` = any geometric gap."""

    fill_mode: Literal["wick", "close"] = "wick"
    """Which price probes the gap for fill progression."""

    max_active: int = 32
    """Cap on concurrently tracked open/partial FVGs (oldest dropped)."""


@dataclass(frozen=True)
class FvgEvent:
    direction: FvgDirection
    bar: int
    """Discovery bar (= c2 index)."""
    start_bar: int
    mid_bar: int
    end_bar: int
    price_low: float
    price_high: float
    gap_atr: float | None
    status: FvgStatus
    fill_bar: int | None = None
    fill_ratio: float | None = None
    invalidated_bar: int | None = None


@dataclass(frozen=True)
class FvgState:
    time: int
    event: FvgEvent | None
    """FVG newly discovered on this bar (else None)."""
    active: tuple[FvgEvent, ...]
    """Open / partial gaps still live after this bar's updates."""


def _gap_height(low: float, high: float) -> float:
    return max(0.0, high - low)


def _probe(c: Candle, mode: str) -> tuple[float, float]:
    """Return (low_probe, high_probe) used for fill checks."""
    if mode == "close":
        return c.close, c.close
    return c.low, c.high


def _advance_fvg(ev: FvgEvent, c: Candle, bar: int, *, fill_mode: str) -> FvgEvent:
    if ev.status in ("filled", "invalidated"):
        return ev
    lo_p, hi_p = _probe(c, fill_mode)
    gap = _gap_height(ev.price_low, ev.price_high)
    if gap <= 0:
        return replace(ev, status="filled", fill_bar=bar, fill_ratio=1.0)

    if ev.direction == "bullish":
        if c.close < ev.price_low:
            return replace(
                ev,
                status="invalidated",
                invalidated_bar=bar,
                fill_ratio=1.0,
                fill_bar=ev.fill_bar or bar,
            )
        if lo_p < ev.price_high:
            if lo_p <= ev.price_low:
                return replace(ev, status="filled", fill_bar=bar, fill_ratio=1.0)
            traversed = max(0.0, ev.price_high - max(lo_p, ev.price_low))
            return replace(
                ev,
                status="partial",
                fill_bar=bar,
                fill_ratio=min(1.0, traversed / gap),
            )
    else:
        if c.close > ev.price_high:
            return replace(
                ev,
                status="invalidated",
                invalidated_bar=bar,
                fill_ratio=1.0,
                fill_bar=ev.fill_bar or bar,
            )
        if hi_p > ev.price_low:
            if hi_p >= ev.price_high:
                return replace(ev, status="filled", fill_bar=bar, fill_ratio=1.0)
            traversed = max(0.0, min(hi_p, ev.price_high) - ev.price_low)
            return replace(
                ev,
                status="partial",
                fill_bar=bar,
                fill_ratio=min(1.0, traversed / gap),
            )
    return ev


def compute_fvg(
    candles: Sequence[Candle],
    params: FvgParams | None = None,
) -> list[FvgState]:
    """Per-bar FVG series — causal, additive, no pipeline side effects."""
    p = params or FvgParams()
    n = len(candles)
    if n == 0:
        return []

    atr_states = compute_atr(candles, AtrParams())
    out: list[FvgState] = []
    live: list[FvgEvent] = []

    for i in range(n):
        # Advance existing gaps with this bar before discovering a new one.
        updated: list[FvgEvent] = []
        for ev in live:
            nxt = _advance_fvg(ev, candles[i], i, fill_mode=p.fill_mode)
            if nxt.status in ("open", "partial"):
                updated.append(nxt)
        live = updated

        event: FvgEvent | None = None
        if i >= 2:
            c0, c2 = candles[i - 2], candles[i]
            atr_val = atr_states[i].atr
            bull_gap = c0.high < c2.low
            bear_gap = c0.low > c2.high
            if bull_gap or bear_gap:
                if bull_gap:
                    direction: FvgDirection = "bullish"
                    price_low, price_high = float(c0.high), float(c2.low)
                else:
                    direction = "bearish"
                    price_low, price_high = float(c2.high), float(c0.low)
                height = _gap_height(price_low, price_high)
                gap_atr = (height / atr_val) if atr_val and atr_val > 0 else None
                ok = True
                if p.min_gap_atr > 0:
                    ok = gap_atr is not None and gap_atr >= p.min_gap_atr
                if ok and height > 0:
                    event = FvgEvent(
                        direction=direction,
                        bar=i,
                        start_bar=i - 2,
                        mid_bar=i - 1,
                        end_bar=i,
                        price_low=price_low,
                        price_high=price_high,
                        gap_atr=gap_atr,
                        status="open",
                    )
                    live.append(event)
                    if len(live) > p.max_active:
                        live = live[-p.max_active :]

        out.append(
            FvgState(
                time=candles[i].time,
                event=event,
                active=tuple(live),
            )
        )

    return out


__all__ = [
    "FvgDirection",
    "FvgEvent",
    "FvgParams",
    "FvgState",
    "FvgStatus",
    "compute_fvg",
]
