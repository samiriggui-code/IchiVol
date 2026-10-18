"""Ève Intelligence API — evaluate / dossiers / verdicts / calibration / V2 paper dry-run.

V1 routes never execute. V2 ``paper-submit`` evaluates Risk Kernel; opens only when
``EVE_PAPER_AUTONOMY`` is enabled (default off).
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from sqlalchemy import select

from app.db.models import PaperPosition, ShadowPosition
from app.db.session import SessionLocal
from app.eve.calibration import active_policy, calibration_report
from app.eve.context import build_engine_context
from app.eve.dossier import (
    decision_summary,
    trade_result,
    dossier_to_dict,
    get_dossier,
    get_verdict,
    list_dossiers,
    verdict_to_dict,
)
from app.eve.followup import followup_summary, list_tracked, run_followup, sync_outcomes
from app.eve.orchestrator import evaluate_opportunity
from app.eve.paper_submit import ALL_VIRTUAL, autonomy_enabled, submit_paper_from_dossier
from app.eve.primitive_study import run_primitive_routing_study
from app.eve.event_radar import analyze_symbol as event_radar_analyze
from app.eve.settings_schema import apply_patch, settings_bundle
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
    """Run Analyst→Challenger→Guardian→Shadow synthesis.

    When persist=true and ``paper_dry_run`` (default true), runs Risk Kernel on an
    existing paper portfolio. Opens/closes only when ``EVE_PAPER_AUTONOMY`` is on
    (local paper test). Never live brokers.
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


@router.get("/decisions")
def eve_decisions(limit: int = Query(default=200, ge=1, le=500)) -> dict:
    """Latest Ève judgements, light: engine proposals per book, Ève's answer, outcome (« Moteur vs Ève »)."""
    session = SessionLocal()
    try:
        rows = list_dossiers(session, limit=limit, max_limit=500)
        refs: dict[str, set[str]] = {"position_id": set(), "shadow_id": set()}
        for d in rows:
            dt = d.decision_time_json if isinstance(d.decision_time_json, dict) else {}
            for p in dt.get("engine_proposals") or []:
                for key, ids in refs.items():
                    if isinstance(p, dict) and isinstance(p.get(key), str):
                        ids.add(p[key])
        results: dict[str, dict] = {}
        for model, key in ((PaperPosition, "position_id"), (ShadowPosition, "shadow_id")):
            if refs[key]:
                for row in session.scalars(select(model).where(model.id.in_(refs[key]))):
                    results[row.id] = trade_result(row)
        return {
            "autonomy_enabled": autonomy_enabled(),
            "results": [
                decision_summary(d, get_verdict(session, d.verdict_id) if d.verdict_id else None, results=results)
                for d in rows
            ],
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


@router.get("/settings/schema")
def eve_settings_schema() -> dict:
    """QuantDinger-style schema with ``is_advanced`` for Settings Basic/Advanced."""
    bundle = settings_bundle()
    return {
        "schema_version": bundle["schema_version"],
        "schema": bundle["schema"],
        "advanced_keys": bundle["advanced_keys"],
        "writable_keys": bundle["writable_keys"],
        "note": bundle["note"],
    }


@router.get("/settings/values")
def eve_settings_values() -> dict:
    """Effective JEV / Radar knobs (secrets masked)."""
    bundle = settings_bundle()
    return {
        "schema_version": bundle["schema_version"],
        "values": bundle["values"],
        "writable_keys": bundle["writable_keys"],
    }


@router.patch("/settings/values")
def eve_settings_patch(body: dict = Body(default_factory=dict)) -> dict:
    """Persist writable knobs (timeouts, confidences, radar flags). Secrets rejected."""
    try:
        return apply_patch(body if isinstance(body, dict) else {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/event-radar/{symbol}")
def eve_event_radar(
    symbol: str,
    use_jev: bool = True,
) -> dict:
    """Instrument-scoped Event Radar (reference-only). Respects EVENT_RADAR_ENABLED."""
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid symbol")
    return event_radar_analyze(symbol, use_jev=use_jev)


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
        "note": "Ève trade sur tous les portefeuilles virtuels actifs; jamais live",
        "default_portfolio_code": ALL_VIRTUAL,
    }


@router.post("/dossiers/{dossier_id}/paper-submit")
def eve_paper_submit(
    dossier_id: str,
    portfolio_code: str | None = None,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
) -> dict:
    """Soumet LONG/SHORT/CLOSE via Risk Kernel.

    Sans ``portfolio_code`` (ou ``ALL``) → tous les portefeuilles virtuels.
    Un code précis → un seul livre. Autonomie off = dry-run.
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

