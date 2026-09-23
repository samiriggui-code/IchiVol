"""Strategy Lab Research HTTP — T5b / T6 / T7 / Researcher (observation only).

Thin wrappers over confluence / auditor / monte_carlo / researcher.
Never alters live gates, scores, or Perf DB.
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.confluence.compare import compare_family_weight_profiles
from app.confluence.profiles import list_family_weight_profiles
from app.confluence.study import run_family_weights_study
from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch
from app.screener.service import scan_symbol
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


@router.get("/strategy-lab/family-weight-profiles")
def get_family_weight_profiles() -> dict:
    """T5b — named family-weight profile catalog (read-only)."""
    profiles = [
        {
            "id": p.id,
            "label": p.label,
            "description": p.description,
            "version": p.config.version,
            "weights": dict(p.config.weights),
        }
        for p in list_family_weight_profiles()
    ]
    return {
        "profiles": profiles,
        "disclaimer": (
            "Family weight profiles — observation / Lab only; "
            "not applied as live decision scores."
        ),
    }


@router.get("/strategy-lab/family-weights/compare")
def get_family_weights_compare(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
) -> dict:
    """T5b — compare all weight profiles on the live pipeline (observation)."""
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        row = scan_symbol(symbol.upper(), timeframe=timeframe, limit=limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = compare_family_weight_profiles(row.pipeline)
    payload["symbol"] = row.symbol
    payload["timeframe"] = row.timeframe
    payload["decision"] = row.decision.decision
    payload["confidence"] = row.decision.confidence
    return payload


@router.get("/strategy-lab/family-weights/study")
def get_family_weights_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 500,
    step: int = 1,
    sample_limit: int = 20,
) -> dict:
    """T5b — historical profile study on BUY/SELL pipeline bars (observation)."""
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    if step < 1:
        raise HTTPException(status_code=422, detail="step must be >= 1")
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol.upper(), timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report = run_family_weights_study(
        candles,
        symbol=symbol.upper(),
        timeframe=timeframe,
        step=step,
        sample_limit=sample_limit,
    )
    return report.to_dict()


def _resolve_ruleset(
    ruleset_id: str | None,
    ruleset: dict | None,
) -> tuple[Any, str | None]:
    if ruleset is not None:
        parsed = parse_ruleset(ruleset)
        rid = getattr(parsed, "id", None)
        return parsed, rid
    if ruleset_id:
        parsed = get_builtin_ruleset(str(ruleset_id))
        return parsed, str(ruleset_id)
    raise HTTPException(status_code=422, detail="provide ruleset_id or ruleset object")


class AuditReportBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 300
    trade_index: int = 0
    ruleset_id: str | None = None
    ruleset: dict | None = None


@router.post("/strategy-lab/audit-report")
def post_audit_report(body: AuditReportBody) -> dict:
    """T6 — post-outcome AuditReport for one ruleset trade (hypotheses proposed)."""
    from app.auditor import build_audit_report_from_trade

    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        ruleset, rid = _resolve_ruleset(body.ruleset_id, body.ruleset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        _prov, _sym, candles = resolve_and_fetch(
            body.symbol.upper(), body.timeframe, body.limit
        )
    except (ValueError, ProviderNotWiredError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol=body.symbol.upper(), timeframe=body.timeframe
    )
    if not result.details:
        raise HTTPException(
            status_code=422, detail="no_trades: ruleset produced zero trades"
        )
    if body.trade_index < 0 or body.trade_index >= len(result.details):
        raise HTTPException(
            status_code=422,
            detail=f"trade_index_out_of_range: {body.trade_index} (n={len(result.details)})",
        )
    report = build_audit_report_from_trade(
        result.details[body.trade_index],
        symbol=body.symbol.upper(),
        timeframe=body.timeframe,
        ruleset_id=rid,
        trade_index=body.trade_index,
    )
    payload = report.to_dict()
    payload["n_trades"] = len(result.details)
    return payload


class MonteCarloBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    n_paths: int = 1000
    seed: int = 42
    ruin_floor: float = 0.5
    min_trades: int = 20
    ruleset_id: str | None = None
    ruleset: dict | None = None


@router.post("/strategy-lab/monte-carlo")
def post_monte_carlo(body: MonteCarloBody) -> dict:
    """T7 — bootstrap Monte Carlo / risk-of-ruin (research only)."""
    from app.risk.monte_carlo import run_monte_carlo

    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    if body.n_paths < 1 or body.n_paths > 20_000:
        raise HTTPException(status_code=422, detail="n_paths must be between 1 and 20000")
    try:
        ruleset, rid = _resolve_ruleset(body.ruleset_id, body.ruleset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        _prov, _sym, candles = resolve_and_fetch(
            body.symbol.upper(), body.timeframe, body.limit
        )
    except (ValueError, ProviderNotWiredError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol=body.symbol.upper(), timeframe=body.timeframe
    )
    net_rets = [math.exp(d.trade.net_log_return) - 1.0 for d in result.details]
    report = run_monte_carlo(
        net_rets,
        n_paths=body.n_paths,
        seed=body.seed,
        ruin_floor=body.ruin_floor,
        min_trades=body.min_trades,
    )
    payload = report.to_dict()
    payload["symbol"] = body.symbol.upper()
    payload["timeframe"] = body.timeframe
    payload["ruleset_id"] = rid
    return payload


class ProposeExperimentPlanBody(BaseModel):
    audit_report: dict[str, Any]
    hypothesis_ids: list[str] | None = Field(default=None)


@router.post("/strategy-lab/propose-experiment-plan")
def post_propose_experiment_plan(body: ProposeExperimentPlanBody) -> dict:
    """Researcher — AuditReport → Lab steps (status=proposed; never auto-run)."""
    from app.researcher import propose_experiment_plan

    try:
        plan = propose_experiment_plan(
            body.audit_report,
            hypothesis_ids=body.hypothesis_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return plan.to_dict()
