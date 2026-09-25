"""Cycle / Spectral Engine HTTP surface — observe only, never a pipeline vote.

See docs/CYCLE_ENGINE_AUDIT.md. Same rule as /correlations: read-only lens.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.cycle.engine import CycleParams, compute_cycle_state
from app.market_data import twelve_data

router = APIRouter(prefix=settings.engine_api_prefix, tags=["cycle"])


@router.get("/cycle/{symbol}")
def get_cycle_state(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    window: int = 128,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Causal CycleState at the last closed bar (FFT + Hilbert + ACF).

    Observe-only — never wired into ``decision/pipeline.py``, never a
    BUY/SELL/LONG/SHORT field. Projections are not returned as certainties;
    ``quality`` / ``methods_agreement`` are agreement metrics, not win odds.
    """
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    if window < 32 or window > 512:
        raise HTTPException(status_code=422, detail="window must be in [32, 512]")
    if limit < window:
        raise HTTPException(status_code=422, detail="limit must be >= window")

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(
            symbol.upper(), timeframe, min(limit, 1000)
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    params = CycleParams(window=window)
    state = compute_cycle_state(candles, params)
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "window": window,
        "n_bars": len(candles),
        "cycle": state.to_dict(),
        "disclaimer": (
            "Observe-only CycleState. Not a trade signal. "
            "methods_agreement is period consensus, not probability of profit."
        ),
    }
