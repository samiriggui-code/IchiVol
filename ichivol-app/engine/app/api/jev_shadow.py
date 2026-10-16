"""API Ève Shadow (JEV/jevos) — observation uniquement.

Distinct from ShadowBroker paper counterfactuals under /paper/.../shadow.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from app.api.decisions import get_decision
from app.jev.adapter import health as jev_health
from app.jev.history import list_evaluations
from app.jev.providers import resolve_provider
from app.jev.shadow import compare_decision

router = APIRouter(prefix="/api/engine", tags=["jev-shadow"])


def _shadow_enabled() -> bool:
    return os.getenv("JEV_SHADOW_ENABLED", "false").lower() == "true"


@router.get("/jev-shadow/health")
def get_jev_shadow_health(provider: str | None = Query(default=None)) -> dict:
    """Provider readiness probe. Available even when Shadow evaluations are disabled."""
    try:
        cfg = resolve_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    probe = jev_health(provider=provider)
    return {
        "shadow_enabled": _shadow_enabled(),
        "configured_provider": cfg.name,
        "base_url": cfg.base_url,
        "score_maturity": cfg.score_maturity,
        "key_present": bool(cfg.api_key),
        "probe": probe,
    }


@router.get("/jev-shadow/history")
def get_shadow_history(limit: int = 50) -> dict:
    if not _shadow_enabled():
        raise HTTPException(status_code=503, detail="jev_shadow_disabled")
    return {"results": list_evaluations(limit)}


@router.get("/jev-shadow/{symbol}")
def evaluate_shadow(symbol: str, timeframe: str = "1h") -> dict:
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid symbol")
    if not _shadow_enabled():
        raise HTTPException(status_code=503, detail="jev_shadow_disabled")
    data = get_decision(symbol=symbol, timeframe=timeframe, persist=False)
    return compare_decision(data)
