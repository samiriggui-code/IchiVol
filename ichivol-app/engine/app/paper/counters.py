"""Structured rejection / funnel counters for the paper pipeline (observability only).

Two different things are counted, and their totals do NOT mix:

1. PIPELINE_FUNNEL (one event per screener cycle and timeframe, pipeline-level, portfolio independent):
   every scanned (symbol, timeframe) row is classified exactly once.
     * ``primary``   -- mutually exclusive: totals add up to ``rows``.
     * ``stage_fail`` -- MULTI-label: one row can fail several stages at once (location+regime...),
       so these counts overlap and must never be summed with each other or with ``primary``.
     * ``sole_blocker`` -- rows where exactly one stage fails: the only rows a relaxation of that
       stage alone could turn into a signal. This is the number to read before loosening a filter.
   Data quality is a separate dimension: ``bar_forming`` (the last candle is not closed -- always true
   for the historical live behaviour) and ``stale``.
   Stored as journal events attached to one portfolio row (the journal table requires a portfolio id);
   the payload states scope="pipeline_all_portfolios".
2. SIGNAL_REJECTED (per portfolio, only for actionable BUY/SELL signals): the FIRST failing entry
   check wins, so reasons are mutually exclusive per signal and sum to the number of rejected signals.
   The exit cause is already carried by the CLOSED journal event (``reason``).
Journaling is opt-in per profile (``log_rejections``) so deploying this code changes nothing for
portfolios that do not enable it.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import PaperJournalEvent, PaperPortfolio

FUNNEL_EVENT = "PIPELINE_FUNNEL"
REJECT_EVENT = "SIGNAL_REJECTED"

# first-failing-check wins; keep in sync with app/paper/gates.py
REJECT_REASONS = (
    "no_atr_stop", "position_already_open", "signal_already_processed", "max_positions", "open_risk_cap",
    "symbol_exposure_cap", "daily_loss_halt", "insufficient_cash_or_size", "order_not_executed",
)

SEMANTICS = {
    "primary": "mutually exclusive; sums to rows",
    "stage_fail": "multi-label; overlaps; do not sum",
    "sole_blocker": "rows failing exactly one stage; subset of the directional rows",
    "data_quality": "bar_forming / stale are separate counters, not part of primary",
}


def classify_row(pipeline: Any, *, bar_forming: bool, stale: bool) -> dict[str, Any]:
    """Pure classification of one scanned row from its PipelineResult."""
    stages = {getattr(s.id, "value", str(s.id)): getattr(s.status, "value", str(s.status)) for s in pipeline.stages}
    failed = [k for k, v in stages.items() if v == "fail"]
    decision = pipeline.decision
    direction = getattr(pipeline.direction, "value", str(pipeline.direction))
    if decision in ("BUY", "SELL"):
        primary = "signal"
    elif stages.get("regime") == "fail":
        primary = "regime"
    elif direction == "NEUTRAL":
        primary = "ichimoku_neutral"
    else:
        primary = next((n for n in ("structure", "participation", "location") if stages.get(n) == "fail"), "other")
    regime_code = None
    for s in pipeline.stages:
        if getattr(s.id, "value", None) == "regime" and getattr(s.status, "value", None) == "fail":
            regime_code = (s.codes or [None])[0]
    sole = failed[0] if len(failed) == 1 and direction != "NEUTRAL" and decision not in ("BUY", "SELL") else None
    return {
        "primary": primary, "failed": failed, "directional": direction != "NEUTRAL", "sole_blocker": sole,
        "regime_code": regime_code, "bar_forming": bar_forming, "stale": stale,
    }


class FunnelAccumulator:
    def __init__(self) -> None:
        self.rows = 0
        self.primary: Counter = Counter()
        self.stage_fail: Counter = Counter()
        self.sole_blocker: Counter = Counter()
        self.regime_code: Counter = Counter()
        self.directional = 0
        self.bar_forming = 0
        self.stale = 0

    def add(self, c: dict[str, Any]) -> None:
        self.rows += 1
        self.primary[c["primary"]] += 1
        self.directional += int(c["directional"])
        for st in c["failed"]:
            self.stage_fail[st] += 1
        if c["sole_blocker"]:
            self.sole_blocker[c["sole_blocker"]] += 1
        if c["regime_code"]:
            self.regime_code[c["regime_code"]] += 1
        self.bar_forming += int(c["bar_forming"])
        self.stale += int(c["stale"])

    def payload(self, timeframe: str) -> dict[str, Any]:
        return {
            "scope": "pipeline_all_portfolios", "timeframe": timeframe, "rows": self.rows,
            "directional_rows": self.directional, "primary": dict(self.primary),
            "stage_fail": dict(self.stage_fail), "sole_blocker": dict(self.sole_blocker),
            "regime_code": dict(self.regime_code), "bar_forming": self.bar_forming, "stale": self.stale,
            "semantics": SEMANTICS,
        }


def record_funnel(session: Session, portfolio: PaperPortfolio, acc: FunnelAccumulator, timeframe: str) -> None:
    session.add(PaperJournalEvent(
        portfolio_id=portfolio.id, position_id=None, event_type=FUNNEL_EVENT,
        payload=acc.payload(timeframe), created_at=datetime.now(timezone.utc),
    ))


def record_rejection(
    session: Session, portfolio: PaperPortfolio, *, symbol: str, timeframe: str, reason: str,
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(PaperJournalEvent(
        portfolio_id=portfolio.id, position_id=None, event_type=REJECT_EVENT,
        payload={"symbol": symbol, "timeframe": timeframe, "reason": reason, **(detail or {})},
        created_at=datetime.now(timezone.utc),
    ))
