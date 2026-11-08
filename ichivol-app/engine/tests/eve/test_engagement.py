"""Le moteur calcule, JEV mesure, Ève s'engage : seuil de rentabilité, dosage, et parcours complet de l'orchestrateur."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.eve.engagement import build_trade_plan, decide_engagement, plan_for_jev
from app.eve.modes import audit_verdict
from app.eve.orchestrator import evaluate_opportunity

PROFILE = {"take_profit_r": 2.0, "commission_bps": 0.0, "spread_bps": 5.0, "slippage_bps": 0.0}


def _plan(**over: Any) -> dict[str, Any]:
    candidate = {"symbol": "EURUSD", "price": 100.0, "stop_distance": 1.0, "rvol": 2.0, "trend": {"long": 2, "short": 0}}
    candidate.update(over)
    plan = build_trade_plan(candidate, PROFILE, equity=50_000.0, open_lots=[])
    assert plan is not None
    return plan


def _p(p: float) -> dict[str, Any]:
    return {"long_target": {"noul": p}, "short_target": {"noul": 1 - p}}


def test_breakeven_includes_costs() -> None:
    plan = _plan()
    # 5 bps par côté sur un stop de 1 % : 0,1 R aller-retour.
    assert plan["cost_r"] == pytest.approx(0.1)
    assert plan["p_min"] == pytest.approx(1.1 / 3.0)


def test_no_plan_or_undecided_means_no_engagement() -> None:
    assert decide_engagement("LONG", None, target_answers=_p(0.6)) is None
    assert decide_engagement("ABSTAIN", _plan(), target_answers=_p(0.6)) is None


def test_refusals_are_numbers() -> None:
    assert decide_engagement("LONG", _plan(), target_answers=None)["reason"] == "no_measure"
    low = decide_engagement("LONG", _plan(), target_answers=_p(0.30))
    assert low["enter"] is False and low["reason"] == "edge_insufficient" and low["edge"] < 0
    expensive = decide_engagement("LONG", _plan(stop_distance=0.05), target_answers=_p(0.9))
    assert expensive["enter"] is False and expensive["reason"] == "cost_too_high"


def test_size_grows_with_the_edge_within_the_range() -> None:
    small = decide_engagement("LONG", _plan(), target_answers=_p(0.38))
    big = decide_engagement("LONG", _plan(), target_answers=_p(0.70))
    assert small["enter"] and big["enter"]
    assert 0.0025 <= small["risk_pct"] < big["risk_pct"] <= 0.01
    assert big["risk_pct"] == pytest.approx(0.01)


def test_each_opinion_only_reduces_the_size() -> None:
    plan = _plan()
    base = decide_engagement("LONG", plan, target_answers=_p(0.6))["risk_pct"]
    gate = {"checks": [{"name": "execution_quality", "result": "caution"}]}
    for kw in ({"fragile": 0.75}, {"gate": gate}, {"audit": {"size_factor": 0.5}}, {"degradation_level": "low_confidence"}):
        out = decide_engagement("LONG", plan, target_answers=_p(0.6), **kw)
        assert out["enter"] and out["risk_pct"] < base


def test_volume_and_trend_condition_the_size() -> None:
    base = decide_engagement("LONG", _plan(), target_answers=_p(0.6))["risk_pct"]
    thin = decide_engagement("LONG", _plan(rvol=0.7), target_answers=_p(0.6))["risk_pct"]
    against = decide_engagement("LONG", _plan(trend={"long": 0, "short": 3}), target_answers=_p(0.6))["risk_pct"]
    assert thin < base and against < base


def test_floor_after_all_factors() -> None:
    out = decide_engagement(
        "LONG", _plan(rvol=0.5, trend={"long": 0, "short": 3}), target_answers=_p(0.38), fragile=0.9,
        gate={"checks": [{"name": "risk_check", "result": "block"}]}, audit={"size_factor": 0.5},
    )
    assert out["risk_pct"] == pytest.approx(0.001)


def test_lot_cap_depends_on_the_market() -> None:
    assert decide_engagement("LONG", _plan(), target_answers=_p(0.6))["max_notional_pct"] == 3.0
    crypto = decide_engagement("LONG", _plan(symbol="BTCUSDT"), target_answers=_p(0.6))
    assert crypto["max_notional_pct"] == 1.0


def test_jev_never_sees_the_threshold() -> None:
    view = plan_for_jev(_plan())
    assert "p_min" not in view and view["stop_pct"] == 1.0 and view["target_pct"] == 2.0


def _audit(choice: str | None = None, score: float | None = None, noul: float | None = None) -> dict[str, Any]:
    return {"jev": {"ok": True, "answers": {
        "independent_action": {"choice": choice}, "audit_confidence": {"score": score}, "review": {"noul": noul},
    }}}


def test_audit_only_blocks_the_opposite_side() -> None:
    assert audit_verdict(_audit("SHORT", 3.0, 0.9), "LONG")["verdict"] == "block"
    undecided = audit_verdict(_audit("ABSTAIN", 3.0, 0.9), "LONG")
    assert undecided["verdict"] == "allow" and undecided["size_factor"] == 0.75
    weak = audit_verdict(_audit("LONG", 1.0, 0.9), "LONG")
    assert weak["verdict"] == "allow" and weak["size_factor"] == 0.5


def _fake_jev(p_long: float):
    def fake(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        assert isinstance(state, dict)
        answers: dict[str, Any] = {}
        for qid, q in questions.items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": {"long_target": p_long, "short_target": 0.2}.get(qid, 0.55)}
            elif q["type"] == "score":
                answers[qid] = {"type": "score", "score": 2.0}
            else:
                choice = {
                    "primary_scenario": "LONG", "alt_action": "ABSTAIN", "risk_stance": "ALLOW",
                    "independent_action": "LONG",
                }.get(qid) or next(iter(q["criteria"]))
                if qid == "execution_quality":
                    choice = "caution"  # la réponse réelle de JEV, qui bloquait tout
                answers[qid] = {"type": "choice", "choice": choice, "confidence": 0.12, "probabilities": {choice: 0.33}}
        return {"ok": True, "answers": answers, "provider": "test", "latency_ms": 1.0}

    return fake


def _context() -> dict[str, Any]:
    return {
        "symbol": "EURUSD", "timeframe": "1h", "data_quality": 0.9, "unavailable": [], "engines": {}, "facts": [],
        "baseline": {"decision": "WATCH", "action_mapped": None, "pipeline": None}, "error": None, "jev_state": {"sym": "EURUSD"},
    }


def _evaluate(p_long: float) -> tuple[dict[str, Any], list[Any]]:
    states: list[Any] = []
    fake = _fake_jev(p_long)

    def spy(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        states.append(state)
        return fake(state, questions)

    with (
        patch("app.eve.orchestrator.build_engine_context", return_value=_context()),
        patch("app.eve.orchestrator.plan_for_candidate", return_value=_plan()),
        patch("app.eve.orchestrator.jev_health", return_value={}),
        patch("app.eve.modes.jev_evaluate", side_effect=spy),
        patch("app.eve.modes.save_evaluation"),
        patch("app.eve.entry_gate.jev_evaluate", side_effect=spy),
        patch("app.paper.portfolio.get_portfolio_by_code", return_value=None),
    ):
        out = evaluate_opportunity(
            "EURUSD", "1h", session=object(), persist=False, paper_dry_run=False,  # type: ignore[arg-type]
            candidate={"symbol": "EURUSD", "portfolio_code": "NOPE"},
        )
    return out, states


def test_eve_engages_on_the_answers_that_used_to_block_everything() -> None:
    out, states = _evaluate(0.55)
    assert out["eve_action"] == "LONG"
    assert out["entry_gate"]["allowed"] is True
    engagement = out["verdict"]["engagement"]
    assert engagement["enter"] is True and 0.001 <= engagement["risk_pct"] <= 0.01
    assert out["decision_time"]["engagement"] == engagement
    # Les calculs du moteur ont bien été donnés à JEV, sans le seuil.
    assert all(s["plan"]["stop_pct"] == 1.0 and "p_min" not in s["plan"] for s in states)


def test_eve_abstains_when_the_measure_is_below_the_threshold() -> None:
    out, _ = _evaluate(0.25)
    assert out["eve_action"] == "ABSTAIN"
    assert out["modes"]["synthesis"]["decision_rule"] == "engagement_edge_insufficient"
