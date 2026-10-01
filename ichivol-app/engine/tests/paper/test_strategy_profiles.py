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


def test_single_portfolio_mode_syncs_the_baseline_then_the_parallel_accounts():
    from app.paper.strategy_profiles import H4_CODE, SHORTS_CODE, WIDE_CODE

    assert syncable_profile_codes() == [BASELINE_CODE, SHORTS_CODE, H4_CODE, WIDE_CODE]


def test_parallel_accounts_differ_from_the_baseline_by_one_key_each():
    from app.paper.strategy_profiles import H4_CODE, PARALLEL_PROFILES, SHORTS_CODE, WIDE_CODE

    def diff(code):
        return {k for k, v in PARALLEL_PROFILES[code].items() if BASELINE_PROFILE.get(k) != v} - {"code", "label"}

    # Shorts allowed everywhere since 2026-10-01: the SHORTS account no longer differs from the baseline.
    assert diff(SHORTS_CODE) == set() and PARALLEL_PROFILES[SHORTS_CODE]["allow_short"] is True
    assert diff(H4_CODE) == {"auto_timeframes"} and PARALLEL_PROFILES[H4_CODE]["auto_timeframes"] == ["4h"]
    assert diff(WIDE_CODE) == {"universe"} and BASELINE_PROFILE["allow_short"] is True


def test_wide_symbols_only_reach_the_wide_account():
    from types import SimpleNamespace

    from app.paper.engine import _portfolio_takes_row
    from app.paper.strategy_profiles import H4_CODE, PARALLEL_PROFILES, WIDE_CODE, WIDE_EXTRA_SYMBOLS

    extra = SimpleNamespace(symbol=WIDE_EXTRA_SYMBOLS[0], timeframe="1h")
    core = SimpleNamespace(symbol="BTCUSDT", timeframe="1h")
    core_4h = SimpleNamespace(symbol="BTCUSDT", timeframe="4h")
    assert not _portfolio_takes_row(BASELINE_PROFILE, extra) and _portfolio_takes_row(BASELINE_PROFILE, core)
    assert _portfolio_takes_row(PARALLEL_PROFILES[WIDE_CODE], extra)
    assert not _portfolio_takes_row(BASELINE_PROFILE, core_4h)
    assert _portfolio_takes_row(PARALLEL_PROFILES[H4_CODE], core_4h)
    assert not _portfolio_takes_row(PARALLEL_PROFILES[H4_CODE], core)


def test_background_loop_scans_4h_and_wide_for_paper():
    from app.screener.cache import paper_timeframes, wide_universe_wanted

    assert paper_timeframes() == {"1h", "4h"} and wide_universe_wanted()


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
