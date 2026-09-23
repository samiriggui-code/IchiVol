"""T4b — structured overlay trade filters."""

from __future__ import annotations

import pytest

from app.chart_objects.filter_trades import (
    filter_trades,
    trade_matches_filters,
    validate_filter_args,
)


def _t(**kwargs):
    base = {
        "trade_id": 0,
        "direction": "LONG",
        "exit_reason": "stop",
        "outcome": "loss",
        "why_entered": [{"key": "price_above_kumo", "clause": "all", "expected": True, "passed": True}],
    }
    base.update(kwargs)
    return base


def test_and_filters():
    trades = [
        _t(trade_id=0, outcome="loss", exit_reason="stop", direction="LONG"),
        _t(trade_id=1, outcome="win", exit_reason="target", direction="LONG"),
        _t(trade_id=2, outcome="loss", exit_reason="stop", direction="SHORT"),
        _t(
            trade_id=3,
            outcome="loss",
            exit_reason="stop",
            direction="LONG",
            why_entered=[{"key": "other", "clause": "all", "expected": True, "passed": True}],
        ),
    ]
    out = filter_trades(
        trades,
        outcome="loss",
        exit_reason="stop",
        direction="LONG",
        why_entered_key="price_above_kumo",
    )
    assert [t["trade_id"] for t in out] == [0]


def test_outcome_all_passthrough():
    trades = [_t(trade_id=0), _t(trade_id=1, outcome="win")]
    assert len(filter_trades(trades, outcome="all")) == 2


def test_why_key_requires_passed_true():
    t = _t(
        why_entered=[
            {"key": "price_above_kumo", "clause": "all", "expected": True, "passed": False}
        ]
    )
    assert trade_matches_filters(t, why_entered_key="price_above_kumo") is False


def test_validate_rejects_bad_exit_reason():
    with pytest.raises(ValueError, match="exit_reason"):
        validate_filter_args(exit_reason="magic")
