"""Append-only accounting journal for the virtual account.

Design rules (mission §7):
- Decimal amounts, one balance per currency.
- Every movement has a cause; nothing is edited in place. A correction is a
  new entry with cause CORRECTION.
- A transaction groups the legs of one event (e.g. a fill = trade cash leg +
  commission leg) and is posted atomically.
- Posting is idempotent on ``key``: replaying an event after a restart returns
  the original transaction and changes nothing, so no double execution and no
  double billing.
- ``reconcile`` recomputes balances from the journal and compares them with an
  independently supplied expectation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Cause(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXECUTION = "execution"
    COMMISSION = "commission"
    FINANCING = "financing"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    CONVERSION = "conversion"
    CORRECTION = "correction"


@dataclass(frozen=True)
class Leg:
    currency: str
    amount: Decimal
    """Signed: positive credits the account, negative debits it."""
    cause: Cause
    memo: str = ""


@dataclass(frozen=True)
class Transaction:
    key: str
    ts: datetime
    legs: tuple[Leg, ...]
    ref: str | None = None
    """Related order/position id, for the per-trade audit trail."""


class DuplicateConflict(Exception):
    """Same idempotency key re-posted with different content."""


class Ledger:
    def __init__(self) -> None:
        self._txs: list[Transaction] = []
        self._by_key: dict[str, Transaction] = {}

    def post(self, key: str, ts: datetime, legs: list[Leg], ref: str | None = None) -> Transaction:
        if not legs:
            raise ValueError("transaction needs at least one leg")
        if ts.tzinfo is None:
            raise ValueError("ts must be timezone-aware")
        tx = Transaction(key=key, ts=ts, legs=tuple(legs), ref=ref)
        existing = self._by_key.get(key)
        if existing is not None:
            if existing.legs != tx.legs or existing.ref != tx.ref:
                raise DuplicateConflict(key)
            return existing
        self._txs.append(tx)
        self._by_key[key] = tx
        return tx

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self._txs)

    def balances(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for tx in self._txs:
            for leg in tx.legs:
                out[leg.currency] = out.get(leg.currency, Decimal(0)) + leg.amount
        return out

    def total_by_cause(self, cause: Cause, currency: str) -> Decimal:
        return sum(
            (l.amount for tx in self._txs for l in tx.legs if l.cause == cause and l.currency == currency),
            Decimal(0),
        )

    def for_ref(self, ref: str) -> list[Transaction]:
        return [t for t in self._txs if t.ref == ref]

    def reconcile(self, expected: dict[str, Decimal]) -> dict[str, Decimal]:
        """Return {currency: journal - expected} for every non-zero difference."""
        actual = self.balances()
        diffs = {}
        for cur in set(actual) | set(expected):
            d = actual.get(cur, Decimal(0)) - expected.get(cur, Decimal(0))
            if d != 0:
                diffs[cur] = d
        return diffs
