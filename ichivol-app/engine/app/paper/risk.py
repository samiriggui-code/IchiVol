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
) -> SizedOrder | None:
    if equity <= 0 or entry_price <= 0 or stop_distance <= 0:
        return None

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
