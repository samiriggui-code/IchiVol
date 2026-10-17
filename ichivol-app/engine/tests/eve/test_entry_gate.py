"""Entry gate — 5 CHOICE converge in code (QuantDinger-inspired, fail-closed)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from app.eve.entry_gate import converge_entry_gate, run_entry_gate


def _answers(**choices: str) -> dict[str, Any]:
    defaults = {
        "data_quality": "sufficient",
        "signal_alignment": "aligned",
        "market_regime": "favorable",
        "risk_check": "clear",
        "execution_quality": "clear",
    }
    defaults.update(choices)
    out: dict[str, Any] = {}
    for name, choice in defaults.items():
        out[name] = {
            "type": "choice",
            "choice": choice,
            "confidence": 0.8,
            "probabilities": {choice: 0.8},
        }
    return out


def test_converge_pass() -> None:
    out = converge_entry_gate(_answers())
    assert out["allowed"] is True
    assert out["decision"] == "pass"
    assert out["reason"] == "gate_entry_approved"


def test_converge_risk_block() -> None:
    out = converge_entry_gate(_answers(risk_check="block"))
    assert out["allowed"] is False
    assert out["reason"] == "gate_entry_rejected:risk_block"


def test_converge_signal_conflict_adverse() -> None:
    out = converge_entry_gate(
        _answers(signal_alignment="conflict", market_regime="adverse")
    )
    assert out["allowed"] is False
    assert out["reason"] == "gate_entry_rejected:signal_conflict"


def test_converge_low_confidence_on_risk() -> None:
    ans = _answers()
    ans["risk_check"]["confidence"] = 0.2
    out = converge_entry_gate(ans, min_confidence=0.55)
    assert out["allowed"] is False
    assert out["reason"] == "gate_low_confidence:risk_check"


def test_converge_malformed() -> None:
    out = converge_entry_gate({"risk_check": {"type": "choice", "choice": "nope"}})
    assert out["allowed"] is False
    assert out["reason"] == "gate_malformed_or_incomplete"


def test_run_skips_non_entry() -> None:
    out = run_entry_gate({"symbol": "BTCUSDT"}, eve_action="HOLD", use_jev=True)
    assert out["decision"] == "skipped"
    assert out["allowed"] is True


def test_run_skips_when_jev_disabled() -> None:
    out = run_entry_gate({"symbol": "BTCUSDT"}, eve_action="LONG", use_jev=False)
    assert out["decision"] == "skipped"


def test_run_fail_closed_on_jev_error() -> None:
    with patch(
        "app.eve.entry_gate.jev_evaluate",
        return_value={"ok": False, "error": "timeout", "late": True},
    ):
        out = run_entry_gate({"symbol": "BTCUSDT"}, eve_action="LONG", use_jev=True)
    assert out["allowed"] is False
    assert out["decision"] == "reject"
    assert "gate_jev_failed" in str(out["reason"])


def test_run_pass_with_mock_jev() -> None:
    with patch(
        "app.eve.entry_gate.jev_evaluate",
        return_value={"ok": True, "answers": _answers(), "provider": "jevos", "latency_ms": 12},
    ):
        out = run_entry_gate({"symbol": "BTCUSDT"}, eve_action="LONG", use_jev=True)
    assert out["allowed"] is True
    assert out["decision"] == "pass"
