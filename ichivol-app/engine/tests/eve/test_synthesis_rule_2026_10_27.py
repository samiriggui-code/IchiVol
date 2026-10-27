"""Règle de synthèse d'Ève du 2026-10-27 (validée par le propriétaire).

Constat en production (174 dossiers du 17 au 27/10) : le Challenger JEV répondait ABSTAIN 172 fois et ce choix
passait avant l'Analyste (SHORT 130 fois, LONG 33 fois) : Ève s'abstenait dans 100 % des cas.
Nouvelle règle : guardian critique → fragilité >= 0,7 → contradiction explicite du Challenger → Analyste.
"""

from __future__ import annotations

import pytest

from app.eve.modes import synthesize_action


def _analyst(action: str | None) -> dict:
    hyp = {"primary_action": action} if action is not None else {}
    return {"mode": "analyst", "hypotheses": hyp, "jev": None}


def _challenger(choice: str | None, fragile: float | None = 0.3) -> dict:
    answers: dict = {}
    if choice is not None:
        answers["alt_action"] = {"type": "choice", "choice": choice}
    if fragile is not None:
        answers["baseline_fragile"] = {"type": "noul", "noul": fragile}
    return {"mode": "challenger", "contradictions": [], "jev": {"ok": True, "answers": answers}}


def _guardian(*, critical: bool = False, stance: str | None = None, risk_level=None, risk_ok=None) -> dict:
    g: dict = {"warnings": [{"code": "x", "severity": "critical"}] if critical else []}
    answers: dict = {}
    if stance is not None:
        answers["risk_stance"] = {"choice": stance}
    if risk_level is not None:
        answers["risk_level"] = {"score": risk_level}
    if risk_ok is not None:
        answers["risk_ok"] = {"noul": risk_ok}
    if answers:
        g["jev"] = {"ok": True, "answers": answers}
    return g


def _synth(analyst, challenger, guardian, baseline="SHORT"):
    # apply_audit=False : comme l'orchestrateur (l'audit indépendant arbitre plus tard, dans l'autopilote).
    return synthesize_action(
        analyst=analyst, challenger=challenger, guardian=guardian, shadow={}, baseline_action=baseline,
        apply_audit=False,
    )


@pytest.mark.parametrize(
    "guardian",
    [
        _guardian(critical=True),
        _guardian(stance="BLOCK"),
        _guardian(risk_level=4),
        _guardian(risk_ok=0.2),
    ],
)
def test_rule1_guardian_critical_abstains(guardian) -> None:
    out = _synth(_analyst("SHORT"), _challenger("LONG"), guardian)
    assert out["action"] == "ABSTAIN"
    assert out["decision_rule"] == "guardian_critical"
    assert out["rationale"].startswith("Règle 1")


def test_rule2_fragility_abstains_even_when_challenger_abstains() -> None:
    out = _synth(_analyst("SHORT"), _challenger("ABSTAIN", fragile=0.7), _guardian())
    assert out["action"] == "ABSTAIN"
    assert out["decision_rule"] == "challenger_fragile"
    assert "directional_despite_fragility" in out["rejected_scenarios"]


def test_rule4_challenger_abstain_is_not_a_refusal_analyst_short_wins() -> None:
    out = _synth(_analyst("SHORT"), _challenger("ABSTAIN"), _guardian())
    assert out["action"] == "SHORT"
    assert out["decision_rule"] == "analyst"
    assert out["rationale"].startswith("Règle 4")


def test_rule4_challenger_hold_or_silent_follows_analyst() -> None:
    assert _synth(_analyst("LONG"), _challenger("HOLD"), _guardian())["action"] == "LONG"
    silent = {"mode": "challenger", "jev": {"ok": False, "error": "timeout"}}
    assert _synth(_analyst("LONG"), silent, _guardian())["action"] == "LONG"


def test_rule3_explicit_contradiction_follows_challenger() -> None:
    out = _synth(_analyst("SHORT"), _challenger("LONG"), _guardian())
    assert out["action"] == "LONG"
    assert out["decision_rule"] == "challenger_contradiction"
    assert out["analyst_action"] == "SHORT" and out["challenger_action"] == "LONG"


def test_rule3_challenger_close_against_analyst_direction() -> None:
    out = _synth(_analyst("LONG"), _challenger("CLOSE"), _guardian())
    assert out["action"] == "CLOSE"
    assert out["decision_rule"] == "challenger_contradiction"


def test_same_direction_is_the_analyst_rule() -> None:
    out = _synth(_analyst("SHORT"), _challenger("SHORT"), _guardian())
    assert out["action"] == "SHORT" and out["decision_rule"] == "analyst"


def test_no_answer_abstains() -> None:
    out = _synth(_analyst(None), {"mode": "challenger", "jev": None}, _guardian(), baseline=None)
    assert out["action"] == "ABSTAIN"
    assert out["decision_rule"] == "no_answer"


def test_shadow_audit_still_applies_when_requested() -> None:
    shadow = {"jev": {"ok": True, "answers": {"independent_action": {"choice": "LONG"}}}}
    out = synthesize_action(
        analyst=_analyst("SHORT"), challenger=_challenger("ABSTAIN"), guardian=_guardian(), shadow=shadow,
        baseline_action="SHORT", apply_audit=True,
    )
    assert out["action"] == "ABSTAIN" and out["decision_rule"] == "shadow_audit"


# Réponses JEV typiques des dossiers réels (eve_dossiers 17-27/10) : Challenger ABSTAIN avec une fragilité
# moyenne, Analyste SHORT ou LONG via primary_scenario, Guardian CAUTION niveau 2-3.
REAL_LIKE = [
    ("SHORT", 0.45, "CAUTION", 2, 0.55),
    ("SHORT", 0.62, "CAUTION", 3, 0.40),
    ("LONG", 0.35, "ALLOW", 2, 0.70),
    ("SHORT", 0.50, "CAUTION", 3, 0.30),
    ("LONG", 0.55, "CAUTION", 2, 0.50),
]


@pytest.mark.parametrize("analyst_choice,fragile,stance,level,risk_ok", REAL_LIKE)
def test_non_regression_real_dossiers_now_propose_a_direction(analyst_choice, fragile, stance, level, risk_ok) -> None:
    analyst = {
        "mode": "analyst",
        "hypotheses": {"primary_action": analyst_choice, "primary_source": "jev_choice"},
        "jev": {"ok": True, "answers": {"primary_scenario": {"type": "choice", "choice": analyst_choice}}},
    }
    out = _synth(analyst, _challenger("ABSTAIN", fragile=fragile),
                 _guardian(stance=stance, risk_level=level, risk_ok=risk_ok))
    assert out["action"] == analyst_choice
    assert out["decision_rule"] == "analyst"
