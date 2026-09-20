"""Identity: total_pnl ≈ realized + unrealized − open entry fees.

Entry commissions reduce cash at open but only enter realized_pnl on close.
"""

from __future__ import annotations


def _reconcile(
    *,
    initial_cash: float,
    cash: float,
    invested: float,
    unrealized: float,
    realized: float,
    open_entry_fees: float,
) -> dict[str, float]:
    equity = cash + invested + unrealized
    total_pnl = equity - initial_cash
    realized_plus_unrealized = realized + unrealized
    pnl_explained = realized_plus_unrealized - open_entry_fees
    return {
        "equity": equity,
        "total_pnl": total_pnl,
        "realized_plus_unrealized": realized_plus_unrealized,
        "pnl_explained": pnl_explained,
        "gap": realized_plus_unrealized - total_pnl,
    }


def test_capture_example_gap_is_open_entry_fees():
    """Numbers from the Synthèse capture (illustrative, not live account)."""
    invested = 3715.15
    open_entry_fees = invested * (5.0 / 10_000.0)  # baseline commission_bps
    r = _reconcile(
        initial_cash=5000.0,
        cash=1291.30,
        invested=invested,
        unrealized=193.86,
        realized=8.31,
        open_entry_fees=open_entry_fees,
    )
    assert abs(r["equity"] - 5200.31) < 0.02
    assert abs(r["total_pnl"] - 200.31) < 0.02
    assert abs(r["gap"] - open_entry_fees) < 0.02
    assert abs(r["pnl_explained"] - r["total_pnl"]) < 0.02


def test_empty_account_identity():
    r = _reconcile(
        initial_cash=5000.0,
        cash=5000.0,
        invested=0.0,
        unrealized=0.0,
        realized=0.0,
        open_entry_fees=0.0,
    )
    assert r["equity"] == 5000.0
    assert r["total_pnl"] == 0.0
    assert r["gap"] == 0.0
