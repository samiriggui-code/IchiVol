"""V1-B / coherence — no invented facts."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from app.eve.actions import normalize_action
from app.eve.coherence import compute_coherence
from app.eve.context import build_engine_context


def test_normalize_action_maps_baseline() -> None:
    assert normalize_action("BUY") == "LONG"
    assert normalize_action("STRONG_SELL") == "SHORT"
    assert normalize_action("NO_TRADE") == "ABSTAIN"
    assert normalize_action("HOLD") == "HOLD"


def test_build_engine_context_from_factsheet() -> None:
    fs = {
        "schema": "ichivol.factsheet.v1",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "as_of": 1700000000,
        "factsheet_id": "abc",
        "facts": [
            {
                "id": "pipeline.decision",
                "engine": "pipeline",
                "field": "decision",
                "value": "BUY",
                "display": "BUY",
                "unit": None,
                "timeframe": "1h",
                "as_of": 1700000000,
                "known_at": 1700000000,
                "source": "test",
                "status": "ok",
                "validation_status": "N/A",
                "decision_role": "signal",
            },
            {
                "id": "structure.bias",
                "engine": "structure",
                "field": "bias",
                "value": None,
                "display": None,
                "status": "unavailable",
                "reason": "missing",
                "timeframe": "1h",
                "source": "test",
                "validation_status": "N/A",
                "decision_role": "context",
            },
        ],
    }
    with patch("app.eve.context.build_factsheet", return_value=fs):
        ctx = build_engine_context("btcusdt", "1h")
    assert ctx["symbol"] == "BTCUSDT"
    assert ctx["baseline"]["action_mapped"] == "LONG"
    assert ctx["data_quality"] == 0.5
    assert "structure.bias" in ctx["unavailable"]
    assert ctx["error"] is None


def test_coherence_documents_non_equivalence() -> None:
    c = compute_coherence(
        data_quality=0.8,
        contradiction_count=1,
        guardian_warning_count=0,
        jev_noul=0.7,
        analyst_agrees_baseline=True,
    )
    assert 0.0 <= c["score"] <= 1.0
    assert "jev_score" in c["not"]
    assert c["policy_version"] == "eve.coherence.v1"


def test_coherence_without_jev_redistributes_weight() -> None:
    c = compute_coherence(
        data_quality=1.0,
        contradiction_count=0,
        guardian_warning_count=0,
        jev_noul=None,
        analyst_agrees_baseline=True,
    )
    assert c["components"]["jev_alignment"] is None
    assert c["weights_applied"]["jev_alignment"] == 0.0
