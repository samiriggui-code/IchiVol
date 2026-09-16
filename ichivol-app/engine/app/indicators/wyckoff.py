"""Wyckoff spring / upthrust detection -- V3 experimental candidate,
"logique maison" (docs/METHODS-ROADMAP.md: "Wyckoff | Accum / distrib /
spring... ? | Régime comportemental | V3 | OHLCV (+VP) | logique maison").

Full discretionary Wyckoff (composite operator theory, Phase A-E
schematics) is not something a deterministic function can honestly claim
to encode -- classifying a multi-bar structure as "really" accumulation
vs. distribution needs context (prior trend, effort-vs-result across many
bars) this module does not attempt to judge. Instead this operationalizes
only the two most literal, widely-cited Wyckoff patterns:

- SPRING: a false breakdown below support that gets reabsorbed within the
  same bar (low pierces the range floor, close reclaims back above it) on
  climax volume -- classically read as absorption/accumulation, a bullish
  *tell*, never a BUY signal itself.
- UPTHRUST: the mirror -- a false breakout above resistance that gets
  rejected within the same bar, on climax volume -- classically read as
  distribution, a bearish tell.

Everything else that isn't one of these two literal tests reports RANGING
or TRENDING (see WyckoffPhase) rather than a guessed-at phase label.

Never votes LONG/SHORT (docs/METHODS-ROADMAP.md §6 rule 3: "ATR / ADX /
Wyckoff ne votent jamais"). Not wired into the live pipeline by default --
same "prove it, don't assume it" path as ADX before its promotion (see
app/backtest/experiments.py's PIPELINE_WYCKOFF_FILTER and the engine
README's ADX section for the precedent this follows).

Built on top of app/indicators/donchian.py's prior-period range (the same
"real breakout of a real range" primitive) instead of redefining its own
support/resistance -- a spring or upthrust only means something relative
to a level the market has already respected. Anti-lookahead by
construction: depends only on donchian_states[i] (itself causal) and
candles[..i] -- never a future bar. See
tests/indicators/test_wyckoff_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.donchian import DonchianBreakout, DonchianState
from app.indicators.ichimoku import Candle


class WyckoffPhase(str, Enum):
    SPRING = "SPRING"
    """False breakdown, reabsorbed on climax volume -- bullish tell."""
    UPTHRUST = "UPTHRUST"
    """False breakout, rejected on climax volume -- bearish tell."""
    RANGING = "RANGING"
    """Contained inside the prior range -- no test in play."""
    TRENDING = "TRENDING"
    """A breakout still holding (no same-bar reclaim/rejection) -- not a test."""
    UNKNOWN = "UNKNOWN"
    """Not enough history yet for a range to test against."""


@dataclass(frozen=True)
class WyckoffParams:
    volume_climax_ratio: float = 1.5
    """A spring/upthrust wick needs volume at least this many times the
    trailing average to count as a real test, not just drift past the
    level on thin volume."""
    volume_lookback: int = 20


@dataclass(frozen=True)
class WyckoffState:
    time: int
    phase: WyckoffPhase
    tested_level: float | None
    """The support (SPRING) or resistance (UPTHRUST) level that was
    tested, when phase is SPRING/UPTHRUST -- None otherwise."""


def _avg_volume(candles: Sequence[Candle], i: int, lookback: int) -> float | None:
    start = max(0, i - lookback)
    window = [c.volume for c in candles[start:i]]  # strictly PRIOR bars, i excluded
    if not window:
        return None
    return sum(window) / len(window)


def compute_wyckoff(
    candles: Sequence[Candle],
    donchian_states: Sequence[DonchianState],
    params: WyckoffParams = WyckoffParams(),
) -> list[WyckoffState]:
    if len(candles) != len(donchian_states):
        raise ValueError("candles and donchian_states must be the same length")

    out: list[WyckoffState] = []
    for i, (c, d) in enumerate(zip(candles, donchian_states)):
        if d.breakout == DonchianBreakout.UNKNOWN or d.upper is None or d.lower is None:
            out.append(WyckoffState(time=c.time, phase=WyckoffPhase.UNKNOWN, tested_level=None))
            continue

        avg_vol = _avg_volume(candles, i, params.volume_lookback)
        vol_ratio = (c.volume / avg_vol) if avg_vol and avg_vol > 0 else None
        climax = vol_ratio is not None and vol_ratio >= params.volume_climax_ratio

        # Spring: this bar's LOW pierces below the prior range's floor, but
        # its CLOSE reclaims back above it -- a false breakdown, not a real one.
        pierced_low = c.low < d.lower
        reclaimed_low = c.close >= d.lower
        # Upthrust: mirror -- pierces the ceiling, closes back under it.
        pierced_high = c.high > d.upper
        rejected_high = c.close <= d.upper

        if pierced_low and reclaimed_low and climax:
            phase, level = WyckoffPhase.SPRING, d.lower
        elif pierced_high and rejected_high and climax:
            phase, level = WyckoffPhase.UPTHRUST, d.upper
        elif d.breakout == DonchianBreakout.INSIDE:
            phase, level = WyckoffPhase.RANGING, None
        else:
            phase, level = WyckoffPhase.TRENDING, None

        out.append(WyckoffState(time=c.time, phase=phase, tested_level=level))

    return out
