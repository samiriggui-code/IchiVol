"""Ève Intelligence V1 API — evaluate / dossiers / verdicts / calibration.

No paper execution. No Risk Kernel submission from these routes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.session import SessionLocal
from app.eve.calibration import active_policy, propose_adjustment
from app.eve.context import build_engine_context
from app.eve.dossier import (
    dossier_to_dict,
    get_dossier,
    get_verdict,
    list_dossiers,
    verdict_to_dict,
)
from app.eve.orchestrator import evaluate_opportunity

router = APIRouter(prefix="/api/engine/eve", tags=["eve"])


@router.get("/context/{symbol}")
def eve_context(symbol: str, timeframe: str = "1h") -> dict:
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid symbol")
    return build_engine_context(symbol, timeframe)


@router.post("/evaluate/{symbol}")
def eve_evaluate(
    symbol: str,
    timeframe: str = "1h",
    persist: bool = True,
    use_jev: bool | None = None,
) -> dict:
    """Run Analyst→Challenger→Guardian→Shadow synthesis. Potential only."""
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid symbol")
    session = SessionLocal() if persist else None
    try:
        return evaluate_opportunity(
            symbol,
            timeframe,
            session=session,
            persist=persist and session is not None,
            use_jev=use_jev,
        )
    finally:
        if session is not None:
            session.close()


@router.get("/dossiers")
def eve_dossiers(
    limit: int = Query(default=20, ge=1, le=100),
    symbol: str | None = None,
) -> dict:
    session = SessionLocal()
    try:
        rows = list_dossiers(session, limit=limit, symbol=symbol)
        return {
            "results": [
                dossier_to_dict(d, get_verdict(session, d.verdict_id) if d.verdict_id else None)
                for d in rows
            ]
        }
    finally:
        session.close()


@router.get("/dossiers/{dossier_id}")
def eve_dossier_detail(dossier_id: str) -> dict:
    session = SessionLocal()
    try:
        d = get_dossier(session, dossier_id)
        if d is None:
            raise HTTPException(status_code=404, detail="dossier_not_found")
        v = get_verdict(session, d.verdict_id) if d.verdict_id else None
        return dossier_to_dict(d, v)
    finally:
        session.close()


@router.get("/verdicts/{verdict_id}")
def eve_verdict_detail(verdict_id: str) -> dict:
    session = SessionLocal()
    try:
        v = get_verdict(session, verdict_id)
        if v is None:
            raise HTTPException(status_code=404, detail="verdict_not_found")
        return verdict_to_dict(v)
    finally:
        session.close()


@router.get("/calibration")
def eve_calibration() -> dict:
    policy = active_policy()
    return {
        "policy": policy,
        "note": "Calibration adjusts thresholds/weights — not LLM fine-tuning",
        "proposal_example": propose_adjustment(
            policy=policy,
            observed={"abstain_rate": 0.0, "mean_coherence": 0.5, "n": 0},
        ),
    }
