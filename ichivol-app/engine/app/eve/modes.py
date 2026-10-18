"""Ève modes — Analyst / Challenger / Guardian / Shadow.

One intelligence, specialized operating modes. Not four concurrent AIs.
JEV primitives (NOUL/CHOICE/SCORE) are selected per mode via calibration policy
from ``primitive_study`` — not assumed equal for every mode.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from app.eve.actions import EveAction, normalize_action, VALID_ACTIONS
from app.eve.context import jev_state_for
from app.jev.adapter import evaluate as jev_evaluate
from app.jev.history import save_evaluation
from app.jev.questions import choice_question, noul_question, score_question

DEFAULT_PRIMITIVES: dict[str, tuple[str, ...]] = {
    # All modes run full NOUL/CHOICE/SCORE (paper trade test activation).
    "analyst": ("noul", "choice", "score"),
    "challenger": ("noul", "choice", "score"),
    "guardian": ("noul", "choice", "score"),
    "shadow": ("noul", "choice", "score"),
}


def _norm_primitives(primitives: Sequence[str] | None, mode: str) -> list[str]:
    allowed = ("noul", "choice", "score")
    if primitives is None:
        return list(DEFAULT_PRIMITIVES.get(mode, ()))
    out = [p for p in primitives if p in allowed]
    return out


def _values_by_engine(context: dict[str, Any], engine: str) -> list[dict[str, Any]]:
    return list((context.get("engines") or {}).get(engine) or [])


def _analyst_questions(primitives: Iterable[str]) -> dict[str, Any]:
    q: dict[str, Any] = {}
    for p in primitives:
        if p == "score":
            q["setup_strength"] = score_question(
                "Rate the strength of the trading setup given the engine facts.",
                [
                    "No actionable setup",
                    "Weak / fragile setup",
                    "Mixed evidence",
                    "Constructive setup",
                    "Strong multi-engine setup",
                ],
            )
        elif p == "choice":
            q["primary_scenario"] = choice_question(
                "Which scenario best matches the engines?",
                {
                    "LONG": "bullish continuation",
                    "SHORT": "bearish continuation",
                    "HOLD": "wait inside range",
                    "ABSTAIN": "insufficient clarity",
                },
            )
        elif p == "noul":
            q["setup_valid"] = noul_question(
                "Is there a valid actionable setup in the supplied engine facts?"
            )
    return q


def _challenger_questions(
    primitives: Iterable[str],
    alternatives: list[str],
) -> dict[str, Any]:
    q: dict[str, Any] = {}
    for p in primitives:
        if p == "choice":
            criteria = {a: f"Prefer {a} given contradictions" for a in alternatives}
            q["alt_action"] = choice_question(
                "Given contradictions and missing data, which action is most defensible?",
                criteria,
            )
        elif p == "noul":
            q["baseline_fragile"] = noul_question(
                "Is the baseline decision fragile given contradictions or missing data?"
            )
        elif p == "score":
            q["fragility"] = score_question(
                "How fragile is the baseline hypothesis?",
                ["Robust", "Mostly robust", "Mixed", "Fragile", "Broken"],
            )
    return q


def _guardian_questions(primitives: Iterable[str]) -> dict[str, Any]:
    q: dict[str, Any] = {}
    for p in primitives:
        if p == "noul":
            q["risk_ok"] = noul_question(
                "Is it prudent to allow a new risk-taking trade given these warnings? "
                "Answer for analytical purposes only; Risk Kernel remains authoritative."
            )
        elif p == "score":
            q["risk_level"] = score_question(
                "Rate the risk level of opening or adding risk now.",
                ["Negligible", "Low", "Moderate", "Elevated", "Critical"],
            )
        elif p == "choice":
            q["risk_stance"] = choice_question(
                "Advisory risk stance (not an execution order).",
                {
                    "ALLOW": "risk-taking analytically acceptable",
                    "REDUCE": "prefer hold / reduce",
                    "BLOCK": "abstain / no new risk",
                },
            )
    return q


def _shadow_questions(primitives: Iterable[str]) -> dict[str, Any]:
    q: dict[str, Any] = {}
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


def run_analyst(
    context: dict[str, Any],
    *,
    use_jev: bool = True,
    primitives: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Interpret calculations and plausible scenarios."""
    baseline = context.get("baseline") or {}
    mapped = baseline.get("action_mapped")
    scenarios: list[dict[str, Any]] = []
    if mapped:
        scenarios.append(
            {
                "id": "baseline_aligned",
                "action": mapped,
                "rationale": f"Baseline pipeline decision maps to {mapped}",
                "source": "baseline",
            }
        )
    scenarios.append(
        {
            "id": "abstain_default",
            "action": "ABSTAIN",
            "rationale": "Default safe scenario when evidence is incomplete",
            "source": "policy",
        }
    )

    engines_used = sorted((context.get("engines") or {}).keys())
    hypotheses = {
        "primary_action": mapped or "ABSTAIN",
        "engines_consulted": engines_used,
        "data_quality": context.get("data_quality"),
        "unavailable_count": len(context.get("unavailable") or []),
    }

    prims = _norm_primitives(primitives, "analyst")
    jev = None
    if use_jev and prims:
        questions = _analyst_questions(prims)
        if questions:
            jev = jev_evaluate(
                jev_state_for(context, engines=engines_used, mode="analyst"),
                questions,
            )
            # If CHOICE returned a scenario, prefer it as primary hypothesis.
            if jev.get("ok"):
                choice = ((jev.get("answers") or {}).get("primary_scenario") or {}).get("choice")
                action = normalize_action(choice)
                if action:
                    hypotheses["primary_action"] = action
                    hypotheses["primary_source"] = "jev_choice"

    return {
        "mode": "analyst",
        "mission": "Interpret calculations, observations and market situations",
        "scenarios": scenarios,
        "hypotheses": hypotheses,
        "primitives_used": prims if use_jev else [],
        "jev": jev,
        "execution_allowed": False,
    }


def run_challenger(
    context: dict[str, Any],
    *,
    use_jev: bool = True,
    primitives: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Seek contradictions and fragile hypotheses."""
    contradictions: list[dict[str, Any]] = []

    if context.get("data_quality", 1) < 0.5:
        contradictions.append(
            {
                "code": "low_data_quality",
                "detail": f"data_quality={context.get('data_quality')}",
                "severity": "high",
            }
        )
    unavailable = context.get("unavailable") or []
    if unavailable:
        contradictions.append(
            {
                "code": "missing_facts",
                "detail": f"{len(unavailable)} facts unavailable",
                "severity": "medium",
            }
        )

    biases: list[str] = []
    for f in context.get("facts") or []:
        field = str(f.get("field") or "").lower()
        if f.get("status") != "ok":
            continue
        if "bias" in field or field.endswith("direction"):
            biases.append(f"{f.get('engine')}:{f.get('value')}")
    if len(set(biases)) >= 2:
        contradictions.append(
            {
                "code": "multi_engine_bias_divergence",
                "detail": ", ".join(biases[:6]),
                "severity": "high",
            }
        )

    alternatives = ["ABSTAIN", "HOLD"]
    primary = (context.get("baseline") or {}).get("action_mapped")
    if primary == "LONG":
        alternatives.extend(["SHORT", "LONG"])
    elif primary == "SHORT":
        alternatives.extend(["LONG", "SHORT"])
    else:
        alternatives.extend(["LONG", "SHORT"])
    alternatives = list(dict.fromkeys(alternatives))

    prims = _norm_primitives(primitives, "challenger")
    jev = None
    if use_jev and prims:
        questions = _challenger_questions(prims, alternatives)
        if questions:
            jev = jev_evaluate(
                jev_state_for(
                    context,
                    mode="challenger",
                    contradictions_n=len(contradictions),
                    alternatives=alternatives[:4],
                ),
                questions,
            )

    return {
        "mode": "challenger",
        "mission": "Find contradictions and confront hypotheses",
        "contradictions": contradictions,
        "alternative_actions": alternatives,
        "primitives_used": prims if use_jev else [],
        "jev": jev,
        "execution_allowed": False,
    }


def run_guardian(
    context: dict[str, Any],
    *,
    use_jev: bool = True,
    primitives: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Analytical risk mode — does NOT replace Risk Kernel authority."""
    warnings: list[dict[str, Any]] = []
    paper_facts = _values_by_engine(context, "paper") + _values_by_engine(context, "risk")
    for f in paper_facts:
        if f.get("status") != "ok":
            warnings.append(
                {
                    "code": "paper_or_risk_unavailable",
                    "field": f.get("field"),
                    "severity": "medium",
                }
            )

    if context.get("error"):
        warnings.append(
            {
                "code": "context_error",
                "detail": context.get("error"),
                "severity": "high",
            }
        )
    if (context.get("data_quality") or 0) < 0.4:
        warnings.append(
            {
                "code": "stale_or_sparse_data",
                "detail": "data_quality below 0.4",
                "severity": "high",
            }
        )

    for f in context.get("facts") or []:
        fid = str(f.get("id") or "").lower()
        field = str(f.get("field") or "").lower()
        if "kill" in fid or "kill" in field:
            if f.get("value") in (True, "armed", "ARMED", 1):
                warnings.append(
                    {
                        "code": "kill_switch_armed",
                        "detail": str(f.get("display") or f.get("value")),
                        "severity": "critical",
                    }
                )

    prims = _norm_primitives(primitives, "guardian")
    jev = None
    if use_jev and prims:
        questions = _guardian_questions(prims)
        if questions:
            jev = jev_evaluate(
                jev_state_for(
                    context,
                    mode="guardian",
                    warnings_n=len(warnings),
                    warn_codes=[w.get("code") for w in warnings[:6]],
                ),
                questions,
            )

    return {
        "mode": "guardian",
        "mission": "Evaluate risks, anomalies and constraints (advisory)",
        "warnings": warnings,
        "risk_kernel_authority": True,
        "note": "Guardian is advisory. Risk Kernel and kill switch remain imperative.",
        "primitives_used": prims if use_jev else [],
        "jev": jev,
        "execution_allowed": False,
    }


def run_shadow_mode(
    context: dict[str, Any],
    *,
    use_jev: bool = True,
    primitives: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Ève Shadow mode — independent counter-evaluation (not ShadowBroker)."""
    prims = _norm_primitives(primitives, "shadow")
    if not use_jev or not prims:
        return {
            "mode": "shadow",
            "mission": "Independent counter-evaluation",
            "skipped": True,
            "reason": "jev_disabled",
            "primitives_used": [],
            "execution_allowed": False,
            "not": "shadow_broker",
        }

    baseline = context.get("baseline") or {}
    original = baseline.get("decision")
    state = jev_state_for(
        context,
        mode="shadow",
        decision=original,
        pipeline_decision=(baseline.get("pipeline") or {}).get("decision")
        if isinstance(baseline.get("pipeline"), dict)
        else original,
    )
    questions = _shadow_questions(prims)
    envelope = jev_evaluate(state, questions)

    # Persist panel-compatible payload when NOUL review is present.
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
            "latency_ms": envelope.get("latency_ms"),
            "primitives": prims,
        }
    else:
        jev_payload = {
            "ok": False,
            "error": envelope.get("error"),
            "provider": envelope.get("provider"),
            "latency_ms": envelope.get("latency_ms"),
            "primitives": prims,
        }

    try:
        save_evaluation(
            str(context.get("symbol") or "UNKNOWN"),
            str(context.get("timeframe") or "UNKNOWN"),
            original,
            jev_payload,
            float(envelope.get("latency_ms") or 0.0),
            provider=envelope.get("provider"),
            response_model=envelope.get("response_model"),
        )
    except Exception:
        pass

    return {
        "mode": "shadow",
        "mission": "Independently re-examine analyses and decisions",
        "primitives_used": prims,
        "result": {
            "mode": "shadow",
            "original_decision": original,
            "jev": jev_payload,
            "provider": envelope.get("provider"),
            "response_model": envelope.get("response_model"),
            "execution_allowed": False,
        },
        "jev": envelope,
        "execution_allowed": False,
        "not": "shadow_broker",
    }


def _shadow_answers(shadow: dict[str, Any]) -> dict[str, Any]:
    """Extract JEV answers from either run_shadow_mode or legacy compare_decision shapes."""
    try:
        answers = ((shadow.get("result") or {}).get("jev") or {}).get("result", {}).get(
            "answers", {}
        )
        if not answers:
            answers = (shadow.get("jev") or {}).get("answers") or {}
        return answers if isinstance(answers, dict) else {}
    except Exception:
        return {}


def synthesize_action(
    *,
    analyst: dict[str, Any],
    challenger: dict[str, Any],
    guardian: dict[str, Any],
    shadow: dict[str, Any],
    baseline_action: EveAction | None,
    apply_audit: bool = True,
) -> dict[str, Any]:
    """Eve strategic synthesis — potential action only.

    ``apply_audit=False`` keeps Ève's own opinion: the independent audit (Shadow mode) is then read apart by
    ``audit_verdict`` and only arbitrates when the engine and Ève agree (app/eve/autopilot.py)."""
    rejected: list[str] = []
    warnings = guardian.get("warnings") or []
    critical = [w for w in warnings if w.get("severity") == "critical"]

    # Guardian JEV may reinforce BLOCK/Critical without replacing Risk Kernel.
    g_jev = guardian.get("jev") or {}
    if g_jev.get("ok"):
        stance = ((g_jev.get("answers") or {}).get("risk_stance") or {}).get("choice")
        risk_level = ((g_jev.get("answers") or {}).get("risk_level") or {}).get("score")
        risk_ok = ((g_jev.get("answers") or {}).get("risk_ok") or {}).get("noul")
        if stance == "BLOCK" or (isinstance(risk_level, (int, float)) and risk_level >= 4):
            critical = critical or [{"code": "guardian_jev_block", "severity": "critical"}]
        if isinstance(risk_ok, (int, float)) and risk_ok < 0.25:
            critical = critical or [{"code": "guardian_jev_noul_low", "severity": "critical"}]

    if critical:
        action: EveAction = "ABSTAIN"
        rationale = "Guardian critical warning → abstain"
        rejected.append("any_risk_taking")
    else:
        action = None
        ch_jev = challenger.get("jev") or {}
        if ch_jev.get("ok"):
            answers = ch_jev.get("answers") or {}
            alt = answers.get("alt_action") or {}
            action = normalize_action(alt.get("choice"))
            fragile = (answers.get("baseline_fragile") or {}).get("noul")
            if isinstance(fragile, (int, float)) and fragile >= 0.7 and action in (
                "LONG",
                "SHORT",
            ):
                # High fragility → prefer abstain over directional challenger pick
                action = "ABSTAIN"
                rejected.append("directional_despite_fragility")
        if action is None:
            hyp = (analyst.get("hypotheses") or {}).get("primary_action")
            action = normalize_action(str(hyp) if hyp else None) or "ABSTAIN"
        if action not in VALID_ACTIONS:
            action = "ABSTAIN"
        rationale = "Synthesized from Analyst/Challenger/Guardian (potential only)"
        if baseline_action and action != baseline_action:
            rejected.append(f"baseline:{baseline_action}")

    # Shadow counter-signals (NOUL + CHOICE + SCORE) — independent audit, never execution.
    s_answers = _shadow_answers(shadow)
    shadow_noul = (s_answers.get("review") or {}).get("noul")
    shadow_choice = normalize_action(
        (s_answers.get("independent_action") or {}).get("choice")
    )
    shadow_score = (s_answers.get("audit_confidence") or {}).get("score")

    if apply_audit and not critical and action in ("LONG", "SHORT"):
        # SCORE levels: 0 Reject … 4 Strong — weak audit blocks directional potential.
        if isinstance(shadow_score, (int, float)) and shadow_score <= 1:
            rejected.append("shadow_low_audit_confidence")
            action = "ABSTAIN"
            rationale = "Shadow SCORE audit_confidence weak → abstain"
        elif shadow_choice is not None and shadow_choice != action:
            rejected.append(f"shadow_choice:{shadow_choice}")
            rationale = (
                f"Shadow CHOICE {shadow_choice} disagrees with {action} → abstain"
            )
            action = "ABSTAIN"
        elif isinstance(shadow_noul, (int, float)) and shadow_noul < 0.35:
            rejected.append("shadow_noul_low")
            action = "ABSTAIN"
            rationale = "Shadow NOUL low coherence → abstain"

    return {
        "action": action,
        "status": "potential",
        "executed": False,
        "authorization": "not_submitted",
        "rationale": rationale,
        "rejected_scenarios": rejected,
        "baseline_action": baseline_action,
        "disagrees_with_baseline": bool(baseline_action and action != baseline_action),
        "shadow_noul": shadow_noul if isinstance(shadow_noul, (int, float)) else None,
        "shadow_choice": shadow_choice,
        "shadow_score": shadow_score if isinstance(shadow_score, (int, float)) else None,
    }


def audit_verdict(shadow: dict[str, Any], proposed: str, *, position_direction: str | None = None) -> dict[str, Any]:
    """Independent audit (Shadow mode) arbitrating a trade the engine and Ève agree on: ``allow`` or ``block``.

    Same thresholds as the synthesis: SCORE ≤ 1 (Reject/Weak), a different CHOICE, or NOUL < 0.35 block an open.
    A close is blocked only when the audit explicitly says to keep the position. No audit answer → ``allow``
    (the agreement stands)."""
    answers = _shadow_answers(shadow)
    noul = (answers.get("review") or {}).get("noul")
    choice = normalize_action((answers.get("independent_action") or {}).get("choice"))
    score = (answers.get("audit_confidence") or {}).get("score")
    out: dict[str, Any] = {
        "verdict": "allow",
        "reason": "no_audit" if not answers else "agrees",
        "choice": choice,
        "score": score if isinstance(score, (int, float)) else None,
        "noul": noul if isinstance(noul, (int, float)) else None,
    }
    if proposed == "CLOSE":
        if choice is not None and (choice == "HOLD" or choice == position_direction):
            out.update(verdict="block", reason=f"choice:{choice}")
        return out
    if isinstance(score, (int, float)) and score <= 1:
        out.update(verdict="block", reason="low_score")
    elif choice is not None and choice != proposed:
        out.update(verdict="block", reason=f"choice:{choice}")
    elif isinstance(noul, (int, float)) and noul < 0.35:
        out.update(verdict="block", reason="low_noul")
    return out
