"""Unit tests for experimental strategy profiles."""

from __future__ import annotations

from app.paper.strategy_profiles import (
    ALL_PROFILES,
    BASELINE_CODE,
    BASELINE_PROFILE,
    profile_for,
    syncable_profile_codes,
)


def test_baseline_has_no_structure_filter():
    assert BASELINE_PROFILE["structure_filter"] is None
    assert BASELINE_PROFILE["structure_detectors"] == []


def test_experimental_codes_registered():
    codes = syncable_profile_codes()
    assert BASELINE_CODE in codes
    assert "STRUCTURE_MVPP" in codes
    assert "STRUCTURE_CONSENSUS" in codes
    assert "ICHIVOL_MS_V1" in codes


def test_profile_for_copies():
    a = profile_for("STRUCTURE_MVPP")
    b = profile_for("STRUCTURE_MVPP")
    a["risk_pct"] = 0.99
    assert b["risk_pct"] == ALL_PROFILES["STRUCTURE_MVPP"]["risk_pct"]
