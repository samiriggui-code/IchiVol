"""Fallback ladder — late → HOLD, low conf → ABSTAIN, jev_down labelled."""

from __future__ import annotations

from app.eve.degradation import (
    apply_degradation,
    assess_degradation,
    extract_probabilities,
)
from app.eve.heuristic import heuristic_badge


def test_late_forces_hold() -> None:
    pack = {
        "analyst": {"ok": False, "error": "timeout", "late": True},
        "challenger": {"ok": True, "answers": {"x": {"type": "noul", "noul": 0.9}}},
    }
    deg = assess_degradation(pack, jev_requested=True)
    assert deg["level"] == "late"
    assert deg["late"] is True
    synth = apply_degradation(
        {"action": "LONG", "rationale": "ok", "rejected_scenarios": []},
        deg,
    )
    assert synth["action"] == "HOLD"
    assert "degradation_late" in synth["rejected_scenarios"]


def test_low_confidence_abstains() -> None:
    pack = {
        "guardian": {
            "ok": True,
            "answers": {
                "risk_ok": {"type": "noul", "noul": 0.2, "confidence": 0.2},
            },
        }
    }
    deg = assess_degradation(pack, jev_requested=True, min_confidence=0.45)
    assert deg["level"] == "low_confidence"
    synth = apply_degradation(
        {"action": "SHORT", "rationale": "ok", "rejected_scenarios": []},
        deg,
    )
    assert synth["action"] == "ABSTAIN"


def test_jev_down_labelled_heuristic() -> None:
    pack = {
        "analyst": {"ok": False, "error": "jev_key_missing"},
        "challenger": {"ok": False, "error": "http_503"},
    }
    deg = assess_degradation(pack, jev_requested=True)
    assert deg["level"] == "jev_down"
    assert deg["source"] == "heuristic"
    badge = heuristic_badge(deg)
    assert badge["stand_in"] is True
    assert badge["label"] == "heuristic"


def test_extract_probabilities() -> None:
    pack = {
        "challenger": {
            "ok": True,
            "provider": "jevos",
            "answers": {
                "alt_action": {
                    "type": "choice",
                    "choice": "HOLD",
                    "probabilities": {"HOLD": 0.6, "LONG": 0.4},
                    "confidence": 0.7,
                }
            },
        }
    }
    probs = extract_probabilities(pack)
    assert "challenger" in probs
    assert probs["challenger"]["answers"]["alt_action"]["choice"] == "HOLD"


def test_jev_not_requested_healthy_deterministic() -> None:
    deg = assess_degradation({}, jev_requested=False)
    assert deg["level"] == "healthy"
    assert deg["source"] == "deterministic"
