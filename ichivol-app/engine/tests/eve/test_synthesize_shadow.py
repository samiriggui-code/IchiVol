"""Synthesis must consume Shadow CHOICE + SCORE (not NOUL-only)."""

from __future__ import annotations

from app.eve.modes import run_analyst, run_challenger, synthesize_action


def _ctx():
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "data_quality": 0.8,
        "unavailable": [],
        "engines": {"pipeline": [], "structure": []},
        "facts": [],
        "baseline": {"decision": "BUY", "action_mapped": "LONG", "pipeline": {"decision": "BUY"}},
        "error": None,
    }


def _shadow(*, noul=0.8, choice="LONG", score=3.0):
    return {
        "mode": "shadow",
        "jev": {
            "ok": True,
            "answers": {
                "review": {"type": "noul", "noul": noul},
                "independent_action": {"type": "choice", "choice": choice},
                "audit_confidence": {"type": "score", "score": score},
            },
        },
        "result": {
            "jev": {
                "ok": True,
                "result": {
                    "answers": {
                        "review": {"type": "noul", "noul": noul},
                        "independent_action": {"type": "choice", "choice": choice},
                        "audit_confidence": {"type": "score", "score": score},
                    }
                },
            }
        },
    }


def test_shadow_choice_disagreement_forces_abstain() -> None:
    synth = synthesize_action(
        analyst=run_analyst(_ctx(), use_jev=False),
        challenger=run_challenger(_ctx(), use_jev=False),
        guardian={"warnings": []},
        shadow=_shadow(choice="SHORT", score=3.0, noul=0.9),
        baseline_action="LONG",
    )
    assert synth["action"] == "ABSTAIN"
    assert "shadow_choice:SHORT" in synth["rejected_scenarios"]
    assert synth["shadow_choice"] == "SHORT"
    assert synth["executed"] is False


def test_shadow_low_score_forces_abstain() -> None:
    synth = synthesize_action(
        analyst=run_analyst(_ctx(), use_jev=False),
        challenger=run_challenger(_ctx(), use_jev=False),
        guardian={"warnings": []},
        shadow=_shadow(choice="LONG", score=1.0, noul=0.9),
        baseline_action="LONG",
    )
    assert synth["action"] == "ABSTAIN"
    assert "shadow_low_audit_confidence" in synth["rejected_scenarios"]
    assert synth["shadow_score"] == 1.0


def test_shadow_aligned_keeps_directional() -> None:
    synth = synthesize_action(
        analyst=run_analyst(_ctx(), use_jev=False),
        challenger=run_challenger(_ctx(), use_jev=False),
        guardian={"warnings": []},
        shadow=_shadow(choice="LONG", score=3.0, noul=0.8),
        baseline_action="LONG",
    )
    assert synth["action"] == "LONG"
    assert synth["shadow_noul"] == 0.8
    assert synth["shadow_choice"] == "LONG"
