"""V1-C modes + orchestrator — potential only, no execution."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from app.eve.modes import run_analyst, run_challenger, run_guardian, synthesize_action
from app.eve.orchestrator import evaluate_opportunity


def _ctx(**overrides: Any) -> dict[str, Any]:
    base = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "data_quality": 0.7,
        "unavailable": [],
        "engines": {"pipeline": [], "structure": []},
        "facts": [
            {
                "id": "a",
                "engine": "structure",
                "field": "bias",
                "value": "bull",
                "status": "ok",
            },
            {
                "id": "b",
                "engine": "cvd",
                "field": "bias",
                "value": "bear",
                "status": "ok",
            },
        ],
        "baseline": {"decision": "BUY", "action_mapped": "LONG", "pipeline": {"decision": "BUY"}},
        "error": None,
    }
    base.update(overrides)
    return base


def test_challenger_detects_bias_divergence() -> None:
    out = run_challenger(_ctx(), use_jev=False)
    codes = {c["code"] for c in out["contradictions"]}
    assert "multi_engine_bias_divergence" in codes
    assert out["execution_allowed"] is False


def test_guardian_critical_kill_switch() -> None:
    ctx = _ctx(
        facts=[
            {
                "id": "risk.kill_switch",
                "engine": "risk",
                "field": "kill_switch",
                "value": "armed",
                "status": "ok",
            }
        ]
    )
    g = run_guardian(ctx, use_jev=False)
    assert any(w["code"] == "kill_switch_armed" for w in g["warnings"])
    assert g["risk_kernel_authority"] is True


def test_synthesize_abstains_on_critical() -> None:
    synth = synthesize_action(
        analyst=run_analyst(_ctx(), use_jev=False),
        challenger=run_challenger(_ctx(), use_jev=False),
        guardian={
            "warnings": [{"code": "kill_switch_armed", "severity": "critical"}],
        },
        shadow={"result": {}},
        baseline_action="LONG",
    )
    assert synth["action"] == "ABSTAIN"
    assert synth["executed"] is False
    assert synth["status"] == "potential"


def test_evaluate_opportunity_no_persist(monkeypatch: Any) -> None:
    fs = {
        "schema": "ichivol.factsheet.v1",
        "symbol": "ETHUSDT",
        "timeframe": "1h",
        "as_of": 1,
        "factsheet_id": "x",
        "facts": [
            {
                "id": "pipeline.decision",
                "engine": "pipeline",
                "field": "decision",
                "value": "WATCH",
                "status": "ok",
                "display": "WATCH",
                "timeframe": "1h",
                "source": "t",
                "validation_status": "N/A",
                "decision_role": "signal",
            }
        ],
    }
    with patch("app.eve.context.build_factsheet", return_value=fs):
        out = evaluate_opportunity("ETHUSDT", "1h", persist=False, use_jev=False)
    assert out["execution_status"] == "not_executed"
    assert out["verdict"]["executed"] is False
    assert out["verdict"]["status"] == "potential"
    assert out["eve_action"] in {"LONG", "SHORT", "HOLD", "CLOSE", "ABSTAIN"}
    assert out["dossier_id"] is None
