"""Response-shape helpers shared by the HTTP routes (app/api/routes.py) and
the agent command channel (app/agent_channel/) -- extracted here so both can
build byte-identical payloads from the same `ScreenerRow`/`Metrics`/
`BacktestResult` without either module importing the other (routes.py used
to own these; agent_channel needing the exact same shapes is what moved them
here, not a redesign)."""

from __future__ import annotations

import math

from app.backtest.engine import BacktestResult
from app.backtest.metrics import Metrics
from app.evidence.engine import evidence_report_dict
from app.screener.service import ScreenerRow


def pipeline_dict(row: ScreenerRow) -> dict:
    # Native staged pipeline (docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md),
    # additive: `decision`/`confidence`/etc. still come from the legacy
    # combiner unchanged wherever they appear. Shape matches
    # ichivol-app/src/lib/decisionPipeline.ts::NativePipelinePayload exactly,
    # so the frontend can consume this natively without a contract change on
    # its side. Included in both the screener summary and the decision
    # detail (docs/CAHIER-DES-CHARGES.md §5.1, CDC-VIZ-001's "API screener
    # enrichie (status par stage)" dependency) -- the matrix view needs
    # per-stage status for every scanned symbol, not just the one a sheet is
    # open on.
    return {
        "decision": row.pipeline.decision,
        "direction": row.pipeline.direction.value,
        "strategy_version": row.pipeline.strategy_version,
        "stages": [
            {"id": s.id.value, "status": s.status.value, "summary": s.summary, "codes": s.codes}
            for s in row.pipeline.stages
        ],
    }


def risk_dict(row: ScreenerRow) -> dict | None:
    # Machine-readable counterpart to the Régime stage's French summary text
    # (docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md §14): `price` (already at top
    # level) + `suggested_stop_distance` is the minimum a caller needs to
    # act on a decision -- paper trading today, any future broker adapter
    # later -- without parsing prose. Still never a position-sizing verdict
    # (no Kelly, no risk caps here -- docs/TRADING_ARCHITECTURE_V2.md).
    if row.atr is None:
        return None
    return {
        "atr": row.atr.atr,
        "regime": row.atr.regime.value,
        "suggested_stop_distance": row.atr.suggested_stop_distance,
    }


def summary_dict(row: ScreenerRow) -> dict:
    from app.events.anomaly import anomaly_observation_dict

    body = {
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "price": row.price,
        "decision": row.decision.decision,
        "direction": row.decision.direction.value,
        "confidence": row.decision.confidence,
        "probability": row.decision.probability,
        "ichimoku_score": row.ichimoku.metadata.get("score"),
        "rvol": row.rvol.metadata.get("rvol"),
        "pipeline": pipeline_dict(row),
        "risk": risk_dict(row),
    }
    # Additive observation — never alters decision/confidence.
    anomaly = anomaly_observation_dict(getattr(row, "market_anomaly", None))
    if anomaly is not None:
        body["market_anomaly"] = {
            "event_suspected": anomaly["event_suspected"],
            "event_type": anomaly["event_type"],
            "market_regime": anomaly["market_regime"],
            "confidence": anomaly["confidence"],
            "feature_version": anomaly["feature_version"],
        }
    return body


def detail_dict(row: ScreenerRow) -> dict:
    from app.events.anomaly import anomaly_observation_dict

    body = {
        **summary_dict(row),
        "reasons": row.decision.reasons,
        "risks": row.decision.risks,
        "invalidation": row.decision.invalidation,
        "positive_evidence": row.decision.positive_evidence,
        "contradictions": row.decision.contradictions,
        "why_not": row.decision.why_not,
        "agreement": row.decision.agreement,
        "weights_used": row.decision.weights_used,
        "strategy_version": row.decision.strategy_version,
        "timestamp": row.candles[-1].time,
        "signal_timing": getattr(row, "signal_timing", None),
        "volume_type": (
            row.candles[-1].volume_type.value if row.candles else "NONE"
        ),
        "ichimoku": {
            "direction": row.ichimoku.direction.value,
            "confidence": row.ichimoku.confidence,
            "probability": row.ichimoku.probability,
            "reasons": row.ichimoku.reasons,
            "metadata": row.ichimoku.metadata,
        },
        "rvol_detail": {
            "confidence": row.rvol.confidence,
            "reasons": row.rvol.reasons,
            "metadata": row.rvol.metadata,
            "volume_type": (
                row.candles[-1].volume_type.value if row.candles else "NONE"
            ),
        },
    }
    full_anomaly = anomaly_observation_dict(getattr(row, "market_anomaly", None))
    if full_anomaly is not None:
        body["market_anomaly"] = full_anomaly
    from app.events.correlate import event_context_dict

    ec = event_context_dict(getattr(row, "event_context", None))
    if ec is not None:
        # Detail: matches + disclaimer; anomaly already in market_anomaly.
        body["event_context"] = {
            "market_regime": ec["market_regime"],
            "matches": ec["matches"],
            "disclaimer": ec["disclaimer"],
        }
    if row.context is not None:
        body["context"] = row.context.to_dict()
    if row.evidence is not None:
        # Prefer Evidence Engine explanations when richer than combiner MVP.
        ev = evidence_report_dict(row.evidence)
        body["evidence"] = ev
        if ev.get("positive_evidence"):
            body["positive_evidence"] = ev["positive_evidence"]
        if ev.get("contradictions"):
            body["contradictions"] = ev["contradictions"]
        if row.pipeline.direction.value == "LONG" and ev.get("why_not_long"):
            body["why_not"] = ev["why_not_long"]
        elif row.pipeline.direction.value == "SHORT" and ev.get("why_not_short"):
            body["why_not"] = ev["why_not_short"]
        elif ev.get("why_not_long") or ev.get("why_not_short"):
            body["why_not"] = list(
                dict.fromkeys([*(ev.get("why_not_long") or []), *(ev.get("why_not_short") or [])])
            )
        if ev.get("invalidation"):
            body["invalidation"] = list(
                dict.fromkeys([*row.decision.invalidation, *ev["invalidation"]])
            )
    return body


def metrics_dict(m: Metrics, *, metrics_basis: str = "net_v1") -> dict:
    return {
        "n_bars": m.n_bars,
        "total_return": m.total_return,
        "cagr": m.cagr,
        "sharpe": m.sharpe,
        "sortino": m.sortino,
        "max_drawdown": m.max_drawdown,
        "num_trades": m.num_trades,
        "win_rate": m.win_rate,
        "profit_factor": m.profit_factor if m.profit_factor != float("inf") else None,
        "expectancy": m.expectancy,
        "exposure": m.exposure,
        "win_rate_gross": m.win_rate_gross,
        "profit_factor_gross": (
            m.profit_factor_gross if m.profit_factor_gross != float("inf") else None
        ),
        "expectancy_gross": m.expectancy_gross,
        "metrics_basis": metrics_basis,
    }


def backtest_dict(result: BacktestResult) -> dict:
    return {
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "n_bars": result.n_bars,
        "commission_bps": result.commission_bps,
        "slippage_bps": result.slippage_bps,
        "eod_return": result.eod_return,
        "trades": [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "direction": t.direction.value,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_pct": math.exp(t.log_return) - 1,
                "pnl_pct_net": math.exp(t.net_log_return) - 1,
                "cost_log": t.cost_log,
            }
            for t in result.trades
        ],
    }
