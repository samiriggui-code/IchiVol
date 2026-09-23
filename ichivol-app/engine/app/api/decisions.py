"""Decision surface: single-symbol and batch."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.common import _atr_params_override, _rvol_params_override
from app.api.serializers import detail_dict
from app.config import settings
from app.db.session import SessionLocal
from app.market_data import twelve_data
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router.get("/decisions/{symbol}")
def get_decision(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    persist: bool = True,
    include_candles: bool = False,
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    twelve_data.set_api_key_override(x_twelve_data_key)
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        row = scan_symbol(
            symbol.upper(), timeframe=timeframe, limit=limit, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if persist:
        session = SessionLocal()
        try:
            persist_scan(session, row)
        finally:
            session.close()

    payload = detail_dict(row)
    if include_candles:
        payload["candles"] = [
            {
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in row.candles
        ]
        payload["provider"] = row.exchange

    # Paper order intent (suggest before act) — never a live order.
    session = SessionLocal()
    try:
        from app.paper.intent import propose_order_intent

        payload["order_intent"] = propose_order_intent(session, row).to_dict()
    except Exception:
        payload["order_intent"] = None
    finally:
        session.close()
    return payload


_MAX_BATCH_ITEMS = 60
_BATCH_CONCURRENCY = 6


class BatchDecisionItem(BaseModel):
    symbol: str
    timeframe: str = "1h"


class BatchDecisionsRequest(BaseModel):
    items: list[BatchDecisionItem] = Field(default_factory=list)
    persist: bool = True


def _scan_for_batch(item: BatchDecisionItem, *, persist: bool) -> dict:
    symbol = item.symbol.upper()
    try:
        row = scan_symbol(symbol, timeframe=item.timeframe)
    except ValueError as exc:
        return {"symbol": symbol, "timeframe": item.timeframe, "ok": False, "error": str(exc)}

    if persist:
        session = SessionLocal()
        try:
            persist_scan(session, row)
        finally:
            session.close()

    return {"ok": True, **detail_dict(row)}


@router.post("/decisions/batch")
def get_decisions_batch(payload: BatchDecisionsRequest) -> dict:
    """Optional batch variant of `GET /decisions/{symbol}` (CDC V2 backlog,
    docs/HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md §3: "batch decisions
    optionnel") -- lets a caller that needs many symbols at once (the server
    Journal watch job, app/server/src/notifications/watch.ts, currently
    re-fetches its confirmed symbols one HTTP call at a time) fetch them
    concurrently in a single request instead of N sequential ones. Same
    response shape per item as the single-symbol endpoint's `detail_dict`
    (so `pipelineFingerprint()` on the server side needs no changes), plus
    `ok`/`error` so one bad symbol never fails the whole batch. Not a
    replacement for `/decisions/{symbol}` -- no RVOL/ATR threshold
    overrides, no `include_candles`, capped at `_MAX_BATCH_ITEMS` items so
    one request can't fan out into an unbounded number of upstream market
    data calls.
    """
    if not payload.items:
        return {"results": []}
    if len(payload.items) > _MAX_BATCH_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"batch_too_large: max {_MAX_BATCH_ITEMS} items per request",
        )

    results: list[dict | None] = [None] * len(payload.items)
    with ThreadPoolExecutor(max_workers=_BATCH_CONCURRENCY) as pool:
        futures = {
            pool.submit(_scan_for_batch, item, persist=payload.persist): index
            for index, item in enumerate(payload.items)
        }
        for future in as_completed(futures):
            index = futures[future]
            item = payload.items[index]
            try:
                results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 -- one symbol's failure must not sink the batch
                results[index] = {
                    "symbol": item.symbol.upper(),
                    "timeframe": item.timeframe,
                    "ok": False,
                    "error": str(exc),
                }

    return {"results": results}
