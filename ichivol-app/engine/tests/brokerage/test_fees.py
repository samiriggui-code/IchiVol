from datetime import date
from decimal import Decimal as D

from app.brokerage.fees import FeeSchedule

S = FeeSchedule(
    id="TEST", version="1", currency="EUR", source="ASSUMPTION: test values",
    effective_from=date(2026, 1, 1), proportional=D("0.001"), minimum=D("2"),
    fx_conversion=D("0.0025"),
)


def test_minimum_applies():
    assert S.order_fee(D("100"), D("1")) == D("2")


def test_proportional_above_minimum():
    assert S.order_fee(D("10000"), D("10")) == D("10")


def test_partial_fills_charge_minimum_once_and_sum_to_order_fee():
    fills = [(D("300"), D("3")), (D("300"), D("3")), (D("400"), D("4"))]
    cn = cq = D(0)
    total = D(0)
    for n, q in fills:
        total += S.fill_fee(cum_notional_before=cn, cum_quantity_before=cq, fill_notional=n, fill_quantity=q)
        cn += n
        cq += q
    assert total == S.order_fee(D("1000"), D("10")) == D("2")


def test_partial_fills_beyond_minimum():
    a = S.fill_fee(cum_notional_before=D(0), cum_quantity_before=D(0), fill_notional=D("1000"), fill_quantity=D(1))
    b = S.fill_fee(cum_notional_before=D("1000"), cum_quantity_before=D(1), fill_notional=D("4000"), fill_quantity=D(4))
    assert a == D("2") and a + b == D("5")


def test_conversion_fee():
    assert S.conversion_fee(D("-1000")) == D("2.5")
