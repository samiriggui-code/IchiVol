"""HTTP surface for Strategy Lab Research (T5b / T6 / T7 / Researcher)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.agents.types import Direction, StrategyAgentOutput
from app.decision.pipeline import build_pipeline
from app.main import app

client = TestClient(app)


def _ichi() -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=Direction.LONG,
        probability=0.7,
        confidence=1.0,
        expected_value=0.0,
        reasons=["tk_cross_bullish"],
        invalidation=[],
        metadata={"score": 50.0},
    )


def _rvol() -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="RVOL_AGENT",
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=0.8,
        expected_value=0.0,
        reasons=[],
        invalidation=[],
        metadata={"confirmed": True, "anomaly_level": "SIGNIFICANT", "rvol": 2.5},
    )


def test_family_weight_profiles_catalog():
    res = client.get("/api/engine/strategy-lab/family-weight-profiles")
    assert res.status_code == 200
    body = res.json()
    assert len(body["profiles"]) >= 1
    assert "observation" in body["disclaimer"].lower() or "lab" in body["disclaimer"].lower()
    row = body["profiles"][0]
    assert "id" in row and "weights" in row and "version" in row


def test_propose_experiment_plan_from_audit_dict():
    audit = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "ruleset_id": "IV_ICHIMOKU_ONLY_LONG_001",
        "hypotheses": [
            {
                "id": "h_stop_widen_or_filter",
                "statement": "Stop may be tight",
                "suggested_experiment": "regime",
                "status": "proposed",
            }
        ],
    }
    res = client.post(
        "/api/engine/strategy-lab/propose-experiment-plan",
        json={"audit_report": audit},
    )
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["status"] == "proposed"
    assert plan["symbol"] == "BTCUSDT"
    assert len(plan["steps"]) >= 1
    assert "never auto-runs" in plan["disclaimer"].lower()


def test_audit_report_rejects_missing_ruleset():
    res = client.post(
        "/api/engine/strategy-lab/audit-report",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100},
    )
    assert res.status_code == 422


def test_monte_carlo_rejects_missing_ruleset():
    res = client.post(
        "/api/engine/strategy-lab/monte-carlo",
        json={"symbol": "BTCUSDT", "limit": 100},
    )
    assert res.status_code == 422


def test_family_weights_compare_monkeypatched(monkeypatch):
    from app.api import strategy_lab_research as mod

    pipe = build_pipeline(_ichi(), _rvol())
    decision = MagicMock()
    decision.decision = "BUY"
    decision.confidence = 0.7
    row = MagicMock()
    row.symbol = "BTCUSDT"
    row.timeframe = "1h"
    row.pipeline = pipe
    row.decision = decision

    monkeypatch.setattr(mod, "scan_symbol", lambda *a, **k: row)

    res = client.get(
        "/api/engine/strategy-lab/family-weights/compare",
        params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "profiles" in body
    assert "observation" in body["disclaimer"].lower()
