"""Ève modes — Analyst / Challenger / Guardian / Shadow.

One intelligence, specialized operating modes. Not four concurrent AIs.
V1: Python engines + optional JEV typed judgments. No order execution.
"""

from __future__ import annotations

from typing import Any

from app.eve.actions import EveAction, normalize_action, VALID_ACTIONS
from app.jev.adapter import evaluate as jev_evaluate
from app.jev.questions import choice_question, noul_question, score_question
from app.jev.shadow import compare_decision


def _values_by_engine(context: dict[str, Any], engine: str) -> list[dict[str, Any]]:
    return list((context.get("engines") or {}).get(engine) or [])


def run_analyst(context: dict[str, Any], *, use_jev: bool = True) -> dict[str, Any]:
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

    jev = None
    if use_jev:
        state = {
            "symbol": context.get("symbol"),
            "timeframe": context.get("timeframe"),
            "baseline": baseline,
            "data_quality": context.get("data_quality"),
            "engines": engines_used,
        }
        jev = jev_evaluate(
            state,
            {
                "setup_strength": score_question(
                    "Rate the strength of the trading setup given the engine facts.",
                    [
                        "No actionable setup",
                        "Weak / fragile setup",
                        "Mixed evidence",
                        "Constructive setup",
                        "Strong multi-engine setup",
                    ],
                )
            },
        )

    return {
        "mode": "analyst",
        "mission": "Interpret calculations, observations and market situations",
        "scenarios": scenarios,
        "hypotheses": hypotheses,
        "jev": jev,
        "execution_allowed": False,
    }


def run_challenger(context: dict[str, Any], *, use_jev: bool = True) -> dict[str, Any]:
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

    # MTF / CVD style divergence if both present with conflicting bias-like fields.
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

    jev = None
    if use_jev:
        criteria = {a: f"Prefer {a} given contradictions" for a in dict.fromkeys(alternatives)}
        jev = jev_evaluate(
            {
                "symbol": context.get("symbol"),
                "contradictions": contradictions,
                "baseline": context.get("baseline"),
            },
            {
                "alt_action": choice_question(
                    "Given contradictions and missing data, which action is most defensible?",
                    criteria,
                )
            },
        )

    return {
        "mode": "challenger",
        "mission": "Find contradictions and confront hypotheses",
        "contradictions": contradictions,
        "alternative_actions": list(dict.fromkeys(alternatives)),
        "jev": jev,
        "execution_allowed": False,
    }


def run_guardian(context: dict[str, Any], *, use_jev: bool = True) -> dict[str, Any]:
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

    # Kill-switch / exposure hints from fact ids when present.
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

    jev = None
    if use_jev:
        jev = jev_evaluate(
            {
                "symbol": context.get("symbol"),
                "warnings": warnings,
                "data_quality": context.get("data_quality"),
            },
            {
                "risk_ok": noul_question(
                    "Is it prudent to allow a new risk-taking trade given these warnings? "
                    "Answer for analytical purposes only; Risk Kernel remains authoritative."
                )
            },
        )

    return {
        "mode": "guardian",
        "mission": "Evaluate risks, anomalies and constraints (advisory)",
        "warnings": warnings,
        "risk_kernel_authority": True,
        "note": "Guardian is advisory. Risk Kernel and kill switch remain imperative.",
        "jev": jev,
        "execution_allowed": False,
    }


def run_shadow_mode(context: dict[str, Any], *, use_jev: bool = True) -> dict[str, Any]:
    """Ève Shadow mode — independent counter-evaluation (not ShadowBroker)."""
    if not use_jev:
        return {
            "mode": "shadow",
            "mission": "Independent counter-evaluation",
            "skipped": True,
            "reason": "jev_disabled",
            "execution_allowed": False,
        }

    data = {
        "symbol": context.get("symbol"),
        "timeframe": context.get("timeframe"),
        "decision": (context.get("baseline") or {}).get("decision"),
        "pipeline": (context.get("baseline") or {}).get("pipeline") or {
            "decision": (context.get("baseline") or {}).get("decision")
        },
    }
    result = compare_decision(data)
    return {
        "mode": "shadow",
        "mission": "Independently re-examine analyses and decisions",
        "result": result,
        "execution_allowed": False,
        "not": "shadow_broker",
    }


def synthesize_action(
    *,
    analyst: dict[str, Any],
    challenger: dict[str, Any],
    guardian: dict[str, Any],
    shadow: dict[str, Any],
    baseline_action: EveAction | None,
) -> dict[str, Any]:
    """Eve strategic synthesis — potential action only."""
    rejected: list[str] = []
    warnings = guardian.get("warnings") or []
    critical = [w for w in warnings if w.get("severity") == "critical"]
    if critical:
        action: EveAction = "ABSTAIN"
        rationale = "Guardian critical warning (e.g. kill switch) → abstain"
        rejected.append("any_risk_taking")
    else:
        # Prefer Challenger JEV CHOICE when valid; else Analyst primary; else ABSTAIN.
        action = None
        ch_jev = challenger.get("jev") or {}
        if ch_jev.get("ok"):
            answers = ch_jev.get("answers") or {}
            alt = answers.get("alt_action") or {}
            action = normalize_action(alt.get("choice"))
        if action is None:
            hyp = (analyst.get("hypotheses") or {}).get("primary_action")
            action = normalize_action(str(hyp) if hyp else None) or "ABSTAIN"
        if action not in VALID_ACTIONS:
            action = "ABSTAIN"
        rationale = "Synthesized from Analyst/Challenger/Guardian (potential only)"
        if baseline_action and action != baseline_action:
            rejected.append(f"baseline:{baseline_action}")

    # Extract shadow noul if present.
    shadow_noul = None
    try:
        shadow_noul = (
            ((shadow.get("result") or {}).get("jev") or {})
            .get("result", {})
            .get("answers", {})
            .get("review", {})
            .get("noul")
        )
    except Exception:
        shadow_noul = None

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
    }
