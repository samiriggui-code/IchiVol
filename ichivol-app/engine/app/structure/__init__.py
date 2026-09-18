"""Market Structure lab — zones, trendlines, consensus (Phase 2).

Does not replace ``app.indicators.structure`` (HH/HL + BOS).
See docs/ARCHITECTURE-CONSOLIDEE-V2.md and docs/ANALYSE-STRUCTURE-ENGINES.md.
"""

from __future__ import annotations

from app.structure.breakout import BreakoutCandidate, evaluate_breakout
from app.structure.consensus import StructureConsensusEngine, build_consensus
from app.structure.detector import StructureDetector
from app.structure.params import StructureEngineParams
from app.structure.retest import RetestCandidate, evaluate_retest
from app.structure.service import detect_market_structure
from app.structure.types import (
    DetectorSource,
    LevelSide,
    MarketStructure,
    MarketStructureSnapshot,
    PivotPoint,
    PriceZone,
    TrendlineSegment,
)

__all__ = [
    "BreakoutCandidate",
    "DetectorSource",
    "LevelSide",
    "MarketStructure",
    "MarketStructureSnapshot",
    "PivotPoint",
    "PriceZone",
    "RetestCandidate",
    "StructureConsensusEngine",
    "StructureDetector",
    "StructureEngineParams",
    "TrendlineSegment",
    "build_consensus",
    "detect_market_structure",
    "evaluate_breakout",
    "evaluate_retest",
]
