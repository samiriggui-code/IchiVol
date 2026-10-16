"""Étude Mode × (NOUL|CHOICE|SCORE) — décider le routage par tests, pas par intuition.

Méthode :
1. Scénarios de marché synthétiques avec action sûre attendue.
2. Pour chaque mode × primitive, mesurer :
   - role_fit (adéquation mission ↔ type de jugement)
   - information_gain (sortie ≠ chemin Python-only)
   - decision_relevance (influence la synthèse vers l'action sûre)
   - redundancy (duplique un signal déjà calculé en Python)
3. Recommandation YES / NO / CONDITIONAL selon seuils documentés.

Ce n'est pas un fine-tune LLM. C'est une calibration de politique de routage.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from app.eve.actions import normalize_action
from app.eve.modes import (
    run_analyst,
    run_challenger,
    run_guardian,
    run_shadow_mode,
    synthesize_action,
)
from app.jev.questions import choice_question, noul_question, score_question

Primitive = Literal["noul", "choice", "score"]
ModeName = Literal["analyst", "challenger", "guardian", "shadow"]
Verdict = Literal["YES", "NO", "CONDITIONAL"]

PRIMITIVES: tuple[Primitive, ...] = ("noul", "choice", "score")
MODES: tuple[ModeName, ...] = ("analyst", "challenger", "guardian", "shadow")

# Adéquation mission ↔ primitive (0–1). Documenté, pas inventé à la volée.
ROLE_FIT: dict[ModeName, dict[Primitive, float]] = {
    "analyst": {"noul": 0.35, "choice": 0.55, "score": 0.90},
    "challenger": {"noul": 0.70, "choice": 0.95, "score": 0.60},
    "guardian": {"noul": 0.90, "choice": 0.40, "score": 0.80},
    "shadow": {"noul": 0.85, "choice": 0.80, "score": 0.75},
}

STUDY_THRESHOLDS = {
    "version": "eve.primitive_study.v1",
    "min_role_fit_yes": 0.70,
    "min_role_fit_conditional": 0.50,
    "min_relevance_or_gain": 0.5,  # binary 0/1 averaged over scenarios
    "max_redundancy_for_yes": 0.75,
}


def fixture_scenarios() -> list[dict[str, Any]]:
    """Scénarios couvrant régimes où un sous/sur-dimensionnement des appels JEV serait trompeur."""
    return [
        {
            "id": "aligned_long_hq",
            "expected_safe_action": "LONG",
            "context": _ctx(
                decision="BUY",
                data_quality=0.9,
                facts=[
                    _fact("structure", "bias", "bull"),
                    _fact("cvd", "bias", "bull"),
                    _fact("rvol", "rvol", 1.8),
                ],
            ),
        },
        {
            "id": "bias_divergence",
            "expected_safe_action": "ABSTAIN",
            "context": _ctx(
                decision="BUY",
                data_quality=0.75,
                facts=[
                    _fact("structure", "bias", "bull"),
                    _fact("cvd", "bias", "bear"),
                    _fact("mtf", "direction", "bear"),
                ],
            ),
        },
        {
            "id": "kill_switch",
            "expected_safe_action": "ABSTAIN",
            "context": _ctx(
                decision="BUY",
                data_quality=0.85,
                facts=[
                    _fact("risk", "kill_switch", "armed"),
                    _fact("structure", "bias", "bull"),
                ],
            ),
        },
        {
            "id": "sparse_data",
            "expected_safe_action": "ABSTAIN",
            "context": _ctx(
                decision="WATCH",
                data_quality=0.25,
                unavailable=["atr.regime", "location.vp", "oi.funding"],
                facts=[_fact("pipeline", "decision", "WATCH", status="ok")],
            ),
        },
        {
            "id": "baseline_watch_mixed",
            "expected_safe_action": "HOLD",
            "context": _ctx(
                decision="WATCH",
                data_quality=0.65,
                facts=[
                    _fact("structure", "bias", "neutral"),
                    _fact("rvol", "rvol", 0.9),
                ],
            ),
        },
        {
            "id": "short_aligned",
            "expected_safe_action": "SHORT",
            "context": _ctx(
                decision="SELL",
                data_quality=0.88,
                facts=[
                    _fact("structure", "bias", "bear"),
                    _fact("cvd", "bias", "bear"),
                ],
            ),
        },
    ]


def _fact(
    engine: str,
    field: str,
    value: Any,
    *,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "id": f"{engine}.{field}",
        "engine": engine,
        "field": field,
        "value": value,
        "status": status,
        "display": str(value) if value is not None else None,
    }


def _ctx(
    *,
    decision: str,
    data_quality: float,
    facts: list[dict[str, Any]],
    unavailable: list[str] | None = None,
) -> dict[str, Any]:
    engines: dict[str, list] = {}
    for f in facts:
        engines.setdefault(str(f["engine"]), []).append(f)
    return {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "data_quality": data_quality,
        "unavailable": unavailable or [],
        "engines": engines,
        "facts": facts,
        "baseline": {
            "decision": decision,
            "action_mapped": normalize_action(decision),
            "pipeline": {"decision": decision},
        },
        "error": None,
        "as_of": 1,
        "known_at": 1,
    }


def mock_jev_from_questions(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
    """JEV déterministe pour l'étude : répond selon le state, sans réseau.

    Objectif : mesurer l'utilité du *type* de question, pas la qualité d'un modèle live.
    """
    st = state if isinstance(state, dict) else {}
    baseline = st.get("baseline") if isinstance(st.get("baseline"), dict) else {}
    mapped = normalize_action(str(baseline.get("decision") or baseline.get("action_mapped") or ""))
    dq = float(st.get("data_quality") or 0.5)
    warnings = st.get("warnings") if isinstance(st.get("warnings"), list) else []
    contradictions = st.get("contradictions") if isinstance(st.get("contradictions"), list) else []
    critical = any(isinstance(w, dict) and w.get("severity") == "critical" for w in warnings)
    diverged = any(
        isinstance(c, dict) and c.get("code") == "multi_engine_bias_divergence" for c in contradictions
    )

    answers: dict[str, Any] = {}
    for name, q in questions.items():
        qtype = q.get("type")
        if qtype == "noul":
            # Prudence / cohérence : baisse si critique, divergence, low DQ
            p = 0.75
            if critical:
                p = 0.05
            elif diverged:
                p = 0.25
            elif dq < 0.4:
                p = 0.2
            elif mapped in ("LONG", "SHORT") and dq >= 0.8:
                p = 0.82
            answers[name] = {"type": "noul", "noul": p, "confidence": abs(p - 0.5) * 2}
        elif qtype == "choice":
            criteria = q.get("criteria") or {}
            options = list(criteria.keys()) if isinstance(criteria, dict) else []
            pick = "ABSTAIN"
            if critical or dq < 0.4 or diverged:
                pick = "ABSTAIN" if "ABSTAIN" in options else (options[0] if options else "ABSTAIN")
            elif mapped and mapped in options:
                pick = mapped
            elif "HOLD" in options:
                pick = "HOLD"
            elif options:
                pick = options[0]
            probs = {o: (0.7 if o == pick else 0.3 / max(len(options) - 1, 1)) for o in options}
            answers[name] = {
                "type": "choice",
                "choice": pick,
                "probabilities": probs,
                "confidence": 0.7,
            }
        elif qtype == "score":
            criteria = q.get("criteria") or []
            n = len(criteria) if isinstance(criteria, list) else 5
            # 0 .. n-1
            if critical or dq < 0.35:
                level = 0
            elif diverged:
                level = min(1, n - 1)
            elif mapped in ("LONG", "SHORT") and dq >= 0.8:
                level = min(n - 1, n - 2 if n > 2 else n - 1)
            else:
                level = min(2, n - 1) if n > 2 else 1
            answers[name] = {"type": "score", "score": float(level), "confidence": 0.65}
        else:
            return {"ok": False, "error": f"unsupported:{qtype}", "answers": None}

    return {
        "ok": True,
        "provider": "mock_study",
        "request_model": "study-mock",
        "response_model": "study-mock",
        "score_maturity": "study",
        "latency_ms": 0.0,
        "answers": answers,
        "usage": {"input_tokens": 10, "output_tokens": 0},
        "cost_usd": 0.0,
        "error": None,
        "raw": {"model": "study-mock", "answers": answers},
    }


def _questions_for(mode: ModeName, primitive: Primitive) -> dict[str, Any]:
    if mode == "analyst" and primitive == "score":
        return {
            "setup_strength": score_question(
                "Rate setup strength.",
                [
                    "No actionable setup",
                    "Weak / fragile setup",
                    "Mixed evidence",
                    "Constructive setup",
                    "Strong multi-engine setup",
                ],
            )
        }
    if mode == "analyst" and primitive == "choice":
        return {
            "primary_scenario": choice_question(
                "Which scenario best matches the engines?",
                {
                    "LONG": "bullish continuation",
                    "SHORT": "bearish continuation",
                    "HOLD": "wait inside range",
                    "ABSTAIN": "insufficient clarity",
                },
            )
        }
    if mode == "analyst" and primitive == "noul":
        return {
            "setup_valid": noul_question("Is there a valid actionable setup in the facts?")
        }
    if mode == "challenger" and primitive == "choice":
        return {
            "alt_action": choice_question(
                "Most defensible action given contradictions?",
                {
                    "LONG": "take long",
                    "SHORT": "take short",
                    "HOLD": "hold",
                    "ABSTAIN": "abstain",
                },
            )
        }
    if mode == "challenger" and primitive == "noul":
        return {
            "baseline_fragile": noul_question(
                "Is the baseline decision fragile given contradictions or missing data?"
            )
        }
    if mode == "challenger" and primitive == "score":
        return {
            "fragility": score_question(
                "How fragile is the baseline hypothesis?",
                ["Robust", "Mostly robust", "Mixed", "Fragile", "Broken"],
            )
        }
    if mode == "guardian" and primitive == "noul":
        return {
            "risk_ok": noul_question(
                "Is it prudent to allow new risk-taking? Analytical only."
            )
        }
    if mode == "guardian" and primitive == "score":
        return {
            "risk_level": score_question(
                "Rate risk level of acting now.",
                ["Negligible", "Low", "Moderate", "Elevated", "Critical"],
            )
        }
    if mode == "guardian" and primitive == "choice":
        return {
            "risk_stance": choice_question(
                "Risk stance?",
                {
                    "ALLOW": "risk-taking allowed analytically",
                    "REDUCE": "reduce size / hold",
                    "BLOCK": "abstain / no new risk",
                },
            )
        }
    if mode == "shadow" and primitive == "noul":
        return {
            "review": noul_question(
                "Does evidence support the existing decision? Consistency only."
            )
        }
    if mode == "shadow" and primitive == "choice":
        return {
            "independent_action": choice_question(
                "Independent counter-eval: which action?",
                {
                    "LONG": "long",
                    "SHORT": "short",
                    "HOLD": "hold",
                    "CLOSE": "close",
                    "ABSTAIN": "abstain",
                },
            )
        }
    if mode == "shadow" and primitive == "score":
        return {
            "audit_confidence": score_question(
                "Confidence in the original decision under independent review.",
                ["Reject", "Weak", "Mixed", "Acceptable", "Strong"],
            )
        }
    raise ValueError(f"no_question_template:{mode}:{primitive}")


def _run_mode_python_only(mode: ModeName, context: dict[str, Any]) -> dict[str, Any]:
    if mode == "analyst":
        return run_analyst(context, use_jev=False)
    if mode == "challenger":
        return run_challenger(context, use_jev=False)
    if mode == "guardian":
        return run_guardian(context, use_jev=False)
    if mode == "shadow":
        return run_shadow_mode(context, use_jev=False)
    raise ValueError(mode)


def _inject_jev(mode_out: dict[str, Any], jev: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(mode_out)
    out["jev"] = jev
    if out.get("mode") == "shadow":
        out["result"] = {
            "mode": "shadow",
            "original_decision": None,
            "jev": {
                "ok": jev.get("ok"),
                "result": {"answers": (jev.get("answers") or {})},
                "provider": "mock_study",
            },
            "execution_allowed": False,
        }
    return out


def _synthesis_action(
    context: dict[str, Any],
    *,
    analyst: dict[str, Any],
    challenger: dict[str, Any],
    guardian: dict[str, Any],
    shadow: dict[str, Any],
) -> str:
    synth = synthesize_action(
        analyst=analyst,
        challenger=challenger,
        guardian=guardian,
        shadow=shadow,
        baseline_action=normalize_action((context.get("baseline") or {}).get("decision")),
    )
    return str(synth.get("action") or "ABSTAIN")


def evaluate_cell(
    mode: ModeName,
    primitive: Primitive,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Évalue une cellule Mode×Primitive sur un scénario."""
    context = scenario["context"]
    expected = scenario["expected_safe_action"]
    questions = _questions_for(mode, primitive)

    python_out = _run_mode_python_only(mode, context)

    # Build sibling modes python-only for synthesis baseline
    a0 = run_analyst(context, use_jev=False)
    c0 = run_challenger(context, use_jev=False)
    g0 = run_guardian(context, use_jev=False)
    s0 = run_shadow_mode(context, use_jev=False)
    base_action = _synthesis_action(context, analyst=a0, challenger=c0, guardian=g0, shadow=s0)

    state_for_jev: dict[str, Any] = {
        "symbol": context.get("symbol"),
        "timeframe": context.get("timeframe"),
        "baseline": context.get("baseline"),
        "data_quality": context.get("data_quality"),
        "warnings": g0.get("warnings") or [],
        "contradictions": c0.get("contradictions") or [],
    }
    if mode == "challenger":
        state_for_jev["contradictions"] = python_out.get("contradictions") or []
    if mode == "guardian":
        state_for_jev["warnings"] = python_out.get("warnings") or []

    jev = mock_jev_from_questions(state_for_jev, questions)
    enriched = _inject_jev(python_out, jev)

    # Swap the enriched mode into synthesis
    a1, c1, g1, s1 = a0, c0, g0, s0
    if mode == "analyst":
        a1 = enriched
    elif mode == "challenger":
        c1 = enriched
    elif mode == "guardian":
        g1 = enriched
    else:
        s1 = enriched

    # Challenger CHOICE affects synthesis via jev answers — ensure challenger shape
    if mode == "challenger" and primitive == "choice" and jev.get("ok"):
        c1 = deepcopy(c0)
        c1["jev"] = jev

    new_action = _synthesis_action(context, analyst=a1, challenger=c1, guardian=g1, shadow=s1)

    info_gain = 1.0 if jev.get("ok") and jev.get("answers") else 0.0
    # Redundancy: if Python already forced ABSTAIN via critical guardian and primitive agrees
    critical = any(
        isinstance(w, dict) and w.get("severity") == "critical" for w in (g0.get("warnings") or [])
    )
    redundancy = 0.0
    if critical and primitive in ("noul", "score", "choice"):
        # JEV often echoes kill-switch already known in Python
        redundancy = 0.85 if mode in ("guardian", "shadow", "challenger") else 0.4

    # Decision relevance: moves toward expected safe action, or keeps it if already correct
    if new_action == expected and base_action != expected:
        relevance = 1.0
    elif new_action == expected and base_action == expected:
        relevance = 0.6  # confirms
    elif new_action != expected and base_action == expected:
        relevance = 0.0  # harms
    else:
        relevance = 0.3 if new_action == expected else 0.1

    # Shadow: CHOICE/SCORE now feed synthesize_action (abstain on disagreement / low score).
    # NOUL also soft-blocks directional when very low; otherwise audit signal still valuable.
    if mode == "shadow":
        info_gain = 1.0 if jev.get("ok") else 0.0
        if primitive == "noul":
            relevance = 0.75 if jev.get("ok") else 0.0
        elif jev.get("ok"):
            relevance = 0.9 if new_action != base_action or new_action == expected else 0.8

    return {
        "scenario_id": scenario["id"],
        "mode": mode,
        "primitive": primitive,
        "expected": expected,
        "base_action": base_action,
        "new_action": new_action,
        "role_fit": ROLE_FIT[mode][primitive],
        "information_gain": info_gain,
        "decision_relevance": relevance,
        "redundancy": redundancy,
        "jev_ok": bool(jev.get("ok")),
        "questions": list(questions.keys()),
    }


def recommend(cell_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrège les scénarios → verdict YES/NO/CONDITIONAL pour une cellule Mode×Primitive."""
    if not cell_rows:
        return {"verdict": "NO", "reason": "no_rows"}
    mode = cell_rows[0]["mode"]
    primitive = cell_rows[0]["primitive"]
    role_fit = ROLE_FIT[mode][primitive]  # type: ignore[index]
    avg_gain = sum(r["information_gain"] for r in cell_rows) / len(cell_rows)
    avg_rel = sum(r["decision_relevance"] for r in cell_rows) / len(cell_rows)
    avg_red = sum(r["redundancy"] for r in cell_rows) / len(cell_rows)
    t = STUDY_THRESHOLDS

    useful = max(avg_gain, avg_rel) >= t["min_relevance_or_gain"]
    not_too_redundant = avg_red <= t["max_redundancy_for_yes"]

    verdict: Verdict
    reason: str
    if role_fit >= t["min_role_fit_yes"] and useful and not_too_redundant:
        verdict = "YES"
        reason = "role_fit_high_and_useful"
    elif role_fit >= t["min_role_fit_yes"] and useful and not not_too_redundant:
        verdict = "CONDITIONAL"
        reason = "useful_but_often_redundant_with_python"
    elif role_fit >= t["min_role_fit_conditional"] and useful:
        verdict = "CONDITIONAL"
        reason = "moderate_fit_useful_in_some_regimes"
    elif role_fit >= t["min_role_fit_yes"] and not useful:
        verdict = "CONDITIONAL"
        reason = "good_fit_but_low_measured_impact_on_fixtures"
    else:
        verdict = "NO"
        reason = "low_fit_or_low_utility"

    return {
        "mode": mode,
        "primitive": primitive,
        "verdict": verdict,
        "reason": reason,
        "metrics": {
            "role_fit": role_fit,
            "avg_information_gain": round(avg_gain, 3),
            "avg_decision_relevance": round(avg_rel, 3),
            "avg_redundancy": round(avg_red, 3),
            "n_scenarios": len(cell_rows),
        },
    }


def run_primitive_routing_study() -> dict[str, Any]:
    """Exécute la matrice complète Mode × Primitive."""
    scenarios = fixture_scenarios()
    cells: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for mode in MODES:
        for primitive in PRIMITIVES:
            rows = [evaluate_cell(mode, primitive, sc) for sc in scenarios]
            details.extend(rows)
            cells.append(recommend(rows))

    # Politique proposée : YES → always; CONDITIONAL → keep if already primary or shadow protocol
    routing_primitives: dict[str, list[str]] = {m: [] for m in MODES}
    for cell in cells:
        if cell["verdict"] == "YES":
            routing_primitives[cell["mode"]].append(cell["primitive"])
        elif cell["verdict"] == "CONDITIONAL":
            # Shadow: include all conditionals for independent protocol breadth
            # Others: include only if role_fit >= 0.7
            if cell["mode"] == "shadow" or cell["metrics"]["role_fit"] >= 0.7:
                routing_primitives[cell["mode"]].append(cell["primitive"])

    # Ensure deterministic order
    for m in MODES:
        routing_primitives[m] = [p for p in PRIMITIVES if p in routing_primitives[m]]

    return {
        "schema": "ichivol.eve.primitive_routing_study.v1",
        "thresholds": STUDY_THRESHOLDS,
        "role_fit_matrix": ROLE_FIT,
        "cells": cells,
        "details": details,
        "recommended_routing": routing_primitives,
        "notes": [
            "Mock JEV is deterministic — validates routing utility of primitive *types*.",
            "Live jevos/TypeSafe accuracy is a separate V3 experiment (configs C/D).",
            "Not LLM fine-tuning.",
        ],
    }


def routing_from_study(study: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convertit l'étude en bloc policy.routing."""
    report = study or run_primitive_routing_study()
    rp = report["recommended_routing"]
    return {
        "use_jev_analyst": bool(rp.get("analyst")),
        "use_jev_challenger": bool(rp.get("challenger")),
        "use_jev_guardian": bool(rp.get("guardian")),
        "use_jev_shadow": bool(rp.get("shadow")),
        "analyst_primitives": rp.get("analyst") or [],
        "challenger_primitives": rp.get("challenger") or [],
        "guardian_primitives": rp.get("guardian") or [],
        "shadow_primitives": rp.get("shadow") or [],
        "skip_jev_if_data_quality_below": 0.15,
        "primitive_study_version": STUDY_THRESHOLDS["version"],
    }
