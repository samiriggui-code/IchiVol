"""T4a — POST /strategy-lab/backtest-overlay (ephemeral BACKTEST ChartObjects)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.chart_objects.from_backtest import (
    backtest_to_chart_objects,
    trade_outcome,
    trade_r_multiple_gross,
    trade_return_pct_gross,
    trade_return_pct_net,
)
from app.config import settings
from app.market_data import twelve_data
from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles
from app.strategy_lab.run_ruleset import _metrics_dict

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

OutcomeFilter = Literal["all", "win", "loss"]


class BacktestOverlayBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = Field(300, ge=50, le=5000)
    ruleset_id: str | None = None
    ruleset: dict[str, Any] | None = None
    outcome: OutcomeFilter = "all"


def _resolve_ruleset(body: BacktestOverlayBody) -> Ruleset:
    if body.ruleset is not None:
        try:
            return parse_ruleset(body.ruleset)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    rid = (body.ruleset_id or "").strip()
    if not rid:
        raise HTTPException(
            status_code=422,
            detail="ruleset_id or ruleset (DSL dict) is required",
        )
    try:
        return get_builtin_ruleset(rid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/strategy-lab/backtest-overlay")
def post_backtest_overlay(
    body: BacktestOverlayBody,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Run catalog/DSL ruleset backtest and return ephemeral BACKTEST ChartObjects.

    Filter ``outcome`` applies to ``objects`` and ``trades``; ``counts`` is
    always over the full trade set. No new backtest logic — wraps
    ``run_ruleset_backtest_on_candles``.
    """
    ruleset = _resolve_ruleset(body)
    symbol = body.symbol.strip().upper()
    timeframe = body.timeframe.strip() or "1h"
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol is required")

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        _provider, _psym, candles = resolve_and_fetch(symbol, timeframe, body.limit)
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = run_ruleset_backtest_on_candles(
        candles,
        ruleset,
        symbol=symbol,
        timeframe=timeframe,
    )

    trades_full: list[dict[str, Any]] = []
    for trade_id, detail in enumerate(result.details):
        ret_gross = trade_return_pct_gross(detail)
        ret_net = trade_return_pct_net(detail)
        outcome = trade_outcome(ret_net)
        entry_i = detail.entry_index
        exit_i = detail.exit_index
        trades_full.append(
            {
                "trade_id": trade_id,
                "direction": detail.trade.direction.value,
                "entry_time": int(candles[entry_i].time)
                if 0 <= entry_i < len(candles)
                else detail.trade.entry_time,
                "exit_time": int(candles[exit_i].time)
                if 0 <= exit_i < len(candles)
                else detail.trade.exit_time,
                "entry_price": detail.trade.entry_price,
                "exit_price": detail.trade.exit_price,
                "exit_reason": detail.exit_reason,
                "return_pct_gross": ret_gross,
                "return_pct_net": ret_net,
                "r_multiple_gross": trade_r_multiple_gross(detail),
                "outcome": outcome,
                "signal_index": detail.signal_index,
                "why_entered": list(detail.why_entered),
                "why_exited": list(detail.why_exited),
            }
        )

    rejected_full = [
        {
            "rejected_id": i,
            "signal_index": r.signal_index,
            "signal_time": int(candles[r.signal_index].time)
            if 0 <= r.signal_index < len(candles)
            else None,
            "direction": r.direction.value,
            "reason": r.reason,
            "why_entered": list(r.why_entered),
        }
        for i, r in enumerate(result.rejected)
    ]

    counts = {
        "total": len(trades_full),
        "win": sum(1 for t in trades_full if t["outcome"] == "win"),
        "loss": sum(1 for t in trades_full if t["outcome"] == "loss"),
        "flat": sum(1 for t in trades_full if t["outcome"] == "flat"),
    }

    filt = body.outcome
    if filt == "all":
        trades = trades_full
        allowed_ids = None
    else:
        trades = [t for t in trades_full if t["outcome"] == filt]
        allowed_ids = {t["trade_id"] for t in trades}

    objects = backtest_to_chart_objects(result, candles)
    if allowed_ids is not None:
        objects = [
            o
            for o in objects
            if o.origin.get("kind") == "rejected"
            or int(o.origin.get("trade_id", -1)) in allowed_ids
        ]

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "ruleset_id": ruleset.id,
        "outcome_filter": filt,
        "objects": [o.to_dict() for o in objects],
        "trades": trades,
        "rejected": rejected_full,
        "metrics": _metrics_dict(result.metrics),
        "counts": counts,
        "n_signals": result.n_signals,
        "n_skipped_in_position": result.n_skipped_in_position,
    }
