"""Bilan du portefeuille unique par décideur et par classe d'actifs, drawdown, règles du compte (lecture seule).

Sert le Desk et la page Portefeuille (2026-10-27) : le front affiche ces chiffres, il ne les recalcule pas.

Décideur d'un lot (même règle que l'ancien calcul du front, src/lib/decider.ts) :
- ``engine_over_eve`` : Ève a refusé, le moteur a tradé quand même (``entry_signal.decided_by``) ;
- ``eve`` : ouvert au nom d'Ève (``user_id = eve_intelligence`` ou ``entry_signal.eve_dossier_id``) ;
- ``engine`` : signal du moteur seul (``source = auto_watchlist``) ;
- ``manual`` : tout le reste (ordre confirmé à la main).
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperEquitySnapshot, PaperPortfolio, PaperPosition

EVE_USER_ID = "eve_intelligence"
DECIDERS: tuple[str, ...] = ("eve", "engine_over_eve", "engine", "manual")
DECIDER_LABEL = {
    "eve": "Ève",
    "engine_over_eve": "Moteur contre Ève",
    "engine": "Moteur seul",
    "manual": "Manuel",
}
ASSET_CLASS_LABEL = {
    "crypto": "Crypto",
    "forex": "Forex",
    "metal": "Métaux",
    "index": "Indices",
    "energy": "Énergie",
    "future": "Futures",
    "equity": "Actions",
    "other": "Autres",
}


def decider_of(position: Any) -> str:
    sig = getattr(position, "entry_signal", None) or {}
    if sig.get("decided_by") == "engine_over_eve":
        return "engine_over_eve"
    if getattr(position, "user_id", None) == EVE_USER_ID or sig.get("eve_dossier_id"):
        return "eve"
    if getattr(position, "source", None) == "auto_watchlist":
        return "engine"
    return "manual"


def asset_class_of(symbol: str) -> str:
    from app.universe.catalog import get_instrument
    from app.universe.types import ProductType

    inst = get_instrument(symbol)
    if inst is None:
        return "crypto" if symbol.endswith("USDT") else "other"
    if getattr(inst, "product_type", None) == ProductType.FUTURE:
        return "future"
    value = str(getattr(inst.asset_class, "value", inst.asset_class)).lower()
    return value if value in ASSET_CLASS_LABEL else "other"


def _empty() -> dict[str, Any]:
    return {"trades": 0, "wins": 0, "losses": 0, "net": 0.0, "fees": 0.0, "open": 0,
            "sum_wins": 0.0, "sum_losses": 0.0}


def _finish(bucket: dict[str, Any]) -> dict[str, Any]:
    t, w, lo = bucket["trades"], bucket["wins"], bucket["losses"]
    bucket["win_rate"] = w / t if t else None
    bucket["avg_win"] = bucket["sum_wins"] / w if w else None
    bucket["avg_loss"] = bucket["sum_losses"] / lo if lo else None
    bucket["net"] = round(bucket["net"], 2)
    bucket["fees"] = round(bucket["fees"], 2)
    return bucket


def score(positions: Iterable[Any], key) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in positions:
        b = out.setdefault(key(p), _empty())
        if p.status == "OPEN":
            b["open"] += 1
            continue
        pnl = getattr(p, "realized_pnl", None)
        if p.status != "CLOSED" or pnl is None:
            continue
        pnl = float(pnl)
        b["trades"] += 1
        b["net"] += pnl
        b["fees"] += float(getattr(p, "entry_fee", 0.0) or 0.0) + float(getattr(p, "exit_fee", 0.0) or 0.0)
        if pnl > 0:
            b["wins"] += 1
            b["sum_wins"] += pnl
        else:
            b["losses"] += 1
            b["sum_losses"] += pnl
    return {k: _finish(v) for k, v in out.items()}


def drawdown(equities: Sequence[float], initial: float) -> dict[str, Any]:
    """Drawdown max et actuel depuis le plus haut (capital de départ compris), en fraction du plus haut."""
    peak = float(initial)
    max_dd = 0.0
    for e in equities:
        peak = max(peak, float(e))
        if peak > 0:
            max_dd = max(max_dd, (peak - float(e)) / peak)
    last = float(equities[-1]) if equities else float(initial)
    current = (peak - last) / peak if peak > 0 else 0.0
    return {"max_pct": max_dd, "current_pct": max(current, 0.0), "peak": peak, "last": last}


def build_breakdown(session: Session, portfolio: PaperPortfolio) -> dict[str, Any]:
    positions = session.execute(
        select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
    ).scalars().all()
    equities = session.execute(
        select(PaperEquitySnapshot.equity)
        .where(PaperEquitySnapshot.portfolio_id == portfolio.id)
        .order_by(PaperEquitySnapshot.timestamp.asc())
    ).scalars().all()
    by_decider = score(positions, decider_of)
    by_class = score(positions, lambda p: asset_class_of(p.symbol))
    profile = dict(portfolio.strategy_profile or {})
    return {
        "portfolio_code": portfolio.code,
        "by_decider": [
            {"decider": d, "label": DECIDER_LABEL[d], **by_decider.get(d, _finish(_empty()))} for d in DECIDERS
        ],
        "by_asset_class": [
            {"asset_class": c, "label": ASSET_CLASS_LABEL.get(c, c), **v}
            for c, v in sorted(by_class.items(), key=lambda kv: -kv[1]["trades"])
        ],
        "drawdown": drawdown([float(e) for e in equities if e is not None], float(portfolio.initial_cash)),
        "rules": {
            "initial_cash": float(portfolio.initial_cash),
            "risk_pct": profile.get("risk_pct"),
            "max_notional_pct": profile.get("max_notional_pct"),
            "max_open_positions": profile.get("max_open_positions"),
            "max_open_risk_pct": profile.get("max_open_risk_pct"),
            "daily_loss_limit_pct": profile.get("daily_loss_limit_pct"),
            "allow_short": profile.get("allow_short"),
            "short_symbols": profile.get("short_symbols"),
            "auto_timeframes": profile.get("auto_timeframes"),
            "take_profit_r": profile.get("take_profit_r"),
            "max_friction_bps": profile.get("max_friction_bps"),
            "min_quote_volume_24h": profile.get("min_quote_volume_24h"),
            "filters_mode": profile.get("filters_mode"),
            "decision_windows_mode": profile.get("decision_windows_mode"),
            "engines": profile.get("engines"),
            "arbitration": profile.get("arbitration"),
        },
        "universe": {
            "symbols": [
                {"symbol": s, "asset_class": asset_class_of(s),
                 "friction_bps": (profile.get("friction_bps_by_symbol") or {}).get(s)}
                for s in profile.get("universe_symbols") or []
            ],
            "exclusions": [
                {"symbol": s, "reason": why} for s, why in sorted((profile.get("universe_exclusions") or {}).items())
            ],
        },
    }
