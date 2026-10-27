"""Why Ève answered what she answered, in plain French, from what the Dossier already stores.

Works on past Dossiers too: it only reads ``modes_json`` (Analyst / Challenger / Guardian / Shadow answers and
the synthesis) and the verdict's rationale, never re-runs anything.
"""

from __future__ import annotations

from typing import Any

from app.eve.actions import normalize_action

ACTION_FR = {
    "LONG": "acheter",
    "SHORT": "vendre à découvert",
    "HOLD": "attendre",
    "CLOSE": "clôturer",
    "ABSTAIN": "s’abstenir",
}

_SETUP_FR = ["aucun setup", "setup fragile", "indices mitigés", "setup solide", "setup fort"]
_RISK_FR = ["risque négligeable", "risque faible", "risque modéré", "risque élevé", "risque critique"]
_AUDIT_FR = ["rejet", "faible", "mitigée", "acceptable", "forte"]
_STANCE_FR = {"ALLOW": "autorise", "REDUCE": "conseille de réduire", "BLOCK": "bloque"}


def _answers(mode: dict[str, Any] | None) -> dict[str, Any]:
    jev = (mode or {}).get("jev") or {}
    answers = jev.get("answers") if jev.get("ok") else None
    if not answers:
        # Shadow mode keeps its answers one level deeper (run_shadow_mode).
        inner = (((mode or {}).get("result") or {}).get("jev") or {}).get("result") or {}
        answers = inner.get("answers")
    return answers if isinstance(answers, dict) else {}


def _pct(v: Any) -> str | None:
    return f"{round(float(v) * 100)} %" if isinstance(v, (int, float)) else None


def _level(labels: list[str], v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return None
    i = max(0, min(len(labels) - 1, int(round(v))))
    return f"{labels[i]} ({i}/{len(labels) - 1})"


def _stance(action: str | None, engine: str | None) -> str:
    if action is None or engine is None:
        return "neutre"
    return "pour" if action == engine else "contre"


def opinions(modes: dict[str, Any] | None, engine_action: str | None) -> list[dict[str, Any]]:
    """Each judge's answer and whether it backs the engine's proposal (``pour`` / ``contre`` / ``neutre``)."""
    modes = modes if isinstance(modes, dict) else {}
    engine = normalize_action(engine_action)
    out: list[dict[str, Any]] = []

    analyst = modes.get("analyst") or {}
    a_ans = _answers(analyst)
    a_action = normalize_action(str((analyst.get("hypotheses") or {}).get("primary_action") or "")) or None
    a_detail = [
        d
        for d in (
            _level(_SETUP_FR, (a_ans.get("setup_strength") or {}).get("score")),
            f"setup valable à {_pct((a_ans.get('setup_valid') or {}).get('noul'))}"
            if _pct((a_ans.get("setup_valid") or {}).get("noul"))
            else None,
        )
        if d
    ]
    out.append({"who": "analyst", "action": a_action, "stance": _stance(a_action, engine), "details": a_detail})

    challenger = modes.get("challenger") or {}
    c_ans = _answers(challenger)
    c_action = normalize_action((c_ans.get("alt_action") or {}).get("choice"))
    fragile = _pct((c_ans.get("baseline_fragile") or {}).get("noul"))
    n_contra = len(challenger.get("contradictions") or [])
    c_detail = [
        d
        for d in (
            f"signal du moteur fragile à {fragile}" if fragile else None,
            f"{n_contra} contradiction{'s' if n_contra > 1 else ''} entre moteurs" if n_contra else None,
        )
        if d
    ]
    out.append({"who": "challenger", "action": c_action, "stance": _stance(c_action, engine), "details": c_detail})

    guardian = modes.get("guardian") or {}
    g_ans = _answers(guardian)
    stance_raw = (g_ans.get("risk_stance") or {}).get("choice")
    critical = [w for w in guardian.get("warnings") or [] if w.get("severity") == "critical"]
    risk_ok = (g_ans.get("risk_ok") or {}).get("noul")
    g_detail = [
        d
        for d in (
            _STANCE_FR.get(str(stance_raw)),
            _level(_RISK_FR, (g_ans.get("risk_level") or {}).get("score")),
            f"prise de risque prudente à {_pct(risk_ok)}" if _pct(risk_ok) else None,
            f"{len(critical)} alerte{'s' if len(critical) > 1 else ''} critique{'s' if len(critical) > 1 else ''}"
            if critical
            else None,
        )
        if d
    ]
    if critical or stance_raw == "BLOCK":
        g_stance = "contre"
    elif stance_raw == "ALLOW":
        g_stance = "pour"
    else:
        g_stance = "neutre"
    out.append({"who": "guardian", "action": None, "stance": g_stance, "details": g_detail})

    shadow = modes.get("shadow") or {}
    s_ans = _answers(shadow)
    s_action = normalize_action((s_ans.get("independent_action") or {}).get("choice"))
    review = _pct((s_ans.get("review") or {}).get("noul"))
    s_detail = [
        d
        for d in (
            f"confiance {_level(_AUDIT_FR, (s_ans.get('audit_confidence') or {}).get('score'))}"
            if _level(_AUDIT_FR, (s_ans.get("audit_confidence") or {}).get("score"))
            else None,
            f"les indices soutiennent la décision à {review}" if review else None,
        )
        if d
    ]
    out.append({"who": "audit", "action": s_action, "stance": _stance(s_action, engine), "details": s_detail})
    return out


def _decisive(rejected: list[str]) -> str | None:
    """The last override applied to Ève's answer (the synthesis appends them in order)."""
    for code in reversed(rejected):
        if code.startswith("baseline:") or code in ("degradation_jev_down", "any_risk_taking"):
            continue
        return code
    return None


def why_fr(
    *,
    eve_action: str | None,
    engine_action: str | None,
    rationale: str | None,
    modes: dict[str, Any] | None,
) -> str | None:
    """One sentence: what made Ève answer this. ``None`` when nothing is known."""
    action = normalize_action(eve_action)
    if action is None:
        return None
    modes = modes if isinstance(modes, dict) else {}
    synthesis = modes.get("synthesis") or {}
    rejected = [str(r) for r in synthesis.get("rejected_scenarios") or []]
    rationale = rationale or synthesis.get("rationale") or ""
    said = ACTION_FR.get(action, action.lower())
    engine = normalize_action(engine_action)

    if rationale.startswith("Policy: data_quality"):
        return f"Données trop incomplètes pour agir : Ève choisit de {said}."
    if rationale.startswith("Policy: too many"):
        return f"Trop de contradictions entre les moteurs : Ève choisit de {said}."
    rule = str(synthesis.get("decision_rule") or "")
    if rule == "guardian_critical" or rationale.startswith("Guardian critical"):
        return "Le gardien du risque a levé une alerte critique : Ève s’abstient."

    code = _decisive(rejected) or ""
    if code == "degradation_late":
        return "JEV a répondu trop tard : Ève attend plutôt que de trader sur des réponses périmées."
    if code == "degradation_low_confidence":
        return "JEV n’était pas assez sûr de ses réponses : Ève s’abstient."
    if code.startswith("entry_gate:"):
        return f"La porte d’entrée de JEV a refusé ce trade ({code.split(':', 1)[1]}) : Ève s’abstient."
    if code.startswith("signal_rules:"):
        return f"Les règles de signal ont refusé ce trade ({code.split(':', 1)[1]}) : Ève s’abstient."
    if code == "shadow_low_audit_confidence":
        return "L’audit indépendant a jugé la proposition faible : Ève s’abstient."
    if code.startswith("shadow_choice:"):
        other = ACTION_FR.get(code.split(":", 1)[1], code.split(":", 1)[1].lower())
        return f"L’audit indépendant voulait {other} : Ève s’abstient."
    if code == "shadow_noul_low":
        return "L’audit indépendant doute que les indices soutiennent la décision : Ève s’abstient."
    if code == "directional_despite_fragility":
        fragile = _pct((_answers(modes.get("challenger")).get("baseline_fragile") or {}).get("noul"))
        return (
            f"Le contradicteur jugeait le signal du moteur fragile ({fragile or 'au-dessus de 70 %'}) : "
            "Ève préfère s’abstenir."
        )

    if rule == "challenger_contradiction":
        return f"Le contradicteur contredisait l’analyste et proposait de {said} : Ève l’a suivi."
    if engine is not None and action == engine:
        return f"Ève est d’accord avec le moteur : {said}."
    c_choice = normalize_action((_answers(modes.get("challenger")).get("alt_action") or {}).get("choice"))
    if c_choice is not None and c_choice == action:
        return f"Le contradicteur jugeait plus prudent de {said}, Ève l’a suivi."
    return f"L’analyste penchait pour « {said} », Ève l’a suivi."
