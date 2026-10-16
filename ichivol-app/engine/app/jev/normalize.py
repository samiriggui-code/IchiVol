"""Validate and normalize System One answers. Never invent evaluations."""

from __future__ import annotations

from typing import Any


def _as_float_01(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n < 0.0 or n > 1.0:
        return None
    return n


def _normalize_noul(answer: dict[str, Any]) -> dict[str, Any] | None:
    noul = _as_float_01(answer.get("noul"))
    if noul is None:
        return None
    out: dict[str, Any] = {"type": "noul", "noul": noul}
    conf = answer.get("confidence")
    if conf is not None:
        c = _as_float_01(conf)
        if c is None:
            return None
        out["confidence"] = c
    return out


def _normalize_choice(answer: dict[str, Any], allowed: set[str]) -> dict[str, Any] | None:
    choice = answer.get("choice")
    if not isinstance(choice, str) or not choice:
        return None
    if allowed and choice not in allowed:
        return None
    out: dict[str, Any] = {"type": "choice", "choice": choice}
    probs = answer.get("probabilities")
    if isinstance(probs, dict):
        cleaned: dict[str, float] = {}
        for k, v in probs.items():
            if not isinstance(k, str):
                return None
            fv = _as_float_01(v)
            if fv is None:
                return None
            cleaned[k] = fv
        out["probabilities"] = cleaned
    conf = answer.get("confidence")
    if conf is not None:
        c = _as_float_01(conf)
        if c is None:
            return None
        out["confidence"] = c
    return out


def _normalize_score(answer: dict[str, Any], n_levels: int) -> dict[str, Any] | None:
    raw_score = answer.get("score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return None
    # Accept integer level index or probability-weighted score in [0, n_levels-1].
    if score < 0 or score > max(n_levels - 1, 0) + 1e-9:
        # Some servers return weighted float in range; allow up to n_levels-1 inclusive.
        if not (0.0 <= score <= float(n_levels - 1)):
            return None
    out: dict[str, Any] = {"type": "score", "score": score}
    probs = answer.get("probabilities")
    if isinstance(probs, dict):
        cleaned: dict[str, float] = {}
        for k, v in probs.items():
            fv = _as_float_01(v)
            if fv is None:
                return None
            cleaned[str(k)] = fv
        out["probabilities"] = cleaned
    conf = answer.get("confidence")
    if conf is not None:
        c = _as_float_01(conf)
        if c is None:
            return None
        out["confidence"] = c
    return out


def normalize_answers(
    questions: dict[str, Any],
    answers: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (normalized_answers, error). On error, answers are None — never fabricated."""
    if not isinstance(questions, dict) or not questions:
        return None, "questions_empty"
    if not isinstance(answers, dict):
        return None, "answers_not_object"

    normalized: dict[str, Any] = {}
    for name, question in questions.items():
        if not isinstance(name, str) or not name:
            return None, "question_name_invalid"
        if not isinstance(question, dict):
            return None, f"question_invalid:{name}"
        qtype = question.get("type")
        raw = answers.get(name)
        if not isinstance(raw, dict):
            return None, f"answer_missing:{name}"

        if qtype == "noul":
            item = _normalize_noul(raw)
            if item is None:
                return None, f"answer_invalid_noul:{name}"
            normalized[name] = item
            continue

        if qtype == "choice":
            criteria = question.get("criteria")
            allowed: set[str] = set()
            if isinstance(criteria, dict):
                allowed = {str(k) for k in criteria.keys()}
            item = _normalize_choice(raw, allowed)
            if item is None:
                return None, f"answer_invalid_choice:{name}"
            normalized[name] = item
            continue

        if qtype == "score":
            criteria = question.get("criteria")
            if not isinstance(criteria, list) or not criteria:
                return None, f"question_invalid_score_criteria:{name}"
            item = _normalize_score(raw, len(criteria))
            if item is None:
                return None, f"answer_invalid_score:{name}"
            normalized[name] = item
            continue

        return None, f"question_type_unsupported:{name}:{qtype}"

    return normalized, None
