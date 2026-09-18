"""Breakout engine — close beyond zone + ATR distance (not price > level)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.structure.types import LevelSide, PriceZone


@dataclass(frozen=True)
class BreakoutCandidate:
    side: LevelSide
    """RESISTANCE breakout → bullish candidate; SUPPORT → bearish."""
    zone: PriceZone
    close: float
    distance_atr: float | None
    body_ratio: float
    rvol: float | None
    confirmed: bool
    reason: str


def evaluate_breakout(
    candle: Candle,
    zones: Sequence[PriceZone],
    *,
    atr: float | None,
    rvol: float | None = None,
    min_distance_atr: float = 0.1,
    min_rvol: float | None = 1.2,
) -> list[BreakoutCandidate]:
    body = abs(candle.close - candle.open)
    full = max(candle.high - candle.low, 1e-9)
    body_ratio = body / full
    out: list[BreakoutCandidate] = []

    for zone in zones:
        if zone.side == LevelSide.RESISTANCE:
            beyond = candle.close > zone.high
            distance = candle.close - zone.high
        else:
            beyond = candle.close < zone.low
            distance = zone.low - candle.close
        if not beyond:
            continue

        dist_atr = (distance / atr) if atr and atr > 0 else None
        reasons: list[str] = ["close_beyond_zone"]
        ok = True
        if dist_atr is not None and dist_atr < min_distance_atr:
            ok = False
            reasons.append("distance_atr_too_small")
        elif dist_atr is not None:
            reasons.append(f"distance_atr={dist_atr:.2f}")

        if min_rvol is not None and rvol is not None:
            if rvol < min_rvol:
                ok = False
                reasons.append("rvol_weak")
            else:
                reasons.append(f"rvol={rvol:.2f}")

        if body_ratio < 0.4:
            reasons.append("small_body")
        else:
            reasons.append(f"body_ratio={body_ratio:.2f}")

        out.append(
            BreakoutCandidate(
                side=zone.side,
                zone=zone,
                close=candle.close,
                distance_atr=dist_atr,
                body_ratio=body_ratio,
                rvol=rvol,
                confirmed=ok,
                reason=";".join(reasons),
            )
        )
    return out
