"""Strategy Lab experiments, ablation, regime slices, walk-forward, optimize."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db.session import SessionLocal
from app.strategy_lab.ablation import ablation_dict, run_ablation
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.perf_db import (
    compare_rulesets,
    experiment_dict,
    experiments_dicts,
    get_experiment,
    lineage_count_for,
    list_experiments,
)
from app.strategy_lab.regime_slices import regime_slices_dict, run_regime_slices
from app.strategy_lab.ruleset import parse_ruleset

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router.get("/strategy-lab/experiments")
def get_strategy_lab_experiments(
    symbol: str | None = None,
    timeframe: str | None = None,
    ruleset_id: str | None = None,
    market_regime: str | None = None,
    hypothesis_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Performance DB — list persisted Strategy Lab experiments."""
    session = SessionLocal()
    try:
        rows = list_experiments(
            session,
            symbol=symbol,
            timeframe=timeframe,
            ruleset_id=ruleset_id,
            market_regime=market_regime,
            hypothesis_id=hypothesis_id,
            limit=limit,
            offset=offset,
        )
        return {
            "experiments": experiments_dicts(session, rows),
            "count": len(rows),
        }
    finally:
        session.close()


@router.get("/strategy-lab/experiments/{experiment_id}")
def get_strategy_lab_experiment(experiment_id: str) -> dict:
    session = SessionLocal()
    try:
        row = get_experiment(session, experiment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="experiment_not_found")
        return experiment_dict(row, lineage_count=lineage_count_for(session, row))
    finally:
        session.close()


@router.get("/strategy-lab/compare")
def get_strategy_lab_compare(
    symbol: str,
    timeframe: str = "1h",
    ruleset_ids: str = "",
    market_regime: str = "GLOBAL",
) -> dict:
    """Latest saved run per ruleset_id for symbol/timeframe (ablation helper)."""
    ids = [x.strip() for x in ruleset_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(status_code=422, detail="ruleset_ids required (comma-separated)")
    session = SessionLocal()
    try:
        rows = compare_rulesets(
            session,
            symbol=symbol.upper(),
            timeframe=timeframe,
            ruleset_ids=ids,
            market_regime=market_regime,
        )
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "market_regime": market_regime,
            "experiments": experiments_dicts(session, rows),
        }
    finally:
        session.close()


class AblationBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "cumulative"
    """cumulative | leave_one_out"""
    direction: str = "LONG"
    stop_atr: float = 1.0
    target_atr: float = 2.0
    persist: bool = False
    layers: list[dict] | None = None
    """Optional [{label, conditions}] — default A→E ladder if omitted (cumulative)."""


@router.post("/strategy-lab/ablation")
def post_strategy_lab_ablation(body: AblationBody) -> dict:
    """Strategy Lab Phase 5 — run ablation matrix on one shared OHLCV window."""
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    if body.stop_atr <= 0 or body.target_atr <= 0:
        raise HTTPException(status_code=422, detail="stop_atr/target_atr must be > 0")
    try:
        result = run_ablation(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            mode=body.mode,
            layers=body.layers,
            direction=body.direction,
            stop_atr=body.stop_atr,
            target_atr=body.target_atr,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ablation_dict(result)


@router.get("/strategy-lab/ablation")
def get_strategy_lab_ablation(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "cumulative",
    direction: str = "LONG",
    persist: bool = False,
) -> dict:
    """Convenience GET — default A→E cumulative ladder (Ichimoku→RVOL→BOS→ATR→CMF)."""
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        result = run_ablation(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            mode=mode,
            direction=direction,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ablation_dict(result)


class RegimeSlicesBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    persist: bool = False
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/regime-slices")
def post_strategy_lab_regime_slices(body: RegimeSlicesBody) -> dict:
    """Strategy Lab Phase 6 — segment ruleset performance by market regime."""
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        report = run_regime_slices(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return regime_slices_dict(report)


@router.get("/strategy-lab/regime-slices")
def get_strategy_lab_regime_slices(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
    persist: bool = False,
) -> dict:
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        report = run_regime_slices(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return regime_slices_dict(report)


