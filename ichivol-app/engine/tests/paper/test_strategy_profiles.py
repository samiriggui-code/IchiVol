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


def test_single_portfolio_mode_syncs_the_baseline_the_sessions_the_futures_crypto_and_eve_accounts():
    assert syncable_profile_codes() == [
        BASELINE_CODE, "ICHIVOL_SESSIONS_V1", "FUTURES_CRYPTO_V1", "EVE_JEV_V1", "EVE_JEVOS_V1",
    ]


def test_eve_accounts_copy_the_baseline_but_decide_their_own_exits():
    base = ALL_PROFILES[BASELINE_CODE]
    assert "eve_source" not in base and base["exit_mode"] == "direction"
    for code, src in (("EVE_JEV_V1", "jev"), ("EVE_JEVOS_V1", "jevos")):
        p = ALL_PROFILES[code]
        assert p["eve_source"] == src and p["exit_mode"] == "eve"
        for key in ("risk_pct", "take_profit_r", "allow_short", "commission_bps_by_symbol", "auto_timeframes",
                    "daily_loss_limit_pct", "max_open_risk_pct"):
            assert p[key] == base[key], key


def test_experimental_codes_registered():
    codes = ALL_PROFILES
    assert BASELINE_CODE in codes
    assert "STRUCTURE_MVPP" in codes
    assert "STRUCTURE_CONSENSUS" in codes
    assert "ICHIVOL_MS_V1" in codes


def test_profile_for_copies():
    a = profile_for("STRUCTURE_MVPP")
    b = profile_for("STRUCTURE_MVPP")
    a["risk_pct"] = 0.99
    assert b["risk_pct"] == ALL_PROFILES["STRUCTURE_MVPP"]["risk_pct"]
