"""Backtest, event-study, and shadow surfaces."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.api.common import _atr_params_override, _rvol_params_override
from app.api.serializers import backtest_dict, metrics_dict
from app.backtest import experiments
from app.backtest.evidence import compute_evidence_summary
from app.config import settings
from app.db.session import SessionLocal
from app.market_data import twelve_data
from app.paper.portfolio import ensure_portfolio, get_portfolio_by_code
from app.paper.strategy_profiles import ALL_PROFILES
from app.shadow.broker import list_shadows, shadow_stats, shadow_to_dict
from app.strategy_lab.event_study import event_study_dict, run_event_study

router_evidence = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])
router_symbol = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])
router_shadow = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router_evidence.get("/backtest/evidence")
def get_backtest_evidence() -> dict:
    """Rollup for the Overview "Preuve edge (C1)" tile -- how much automated
    backtest evidence has been collected (app/backtest/evidence.py's
    scheduled job) and how often PIPELINE's Sharpe beat plain Ichimoku in
    the most recent cycle. Purely descriptive, never a verdict: Option C
    stays a reviewed call, this just makes the raw material visible.
    Declared before `/backtest/{symbol}` so `evidence` is never parsed as a
    symbol path param."""
    session = SessionLocal()
    try:
        return compute_evidence_summary(session)
    finally:
        session.close()


@router_evidence.get("/event-study/{symbol}")
def get_event_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    variant: str = experiments.PIPELINE,
    horizons: str = "1,3,5,10",
    r_multiple: float = 1.0,
    include_events: bool = False,
) -> dict:
    """Strategy Lab Phase 1 — Event Study.

    For each entry signal of the named backtest variant, measure forward
    ATR-normalized returns at +N candles, MFE/MAE, and % hitting +R before -R.
    No capital, fees, or sizing. Complements `/backtest/{symbol}` (full
    simulator) without replacing it.
    """
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
    if r_multiple <= 0:
        raise HTTPException(status_code=422, detail="r_multiple must be > 0")
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        result = run_event_study(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            variant=variant,
            horizons=horizon_list,
            r_multiple=r_multiple,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return event_study_dict(result, include_events=include_events)


@router_symbol.get("/backtest/{symbol}")
def get_backtest(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Compares ICHIMOKU_ONLY / ICHIMOKU_RVOL / ICHIMOKU_RVOL_ENTRY_GATE /
    PIPELINE over the same historical window -- see
    app/backtest/experiments.py for what each variant actually does. Not
    persisted (unlike /decisions): a backtest run isn't a live decision, and
    re-running it is cheap and deterministic given the same historical
    data. RVOL/ATR threshold overrides let a Settings tweak be validated by
    backtest before it's trusted live."""
    twelve_data.set_api_key_override(x_twelve_data_key)
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        results = experiments.compare(
            symbol.upper(), timeframe=timeframe, limit=limit, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "experiments": {
            name: {
                "metrics": metrics_dict(exp.metrics),
                "backtest": backtest_dict(exp.backtest),
            }
            for name, exp in results.items()
        },
    }


@router_shadow.get("/shadow/stats")
def get_shadow_stats(portfolio_code: str | None = None) -> dict:
    """ShadowBroker counterfactual summary — hors cash."""
    session = SessionLocal()
    try:
        portfolio_id = None
        if portfolio_code:
            if portfolio_code in ALL_PROFILES:
                ensure_portfolio(session, portfolio_code)
                session.commit()
            p = get_portfolio_by_code(session, portfolio_code)
            if p is None:
                raise HTTPException(status_code=404, detail="portfolio_not_found")
            portfolio_id = p.id
        return shadow_stats(session, portfolio_id=portfolio_id)
    finally:
        session.close()


@router_shadow.get("/shadow/positions")
def get_shadow_positions(
    portfolio_code: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    session = SessionLocal()
    try:
        portfolio_id = None
        if portfolio_code:
            p = get_portfolio_by_code(session, portfolio_code)
            if p is None:
                raise HTTPException(status_code=404, detail="portfolio_not_found")
            portfolio_id = p.id
        rows = list_shadows(
            session,
            portfolio_id=portfolio_id,
            status=status,
            limit=min(limit, 200),
        )
        return {"positions": [shadow_to_dict(r) for r in rows]}
    finally:
        session.close()
