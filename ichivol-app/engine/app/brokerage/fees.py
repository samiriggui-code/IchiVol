"""Versioned, sourced fee schedules (Decimal, never float).

A schedule is data, not code: every rate carries a source and effective date so
a backtest can record exactly which tariff produced its costs. Rates below in
tests/examples are illustrative placeholders, NOT a real broker's tariff --
real schedules must be loaded from a documented source before use.

Spread: fees here never include the bid/ask spread. When fills already use
real bid/ask prices the spread is in the price; adding it again here would
double-charge it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def _q(value: Decimal, places: int = 8) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FeeSchedule:
    id: str
    version: str
    currency: str
    source: str
    """Where the tariff comes from (URL/document) or 'ASSUMPTION: ...'."""
    effective_from: date

    proportional: Decimal = Decimal(0)
    """Fraction of notional, e.g. Decimal('0.001') = 10 bps."""
    per_unit: Decimal = Decimal(0)
    """Fee per share/contract/coin unit."""
    fixed: Decimal = Decimal(0)
    """Flat fee per order."""
    minimum: Decimal = Decimal(0)
    """Minimum total commission per ORDER (not per partial fill)."""
    maximum: Decimal | None = None
    """Optional cap per order, as a fraction of order notional."""
    fx_conversion: Decimal = Decimal(0)
    """Fraction of converted amount when a currency conversion is needed."""
    assumptions: str = ""

    def order_fee(self, notional: Decimal, quantity: Decimal) -> Decimal:
        """Total commission for an order of this cumulative size."""
        fee = self.fixed + self.proportional * notional + self.per_unit * quantity
        if self.maximum is not None:
            fee = min(fee, self.maximum * notional)
        if fee > 0 or notional > 0:
            fee = max(fee, self.minimum)
        return _q(fee)

    def fill_fee(
        self,
        *,
        cum_notional_before: Decimal,
        cum_quantity_before: Decimal,
        fill_notional: Decimal,
        fill_quantity: Decimal,
    ) -> Decimal:
        """Incremental fee for one (possibly partial) fill.

        Computed as fee(cumulative after) - fee(cumulative before), so the
        per-order minimum is charged once across all partial fills of the
        same order, and the sum of fills always equals the whole-order fee.
        """
        after = self.order_fee(cum_notional_before + fill_notional, cum_quantity_before + fill_quantity)
        if cum_notional_before == 0 and cum_quantity_before == 0:
            return after
        before = self.order_fee(cum_notional_before, cum_quantity_before)
        return _q(after - before)

    def conversion_fee(self, amount: Decimal) -> Decimal:
        return _q(abs(amount) * self.fx_conversion)
