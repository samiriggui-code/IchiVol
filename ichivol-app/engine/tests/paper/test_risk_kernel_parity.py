"""T13b — Risk Kernel parity with legacy entry_gate + size defaults."""

from __future__ import annotations

from app.paper.risk_kernel import (
    OpenLotSnap,
    OpenPlan,
    PortfolioState,
    evaluate,
    evaluate_entry_codes,
    market_state_from_profile,
)
from app.paper.strategy_profiles import BASELINE_PROFILE


def _baseline_state(
    *,
    cash: float = 10_000.0,
    equity: float = 10_000.0,
    opens: tuple[OpenLotSnap, ...] = (),
    day_start: float = 10_000.0,
    traded_run_id: int | None = None,
    profile: dict | None = None,
) -> PortfolioState:
    return PortfolioState(
        cash=cash,
        equity=equity,
        profile=dict(profile if profile is not None else BASELINE_PROFILE),
        open_positions=opens,
        day_start_equity=day_start,
        traded_run_id=traded_run_id,
    )


def test_evaluate_entry_codes_matches_gate_order():
    state = _baseline_state()
    plan = OpenPlan(
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        price=50_000.0,
        stop_distance=None,
    )
    assert evaluate_entry_codes(plan, state) == "no_atr_stop"

    plan2 = OpenPlan(
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        price=50_000.0,
        stop_distance=500.0,
    )
    assert evaluate_entry_codes(plan2, state) is None

    # one position per symbol
    state2 = _baseline_state(
        opens=(OpenLotSnap(symbol="BTCUSDT", notional=1000.0, risk_amount=50.0),)
    )
    assert evaluate_entry_codes(plan2, state2) == "position_already_open"


def test_evaluate_stale_and_short():
    state = _baseline_state()
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    stale = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
            stale=True,
        ),
        state,
        market,
    )
    assert not stale.accepted
    assert stale.primary_code() == "stale_data"

    short = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="SHORT",
            price=50_000.0,
            stop_distance=500.0,
        ),
        state,
        market,
    )
    assert not short.accepted
    assert short.primary_code() == "short_not_allowed"


def test_evaluate_accept_baseline_happy_path():
    state = _baseline_state()
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
        ),
        state,
        market,
    )
    assert d.accepted
    assert d.sized is not None
    assert d.sized.qty > 0


def test_evaluate_quality_code_does_not_reject():
    """T11a quality is observation-only — never a hard refuse (T13b parity)."""
    state = _baseline_state()
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
            data_quality_gate="fail",
        ),
        state,
        market,
    )
    assert d.accepted
    assert "quality_fail" in d.codes


def test_evaluate_open_risk_cap_parity():
    # Fill open risk near baseline max_open_risk_pct=0.04 on 10k → $400
    opens = (
        OpenLotSnap(symbol="ETHUSDT", notional=2000.0, risk_amount=395.0),
    )
    state = _baseline_state(opens=opens)
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    d = evaluate(
        OpenPlan(
            symbol="BTCUSDT",
            timeframe="1h",
            direction="LONG",
            price=50_000.0,
            stop_distance=500.0,
        ),
        state,
        market,
        check_size=False,
    )
    assert not d.accepted
    assert d.primary_code() == "open_risk_cap"


def test_manual_notional_skips_gates_like_sync_position():
    """manual_notional historically bypasses entry_gate in sync_position."""
    opens = tuple(
        OpenLotSnap(symbol=f"S{i}", notional=100.0, risk_amount=10.0) for i in range(10)
    )
    state = _baseline_state(opens=opens)  # at max_open_positions=10
    market = market_state_from_profile(BASELINE_PROFILE, "BTCUSDT")
    # Without manual — max_positions
    d1 = evaluate(
        OpenPlan(
            symbol="NEW",
            timeframe="1h",
            direction="LONG",
            price=100.0,
            stop_distance=2.0,
        ),
        state,
        market,
        check_size=False,
    )
    assert d1.primary_code() == "max_positions"
    # With manual — gates skipped (size may still fail)
    d2 = evaluate(
        OpenPlan(
            symbol="NEW",
            timeframe="1h",
            direction="LONG",
            price=100.0,
            stop_distance=2.0,
            manual_notional=50.0,
        ),
        state,
        market,
        check_size=False,
    )
    assert d2.accepted
