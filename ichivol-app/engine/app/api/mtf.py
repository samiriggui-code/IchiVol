"""API — MTF-1 matrice de tendance multi-horizons (lecture seule, observe-only).

GET /mtf/{symbol}?timeframe=1h&as_of=<unix>

Live (``as_of`` absent) : matrice + étapes du pipeline réel (même ``scan_symbol`` que Décisions, aucune
synchro paper) + phrase restituée + lecture « Portefeuille » du portefeuille de référence.
Historique (``as_of``) : matrice seule, relue à cet instant ; le pipeline historique n'est pas recalculé ici
(``pipeline_reason = historical_as_of_not_supported``, même convention que la FactSheet).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.market_data.resolve import ProviderNotWiredError
from app.mtf.matrix import HORIZON_SECONDS, describe, portfolio_reading

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

_DECISION_TFS = ("15m", "1h", "4h", "1d")


def _pipeline_dict(pipeline: Any) -> dict[str, Any]:
    return {
        "decision": pipeline.decision,
        "direction": getattr(pipeline.direction, "value", str(pipeline.direction)),
        "strategy_version": pipeline.strategy_version,
        "stages": [
            {"id": s.id.value, "status": s.status.value, "summary": s.summary, "codes": list(s.codes)}
            for s in pipeline.stages
        ],
    }


def _baseline_context(symbol: str, timeframe: str) -> dict[str, Any] | None:
    """Profil du portefeuille de référence + lot long automatique ouvert sur (symbole, timeframe)."""
    from sqlalchemy import select

    from app.db.models import PaperPortfolio, PaperPosition
    from app.db.session import SessionLocal
    from app.paper.portfolio import BASELINE_CODE

    session = SessionLocal()
    try:
        pf = session.execute(select(PaperPortfolio).where(PaperPortfolio.code == BASELINE_CODE)).scalar_one_or_none()
        if pf is None:
            return None
        open_long = session.execute(
            select(PaperPosition.id).where(
                PaperPosition.portfolio_id == pf.id,
                PaperPosition.symbol == symbol,
                PaperPosition.timeframe == timeframe,
                PaperPosition.source == "auto_watchlist",
                PaperPosition.direction == "LONG",
                PaperPosition.status == "OPEN",
            )
        ).first()
        return {"code": pf.code, "profile": dict(pf.strategy_profile or {}), "open_long_on_tf": open_long is not None}
    finally:
        session.close()


@router.get("/mtf/{symbol}")
def get_mtf(
    symbol: str,
    timeframe: str = Query("1h", description="Horizon de décision (15m, 1h, 4h, 1d)"),
    as_of: int | None = Query(default=None, description="Unix seconds — matrice relue à cet instant"),
) -> dict[str, Any]:
    if timeframe not in _DECISION_TFS:
        raise HTTPException(status_code=422, detail=f"timeframe must be one of {list(_DECISION_TFS)}")
    sym = symbol.upper()
    try:
        if as_of is not None:
            from app.mtf.service import matrix_as_of

            matrix = matrix_as_of(sym, timeframe, int(as_of))
            return {
                "symbol": sym,
                "timeframe": timeframe,
                "as_of": int(as_of),
                "matrix": matrix.to_dict(),
                "pipeline": None,
                "pipeline_reason": "historical_as_of_not_supported",
                "sentence": describe(matrix),
                "portfolio": None,
                "horizon_seconds": HORIZON_SECONDS,
                "observe_only": True,
            }

        from app.screener.service import scan_symbol

        row = scan_symbol(sym, timeframe=timeframe)
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if row.mtf_matrix is None:
        raise HTTPException(status_code=502, detail="mtf_matrix_unavailable")
    pipeline = _pipeline_dict(row.pipeline)
    portfolio = None
    try:
        ctx = _baseline_context(sym, timeframe)
        if ctx is not None:
            prof = ctx["profile"]
            portfolio = {
                "code": ctx["code"],
                "allow_short": bool(prof.get("allow_short", False)),
                "exit_mode": prof.get("exit_mode"),
                "auto_timeframes": list(prof.get("auto_timeframes") or ["1h"]),
                "open_long_on_tf": ctx["open_long_on_tf"],
                "reading": portfolio_reading(
                    pipeline, timeframe=timeframe, profile=prof, open_long_on_tf=ctx["open_long_on_tf"]
                ),
            }
    except Exception:
        logger.warning("mtf: baseline portfolio context unavailable", exc_info=True)
    return {
        "symbol": sym,
        "timeframe": timeframe,
        "as_of": None,
        "matrix": row.mtf_matrix.to_dict(),
        "pipeline": pipeline,
        "pipeline_reason": None,
        "signal_timing": row.signal_timing,
        "sentence": describe(row.mtf_matrix, pipeline),
        "portfolio": portfolio,
        "horizon_seconds": HORIZON_SECONDS,
        "observe_only": True,
    }
