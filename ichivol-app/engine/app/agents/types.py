"""Shared StrategyAgent contract.

Mirrors the TypeScript interface defined in docs/TRADING_ARCHITECTURE_V2.md
§3 exactly, so any agent built here (Ichimoku now, RVOL/Momentum/Volatility/
Structure/Bayesian later) can eventually be combined by a Consensus Engine
without reshaping its output. This engine does not implement a Consensus
Engine, Edge Engine, or Risk Engine -- those are out of scope for this
mission (see docs/INTEGRATION_PLAN.md) and are left for whoever builds that
layer to consume this shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class StrategyAgentOutput:
    agent: str
    direction: Direction
    probability: float
    confidence: float
    expected_value: float
    reasons: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
