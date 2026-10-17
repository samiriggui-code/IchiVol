"""Gamma-style AND signal rules in code."""

from __future__ import annotations

from app.eve.signal_rules import apply_signal_rules, evaluate_long_gates


def _pack(**nouls: float) -> dict:
    return {
        "analyst": {
            "ok": True,
            "answers": {k: {"type": "noul", "noul": v} for k, v in nouls.items()},
        }
    }


def test_long_gates_pass() -> None:
    out = evaluate_long_gates(
        {
            "trend_bullish": 0.8,
            "momentum_positive": 0.8,
            "relative_strength_positive": 0.7,
            "event_risk": 0.2,
            "asset_overextended": 0.4,
        }
    )
    assert out["allowed"] is True
    assert out["decision"] == "pass"


def test_high_event_risk_blocks() -> None:
    out = apply_signal_rules(
        "LONG",
        _pack(
            trend_bullish=0.8,
            momentum_positive=0.8,
            relative_strength_positive=0.7,
            event_risk=0.7,
            asset_overextended=0.4,
        ),
    )
    assert out["decision"] == "reject"
    assert out["allowed"] is False


def test_skip_when_insufficient_signals() -> None:
    out = apply_signal_rules("LONG", _pack(trend_bullish=0.9))
    assert out["decision"] == "skip"
    assert out["allowed"] is True
