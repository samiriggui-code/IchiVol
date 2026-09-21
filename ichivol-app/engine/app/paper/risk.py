"""Fixed-fractional risk sizing for the paper broker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizedOrder:
    qty: float
    notional: float
    stop_price: float
    take_profit_price: float
    risk_pct: float
    risk_amount: float
    entry_fill: float


def apply_entry_friction(price: float, *, direction: str, spread_bps: float, slippage_bps: float) -> float:
    """Adverse fill for the taker: long pays up, short sells down."""
    total = (spread_bps + slippage_bps) / 10_000.0
    if direction == "LONG":
        return price * (1.0 + total)
    return price * (1.0 - total)


def apply_exit_friction(price: float, *, direction: str, spread_bps: float, slippage_bps: float) -> float:
    total = (spread_bps + slippage_bps) / 10_000.0
    if direction == "LONG":
        return price * (1.0 - total)
    return price * (1.0 + total)


def _size_manual(
    *, equity: float, cash: float, direction: str, entry_price: float, stop_distance: float, take_profit_r: float,
    commission_bps: float, spread_bps: float, slippage_bps: float, min_notional: float, notional_target: float,
) -> SizedOrder | None:
    """Discretionary order: the USER picks the amount. The risk-% and per-order caps do not apply (the caller
    checks portfolio-level guards and shows the resulting risk); cash still can never go negative."""
    entry_fill = apply_entry_friction(
        entry_price, direction=direction, spread_bps=spread_bps, slippage_bps=slippage_bps
    )
    if notional_target <= 0 or notional_target < min_notional:
        return None
    qty = notional_target / entry_fill
    notional = qty * entry_fill
    if notional * (1.0 + commission_bps / 10_000.0) > cash + 1e-9:
        return None
    if direction == "LONG":
        stop_price = entry_fill - stop_distance
        take_profit_price = entry_fill + stop_distance * take_profit_r
    else:
        stop_price = entry_fill + stop_distance
        take_profit_price = entry_fill - stop_distance * take_profit_r
    if stop_price <= 0 or take_profit_price <= 0:
        return None
    risk_amount = qty * stop_distance
    return SizedOrder(
        qty=qty, notional=notional, stop_price=stop_price, take_profit_price=take_profit_price,
        risk_pct=(risk_amount / equity) if equity > 0 else 0.0, risk_amount=risk_amount, entry_fill=entry_fill,
    )


def size_position(
    *,
    equity: float,
    cash: float,
    direction: str,
    entry_price: float,
    stop_distance: float,
    risk_pct: float = 0.01,
    take_profit_r: float = 2.0,
    max_notional_pct: float = 0.25,
    commission_bps: float = 5.0,
    spread_bps: float = 2.0,
    slippage_bps: float = 3.0,
    min_fill_fraction: float = 0.0,
    min_notional: float = 0.0,
    manual_notional: float | None = None,
) -> SizedOrder | None:
    if equity <= 0 or entry_price <= 0 or stop_distance <= 0:
        return None
    if manual_notional is not None:
        return _size_manual(
            equity=equity, cash=cash, direction=direction, entry_price=entry_price, stop_distance=stop_distance,
            take_profit_r=take_profit_r, commission_bps=commission_bps, spread_bps=spread_bps,
            slippage_bps=slippage_bps, min_notional=min_notional, notional_target=manual_notional,
        )

    entry_fill = apply_entry_friction(
        entry_price, direction=direction, spread_bps=spread_bps, slippage_bps=slippage_bps
    )
    risk_amount = equity * risk_pct
    qty = risk_amount / stop_distance
    notional = qty * entry_fill

    max_notional = equity * max_notional_pct
    if notional > max_notional and max_notional > 0:
        qty = max_notional / entry_fill
        notional = qty * entry_fill
        risk_amount = qty * stop_distance

    intended_notional = notional
    fee = notional * (commission_bps / 10_000.0)
    if notional + fee > cash:
        affordable = cash / (1.0 + commission_bps / 10_000.0)
        if affordable <= 0:
            return None
        qty = affordable / entry_fill
        notional = qty * entry_fill
        risk_amount = qty * stop_distance
        if qty <= 0 or notional <= 0:
            return None
        # Cash-limited: refuse a dust lot far below the intended risk-based size
        # rather than opening a position that no longer matches the risk plan.
        if notional < intended_notional * min_fill_fraction:
            return None
    if notional < min_notional:
        return None

    if direction == "LONG":
        stop_price = entry_fill - stop_distance
        take_profit_price = entry_fill + stop_distance * take_profit_r
    else:
        stop_price = entry_fill + stop_distance
        take_profit_price = entry_fill - stop_distance * take_profit_r

    if stop_price <= 0 or take_profit_price <= 0:
        return None

    return SizedOrder(
        qty=qty,
        notional=notional,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
        risk_pct=risk_pct,
        risk_amount=risk_amount,
        entry_fill=entry_fill,
    )
