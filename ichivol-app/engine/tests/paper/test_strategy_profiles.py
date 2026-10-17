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


def test_single_portfolio_mode_syncs_the_baseline_then_every_parallel_account():
    from app.paper.strategy_profiles import COMBO_CODE, H4_CODE, SHORTS_CODE, WIDE_CODE

    assert syncable_profile_codes() == [
        BASELINE_CODE, "ICHIVOL_SESSIONS_V1", "FUTURES_CRYPTO_V1", SHORTS_CODE, H4_CODE, WIDE_CODE, COMBO_CODE,
    ]


def test_parallel_accounts_differ_from_the_baseline_by_one_key_each():
    from app.paper.strategy_profiles import H4_CODE, PARALLEL_PROFILES, SHORTS_CODE, WIDE_CODE

    def diff(code):
        return {k for k, v in PARALLEL_PROFILES[code].items() if BASELINE_PROFILE.get(k) != v} - {"code", "label"}

    assert diff(SHORTS_CODE) == {"allow_short"} and PARALLEL_PROFILES[SHORTS_CODE]["allow_short"] is True
    assert diff(H4_CODE) == {"auto_timeframes"} and PARALLEL_PROFILES[H4_CODE]["auto_timeframes"] == ["4h"]
    assert diff(WIDE_CODE) == {"universe"} and BASELINE_PROFILE["allow_short"] is False


def test_combo_account_only_adds_the_confirmation_filters():
    from app.paper.strategy_profiles import COMBO_CODE, PARALLEL_PROFILES

    combo = PARALLEL_PROFILES[COMBO_CODE]
    diff = {k for k, v in combo.items() if BASELINE_PROFILE.get(k) != v} - {"code", "label"}
    assert diff == {
        "structure_filter", "structure_detectors", "fibonacci_filter",
        "context_rsi", "context_cmf", "context_obv", "context_regime_hard", "shadow_on_block",
    }
    # Same market, timeframe and direction rules as the baseline: only the filters differ.
    assert combo["auto_timeframes"] == ["1h"] and combo["allow_short"] is False


def test_wide_symbols_only_reach_the_wide_account():
    from app.paper.engine import auto_timeframes, trades_symbol
    from app.paper.strategy_profiles import H4_CODE, PARALLEL_PROFILES, WIDE_CODE, WIDE_EXTRA_SYMBOLS

    extra = WIDE_EXTRA_SYMBOLS[0]
    assert not trades_symbol(BASELINE_PROFILE, extra) and trades_symbol(BASELINE_PROFILE, "BTCUSDT")
    assert trades_symbol(PARALLEL_PROFILES[WIDE_CODE], extra)
    assert auto_timeframes(PARALLEL_PROFILES[H4_CODE]) == ("4h",)
    assert auto_timeframes(BASELINE_PROFILE) == ("1h",)


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
