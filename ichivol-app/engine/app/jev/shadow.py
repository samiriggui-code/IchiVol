"""Ève Shadow mode — independent JEV/jevos counter-evaluation, no execution.

Not to be confused with ShadowBroker (engine/app/shadow): Python counterfactual
paper positions when a filter blocks a trade.

``compare_decision`` uses NOUL + CHOICE + SCORE (same set as Eve Shadow mode
defaults from the Mode×primitive study).
"""

from __future__ import annotations

import logging
import time

from app.jev.adapter import evaluate as adapter_evaluate
from app.jev.history import save_evaluation
from app.jev.questions import choice_question, noul_question, score_question

# Aligned with app.eve.modes.DEFAULT_PRIMITIVES["shadow"] / primitive_study routing.
SHADOW_PRIMITIVES: tuple[str, ...] = ("noul", "choice", "score")


def _shadow_questions(primitives: tuple[str, ...] | list[str]) -> dict:
    q: dict = {}
    for p in primitives:
        if p == "noul":
            q["review"] = noul_question(
                "Does the supplied evidence support the existing decision? "
                "Assess consistency only. Do not suggest trade execution."
            )
        elif p == "choice":
            q["independent_action"] = choice_question(
                "Independent counter-evaluation: which action is most consistent with the evidence?",
                {
                    "LONG": "long",
                    "SHORT": "short",
                    "HOLD": "hold",
                    "CLOSE": "close",
                    "ABSTAIN": "abstain",
                },
            )
        elif p == "score":
            q["audit_confidence"] = score_question(
                "Confidence in the original decision under independent review.",
                ["Reject", "Weak", "Mixed", "Acceptable", "Strong"],
            )
    return q


def compare_decision(data: dict) -> dict:
    """Observe-only Shadow protocol (NOUL + CHOICE + SCORE). Never suggests execution."""
    pipeline = data.get("pipeline") or {}
    original = pipeline.get("decision") or data.get("decision")
    state = {
        "symbol": data.get("symbol"),
        "timeframe": data.get("timeframe"),
        "decision": original,
        "pipeline": pipeline,
    }
    primitives = list(SHADOW_PRIMITIVES)
    questions = _shadow_questions(primitives)
    started = time.monotonic()
    envelope = adapter_evaluate(state, questions)
    latency_ms = envelope.get("latency_ms")
    if latency_ms is None:
        latency_ms = round((time.monotonic() - started) * 1000, 2)

    # Persist panel-compatible payload (answers.review / independent_action / audit_confidence).
    if envelope.get("ok"):
        jev_payload = {
            "ok": True,
            "result": envelope.get("raw")
            if isinstance(envelope.get("raw"), dict)
            else {"answers": envelope.get("answers")},
            "provider": envelope.get("provider"),
            "response_model": envelope.get("response_model"),
            "request_model": envelope.get("request_model"),
            "score_maturity": envelope.get("score_maturity"),
            "usage": envelope.get("usage"),
            "cost_usd": envelope.get("cost_usd"),
            "latency_ms": latency_ms,
            "primitives": primitives,
        }
    else:
        jev_payload = {
            "ok": False,
            "error": envelope.get("error"),
            "provider": envelope.get("provider"),
            "latency_ms": latency_ms,
            "raw": envelope.get("raw"),
            "primitives": primitives,
        }

    try:
        save_evaluation(
            data.get("symbol") or "UNKNOWN",
            data.get("timeframe") or "UNKNOWN",
            original,
            jev_payload,
            float(latency_ms),
            provider=envelope.get("provider"),
            response_model=envelope.get("response_model"),
        )
    except Exception:
        logging.getLogger(__name__).exception("JEV Shadow history unavailable")

    return {
        "mode": "shadow",
        "original_decision": original,
        "jev": jev_payload,
        "provider": envelope.get("provider"),
        "response_model": envelope.get("response_model"),
        "primitives_used": primitives,
        "execution_allowed": False,
    }
