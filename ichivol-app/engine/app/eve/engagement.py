"""Le moteur calcule, JEV mesure, Ève s'engage (2026-11-08).

``build_trade_plan`` : les chiffres du moteur pour une opportunité (stop, objectif, coûts, seuil de rentabilité,
volume, tendance, exposition du compte). ``plan_for_jev`` en est la vue envoyée à JEV : le seuil ``p_min`` n'y figure
pas, JEV ne doit pas être ancré sur la réponse attendue.

``decide_engagement`` traduit les trois primitives de JEV en finance : NOUL = la probabilité d'atteindre l'objectif
avant le stop, comparée à ``p_min`` ; CHOICE = la direction (déjà tranchée par la synthèse) ; SCORE et les avis
(Challenger, porte d'entrée, audit) = des facteurs qui réduisent le risque engagé. Le volume et la tendance du moteur
font de même. Seuls bloquent : pas de mesure, coûts trop lourds, écart négatif.

Le pourcentage de JEV n'est pas encore calibré (rejeu du 08/11 sur 40 décisions : 0,49 en moyenne sur les perdants,
0,45 sur les gagnants) : d'où la fourchette de risque étroite. Paper uniquement.
"""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.paper.risk_kernel import market_state_from_profile
from app.paper.strategy_profiles import _is_spot_crypto

ENGAGEMENT_SCHEMA = "ichivol.eve.engagement.v1"

DEFAULT_ENGAGEMENT: dict[str, float] = {
    "risk_min": 0.0025,  # risque du capital quand l'écart est tout juste positif
    "risk_max": 0.01,  # risque du capital à ``edge_full`` et au-delà
    "risk_floor": 0.001,  # plancher une fois les facteurs appliqués
    "edge_full": 0.20,
    "max_cost_r": 0.5,  # au-delà, les coûts mangent la moitié du stop : pas de trade
    "crypto_max_notional_pct": 1.0,
    "other_max_notional_pct": 3.0,
}

TARGET_QUESTION_BY_ACTION = {"LONG": "long_target", "SHORT": "short_target"}


def build_trade_plan(
    candidate: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    equity: float,
    open_lots: Any,
    day_start_equity: float | None = None,
) -> dict[str, Any] | None:
    """Les calculs du moteur pour un candidat. ``None`` sans prix ou sans stop exploitable."""
    symbol = str(candidate.get("symbol") or "")
    price = candidate.get("price")
    stop = candidate.get("stop_distance")
    if not isinstance(price, (int, float)) or not isinstance(stop, (int, float)) or price <= 0 or stop <= 0:
        return None
    market = market_state_from_profile(profile, symbol)
    stop_pct = float(stop) / float(price)
    target_r = float(profile.get("take_profit_r", 2.0))
    side_bps = market.commission_bps + market.spread_bps + market.slippage_bps
    cost_r = (2.0 * side_bps / 10_000.0) / stop_pct
    net_win_r = target_r - cost_r
    net_loss_r = 1.0 + cost_r
    lots = list(open_lots or [])
    open_risk = sum(float(getattr(o, "risk_amount", 0.0) or 0.0) for o in lots)
    exposure = sum(float(getattr(o, "notional", 0.0) or 0.0) for o in lots)
    day_pnl = (equity / day_start_equity - 1.0) if day_start_equity and day_start_equity > 0 else None
    return {
        "symbol": symbol,
        "price": float(price),
        "stop_distance": float(stop),
        "stop_pct": stop_pct,
        "target_pct": stop_pct * target_r,
        "target_r": target_r,
        "side_cost_bps": side_bps,
        "cost_r": cost_r,
        "net_win_r": net_win_r,
        "net_loss_r": net_loss_r,
        "p_min": net_loss_r / (net_win_r + net_loss_r),
        "rvol": candidate.get("rvol"),
        "trend": candidate.get("trend") or {},
        "regime": candidate.get("regime") or [],
        "engine_signal": bool(candidate.get("engine_signal", True)),
        "equity": float(equity),
        "open_n": len(lots),
        "open_risk_pct": (open_risk / equity) if equity > 0 else None,
        "exposure_x": (exposure / equity) if equity > 0 else None,
        "day_pnl_pct": day_pnl,
    }


def plan_for_jev(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Ce que JEV reçoit. Sans ``p_min`` : il mesure, il ne recopie pas le seuil."""

    def pct(key: str) -> float | None:
        value = plan.get(key)
        return round(float(value) * 100.0, 3) if isinstance(value, (int, float)) else None

    def num(key: str) -> float | None:
        value = plan.get(key)
        return round(float(value), 3) if isinstance(value, (int, float)) else None

    return {
        "stop_pct": pct("stop_pct"),
        "target_pct": pct("target_pct"),
        "target_r": num("target_r"),
        "cost_r": num("cost_r"),
        "spread_bps": num("side_cost_bps"),
        "rvol": num("rvol"),
        "trend_htf": plan.get("trend") or {},
        "regime": list(plan.get("regime") or [])[:2],
        "open_n": plan.get("open_n"),
        "open_risk_pct": pct("open_risk_pct"),
        "exposure_x": num("exposure_x"),
        "day_pnl_pct": pct("day_pnl_pct"),
    }


def plan_for_candidate(session: Session, candidate: Mapping[str, Any]) -> dict[str, Any] | None:
    """``build_trade_plan`` sur l'état réel du compte visé par le candidat."""
    from app.paper import broker as paper_broker
    from app.paper import gates as paper_gates
    from app.paper.portfolio import get_portfolio_by_code

    portfolio = get_portfolio_by_code(session, str(candidate.get("portfolio_code") or ""))
    if portfolio is None:
        return None
    return build_trade_plan(
        candidate,
        portfolio.strategy_profile or {},
        equity=float(paper_broker.estimate_equity(session, portfolio)),
        open_lots=paper_gates.open_positions(session, portfolio.id),
        day_start_equity=paper_gates.day_start_equity(session, portfolio),
    )


def _fragility_factor(fragile: Any) -> float:
    if not isinstance(fragile, (int, float)):
        return 1.0
    if fragile >= 0.7:
        return 0.5
    return 0.75 if fragile >= 0.6 else 1.0


def _gate_factor(gate: Mapping[str, Any] | None) -> float:
    """``block`` à faible confiance et ``caution`` réduisent ; ``insufficient`` ne dit rien de plus."""
    factor = 1.0
    for check in (gate or {}).get("checks") or []:
        if check.get("name") not in ("risk_check", "execution_quality"):
            continue
        if check.get("result") == "block":
            factor = min(factor, 0.5)
        elif check.get("result") == "caution":
            factor = min(factor, 0.85)
    return factor


def _volume_factor(rvol: Any) -> float:
    if not isinstance(rvol, (int, float)):
        return 0.85
    if rvol >= 1.5:
        return 1.0
    return 0.85 if rvol >= 1.0 else 0.6


def _trend_factor(trend: Mapping[str, Any] | None, action: str) -> float:
    """Horizons supérieurs dans le sens du trade contre ceux à l'opposé ; rien de connu = neutre."""
    trend = trend or {}
    with_trade = int(trend.get(action.lower()) or 0)
    against = int(trend.get("short" if action == "LONG" else "long") or 0)
    if with_trade == 0 and against == 0:
        return 1.0
    if against > with_trade:
        return 0.6
    return 0.8 if against == with_trade else 1.0


def decide_engagement(
    action: str,
    plan: Mapping[str, Any] | None,
    *,
    target_answers: Mapping[str, Any] | None,
    fragile: Any = None,
    gate: Mapping[str, Any] | None = None,
    audit: Mapping[str, Any] | None = None,
    degradation_level: str | None = None,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """S'engager ou non, et de combien. ``None`` hors LONG/SHORT ou sans plan du moteur."""
    question = TARGET_QUESTION_BY_ACTION.get(action)
    if question is None or plan is None:
        return None
    cfg = {**DEFAULT_ENGAGEMENT, **dict(settings or {})}
    out: dict[str, Any] = {
        "schema": ENGAGEMENT_SCHEMA,
        "action": action,
        "enter": False,
        "p_min": round(float(plan["p_min"]), 4),
        "cost_r": round(float(plan["cost_r"]), 4),
    }
    raw = ((target_answers or {}).get(question) or {}).get("noul")
    if not isinstance(raw, (int, float)):
        return {**out, "reason": "no_measure"}
    p_win = float(raw)
    edge = p_win - float(plan["p_min"])
    out.update(p_win=round(p_win, 4), edge=round(edge, 4))
    if float(plan["cost_r"]) > float(cfg["max_cost_r"]):
        return {**out, "reason": "cost_too_high"}
    if edge <= 0:
        return {**out, "reason": "edge_insufficient"}

    base = float(cfg["risk_min"]) + (float(cfg["risk_max"]) - float(cfg["risk_min"])) * min(
        edge / float(cfg["edge_full"]), 1.0
    )
    factors = {
        "fragility": _fragility_factor(fragile),
        "gate": _gate_factor(gate),
        "audit": float((audit or {}).get("size_factor") or 1.0),
        "jev_confidence": 0.75 if degradation_level == "low_confidence" else 1.0,
        "volume": _volume_factor(plan.get("rvol")),
        "trend": _trend_factor(plan.get("trend"), action),
    }
    product = 1.0
    for value in factors.values():
        product *= value
    risk_pct = max(float(cfg["risk_floor"]), base * product)
    cap_key = "crypto_max_notional_pct" if _is_spot_crypto(str(plan.get("symbol") or "")) else "other_max_notional_pct"
    max_notional_pct = float(cfg[cap_key])
    return {
        **out,
        "enter": True,
        "reason": "edge_positive",
        "base_risk_pct": round(base, 6),
        "factors": factors,
        "risk_pct": round(risk_pct, 6),
        "max_notional_pct": max_notional_pct,
        "planned_leverage": round(min(risk_pct / float(plan["stop_pct"]), max_notional_pct), 3),
    }
