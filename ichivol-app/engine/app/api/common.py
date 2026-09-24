"""Shared helpers for engine API route modules (T1g — moved, not rewritten)."""

from __future__ import annotations

import time

from fastapi import HTTPException

from app.indicators.atr import AtrParams
from app.indicators.rvol import RvolParams
from app.structure.types import PriceZone, TrendlineSegment

def _rvol_params_override(
    low: float | None,
    significant: float | None,
    strong: float | None,
    anomaly: float | None,
) -> RvolParams:
    """CDC V1 "Seuils RVOL/ATR configurables Settings": only the anomaly
    buckets are exposed to the caller, never `primary_window`/
    `percentile_lookback` -- those are indicator internals, not a product
    threshold. `None` means "leave this one at its default"."""
    d = RvolParams()
    low = d.low_threshold if low is None else low
    significant = d.significant_threshold if significant is None else significant
    strong = d.strong_threshold if strong is None else strong
    anomaly = d.anomaly_threshold if anomaly is None else anomaly
    if not (0 <= low < significant < strong < anomaly):
        raise HTTPException(
            status_code=422,
            detail="invalid_rvol_thresholds: expected 0 <= rvol_low < rvol_significant < rvol_strong < rvol_anomaly",
        )
    return RvolParams(
        low_threshold=low,
        significant_threshold=significant,
        strong_threshold=strong,
        anomaly_threshold=anomaly,
    )


def _atr_params_override(
    dead_percentile: float | None,
    extreme_percentile: float | None,
    stop_multiplier: float | None,
) -> AtrParams:
    d = AtrParams()
    dead_percentile = d.dead_percentile if dead_percentile is None else dead_percentile
    extreme_percentile = d.extreme_percentile if extreme_percentile is None else extreme_percentile
    stop_multiplier = d.stop_multiplier if stop_multiplier is None else stop_multiplier
    if not (0 <= dead_percentile < extreme_percentile <= 1):
        raise HTTPException(
            status_code=422,
            detail="invalid_atr_percentiles: expected 0 <= atr_dead_percentile < atr_extreme_percentile <= 1",
        )
    if stop_multiplier <= 0:
        raise HTTPException(status_code=422, detail="invalid_atr_stop_multiplier: must be > 0")
    return AtrParams(
        dead_percentile=dead_percentile,
        extreme_percentile=extreme_percentile,
        stop_multiplier=stop_multiplier,
    )


def _zone_dict(z: PriceZone) -> dict:
    return {
        "side": z.side.value,
        "low": z.low,
        "high": z.high,
        "mid": z.mid,
        "score": z.score,
        "touch_count": z.touch_count,
        "sources": [s.value for s in z.sources],
        "atr_width": z.atr_width,
    }


def _line_dict(line: TrendlineSegment, series: list | None = None) -> dict:
    out = {
        "side": line.side.value,
        "slope": line.slope,
        "intercept": line.intercept,
        "start_bar": line.start_bar,
        "end_bar": line.end_bar,
        "touch_count": line.touch_count,
        "score": line.score,
        "source": line.source.value,
        "pivot_bars": list(line.pivot_bars),
    }
    # Bar indices are relative to the detector's windowed series; the chart
    # needs absolute time/price to draw the segment. `series` is that window.
    if series and 0 <= line.start_bar < len(series) and 0 <= line.end_bar < len(series):
        out["start_time"] = series[line.start_bar].time
        out["end_time"] = series[line.end_bar].time
        out["start_price"] = line.price_at(line.start_bar)
        out["end_price"] = line.price_at(line.end_bar)
    return out

from app.paper.costs import compute_costs
from app.paper.verdict import compute_progress

def _paper_position_dict(p, *, partial_exits: list | None = None) -> dict:
    out = {
        "id": p.id,
        "portfolio_id": p.portfolio_id,
        "symbol": p.symbol,
        "timeframe": p.timeframe,
        "source": p.source,
        "user_id": p.user_id,
        "direction": p.direction,
        "status": p.status,
        "entry_time": p.entry_time.isoformat(),
        "entry_price": p.entry_price,
        "entry_decision": p.entry_decision,
        "exit_time": p.exit_time.isoformat() if p.exit_time else None,
        "exit_price": p.exit_price,
        "exit_reason": p.exit_reason,
        "pnl_pct": p.pnl_pct,
        "qty": p.qty,
        "notional": p.notional,
        "stop_price": p.stop_price,
        "take_profit_price": p.take_profit_price,
        "risk_pct": p.risk_pct,
        "risk_amount": p.risk_amount,
        "entry_fee": getattr(p, "entry_fee", None),
        "exit_fee": getattr(p, "exit_fee", None),
        "realized_pnl": p.realized_pnl,
        "mfe_pct": p.mfe_pct,
        "mae_pct": p.mae_pct,
        "decision_id": getattr(p, "decision_id", None),
        "evidence_id": getattr(p, "evidence_id", None),
        "entry_signal": getattr(p, "entry_signal", None),
    }
    if partial_exits is not None:
        out["partial_exits"] = [
            {
                "seq": e.seq,
                "r_multiple": e.r_multiple,
                "fraction": e.fraction,
                "qty": e.qty,
                "price": e.price,
                "fee": e.fee,
                "realized_pnl": e.realized_pnl,
                "time_ms": e.time_ms,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in partial_exits
        ]
    return out


def _paper_perf_dict(perf) -> dict:
    return {
        "num_closed_trades": perf.num_closed_trades,
        "num_open_positions": perf.num_open_positions,
        "total_return": perf.total_return,
        "win_rate": perf.win_rate,
        "profit_factor": perf.profit_factor if perf.profit_factor != float("inf") else None,
        "expectancy": perf.expectancy,
        "avg_holding_hours": perf.avg_holding_hours,
        "best_trade_pct": perf.best_trade_pct,
        "worst_trade_pct": perf.worst_trade_pct,
        "initial_cash": getattr(perf, "initial_cash", None),
        "cash": getattr(perf, "cash", None),
        "equity": getattr(perf, "equity", None),
        "realized_pnl": getattr(perf, "realized_pnl", None),
        "unrealized_pnl": getattr(perf, "unrealized_pnl", None),
        "max_drawdown": getattr(perf, "max_drawdown", None),
        "expectancy_eur": getattr(perf, "expectancy_eur", None),
        "valuation_mode": getattr(perf, "valuation_mode", None),
    }


def _portfolio_dict(p) -> dict:
    from app.paper.kill_switch import lock_status

    out = {
        "id": p.id,
        "code": p.code,
        "label": p.label,
        "currency": p.currency,
        "valuation_mode": p.valuation_mode,
        "initial_cash": p.initial_cash,
        "cash": p.cash,
        "realized_pnl": p.realized_pnl,
        "is_active": p.is_active,
        "started_at": p.started_at.isoformat(),
        "strategy_profile": p.strategy_profile,
    }
    out.update(lock_status(p))
    return out


def _latest_marks() -> dict[str, tuple[float, float]]:
    """symbol -> (last screener price, computed_at epoch). Read-only cache peek.

    Prefer ``app.paper.marks.resolve_marks`` for valuation (cache + candle fallback).
    """
    from app.paper.marks import peek_screener_marks

    return peek_screener_marks()


