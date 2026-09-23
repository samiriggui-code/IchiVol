"""Causal market-regime tags for Strategy Lab Phase 6.

Uses existing Grand V2 indicators only:
  - ADX strength → TRENDING vs RANGING
  - ATR percentile regime → HIGH / LOW / NORMAL volatility
  - +DI vs -DI → BULL / BEAR / SIDEWAYS (when a trend exists)

Never votes LONG/SHORT for entries — research segmentation only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.adx import AdxParams, TrendStrength
from app.indicators.atr import AtrParams, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY


class StructureRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    UNKNOWN = "UNKNOWN"


class VolRegime(str, Enum):
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class DirectionRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RegimeTags:
    structure: StructureRegime
    volatility: VolRegime
    direction: DirectionRegime

    def labels(self) -> tuple[str, ...]:
        """Orthogonal tags used as slice keys (excludes UNKNOWN)."""
        out: list[str] = []
        if self.structure != StructureRegime.UNKNOWN:
            out.append(self.structure.value)
        if self.volatility != VolRegime.UNKNOWN:
            out.append(self.volatility.value)
        if self.direction != DirectionRegime.UNKNOWN:
            out.append(self.direction.value)
        return tuple(out)


def _structure_from_adx(strength: TrendStrength) -> StructureRegime:
    if strength in (TrendStrength.TRENDING, TrendStrength.STRONG):
        return StructureRegime.TRENDING
    if strength in (TrendStrength.ABSENT, TrendStrength.DEVELOPING):
        return StructureRegime.RANGING
    return StructureRegime.UNKNOWN


def _vol_from_atr(regime: VolatilityRegime) -> VolRegime:
    if regime == VolatilityRegime.EXTREME:
        return VolRegime.HIGH_VOLATILITY
    if regime == VolatilityRegime.DEAD:
        return VolRegime.LOW_VOLATILITY
    if regime == VolatilityRegime.NORMAL:
        return VolRegime.NORMAL_VOLATILITY
    return VolRegime.UNKNOWN


def _direction_from_di(
    plus_di: float | None,
    minus_di: float | None,
    structure: StructureRegime,
    *,
    side_band: float = 2.0,
) -> DirectionRegime:
    if structure == StructureRegime.RANGING:
        return DirectionRegime.SIDEWAYS
    if plus_di is None or minus_di is None:
        return DirectionRegime.UNKNOWN
    if plus_di > minus_di + side_band:
        return DirectionRegime.BULL
    if minus_di > plus_di + side_band:
        return DirectionRegime.BEAR
    return DirectionRegime.SIDEWAYS


def classify_regimes(
    candles: Sequence[Candle],
    *,
    adx_params: AdxParams = AdxParams(),
    atr_params: AtrParams = AtrParams(),
) -> list[RegimeTags]:
    computed = REGISTRY.compute_many(
        ["adx", "atr"],
        candles,
        params_by_id={"adx": adx_params, "atr": atr_params},
    )
    adx = computed["adx"]
    atr = computed["atr"]
    if len(adx) != len(candles) or len(atr) != len(candles):
        raise ValueError("regime series length mismatch")
    out: list[RegimeTags] = []
    for a, v in zip(adx, atr):
        structure = _structure_from_adx(a.strength)
        volatility = _vol_from_atr(v.regime)
        direction = _direction_from_di(a.plus_di, a.minus_di, structure)
        out.append(
            RegimeTags(structure=structure, volatility=volatility, direction=direction)
        )
    return out
