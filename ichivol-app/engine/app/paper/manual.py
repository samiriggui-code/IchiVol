"""Discretionary (user-chosen) paper buy: preview and validation. Paper only, never a real order.

The user picks the amount (EUR), how far the stop is (% of price) and the target multiple. This module tells
them, BEFORE anything is opened: what it will cost (commission + spread/slippage), what they lose if the stop is
hit and gain if the target is hit -- both NET of costs -- and what it does to the portfolio (cash, number of lines,
cumulative risk). It also lists blocking issues, so a refusal is explained rather than silent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.paper import broker as paper_broker
from app.paper import gates as paper_gates
from app.paper.risk import apply_entry_friction, apply_exit_friction, size_position
from app.paper.strategy_profiles import BASELINE_PROFILE

MIN_STOP_PCT, MAX_STOP_PCT = 0.002, 0.30
MIN_TP_R, MAX_TP_R = 0.5, 10.0


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def preview_manual_buy(
    session: Session,
    row: Any,
    *,
    notional: float,
    stop_pct: float | None = None,
    take_profit_r: float | None = None,
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
) -> dict[str, Any]:
    portfolio = paper_broker_get_portfolio(session, portfolio_code)
    profile = portfolio.strategy_profile or dict(BASELINE_PROFILE)
    symbol, price = row.symbol, float(row.price)
    equity = paper_broker.estimate_equity(session, portfolio)
    cash = float(portfolio.cash)
    tp_r = float(take_profit_r if take_profit_r is not None else profile.get("take_profit_r", 2.0))
    atr_stop = getattr(getattr(row, "atr", None), "suggested_stop_distance", None)
    blocking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if (getattr(row, "signal_timing", None) or {}).get("stale"):
        blocking.append(_issue("stale_data", "Les prix de ce marché ne sont plus à jour (marché fermé ou données en retard)."))
    if not (MIN_TP_R <= tp_r <= MAX_TP_R):
        blocking.append(_issue("bad_target", f"Objectif hors limites ({MIN_TP_R} à {MAX_TP_R} fois le risque)."))
    if stop_pct is not None:
        if not (MIN_STOP_PCT <= stop_pct <= MAX_STOP_PCT):
            blocking.append(_issue("bad_stop", f"Stop hors limites ({MIN_STOP_PCT:.1%} à {MAX_STOP_PCT:.0%} du prix)."))
        stop_distance = price * stop_pct
    else:
        stop_distance = float(atr_stop) if atr_stop else None
    if not stop_distance or stop_distance <= 0:
        blocking.append(_issue("no_stop", "Aucun stop calculable : indiquez un stop en % du prix."))
        stop_distance = price * 0.02  # only to keep the numbers below finite; the order stays blocked

    spread_bps, slippage_bps = paper_broker._friction(profile, symbol)
    comm_bps = paper_broker._commission_bps(profile, symbol)
    sized = size_position(
        equity=equity, cash=cash, direction="LONG", entry_price=price, stop_distance=stop_distance,
        take_profit_r=tp_r, commission_bps=comm_bps, spread_bps=spread_bps, slippage_bps=slippage_bps,
        min_notional=float(profile.get("min_notional", 10.0)), manual_notional=notional,
    )
    if sized is None:
        if notional < float(profile.get("min_notional", 10.0)):
            blocking.append(_issue("below_minimum", f"Montant trop petit (minimum {profile.get('min_notional', 10):.0f} €)."))
        else:
            blocking.append(_issue("insufficient_cash", f"Fonds insuffisants : {cash:,.2f} € disponibles, frais compris.".replace(",", " ")))
        qty = notional / price
        entry_fill = apply_entry_friction(price, direction="LONG", spread_bps=spread_bps, slippage_bps=slippage_bps)
        stop_price, tp_price = entry_fill - stop_distance, entry_fill + stop_distance * tp_r
    else:
        qty, entry_fill, stop_price, tp_price = sized.qty, sized.entry_fill, sized.stop_price, sized.take_profit_price
    real_notional = qty * entry_fill

    entry_fee = real_notional * comm_bps / 10_000.0
    entry_friction = qty * abs(entry_fill - price)
    exit_at_tp = apply_exit_friction(tp_price, direction="LONG", spread_bps=spread_bps, slippage_bps=slippage_bps)
    exit_at_stop = apply_exit_friction(stop_price, direction="LONG", spread_bps=spread_bps, slippage_bps=slippage_bps)
    fee_tp = qty * exit_at_tp * comm_bps / 10_000.0
    fee_stop = qty * exit_at_stop * comm_bps / 10_000.0
    gain_at_target = qty * (exit_at_tp - entry_fill) - entry_fee - fee_tp
    loss_at_stop = qty * (exit_at_stop - entry_fill) - entry_fee - fee_stop  # negative
    risk_amount = -loss_at_stop
    round_trip_costs = entry_fee + fee_tp + entry_friction + qty * abs(tp_price - exit_at_tp)

    opens = paper_gates.open_positions(session, portfolio.id)
    max_open = int(profile.get("max_open_positions", 5))
    open_risk_now = sum(float(o.risk_amount or 0.0) for o in opens)
    risk_cap_pct = profile.get("max_open_risk_pct")
    if any(o.symbol == symbol for o in opens):
        blocking.append(_issue("already_open", f"{symbol} est déjà dans votre portefeuille (un seul lot par marché). Fermez-le d'abord ou choisissez un autre marché."))
    if len(opens) >= max_open:
        blocking.append(_issue("max_positions", f"Portefeuille plein : {len(opens)} lignes sur {max_open} autorisées."))
    if risk_cap_pct and open_risk_now + risk_amount > equity * float(risk_cap_pct) + 1e-9:
        blocking.append(_issue(
            "open_risk_cap",
            f"Risque cumulé trop élevé : {open_risk_now + risk_amount:,.0f} € jusqu'aux stops pour un plafond de "
            f"{equity * float(risk_cap_pct):,.0f} € ({float(risk_cap_pct):.0%} du capital). Réduisez le montant ou rapprochez le stop.".replace(",", " "),
        ))
    if profile.get("daily_loss_limit_pct"):
        start = paper_gates.day_start_equity(session, portfolio)
        if start > 0 and equity <= start * (1 - float(profile["daily_loss_limit_pct"])):
            blocking.append(_issue("daily_loss_halt", "Perte journalière maximale atteinte : plus d'entrée jusqu'à demain (UTC)."))

    decision = row.pipeline.decision
    if decision != "BUY":
        warnings.append(_issue("signal_not_buy", f"Le moteur ne recommande pas d'achat ici (verdict : {decision}). Achat discrétionnaire, à vos risques."))
    if notional > 0 and real_notional > equity * 0.25:
        warnings.append(_issue("large_position", f"Cette ligne pèse {real_notional / equity:.0%} du capital."))
    if round_trip_costs > 0 and gain_at_target > 0 and round_trip_costs / (gain_at_target + round_trip_costs) > 0.3:
        warnings.append(_issue("costs_heavy", "Les frais absorbent plus de 30 % du gain visé."))

    return {
        "ok": not blocking,
        "blocking": blocking,
        "warnings": warnings,
        "symbol": symbol,
        "timeframe": row.timeframe,
        "direction": "LONG",
        "price": price,
        "engine_verdict": decision,
        "engine_stop_distance": atr_stop,
        "inputs": {"notional": notional, "stop_pct": stop_distance / price, "stop_distance": stop_distance, "take_profit_r": tp_r},
        "order": {
            "qty": qty, "entry_fill": entry_fill, "notional": real_notional, "stop_price": stop_price,
            "take_profit_price": tp_price, "risk_amount": risk_amount, "risk_pct_of_equity": (risk_amount / equity) if equity else None,
        },
        "costs": {
            "commission_entry": entry_fee, "commission_exit_at_target": fee_tp, "spread_slippage_entry": entry_friction,
            "round_trip_at_target": round_trip_costs, "commission_bps": comm_bps, "friction_bps_per_side": spread_bps + slippage_bps,
        },
        "outcomes": {"net_gain_if_target": gain_at_target, "net_loss_if_stop": loss_at_stop,
                     "reward_risk_net": (gain_at_target / risk_amount) if risk_amount > 0 else None},
        "portfolio": {
            "cash_before": cash, "cash_after": cash - real_notional - entry_fee, "equity": equity,
            "lines_before": len(opens), "lines_after": len(opens) + 1, "max_lines": max_open,
            "open_risk_before": open_risk_now, "open_risk_after": open_risk_now + risk_amount,
            "open_risk_cap": (equity * float(risk_cap_pct)) if risk_cap_pct else None,
        },
    }


def paper_broker_get_portfolio(session: Session, code: str):
    from app.paper.portfolio import ensure_baseline_portfolio, get_portfolio_by_code

    portfolio = ensure_baseline_portfolio(session)
    if code != portfolio.code:
        alt = get_portfolio_by_code(session, code)
        if alt is not None:
            portfolio = alt
    return portfolio
