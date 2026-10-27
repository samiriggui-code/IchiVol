"""Fallback ladder for Ève System One — inspired by buberlo + jarrodwatts.

Precedence (worst wins):
  kill / critical → already handled by Guardian / Risk Kernel
  late (timeout)  → HOLD (never directional on stale budget)
  jev_down        → deterministic modes only, labelled heuristic
  low_confidence  → ABSTAIN (soft) / paper size reduce
  healthy         → normal

Never opens orders. Never uses OpenRouter as System One.
"""

from __future__ import annotations

from typing import Any, Literal

from app.eve.actions import EveAction, normalize_action

DegradationLevel = Literal[
    "healthy",
    "low_confidence",
    "late",
    "jev_down",
]


def _iter_jev_envelopes(jev_pack: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(jev_pack, dict):
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for mode, env in jev_pack.items():
        if isinstance(env, dict):
            out.append((str(mode), env))
    return out


def collect_confidences(jev_pack: dict[str, Any] | None) -> list[float]:
    """Pull confidence / noul scalars from normalized JEV answers."""
    vals: list[float] = []
    for _, env in _iter_jev_envelopes(jev_pack):
        if not env.get("ok"):
            continue
        answers = env.get("answers")
        if not isinstance(answers, dict):
            continue
        for ans in answers.values():
            if not isinstance(ans, dict):
                continue
            for key in ("confidence", "noul"):
                raw = ans.get(key)
                if isinstance(raw, (int, float)) and 0.0 <= float(raw) <= 1.0:
                    vals.append(float(raw))
    return vals


def extract_probabilities(jev_pack: dict[str, Any] | None) -> dict[str, Any]:
    """Compact probability map for decision_time persistence (Brier later)."""
    by_mode: dict[str, Any] = {}
    for mode, env in _iter_jev_envelopes(jev_pack):
        if not env.get("ok"):
            continue
        answers = env.get("answers")
        if not isinstance(answers, dict):
            continue
        mode_probs: dict[str, Any] = {}
        for qid, ans in answers.items():
            if not isinstance(ans, dict):
                continue
            entry: dict[str, Any] = {"type": ans.get("type")}
            if "choice" in ans:
                entry["choice"] = ans.get("choice")
            if "score" in ans:
                entry["score"] = ans.get("score")
            if "noul" in ans:
                entry["noul"] = ans.get("noul")
            if isinstance(ans.get("probabilities"), dict):
                entry["probabilities"] = ans["probabilities"]
            if isinstance(ans.get("confidence"), (int, float)):
                entry["confidence"] = float(ans["confidence"])
            mode_probs[str(qid)] = entry
        if mode_probs:
            by_mode[mode] = {
                "provider": env.get("provider"),
                "response_model": env.get("response_model"),
                "latency_ms": env.get("latency_ms"),
                "answers": mode_probs,
            }
    return by_mode


def assess_degradation(
    jev_pack: dict[str, Any] | None,
    *,
    jev_requested: bool,
    min_confidence: float = 0.45,
) -> dict[str, Any]:
    """Classify System One health for this evaluation cycle."""
    envelopes = _iter_jev_envelopes(jev_pack)
    attempted = [e for _, e in envelopes if e.get("ok") is not None or e.get("error")]
    # Modes that never called JEV leave jev=None — ignore those.
    called = [(m, e) for m, e in envelopes if isinstance(e, dict) and ("ok" in e or "error" in e)]
    if not jev_requested or not called:
        return {
            "level": "healthy" if not jev_requested else "jev_down",
            "late": False,
            "source": "deterministic" if not jev_requested else "heuristic",
            "reasons": [] if not jev_requested else ["jev_not_called"],
            "mean_confidence": None,
            "ok_count": 0,
            "fail_count": 0,
            "timeout_count": 0,
        }

    ok_count = sum(1 for _, e in called if e.get("ok"))
    fail_count = sum(1 for _, e in called if not e.get("ok"))
    timeout_count = sum(
        1
        for _, e in called
        if (not e.get("ok")) and str(e.get("error") or "") in ("timeout", "late")
    )
    late = timeout_count > 0 or any(bool(e.get("late")) for _, e in called)
    confs = collect_confidences({m: e for m, e in called})
    mean_conf = (sum(confs) / len(confs)) if confs else None

    reasons: list[str] = []
    level: DegradationLevel
    source: str

    if late:
        level = "late"
        source = "degraded"
        reasons.append("jev_timeout_or_late")
    elif ok_count == 0 and fail_count > 0:
        level = "jev_down"
        source = "heuristic"
        reasons.append("all_jev_calls_failed")
    elif mean_conf is not None and mean_conf < min_confidence:
        level = "low_confidence"
        source = "jev"
        reasons.append(f"mean_confidence<{min_confidence}")
    else:
        level = "healthy"
        source = "jev"
        if fail_count:
            reasons.append("partial_jev_failures")

    return {
        "level": level,
        "late": late,
        "source": source,
        "reasons": reasons,
        "mean_confidence": round(mean_conf, 4) if mean_conf is not None else None,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "timeout_count": timeout_count,
        "attempted_modes": [m for m, _ in called],
    }


def apply_degradation(
    synthesis: dict[str, Any],
    degradation: dict[str, Any],
) -> dict[str, Any]:
    """Mutate a copy of synthesis according to the ladder. Potential only."""
    out = dict(synthesis)
    rejected = list(out.get("rejected_scenarios") or [])
    action = normalize_action(out.get("action")) or "ABSTAIN"
    level = str(degradation.get("level") or "healthy")

    if level == "late" and action in ("LONG", "SHORT", "CLOSE"):
        rejected.append("degradation_late")
        out["action"] = "HOLD"
        out["rationale"] = "JEV late/timeout → HOLD (never directional on stale budget)"
        out["decision_rule"] = "degradation_late"
        action = "HOLD"
    elif level == "jev_down" and action in ("LONG", "SHORT"):
        # Deterministic engines may still propose a direction — keep but label;
        # soft-abstain only if no baseline agreement signal (caller may override).
        rejected.append("degradation_jev_down")
        out["rationale"] = (
            (out.get("rationale") or "") + " · JEV down — heuristic/deterministic only"
        ).strip(" ·")
    elif level == "low_confidence" and action in ("LONG", "SHORT"):
        rejected.append("degradation_low_confidence")
        out["action"] = "ABSTAIN"
        out["rationale"] = "JEV mean confidence low → ABSTAIN"
        out["decision_rule"] = "degradation_low_confidence"
        action = "ABSTAIN"

    out["rejected_scenarios"] = rejected
    out["degradation"] = {
        "level": level,
        "source": degradation.get("source"),
        "late": bool(degradation.get("late")),
        "mean_confidence": degradation.get("mean_confidence"),
        "reasons": list(degradation.get("reasons") or []),
    }
    out["action"] = action if action in ("LONG", "SHORT", "HOLD", "CLOSE", "ABSTAIN") else "ABSTAIN"
    _ = EveAction  # typing anchor
    return out
