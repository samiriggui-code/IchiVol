"""Ève Intelligence API — evaluate / dossiers / verdicts / calibration / V2 paper dry-run.

V1 routes never execute. V2 ``paper-submit`` evaluates Risk Kernel; opens only when
``EVE_PAPER_AUTONOMY`` is enabled (default off).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.session import SessionLocal
from app.eve.calibration import active_policy, calibration_report
from app.eve.context import build_engine_context
from app.eve.dossier import (
    dossier_to_dict,
    get_dossier,
    get_verdict,
    list_dossiers,
    verdict_to_dict,
)
from app.eve.orchestrator import evaluate_opportunity
from app.eve.followup import followup_summary, list_tracked, run_followup, sync_outcomes
from app.eve.paper_submit import autonomy_enabled, submit_paper_from_dossier
from app.eve.primitive_study import run_primitive_routing_study
from app.paper.strategy_profiles import BASELINE_CODE

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
    paper_dry_run: bool = True,
) -> dict:
    """Run Analyst→Challenger→Guardian→Shadow synthesis. Potential only.

    When persist=true, optionally dry-runs Risk Kernel (``paper_dry_run``, default
    true). Never opens unless ``EVE_PAPER_AUTONOMY`` is enabled *and* a separate
    paper-submit with execute is used.
    """
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
            paper_dry_run=paper_dry_run,
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
def eve_calibration(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    """Active policy + observation-backed proposal (never auto-applied)."""
    session = SessionLocal()
    try:
        report = calibration_report(session, limit=limit)
        return {
            "policy": active_policy(),
            "observed": report["observed"],
            "proposal": report["proposal"],
            "note": "Calibration adjusts thresholds/weights — not LLM fine-tuning",
            "applied": False,
        }
    finally:
        session.close()


@router.get("/primitive-study")
def eve_primitive_study() -> dict:
    """Matrice Mode × NOUL/CHOICE/SCORE — base du routage JEV (étude déterministe)."""
    return run_primitive_routing_study()


@router.get("/paper-autonomy")
def eve_paper_autonomy() -> dict:
    """V2 flag — when false, paper-submit is Risk Kernel dry-run only."""
    return {
        "autonomy_enabled": autonomy_enabled(),
        "env": "EVE_PAPER_AUTONOMY",
        "default": False,
        "note": "No Eve portfolio; existing paper books only; never live trading",
    }


@router.post("/dossiers/{dossier_id}/paper-submit")
def eve_paper_submit(
    dossier_id: str,
    portfolio_code: str = BASELINE_CODE,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
) -> dict:
    """V2: submit potential LONG/SHORT via Risk Kernel (default dry-run).

    ``execute`` defaults to the autonomy flag. Passing ``execute=true`` while
    autonomy is off is ignored unless autonomy is on — callers must enable
    ``EVE_PAPER_AUTONOMY`` to open paper lots.
    """
    session = SessionLocal()
    try:
        # Hard gate: never honor execute=true when autonomy is off.
        do_exec = None if execute is None else (bool(execute) and autonomy_enabled())
        if execute is True and not autonomy_enabled():
            do_exec = False
        out = submit_paper_from_dossier(
            session,
            dossier_id,
            portfolio_code=portfolio_code,
            price=price,
            stop_distance=stop_distance,
            execute=do_exec if execute is not None else None,
        )
        if out.get("error") == "dossier_not_found":
            raise HTTPException(status_code=404, detail="dossier_not_found")
        if out.get("error") == "unknown_portfolio":
            raise HTTPException(status_code=404, detail=f"unknown_portfolio: {portfolio_code}")
        session.commit()
        return out
    finally:
        session.close()


@router.get("/followup")
def eve_followup_list(
    portfolio_code: str = BASELINE_CODE,
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    """Phase J — positions Eve trackées + dossiers en surveillance."""
    session = SessionLocal()
    try:
        return list_tracked(session, portfolio_code=portfolio_code, limit=limit)
    finally:
        session.close()


@router.get("/dossiers/{dossier_id}/followup")
def eve_followup_get(dossier_id: str) -> dict:
    """Phase J — résumé suivi / outcome (decision_time immuable)."""
    session = SessionLocal()
    try:
        out = followup_summary(session, dossier_id)
        if out.get("error") == "dossier_not_found":
            raise HTTPException(status_code=404, detail="dossier_not_found")
        return out
    finally:
        session.close()


@router.post("/dossiers/{dossier_id}/followup")
def eve_followup_run(
    dossier_id: str,
    apply: bool = False,
    use_jev: bool = False,
    use_shadow: bool = True,
) -> dict:
    """Phase J/K — proposer HOLD/CLOSE/ABSTAIN (+ Shadow audit).

    ``apply=true`` attempts CLOSE via paper_submit; autonomy off → dry-run only.
    ``use_shadow`` (default true) runs Ève Shadow independent review (≠ ShadowBroker).
    """
    session = SessionLocal()
    try:
        out = run_followup(
            session,
            dossier_id,
            apply=bool(apply),
            use_jev=use_jev,
            use_shadow=use_shadow,
        )
        if out.get("error") == "dossier_not_found":
            raise HTTPException(status_code=404, detail="dossier_not_found")
        session.commit()
        return out
    finally:
        session.close()


@router.post("/outcomes/sync")
def eve_outcomes_sync(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    """Phase J — enregistre les outcomes des positions CLOSED liées aux dossiers."""
    session = SessionLocal()
    try:
        out = sync_outcomes(session, limit=limit)
        session.commit()
        return out
    finally:
        session.close()

