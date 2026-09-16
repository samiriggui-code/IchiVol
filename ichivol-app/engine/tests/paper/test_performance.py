from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import PaperPosition
from app.paper.performance import compute_performance


def _position(
    pnl_pct: float | None = None,
    status: str = "CLOSED",
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
) -> PaperPosition:
    return PaperPosition(
        symbol="BTCUSDT", timeframe="1h", source="auto_watchlist", user_id=None,
        direction="LONG", status=status,
        entry_time=entry_time or datetime(2026, 1, 1, tzinfo=timezone.utc),
        entry_price=100.0, entry_decision="BUY",
        exit_time=exit_time, exit_price=None, exit_reason=None, pnl_pct=pnl_pct,
    )


def test_no_positions_returns_all_none():
    result = compute_performance([])
    assert result.num_closed_trades == 0
    assert result.num_open_positions == 0
    assert result.total_return is None


def test_only_open_positions_reports_zero_closed_but_counts_open():
    result = compute_performance([_position(status="OPEN", pnl_pct=None)])
    assert result.num_closed_trades == 0
    assert result.num_open_positions == 1
    assert result.total_return is None


def test_compounds_returns_across_multiple_trades():
    positions = [_position(pnl_pct=0.10), _position(pnl_pct=-0.05)]
    result = compute_performance(positions)
    assert result.total_return == pytest.approx(1.10 * 0.95 - 1)


def test_win_rate_and_profit_factor():
    positions = [
        _position(pnl_pct=0.10), _position(pnl_pct=0.20), _position(pnl_pct=-0.10),
    ]
    result = compute_performance(positions)
    assert result.num_closed_trades == 3
    assert result.win_rate == pytest.approx(2 / 3)
    assert result.profit_factor == pytest.approx(0.30 / 0.10)
    assert result.expectancy == pytest.approx((0.10 + 0.20 - 0.10) / 3)
    assert result.best_trade_pct == pytest.approx(0.20)
    assert result.worst_trade_pct == pytest.approx(-0.10)


def test_profit_factor_is_infinite_with_no_losses():
    result = compute_performance([_position(pnl_pct=0.10), _position(pnl_pct=0.05)])
    assert result.profit_factor == float("inf")


def test_avg_holding_hours_computed_from_entry_and_exit_times():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    positions = [
        _position(pnl_pct=0.01, entry_time=base, exit_time=base + timedelta(hours=2)),
        _position(pnl_pct=0.01, entry_time=base, exit_time=base + timedelta(hours=6)),
    ]
    result = compute_performance(positions)
    assert result.avg_holding_hours == pytest.approx(4.0)


def test_open_positions_are_excluded_from_trade_stats_but_still_counted():
    positions = [_position(pnl_pct=0.10), _position(status="OPEN", pnl_pct=None)]
    result = compute_performance(positions)
    assert result.num_closed_trades == 1
    assert result.num_open_positions == 1
    assert result.total_return == pytest.approx(0.10)
