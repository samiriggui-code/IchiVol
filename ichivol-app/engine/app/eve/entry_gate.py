"""Pre-trade entry gate — QuantDinger-inspired atomic CHOICE battery.

Jev judges five independent checks; **code** converges pass/reject.
Fail-closed for paper: if JEV is unavailable or malformed → reject directional
(HOLD/ABSTAIN), never fail-open live.

Does NOT replace Risk Kernel. Guardian remains advisory; this gate only blocks
Eve potential LONG/SHORT (and paper execute) when rules say reject.
"""

from __future__ import annotations

from typing import Any

from app.eve.context import jev_state_for
from app.jev.adapter import evaluate as jev_evaluate
from app.jev.questions import choice_question

GATE_QUESTION_IDS = (
    "data_quality",
    "signal_alignment",
    "market_regime",
    "risk_check",
    "execution_quality",
)

GATE_OPTIONS: dict[str, set[str]] = {
    "data_quality": {"sufficient", "partial", "insufficient"},
    "signal_alignment": {"aligned", "mixed", "conflict", "insufficient"},
    "market_regime": {"favorable", "neutral", "adverse", "insufficient"},
    "risk_check": {"clear", "caution", "block", "insufficient"},
    "execution_quality": {"clear", "caution", "block", "insufficient"},
}


def build_gate_questions() -> dict[str, Any]:
    return {
        "data_quality": choice_question(
            "Assess whether the supplied point-in-time engine evidence is sufficient "
            "for a pre-trade decision.",
            {
                "sufficient": "Market, signal, portfolio, and execution evidence are current and usable.",
                "partial": "Some evidence is missing or stale, but concrete risk checks remain possible.",
                "insufficient": "The state lacks enough current evidence for a directional or risk judgement.",
            },
        ),
        "signal_alignment": choice_question(
            "Compare the requested Eve action with engine facts and baseline. "
            "Treat missing evidence as insufficient rather than conflict.",
            {
                "aligned": "Price trend, momentum, and structure support the requested direction.",
                "mixed": "Evidence is usable but timeframes or engines disagree without strong contradiction.",
                "conflict": "Current evidence materially contradicts the requested direction.",
                "insufficient": "Not enough current market evidence to judge alignment.",
            },
        ),
        "market_regime": choice_question(
            "Judge whether the current multi-engine regime is suitable for this entry.",
            {
                "favorable": "Trend, momentum, and volatility reasonably support this entry.",
                "neutral": "Regime is mixed or range-bound but does not materially oppose the entry.",
                "adverse": "Regime materially opposes the entry or looks unstable for it.",
                "insufficient": "Market evidence unavailable or too stale to judge the regime.",
            },
        ),
        "risk_check": choice_question(
            "Assess portfolio exposure, kill switch, drawdown, and sizing risk for this entry.",
            {
                "clear": "New exposure looks proportionate; no material account risk visible.",
                "caution": "Risk elevated but within limits; does not require blocking.",
                "block": "Concrete sizing, concentration, drawdown, or protection risk requires blocking.",
                "insufficient": "Account evidence incomplete; no concrete blocking risk established.",
            },
        ),
        "execution_quality": choice_question(
            "Assess price freshness, stop distance availability, and execution constraints.",
            {
                "clear": "Order can be sized with current data; no material execution concern.",
                "caution": "Execution imperfect but does not justify blocking.",
                "block": "Stale/contradictory pricing, missing stop, or concrete execution issue requires blocking.",
                "insufficient": "Execution evidence incomplete; no concrete blocking issue established.",
            },
        ),
    }


def _choice_of(answer: Any, allowed: set[str]) -> tuple[str | None, dict[str, float], float | None]:
    if not isinstance(answer, dict):
        return None, {}, None
    choice = answer.get("choice")
    if not isinstance(choice, str) or choice not in allowed:
        return None, {}, None
    probs: dict[str, float] = {}
    raw_probs = answer.get("probabilities")
    if isinstance(raw_probs, dict):
        for k, v in raw_probs.items():
            if isinstance(k, str) and isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0:
                probs[k] = float(v)
    conf = answer.get("confidence")
    confidence: float | None
    if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0:
        confidence = float(conf)
    elif choice in probs:
        confidence = probs[choice]
    else:
        confidence = None
    return choice, probs, confidence


def converge_entry_gate(
    answers: dict[str, Any],
    *,
    min_confidence: float = 0.55,
) -> dict[str, Any]:
    """Deterministic convergence — QuantDinger rules, fail-closed on bad answers."""
    checks: list[dict[str, Any]] = []
    results: dict[str, tuple[str | None, dict[str, float], float | None]] = {}
    malformed = False

    for name in GATE_QUESTION_IDS:
        choice, probs, confidence = _choice_of(answers.get(name), GATE_OPTIONS[name])
        results[name] = (choice, probs, confidence)
        if choice is None:
            malformed = True
        checks.append(
            {
                "name": name,
                "result": choice,
                "confidence": confidence,
                "probabilities": probs,
            }
        )

    if malformed:
        return {
            "allowed": False,
            "decision": "reject",
            "reason": "gate_malformed_or_incomplete",
            "checks": checks,
            "confidence": None,
            "provider": "rules",
        }

    # Soft confidence gate on risk/execution (QD behaviour).
    for name in ("risk_check", "execution_quality"):
        conf = results[name][2]
        if conf is None or conf < min_confidence:
            return {
                "allowed": False,
                "decision": "reject",
                "reason": f"gate_low_confidence:{name}",
                "checks": checks,
                "confidence": conf,
                "provider": "rules",
            }

    risk_choice, _, risk_conf = results["risk_check"]
    exec_choice, _, exec_conf = results["execution_quality"]
    signal_choice, _, signal_conf = results["signal_alignment"]
    regime_choice, _, regime_conf = results["market_regime"]

    directional_block = (
        signal_choice == "conflict"
        and regime_choice == "adverse"
        and float(signal_conf or 0) >= min_confidence
        and float(regime_conf or 0) >= min_confidence
    )
    allowed = (
        risk_choice != "block"
        and exec_choice != "block"
        and not directional_block
    )

    if allowed:
        reason = "gate_entry_approved"
        confidence = min(float(risk_conf or 0), float(exec_conf or 0))
    elif risk_choice == "block":
        reason = "gate_entry_rejected:risk_block"
        confidence = risk_conf
    elif exec_choice == "block":
        reason = "gate_entry_rejected:execution_block"
        confidence = exec_conf
    elif directional_block:
        reason = "gate_entry_rejected:signal_conflict"
        confidence = min(float(signal_conf or 0), float(regime_conf or 0))
    else:
        reason = "gate_entry_rejected"
        confidence = None

    return {
        "allowed": allowed,
        "decision": "pass" if allowed else "reject",
        "reason": reason,
        "checks": checks,
        "confidence": confidence,
        "provider": "rules",
    }


def run_entry_gate(
    context: dict[str, Any],
    *,
    eve_action: str | None,
    use_jev: bool = True,
    min_confidence: float = 0.55,
) -> dict[str, Any]:
    """Call System One for the 5 CHOICE battery then converge in code.

    Skip (allowed=True, decision=skipped) for non-entry actions HOLD/ABSTAIN/CLOSE.
    Fail-closed if JEV errors.
    """
    action = (eve_action or "").upper()
    base: dict[str, Any] = {
        "schema": "ichivol.eve.entry_gate.v1",
        "eve_action": action or None,
        "not": "risk_kernel",
    }
    if action not in ("LONG", "SHORT"):
        return {
            **base,
            "allowed": True,
            "decision": "skipped",
            "reason": "non_entry_action",
            "checks": [],
            "confidence": None,
            "provider": "none",
            "jev": None,
        }

    if not use_jev:
        # Offline / study path (handoff: test use_jev=false first). Skip gate;
        # paper execute remains gated by autonomy + degradation.
        return {
            **base,
            "allowed": True,
            "decision": "skipped",
            "reason": "gate_jev_disabled_skipped",
            "checks": [],
            "confidence": None,
            "provider": "none",
            "jev": None,
            "note": "Gate skipped when use_jev=false (deterministic modes only)",
        }

    state = jev_state_for(context, mode="entry_gate", eve_action=action)
    questions = build_gate_questions()
    envelope = jev_evaluate(state, questions)
    if not envelope.get("ok"):
        return {
            **base,
            "allowed": False,
            "decision": "reject",
            "reason": f"gate_jev_failed:{envelope.get('error') or 'unknown'}",
            "checks": [],
            "confidence": None,
            "provider": envelope.get("provider") or "jev",
            "jev": envelope,
            "late": bool(envelope.get("late")),
            "note": "Fail-closed on JEV error (no OpenRouter fallback for System One)",
        }

    converged = converge_entry_gate(
        envelope.get("answers") or {},
        min_confidence=min_confidence,
    )
    return {
        **base,
        **converged,
        "provider": envelope.get("provider") or converged.get("provider"),
        "jev": envelope,
        "latency_ms": envelope.get("latency_ms"),
        "response_model": envelope.get("response_model"),
    }
