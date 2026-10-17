"""Ève Intelligence V1 — read-only API over the Dossier IchiVol (Postgres). Never calls JEV: only the paper loop
does, once per closed bar. Secrets never leave the engine (status shows whether a key is set, not the key)."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.config import settings
from app.db.models import EveDossier
from app.db.session import SessionLocal
from app.jev import client as jev_client
from app.jev import dossier as eve_dossier
from app.jev.questions import LABELS_FR
from app.paper.strategy_profiles import ALL_PROFILES, EVE_CODES

router = APIRouter(prefix=settings.engine_api_prefix, tags=["eve"])


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _summary(d: EveDossier) -> dict:
    return {
        "id": d.id,
        "created_at": _iso(d.created_at),
        "portfolio_code": d.portfolio_code,
        "symbol": d.symbol,
        "timeframe": d.timeframe,
        "bar_time": d.bar_time,
        "price": d.price,
        "holding": d.holding,
        "battery": d.battery,
        "engine_decision": d.engine_decision,
        "engine_action": d.engine_action,
        "eve_action": d.eve_action,
        "eve_label": d.eve_label,
        "decisive": d.decisive,
        "coherence": d.coherence,
        "p_up": d.p_up,
        "executed_action": d.executed_action,
        "decided_by": d.decided_by,
        "executed_result": d.executed_result,
        "position_id": d.position_id,
        "provider": d.provider,
        "model": d.model,
        "jev_ok": d.jev_ok,
        "jev_error": d.jev_error,
        "reused": d.reused,
        "reasons": d.reasons or [],
        "outcome_bars": d.outcome_bars,
        "outcome_return": d.outcome_return,
    }


@router.get("/eve/status")
def get_eve_status() -> dict:
    session = SessionLocal()
    try:
        last = session.execute(
            select(EveDossier).where(EveDossier.reused.is_(False)).order_by(EveDossier.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        total = int(session.execute(select(func.count(EveDossier.id))).scalar() or 0)
        used = eve_dossier.calls_today(session, "jev")
    finally:
        session.close()
    endpoints = [
        {"role": ep.name, "provider": ep.label, "host": urlparse(ep.url).netloc, "model": ep.model,
         "key_set": bool(ep.api_key)}
        for ep in jev_client.endpoints_from_env()
    ]
    return {
        "enabled": eve_dossier.enabled(),
        "execution": eve_dossier.execution_enabled(),
        "portfolios": [
            {"code": c, "label": ALL_PROFILES[c].get("label", c), "source": ALL_PROFILES[c].get("eve_source")}
            for c in EVE_CODES
        ],
        "endpoints": endpoints,
        "calls_today": used,
        "daily_cap": eve_dossier.daily_cap(),
        "dossiers_total": total,
        "last_call": _summary(last) if last else None,
        "outcome_bars": eve_dossier.OUTCOME_BARS,
        "now": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/eve/dossiers")
def list_eve_dossiers(
    portfolio: str | None = None,
    symbol: str | None = None,
    decided_by: str | None = Query(default=None, pattern="^(eve|eve_indecise|observation)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    session = SessionLocal()
    try:
        stmt = select(EveDossier).order_by(EveDossier.created_at.desc()).limit(limit)
        if portfolio:
            stmt = stmt.where(EveDossier.portfolio_code == portfolio)
        if symbol:
            stmt = stmt.where(EveDossier.symbol == symbol.upper())
        if decided_by:
            stmt = stmt.where(EveDossier.decided_by == decided_by)
        return {"results": [_summary(d) for d in session.execute(stmt).scalars()]}
    finally:
        session.close()


@router.get("/eve/dossiers/{dossier_id}")
def get_eve_dossier(dossier_id: str) -> dict:
    session = SessionLocal()
    try:
        d = session.get(EveDossier, dossier_id)
        if d is None:
            raise HTTPException(status_code=404, detail="dossier_not_found")
        src = d
        if d.reused:
            # The state and questions live on the dossier that made the JEV call.
            src = session.execute(
                select(EveDossier).where(EveDossier.call_key == d.call_key, EveDossier.reused.is_(False)).limit(1)
            ).scalar_one_or_none() or d
        body = _summary(d)
        body.update({
            "state": src.state,
            "state_chars": src.state_chars,
            "questions": d.questions,
            "answers": d.answers,
            "labels_fr": LABELS_FR,
            "usage": src.usage,
            "latency_ms": d.latency_ms,
            "jev_errors": d.jev_errors or [],
            "call_source_id": src.id if src is not d else None,
            "outcome_close": d.outcome_close,
            "outcome_at": _iso(d.outcome_at),
        })
        return body
    finally:
        session.close()


@router.get("/eve/calibration")
def get_eve_calibration(portfolio: str | None = None, days: int = Query(default=30, ge=1, le=365)) -> dict:
    session = SessionLocal()
    try:
        return eve_dossier.calibration(session, portfolio_code=portfolio, days=days)
    finally:
        session.close()
