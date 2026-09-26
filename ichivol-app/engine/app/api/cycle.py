"""Cycle / Spectral Engine HTTP surface — observe only, never a pipeline vote.

See docs/CYCLE_ENGINE_AUDIT.md. Same rule as /correlations: read-only lens.
B4 — drop the still-forming bar via ``closed_candles`` (same as deep_history).
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import settings
from app.cycle.closed_fetch import filter_closed_candles
from app.cycle.engine import CycleParams, compute_cycle_state
from app.cycle.study import CycleStudyParams, run_cycle_regime_study, validate_cycle_synthetic
from app.market_data import twelve_data

router = APIRouter(prefix=settings.engine_api_prefix, tags=["cycle"])


def _fetch_closed_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    x_twelve_data_key: str | None,
    *,
    now: int | None,
):
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(
            symbol.upper(), timeframe, min(limit, 1000)
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        closed, now_s = filter_closed_candles(candles, timeframe, now=now)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return provider, provider_symbol, closed, now_s


@router.get("/cycle/{symbol}/study")
def get_cycle_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 500,
    window: int = 96,
    horizon: int = 8,
    now: int | None = Query(
        default=None,
        description="Unix seconds for closed-bar filter (tests). Default: server now.",
    ),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Regime-filter study with independent future ER + surrogate CYCLE rates."""
    if window < 32 or window > 512:
        raise HTTPException(status_code=422, detail="window must be in [32, 512]")
    if horizon < 1 or horizon > 64:
        raise HTTPException(status_code=422, detail="horizon must be in [1, 64]")
    if limit < window + horizon + 40:
        raise HTTPException(
            status_code=422,
            detail="limit too small for walk-forward (need window + horizon + warmup)",
        )

    provider, provider_symbol, candles, now_s = _fetch_closed_candles(
        symbol, timeframe, limit, x_twelve_data_key, now=now
    )
    study = run_cycle_regime_study(
        candles,
        CycleStudyParams(window=window, horizon=horizon),
    )
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "now": now_s,
        "n_closed_bars": len(candles),
        "study": study,
        "disclaimer": (
            "Research only (independent future ER + surrogates). Not a trade signal. "
            "Does not modify the decision pipeline."
        ),
    }


@router.get("/cycle/synthetic/validate")
def get_cycle_synthetic_validate(
    window: int = 128,
) -> dict:
    """(a) Synthetic truth probes — no market fetch. Observe-only."""
    if window < 64 or window > 256:
        raise HTTPException(status_code=422, detail="window must be in [64, 256]")
    return {
        "study": validate_cycle_synthetic(window=window),
        "disclaimer": "Synthetic validation only. promote_to_decision is never set here.",
    }


@router.get("/cycle/{symbol}")
def get_cycle_state(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    window: int = 128,
    now: int | None = Query(
        default=None,
        description="Unix seconds for closed-bar filter (tests). Default: server now.",
    ),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Causal CycleState at the last **closed** bar (FFT + Homodyne + ACF)."""
    if window < 32 or window > 512:
        raise HTTPException(status_code=422, detail="window must be in [32, 512]")
    if limit < window:
        raise HTTPException(status_code=422, detail="limit must be >= window")

    provider, provider_symbol, candles, now_s = _fetch_closed_candles(
        symbol, timeframe, limit, x_twelve_data_key, now=now
    )
    params = CycleParams(window=window, max_period=min(80.0, window / 3.0))
    state = compute_cycle_state(candles, params)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "window": window,
        "now": now_s,
        "n_bars": len(candles),
        "cycle": state.to_dict(),
        "disclaimer": (
            "Observe-only CycleState on closed candles. Not a trade signal. "
            "methods_agreement is period consensus, not probability of profit."
        ),
    }
