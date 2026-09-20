from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from app.brokerage.ledger import Cause, DuplicateConflict, Leg, Ledger

T = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _fill(ledger, key="fill-1"):
    return ledger.post(
        key, T,
        [Leg("EUR", D("-1000"), Cause.EXECUTION), Leg("EUR", D("-2"), Cause.COMMISSION)],
        ref="order-1",
    )


def test_replay_is_idempotent_no_double_billing():
    l = Ledger()
    l.post("dep", T, [Leg("EUR", D("5000"), Cause.DEPOSIT)])
    _fill(l)
    _fill(l)  # restart replays the same event
    assert l.balances()["EUR"] == D("3998")
    assert len(l.transactions) == 2
    assert l.total_by_cause(Cause.COMMISSION, "EUR") == D("-2")


def test_same_key_different_content_is_rejected():
    l = Ledger()
    _fill(l)
    with pytest.raises(DuplicateConflict):
        l.post("fill-1", T, [Leg("EUR", D("-999"), Cause.EXECUTION)], ref="order-1")


def test_multi_currency_and_reconcile():
    l = Ledger()
    l.post("dep", T, [Leg("EUR", D("5000"), Cause.DEPOSIT)])
    l.post("fx", T, [Leg("EUR", D("-1000"), Cause.CONVERSION), Leg("USD", D("1150"), Cause.CONVERSION)])
    assert l.balances() == {"EUR": D("4000"), "USD": D("1150")}
    assert l.reconcile({"EUR": D("4000"), "USD": D("1150")}) == {}
    assert l.reconcile({"EUR": D("4001"), "USD": D("1150")}) == {"EUR": D("-1")}


def test_requires_tz_and_legs():
    l = Ledger()
    with pytest.raises(ValueError):
        l.post("x", datetime(2026, 1, 1), [Leg("EUR", D(1), Cause.DEPOSIT)])
    with pytest.raises(ValueError):
        l.post("y", T, [])


def test_audit_trail_by_ref():
    l = Ledger()
    _fill(l)
    assert [t.key for t in l.for_ref("order-1")] == ["fill-1"]
