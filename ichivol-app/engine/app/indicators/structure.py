"""Price structure: swing highs/lows, HH/HL vs LH/LL bias, BOS / CHoCH,
and break quality (wick | close | confirmed).

Mission realignment (docs/METHODS-ROADMAP.md §4 step 2,
docs/TRADING_ARCHITECTURE_V2.md §1): Structure half of Direction/Structure.

Anti-lookahead by construction: a swing at index j is only usable once
``swing_lookback`` bars have passed (confirmed at j + swing_lookback).
A break with quality ``confirmed`` is never known before its confirmation
bar (see tests/indicators/test_t9b_choch.py).

T9b: ``StructureState.bos`` (legacy close-cross) stays bit-identical to
pre-T9b goldens. Richer ``StructureEvent`` (BOS|CHOCH + break_quality)
sits alongside; no FVG / no decision-pipeline change in this tranche.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Sequence

from app.indicators.atr import AtrParams, compute_atr
from app.indicators.ichimoku import Candle
from app.indicators.pivots import fractal_confirmed_at
from app.indicators.rvol import RvolParams, compute_rvol


class StructureBias(str, Enum):
    BULLISH = "BULLISH"  # last confirmed swing: higher high + higher low
    BEARISH = "BEARISH"  # last confirmed swing: lower high + lower low
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class BosEvent(str, Enum):
    """Legacy per-bar close-cross of last swing (golden-locked)."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class StructureEventType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"


class BreakQuality(str, Enum):
    WICK = "wick"
    CLOSE = "close"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class StructureParams:
    swing_lookback: int = 2
    """Bars required on each side of a candidate swing point before it is
    confirmed. Small default (2) for responsiveness on the timeframes this
    engine already screens (15m/1h/4h/1d); the classic 5-bar fractal is
    available by passing a larger value."""

    confirm_bars: int = 1
    """Subsequent bars *after* a close-break that must also close beyond
    the broken level before ``break_quality`` upgrades to ``confirmed``
    via the bar-count path. ``0`` disables the bar-count path (ATR
    displacement may still confirm). Explicit parameter — not a magic
    constant inside the detector."""

    confirm_displacement_atr: float = 1.0
    """If ATR is known and ``|close - level| / ATR >=`` this value on or
    after the close-break bar, quality upgrades to ``confirmed`` (ATR
    path). Explicit parameter."""


@dataclass(frozen=True)
class StructureEvent:
    """Discrete structure break (T9b) — BOS with bias, CHoCH against bias."""

    type: StructureEventType
    direction: Literal["bullish", "bearish"]
    level: float
    bar: int
    """Bar index at which this event becomes known (confirmation bar for
    ``confirmed`` quality; pierce/close bar otherwise)."""
    break_quality: BreakQuality
    displacement_atr: float | None
    rvol: float | None


@dataclass(frozen=True)
class StructureState:
    time: int
    last_swing_high: float | None
    last_swing_low: float | None
    bias: StructureBias
    bos: BosEvent
    """Legacy close-cross BOS — bit-identical to pre-T9b."""
    event: StructureEvent | None = None
    """Richest T9b event that becomes known on this bar, if any."""


def _classify_break(
    *,
    bullish_break: bool,
    bias: StructureBias,
) -> StructureEventType:
    """BOS = with bias; CHoCH = against bias. MIXED/UNKNOWN → BOS default."""
    if bullish_break:
        if bias == StructureBias.BEARISH:
            return StructureEventType.CHOCH
        return StructureEventType.BOS
    if bias == StructureBias.BULLISH:
        return StructureEventType.CHOCH
    return StructureEventType.BOS


@dataclass
class _PendingBreak:
    direction: Literal["bullish", "bearish"]
    level: float
    event_type: StructureEventType
    close_bar: int
    subsequent_beyond: int = 0


def compute_structure(
    candles: Sequence[Candle],
    params: StructureParams = StructureParams(),
) -> list[StructureState]:
    n = len(candles)
    k = params.swing_lookback

    last_high: float | None = None
    last_low: float | None = None
    prev_high: float | None = None
    prev_low: float | None = None
    bias = StructureBias.UNKNOWN

    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    atr_series = compute_atr(candles, AtrParams())
    rvol_series = compute_rvol(candles, RvolParams())

    pending: _PendingBreak | None = None
    out: list[StructureState] = []

    for i in range(n):
        # Shared causal fractal (T9a): pivot at j confirmed only at i = j + k.
        hi = fractal_confirmed_at(highs, i, left=k, right=k, mode="max")
        if hi is not None:
            prev_high, last_high = last_high, hi[1]
        lo = fractal_confirmed_at(lows, i, left=k, right=k, mode="min")
        if lo is not None:
            prev_low, last_low = last_low, lo[1]

        if hi is not None or lo is not None:
            if prev_high is not None and prev_low is not None:
                higher_high = last_high > prev_high
                higher_low = last_low > prev_low
                lower_high = last_high < prev_high
                lower_low = last_low < prev_low
                if higher_high and higher_low:
                    bias = StructureBias.BULLISH
                elif lower_high and lower_low:
                    bias = StructureBias.BEARISH
                else:
                    bias = StructureBias.MIXED

        # --- Legacy BOS (golden-locked close-cross) ---
        bos = BosEvent.UNKNOWN
        if last_high is not None and last_low is not None and i > 0:
            close = candles[i].close
            prev_close = candles[i - 1].close
            if prev_close <= last_high < close:
                bos = BosEvent.BULLISH
            elif prev_close >= last_low > close:
                bos = BosEvent.BEARISH
            else:
                bos = BosEvent.NONE

        # --- T9b StructureEvent (wick | close | confirmed) ---
        event: StructureEvent | None = None
        atr_now = atr_series[i].atr
        rvol_now = rvol_series[i].rvol
        c = candles[i]

        def _disp(level: float) -> float | None:
            if atr_now is None or atr_now <= 0:
                return None
            return abs(c.close - level) / atr_now

        def _make(
            *,
            bullish: bool,
            level: float,
            quality: BreakQuality,
            etype: StructureEventType,
        ) -> StructureEvent:
            return StructureEvent(
                type=etype,
                direction="bullish" if bullish else "bearish",
                level=level,
                bar=i,
                break_quality=quality,
                displacement_atr=_disp(level),
                rvol=rvol_now,
            )

        # Resolve pending confirmation first (anti-lookahead: only at i).
        if pending is not None:
            beyond = (
                c.close > pending.level
                if pending.direction == "bullish"
                else c.close < pending.level
            )
            if beyond:
                pending.subsequent_beyond += 1
            else:
                pending = None  # break invalidated

            if pending is not None:
                disp = _disp(pending.level)
                atr_ok = (
                    disp is not None and disp >= params.confirm_displacement_atr
                )
                bars_ok = (
                    params.confirm_bars > 0
                    and pending.subsequent_beyond >= params.confirm_bars
                )
                if atr_ok or bars_ok:
                    event = _make(
                        bullish=pending.direction == "bullish",
                        level=pending.level,
                        quality=BreakQuality.CONFIRMED,
                        etype=pending.event_type,
                    )
                    pending = None

        # Fresh pierce / close on this bar (may coexist with confirm on rare
        # overlaps — confirm wins if already set).
        if event is None and last_high is not None and last_low is not None and i > 0:
            prev_close = candles[i - 1].close
            close = c.close

            # Bullish side
            close_bull = prev_close <= last_high < close
            wick_bull = c.high > last_high and close <= last_high
            # Bearish side
            close_bear = prev_close >= last_low > close
            wick_bear = c.low < last_low and close >= last_low

            if close_bull:
                et = _classify_break(bullish_break=True, bias=bias)
                disp = _disp(last_high)
                atr_ok = (
                    disp is not None and disp >= params.confirm_displacement_atr
                )
                if atr_ok and params.confirm_bars == 0:
                    # ATR-only confirm allowed on the break bar itself.
                    event = _make(
                        bullish=True,
                        level=last_high,
                        quality=BreakQuality.CONFIRMED,
                        etype=et,
                    )
                    pending = None
                elif atr_ok:
                    # Close qualifies; ATR also met → confirmed same bar.
                    event = _make(
                        bullish=True,
                        level=last_high,
                        quality=BreakQuality.CONFIRMED,
                        etype=et,
                    )
                    pending = None
                else:
                    event = _make(
                        bullish=True,
                        level=last_high,
                        quality=BreakQuality.CLOSE,
                        etype=et,
                    )
                    pending = _PendingBreak(
                        direction="bullish",
                        level=last_high,
                        event_type=et,
                        close_bar=i,
                        subsequent_beyond=0,
                    )
            elif close_bear:
                et = _classify_break(bullish_break=False, bias=bias)
                disp = _disp(last_low)
                atr_ok = (
                    disp is not None and disp >= params.confirm_displacement_atr
                )
                if atr_ok:
                    event = _make(
                        bullish=False,
                        level=last_low,
                        quality=BreakQuality.CONFIRMED,
                        etype=et,
                    )
                    pending = None
                else:
                    event = _make(
                        bullish=False,
                        level=last_low,
                        quality=BreakQuality.CLOSE,
                        etype=et,
                    )
                    pending = _PendingBreak(
                        direction="bearish",
                        level=last_low,
                        event_type=et,
                        close_bar=i,
                        subsequent_beyond=0,
                    )
            elif wick_bull:
                et = _classify_break(bullish_break=True, bias=bias)
                event = _make(
                    bullish=True,
                    level=last_high,
                    quality=BreakQuality.WICK,
                    etype=et,
                )
            elif wick_bear:
                et = _classify_break(bullish_break=False, bias=bias)
                event = _make(
                    bullish=False,
                    level=last_low,
                    quality=BreakQuality.WICK,
                    etype=et,
                )

        out.append(
            StructureState(
                time=candles[i].time,
                last_swing_high=last_high,
                last_swing_low=last_low,
                bias=bias,
                bos=bos,
                event=event,
            )
        )

    return out
