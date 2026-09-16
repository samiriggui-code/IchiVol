"""Ichimoku x RVOL combiner -- this mission's Decision Engine (brief §6, §8).

STATUS (2026-09-15 north star realignment, docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md):
this is the **MVP shortcut**, not the locked product rule. `confidence =
ichimoku.confidence * rvol.confidence` is explicitly called out in
docs/TRADING_ARCHITECTURE_V2.md §2 as forbidden as a *final* design ("pas de
multiplication arbitraire comme regle produit definitive"). The target is a
staged gate pipeline (Direction -> Participation -> Structure/MTF -> Location
-> Regime/Risk -> label), not a two-factor product. This module is not being
replaced in this pass -- see docs/METHODS-ROADMAP.md for the build order
(structure_agent + MTF, then volatility_agent/ATR, before the combiner itself
is restructured into stages) -- but nobody should read the code below as the
intended long-term decision rule. `Decision.decision` values here
(STRONG_BUY/BUY/WATCH/WAIT/SELL/STRONG_SELL) are also legacy; the target
label set is BUY/SELL/WATCH/NO_TRADE (+ a separate quality signal) per
TRADING_ARCHITECTURE_V2.md §2 -- not changed here yet since the frontend
(DecisionsPage.tsx / decisionLabels.ts) still reads today's values, and
ichivol-app/src/lib/decisionPipeline.ts already has a graceful
native-vs-adapted fallback ready for whenever this does change.

Principle, straight from the brief: Ichimoku determines STRUCTURE/DIRECTION,
RVOL determines PARTICIPATION/CONVICTION. Concretely:

- Only ICHIMOKU_AGENT's direction is used. RVOL_AGENT never votes on
  direction (see app/agents/rvol_agent.py) -- it only scales confidence.
- `probability` is passed through unchanged from ICHIMOKU_AGENT: RVOL has
  no opinion on whether the direction call is correct, only on how well
  participation supports it. Conflating the two would hide information a
  future Consensus Engine (or a human) might want separately.
- `confidence` is multiplicative: ichimoku.confidence * rvol.confidence.
  This reproduces the brief's worked example directly -- a textbook-perfect
  Ichimoku confluence (confidence ~1.0) paired with RVOL = 0.55 (low
  participation, confidence ~0.1) collapses combined confidence to ~0.1
  (WATCH), while the same Ichimoku setup with RVOL = 2.8 (confidence ~1.0)
  keeps combined confidence high (STRONG_BUY) -- a simple average would not
  punish low participation nearly as hard, and would misrepresent RVOL's
  role as a confirmation *gate* rather than an equal-weight voter.

This is a fixed, hardcoded, two-agent combiner -- not a general pluggable
Consensus Engine (out of scope; see docs/TRADING_ARCHITECTURE_V2.md). The
LLM plays no part in this computation, per the mission's explicit rule:
the quantitative engine produces the decision and its reasons first; an LLM
may only explain/summarize/comment on it afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.types import Direction, StrategyAgentOutput

STRATEGY_VERSION = "ichimoku_rvol_v1"

_STRONG_THRESHOLD = 0.75
_ACTIONABLE_THRESHOLD = 0.4
_LOW_RVOL_RISK_THRESHOLD = 0.4
_LOW_ICHIMOKU_RISK_THRESHOLD = 0.6


@dataclass(frozen=True)
class DecisionResult:
    strategy_version: str
    decision: str  # STRONG_BUY | BUY | WATCH | WAIT | SELL | STRONG_SELL
    direction: Direction
    probability: float
    confidence: float
    agreement: float
    weights_used: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)


def _decision_label(direction: Direction, confidence: float) -> str:
    if direction == Direction.NEUTRAL:
        return "WAIT"
    if direction == Direction.LONG:
        if confidence >= _STRONG_THRESHOLD:
            return "STRONG_BUY"
        if confidence >= _ACTIONABLE_THRESHOLD:
            return "BUY"
        return "WATCH"
    # SHORT
    if confidence >= _STRONG_THRESHOLD:
        return "STRONG_SELL"
    if confidence >= _ACTIONABLE_THRESHOLD:
        return "SELL"
    return "WATCH"


def _risks(ichimoku: StrategyAgentOutput, rvol: StrategyAgentOutput) -> list[str]:
    risks = []
    if rvol.confidence < _LOW_RVOL_RISK_THRESHOLD:
        risks.append("low_relative_volume_participation")
    if ichimoku.confidence < _LOW_ICHIMOKU_RISK_THRESHOLD:
        risks.append("incomplete_ichimoku_confluence")
    if ichimoku.direction == Direction.NEUTRAL:
        risks.append("no_clear_structural_bias")
    return risks


def combine_ichimoku_rvol(
    ichimoku: StrategyAgentOutput,
    rvol: StrategyAgentOutput,
) -> DecisionResult:
    if ichimoku.agent != "ICHIMOKU_AGENT" or rvol.agent != "RVOL_AGENT":
        raise ValueError(
            f"combine_ichimoku_rvol expects (ICHIMOKU_AGENT, RVOL_AGENT), "
            f"got ({ichimoku.agent!r}, {rvol.agent!r})"
        )

    direction = ichimoku.direction
    probability = ichimoku.probability
    confidence = round(ichimoku.confidence * rvol.confidence, 4)
    decision = _decision_label(direction, confidence)

    return DecisionResult(
        strategy_version=STRATEGY_VERSION,
        decision=decision,
        direction=direction,
        probability=probability,
        confidence=confidence,
        agreement=rvol.confidence,
        weights_used={
            "ICHIMOKU_AGENT": "direction+probability",
            "RVOL_AGENT": "confidence_multiplier",
            "rvol_confidence": rvol.confidence,
            "ichimoku_confidence": ichimoku.confidence,
        },
        reasons=[*ichimoku.reasons, *rvol.reasons],
        risks=_risks(ichimoku, rvol),
        invalidation=ichimoku.invalidation,
    )
