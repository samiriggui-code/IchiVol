"""NOUL / CHOICE / SCORE answer validation — never invent."""

from __future__ import annotations

from app.jev.normalize import normalize_answers
from app.jev.questions import choice_question, noul_question, score_question


def test_noul_ok() -> None:
    q = {"review": noul_question("ok?")}
    answers, err = normalize_answers(q, {"review": {"type": "noul", "noul": 0.82}})
    assert err is None
    assert answers == {"review": {"type": "noul", "noul": 0.82}}


def test_noul_out_of_range_rejected() -> None:
    q = {"review": noul_question("ok?")}
    answers, err = normalize_answers(q, {"review": {"noul": 1.5}})
    assert answers is None
    assert err == "answer_invalid_noul:review"


def test_choice_ok() -> None:
    q = {
        "action": choice_question(
            "pick",
            {"LONG": "enter long", "HOLD": "stay flat", "ABSTAIN": None},
        )
    }
    answers, err = normalize_answers(
        q,
        {
            "action": {
                "type": "choice",
                "choice": "HOLD",
                "probabilities": {"LONG": 0.1, "HOLD": 0.7, "ABSTAIN": 0.2},
                "confidence": 0.7,
            }
        },
    )
    assert err is None
    assert answers is not None
    assert answers["action"]["choice"] == "HOLD"


def test_choice_unknown_option_rejected() -> None:
    q = {"action": choice_question("pick", {"LONG": "a", "SHORT": "b"})}
    answers, err = normalize_answers(q, {"action": {"choice": "HOLD"}})
    assert answers is None
    assert err == "answer_invalid_choice:action"


def test_score_ok() -> None:
    q = {
        "risk": score_question(
            "rate risk",
            ["negligible", "moderate", "elevated", "extreme"],
        )
    }
    answers, err = normalize_answers(q, {"risk": {"type": "score", "score": 2.0}})
    assert err is None
    assert answers is not None
    assert answers["risk"]["score"] == 2.0


def test_missing_answer_rejected() -> None:
    q = {"review": noul_question("ok?")}
    answers, err = normalize_answers(q, {})
    assert answers is None
    assert err == "answer_missing:review"


def test_choice_builder_requires_criteria() -> None:
    try:
        choice_question("pick", {})
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "choice_criteria_required" in str(exc)
