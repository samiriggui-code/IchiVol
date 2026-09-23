"""Shared Market Structure datatypes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DetectorSource(str, Enum):
    MVPP = "mvpp"
    TRENDLN = "trendln"
    PYTRENDLINE = "pytrendline"
    CONSENSUS = "consensus"


class LevelSide(str, Enum):
    SUPPORT = "support"
    RESISTANCE = "resistance"


@dataclass(frozen=True)
class PivotPoint:
    bar_index: int
    time: int
    price: float
    side: LevelSide
    quality: float = 1.0
    is_high_volume: bool = False
    # Confirmation metadata (T1f) — measure/mark only; not exposed in API/goldens.
    confirmed_bar: int | None = None
    """Index of the bar at which this pivot becomes known (causal)."""
    provisional: bool = False
    """True if the pivot may disappear or change when a new bar arrives."""


@dataclass(frozen=True)
class TrendlineSegment:
    side: LevelSide
    slope: float
    intercept: float
    start_bar: int
    end_bar: int
    touch_count: int
    score: float
    source: DetectorSource
    pivot_bars: tuple[int, ...] = ()
    """Bars that touch the line (tolerance), not necessarily the fit anchors."""
    fit_pivot_bars: tuple[int, ...] = ()
    """The two (or more) pivot bar indices used to define slope/intercept."""

    def price_at(self, bar_index: int) -> float:
        return self.slope * bar_index + self.intercept


@dataclass(frozen=True)
class PriceZone:
    """ATR-normalized support/resistance zone (not a magic tick price)."""

    side: LevelSide
    low: float
    high: float
    mid: float
    score: float
    touch_count: int
    sources: tuple[DetectorSource, ...]
    atr_width: float | None = None

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high

    def distance(self, price: float) -> float:
        if price < self.low:
            return self.low - price
        if price > self.high:
            return price - self.high
        return 0.0


@dataclass(frozen=True)
class MarketStructure:
    """Snapshot from one StructureDetector."""

    source: DetectorSource
    pivots: tuple[PivotPoint, ...] = ()
    support_trendlines: tuple[TrendlineSegment, ...] = ()
    resistance_trendlines: tuple[TrendlineSegment, ...] = ()
    support_zones: tuple[PriceZone, ...] = ()
    resistance_zones: tuple[PriceZone, ...] = ()
    structure_score: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MarketStructureSnapshot:
    """Consensus view + optional per-detector raw results."""

    consensus: MarketStructure
    by_detector: dict[str, MarketStructure] = field(default_factory=dict)
    atr: float | None = None
    last_close: float | None = None
    distance_to_support: float | None = None
    distance_to_resistance: float | None = None
    breakout_candidates: tuple = ()
    retest_candidates: tuple = ()
