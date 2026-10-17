"""Ève's question batteries — one JEV call per decision, each mode asking only what it needs.

Atomic questions, composed in code (idea from buberlo/jev-trader); every CHOICE keeps an explicit
abstain / insufficient option (QuantDinger) so JEV is never forced to pick a side without evidence.
Questions are in English (JEV's training language); the UI shows them in French (``LABELS_FR``).
"""

from __future__ import annotations

from typing import Any

BATTERY_VERSION = "eve-v1"

QUALITY_LEVELS = [
    "No trade: the calculations show no usable opportunity",
    "Weak: one or two signals, many contradictions",
    "Average: a direction is visible but important confirmations are missing",
    "Good: most calculations agree, few contradictions",
    "Excellent: trend, participation, structure, location and regime all agree",
]
RISK_LEVELS = [
    "Calm: no visible threat to a position",
    "Elevated: some adverse signals, stay alert",
    "High: several adverse signals, position at risk",
    "Critical: the calculations show a likely adverse move now",
]

_INPUTS = (
    "`engine` holds every IchiVol calculation for the last closed bar: `pipeline` (staged decision: direction "
    "from Ichimoku, participation from RVOL/CVD/OI, structure with BOS and higher-timeframe alignment, location "
    "vs value area / VWAP / AVWAP, regime from ATR / ADX / Donchian), `ichimoku`, `rvol_detail`, `risk` (ATR stop "
    "distance), `context`, `lab_context` (CHoCH, FVG, Fibonacci, impulse), `mtf_matrix` (1h/4h/1d/1w), `evidence` "
    "(historical matches, contradictions, invalidation), anomalies and data quality. `portfolio.position` is what "
    "we hold now."
)


def entry_battery(*, allow_short: bool) -> dict[str, dict[str, Any]]:
    """Flat on this market: decide long / short / abstain."""
    criteria = {
        "long": "Buy now: the calculations make a rise over the next bars more likely than a fall.",
        "abstain": "Do nothing: no edge, contradictory or insufficient calculations.",
    }
    if allow_short:
        criteria = {
            "long": criteria["long"],
            "short": "Sell short now: the calculations make a fall over the next bars more likely than a rise.",
            "abstain": criteria["abstain"],
        }
    return {
        # Ève Analyst / decision
        "decision": {
            "type": "choice",
            "instructions": {
                "question": "Which trade should be taken on this market now?",
                "goal": "A position opened now is protected by the engine's ATR stop and a 2R target.",
                "inputs": _INPUTS,
            },
            "criteria": criteria,
        },
        "regime": {
            "type": "choice",
            "instructions": "Which market regime do the calculations describe?",
            "criteria": {
                "trend": "Directional trend with participation",
                "range": "Range / mean reversion",
                "volatile": "Disorderly or extreme volatility",
                "insufficient": "Not enough reliable calculations to say",
            },
        },
        "quality": {
            "type": "score",
            "instructions": "How good is the best available trade according to the calculations?",
            "criteria": QUALITY_LEVELS,
        },
        # Ève Challenger
        "contradiction": {
            "type": "noul",
            "instructions": (
                "Do the calculations contain a material contradiction against the most likely direction "
                "(higher timeframe opposed, weak participation, adverse location, dead or extreme regime, "
                "structure break against it)?"
            ),
        },
        # Ève Shadow — independent check of the engine's own staged verdict
        "engine_supported": {
            "type": "noul",
            "instructions": "Does the evidence support the decision written in `engine.pipeline.decision`?",
        },
    }


def manage_battery(*, direction: str) -> dict[str, dict[str, Any]]:
    """Holding a position: keep it or liquidate it."""
    side = "long" if direction == "LONG" else "short"
    return {
        "manage": {
            "type": "choice",
            "instructions": {
                "question": f"We hold a {side} position (see `portfolio.position`). Keep it or close it now?",
                "goal": "The engine's stop and target stay active either way; closing locks the current result.",
                "inputs": _INPUTS,
            },
            "criteria": {
                "hold": f"Keep the {side}: the calculations still favour this direction.",
                "close": f"Close the {side} now: the calculations turned against it or the edge is gone.",
            },
        },
        # Ève Guardian
        "position_risk": {
            "type": "score",
            "instructions": "How threatened is the open position according to the calculations?",
            "criteria": RISK_LEVELS,
        },
        "thesis_valid": {
            "type": "noul",
            "instructions": f"Is the {side} thesis still supported by the calculations?",
        },
        "engine_supported": {
            "type": "noul",
            "instructions": "Does the evidence support the decision written in `engine.pipeline.decision`?",
        },
    }


LABELS_FR: dict[str, str] = {
    "decision": "Décision (CHOICE)",
    "regime": "Régime (CHOICE)",
    "quality": "Qualité de l'opportunité (SCORE)",
    "contradiction": "Contradiction (NOUL, Challenger)",
    "engine_supported": "Le moteur est-il soutenu ? (NOUL, Shadow)",
    "manage": "Garder ou liquider (CHOICE)",
    "position_risk": "Risque de la position (SCORE, Guardian)",
    "thesis_valid": "Thèse toujours valable ? (NOUL)",
}
