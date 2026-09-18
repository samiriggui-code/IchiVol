"""Phase 3 profile registration tests."""

from __future__ import annotations

from app.paper.strategy_profiles import ALL_PROFILES, BASELINE_CODE, syncable_profile_codes


def test_phase3_profiles_present():
    codes = syncable_profile_codes()
    assert BASELINE_CODE in codes
    for code in (
        "ICHIVOL_CTX_RSI",
        "ICHIVOL_CTX_FLOW",
        "ICHIVOL_CTX_REGIME",
        "ICHIVOL_MS_REGIME",
        "ICHIVOL_CTX_FULL",
    ):
        assert code in codes
        assert ALL_PROFILES[code]["shadow_on_block"] is True


def test_baseline_context_flags_false():
    b = ALL_PROFILES[BASELINE_CODE]
    assert b["context_rsi"] is False
    assert b["context_cmf"] is False
    assert b["context_obv"] is False
    assert b["context_regime_hard"] is False
    assert b["fibonacci_filter"] is None


def test_phase4_fib_profile_present():
    codes = syncable_profile_codes()
    assert "ICHIVOL_MS_FIB" in codes
    assert ALL_PROFILES["ICHIVOL_MS_FIB"]["fibonacci_filter"] == "require_confluence"
