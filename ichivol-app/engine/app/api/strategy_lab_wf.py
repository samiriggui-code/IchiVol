"""Strategy Lab walk-forward and optimize endpoints (T1g split of strategy_lab)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.optimization import (
    optimize_dict,
    run_optimize,
    run_walk_forward_opt,
    walk_forward_opt_dict,
)
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.walk_forward import run_walk_forward, walk_forward_dict

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

class WalkForwardBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "rolling"
    train_bars: int = 400
    test_bars: int = 100
    step_bars: int | None = None
    warmup_bars: int = 52
    include_train: bool = True
    persist: bool = False
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/walk-forward")
def post_strategy_lab_walk_forward(body: WalkForwardBody) -> dict:
    """Strategy Lab Phase 7 — walk-forward IS/OOS on a fixed ruleset (no optimizer)."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            mode=body.mode,
            train_bars=body.train_bars,
            test_bars=body.test_bars,
            step_bars=body.step_bars,
            warmup_bars=body.warmup_bars,
            include_train=body.include_train,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_dict(report)


@router.get("/strategy-lab/walk-forward")
def get_strategy_lab_walk_forward(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    include_train: bool = True,
    persist: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            mode=mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
            include_train=include_train,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_dict(report)


class OptimizeBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    objective: str = "expectancy"
    min_trades: int = 5
    warmup_bars: int = 52
    persist_best: bool = False
    grid: dict[str, list] | None = None
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/optimize")
def post_strategy_lab_optimize(body: OptimizeBody) -> dict:
    """Strategy Lab Phase 8 — single-window grid search (IS only; prefer WF-opt)."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_optimize(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            grid=body.grid,
            objective=body.objective,
            min_trades=body.min_trades,
            warmup_bars=body.warmup_bars,
            persist_best=body.persist_best,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return optimize_dict(report)


@router.get("/strategy-lab/optimize")
def get_strategy_lab_optimize(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    objective: str = "expectancy",
    min_trades: int = 5,
    warmup_bars: int = 52,
    persist_best: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_optimize(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            objective=objective,
            min_trades=min_trades,
            warmup_bars=warmup_bars,
            persist_best=persist_best,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return optimize_dict(report)


class WalkForwardOptBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "rolling"
    train_bars: int = 400
    test_bars: int = 100
    step_bars: int | None = None
    warmup_bars: int = 52
    objective: str = "expectancy"
    min_trades: int = 5
    persist: bool = False
    grid: dict[str, list] | None = None
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/walk-forward-opt")
def post_strategy_lab_walk_forward_opt(body: WalkForwardOptBody) -> dict:
    """Strategy Lab Phase 8 — optimize on IS per fold, measure on OOS."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward_opt(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            mode=body.mode,
            train_bars=body.train_bars,
            test_bars=body.test_bars,
            step_bars=body.step_bars,
            warmup_bars=body.warmup_bars,
            grid=body.grid,
            objective=body.objective,
            min_trades=body.min_trades,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_opt_dict(report)


@router.get("/strategy-lab/walk-forward-opt")
def get_strategy_lab_walk_forward_opt(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    objective: str = "expectancy",
    min_trades: int = 5,
    persist: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward_opt(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            mode=mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
            objective=objective,
            min_trades=min_trades,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_opt_dict(report)

