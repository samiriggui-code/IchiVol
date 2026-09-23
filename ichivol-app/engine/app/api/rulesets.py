"""Ruleset catalog and event-study endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.perf_db import persist_study_result
from app.strategy_lab.ruleset import CONDITION_SCHEMA, parse_ruleset
from app.strategy_lab.run_ruleset import ruleset_study_dict, run_ruleset_event_study

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router.get("/rulesets")
def get_rulesets() -> dict:
    """Strategy Lab Phase 2 — list built-in declarative rulesets + condition schema."""
    return {
        "rulesets": [r.to_dict() for r in list_builtin_rulesets()],
        "condition_keys": sorted(CONDITION_SCHEMA.keys()),
    }


class RulesetStudyBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    horizons: str = "1,3,5,10"
    include_events: bool = False
    with_backtest: bool = True
    persist: bool = False
    """If true, save results to strategy_lab_experiments (Performance DB)."""
    ruleset_id: str | None = None
    """Built-in id; ignored if `ruleset` body is provided."""
    ruleset: dict | None = None
    """Inline ruleset JSON (takes precedence over ruleset_id)."""


@router.post("/ruleset/event-study")
def post_ruleset_event_study(body: RulesetStudyBody) -> dict:
    """Strategy Lab Phase 2 — evaluate a ruleset then run Event Study on rising-edge hits."""
    try:
        horizon_list = tuple(
            int(x.strip()) for x in body.horizons.split(",") if x.strip()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if not horizon_list or any(h < 1 for h in horizon_list):
        raise HTTPException(status_code=422, detail="horizons must be positive integers")
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        if body.ruleset is not None:
            ruleset = parse_ruleset(body.ruleset)
        elif body.ruleset_id:
            ruleset = get_builtin_ruleset(body.ruleset_id)
        else:
            raise HTTPException(
                status_code=422, detail="provide ruleset_id or ruleset object"
            )
        result = run_ruleset_event_study(
            ruleset,
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            horizons=horizon_list,
            with_backtest=body.with_backtest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = ruleset_study_dict(result, include_events=body.include_events)
    if body.persist:
        try:
            saved = persist_study_result(
                result,
                parameters={
                    "limit": body.limit,
                    "horizons": list(horizon_list),
                    "with_backtest": body.with_backtest,
                },
            )
            payload["experiment"] = saved
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"persist_failed: {exc}") from exc
    return payload


@router.get("/ruleset/{ruleset_id}/event-study")
def get_ruleset_event_study(
    ruleset_id: str,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    horizons: str = "1,3,5,10",
    include_events: bool = False,
    with_backtest: bool = True,
    persist: bool = False,
) -> dict:
    """Run a built-in ruleset Event Study (+ ATR backtest by default)."""
    try:
        horizon_list = tuple(
            int(x.strip()) for x in horizons.split(",") if x.strip()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if not horizon_list or any(h < 1 for h in horizon_list):
        raise HTTPException(status_code=422, detail="horizons must be positive integers")
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        ruleset = get_builtin_ruleset(ruleset_id)
        result = run_ruleset_event_study(
            ruleset,
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            horizons=horizon_list,
            with_backtest=with_backtest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = ruleset_study_dict(result, include_events=include_events)
    if persist:
        try:
            saved = persist_study_result(
                result,
                parameters={
                    "limit": limit,
                    "horizons": list(horizon_list),
                    "with_backtest": with_backtest,
                },
            )
            payload["experiment"] = saved
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"persist_failed: {exc}") from exc
    return payload
