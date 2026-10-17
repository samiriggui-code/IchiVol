"""Ève's own paper accounts inside the paper loop, and the Dossier IchiVol that records every decision.

The engine computes and presents its calculations to Ève; Ève decides (open / close / hold / abstain); the paper
broker executes what the Risk Kernel and the kill switch allow (stop / target are checked first in
``sync_position``). When Ève cannot decide she abstains or keeps what she holds: the engine never takes her place.
One Ève account per judgment source (profile key ``eve_source``: ``jev`` hosted with jevos fallback, ``jevos``
local), compared with the baseline ("engine alone") on the same bars.

One Dossier per (portfolio, symbol, timeframe, closed bar): the 300 s loop sees the same closed bar several times
and reuses its Dossier instead of asking JEV again. Accounts with the same source and position state on a bar
reuse one JEV call (``call_key``).
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EveDossier, PaperPosition
from app.jev import client as jev_client
from app.jev.questions import BATTERY_VERSION, entry_battery, manage_battery
from app.jev.state import build_state, state_chars
from app.jev.verdict import decide_entry, decide_manage, engine_action, execute, pipeline_decision_for
from app.market_data.timeframes import TF_SECONDS

log = logging.getLogger(__name__)

SOURCES = ("jev", "jevos")
OUTCOME_BARS = 4  # the observed result is measured this many bars after the decided bar


def enabled() -> bool:
    return (os.getenv("EVE_ENABLED", "true") or "").strip().lower() not in ("0", "false", "no", "off")


def execution_enabled() -> bool:
    """V1 = dossiers only (EVE_EXECUTION=false); V2 = Ève's paper accounts execute her decisions (default)."""
    return (os.getenv("EVE_EXECUTION", "true") or "").strip().lower() not in ("0", "false", "no", "off")


def source_of(profile: dict[str, Any] | None) -> str | None:
    src = (profile or {}).get("eve_source")
    return src if src in SOURCES else None


def daily_cap() -> int:
    try:
        return max(0, int(os.getenv("JEV_DAILY_MAX_CALLS", "1000") or 1000))
    except ValueError:
        return 1000


def cycle_budget_s() -> float:
    try:
        return float(os.getenv("EVE_CYCLE_BUDGET_S", "200") or 200)
    except ValueError:
        return 200.0


def applies_to(profile: dict[str, Any] | None) -> bool:
    return enabled() and source_of(profile) is not None


def calls_today(session: Session, source: str = "jev") -> int:
    """JEV calls made today by one source (the cap protects the hosted credit; jevos is free)."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(EveDossier.id)).where(
        EveDossier.created_at >= start,
        EveDossier.reused.is_(False),
        func.coalesce(EveDossier.jev_error, "") != "daily_cap",
        EveDossier.call_key.like(f"{source}:%"),
    )
    return int(session.execute(stmt).scalar() or 0)


def _position_dict(pos: PaperPosition, price: float) -> dict[str, Any]:
    sign = 1.0 if pos.direction == "LONG" else -1.0
    unreal = (price - pos.entry_price) / pos.entry_price * sign if pos.entry_price else None
    return {
        "direction": pos.direction,
        "entry_price": pos.entry_price,
        "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
        "stop_price": pos.stop_price,
        "take_profit_price": pos.take_profit_price,
        "unrealized_return": round(unreal, 5) if unreal is not None else None,
    }


def _detail(row: Any) -> dict[str, Any]:
    from app.api.serializers import detail_dict

    try:
        return detail_dict(row)
    except Exception:  # never let a serializer edge case stop the paper loop
        log.exception("eve: detail_dict failed for %s %s", getattr(row, "symbol", "?"), getattr(row, "timeframe", "?"))
        return {"symbol": row.symbol, "timeframe": row.timeframe, "price": row.price,
                "pipeline": {"decision": getattr(row.pipeline, "decision", None)}}


@dataclass
class EveOutcome:
    decision: str  # pipeline decision to execute (BUY / SELL / NO_TRADE)
    close_reason: str | None  # exit reason when Ève closes a held position
    dossier: EveDossier
    execute: bool  # False in V1 (dossiers only): the account does not act on the signal


class CycleCalls:
    """Per-cycle memory: JEV calls already made (by call_key) and the time budget."""

    def __init__(self) -> None:
        self.calls: dict[str, EveDossier] = {}
        self.deadline = time.monotonic() + cycle_budget_s()
        self.used_today: dict[str, int] = {}


def run(
    session: Session,
    *,
    row: Any,
    portfolio_code: str,
    source: str,
    allow_short: bool,
    existing: PaperPosition | None,
    engine_decision: str,
    cycle: CycleCalls,
) -> EveOutcome | None:
    """Ève's decision for her account on the row's last closed bar.

    ``None`` means: do not act on the signal this cycle (no closed bar, or the cycle's JEV time budget is spent;
    the next cycle retries the same bar). Stop / target are still checked by the caller."""
    bar_close = (getattr(row, "signal_timing", None) or {}).get("signal_bar_close")
    if bar_close is None:
        return None
    bar_time = int(bar_close)
    holding = existing.direction if existing is not None else None

    prior = session.execute(
        select(EveDossier).where(
            EveDossier.portfolio_code == portfolio_code,
            EveDossier.symbol == row.symbol,
            EveDossier.timeframe == row.timeframe,
            EveDossier.bar_time == bar_time,
        )
    ).scalar_one_or_none()
    if prior is not None:
        # Same closed bar seen again by the 300 s loop: the decision is already taken.
        return EveOutcome(pipeline_decision_for(prior.executed_action, holding) or "NO_TRADE",
                          _close_reason(prior), prior, execute=prior.decided_by != "observation")

    battery = "manage" if holding else "entry"
    call_key = f"{source}:{row.symbol}:{row.timeframe}:{bar_time}:{holding or 'flat'}:{int(allow_short)}:{BATTERY_VERSION}"
    questions = manage_battery(direction=holding) if holding else entry_battery(allow_short=allow_short)

    shared = cycle.calls.get(call_key)
    if shared is None:
        shared = session.execute(
            select(EveDossier).where(EveDossier.call_key == call_key, EveDossier.reused.is_(False))
            .order_by(EveDossier.created_at).limit(1)
        ).scalar_one_or_none()

    d = EveDossier(
        portfolio_code=portfolio_code, symbol=row.symbol, timeframe=row.timeframe, bar_time=bar_time,
        price=row.price, holding=holding, battery=battery, battery_version=BATTERY_VERSION, call_key=call_key,
        questions=questions, engine_decision=engine_decision,
    )
    if shared is not None:
        d.reused = True
        for f in ("answers", "jev_ok", "jev_error", "jev_errors", "provider", "model", "latency_ms"):
            setattr(d, f, getattr(shared, f))
    else:
        if time.monotonic() > cycle.deadline:
            return None
        state = build_state(_detail(row), position=_position_dict(existing, row.price) if existing else None,
                            allow_short=allow_short, portfolio_code=portfolio_code)
        d.state, d.state_chars = state, state_chars(state)
        if source not in cycle.used_today:
            cycle.used_today[source] = calls_today(session, source)
        if source == "jev" and cycle.used_today[source] >= daily_cap():
            call = jev_client.JevCall(ok=False, error="daily_cap")
        else:
            call = jev_client.system_one(state, questions, endpoints=jev_client.endpoints_for(source))
            cycle.used_today[source] += 1
        d.reused = False
        d.answers, d.jev_ok, d.jev_error, d.jev_errors = call.answers, call.ok, call.error, call.errors
        d.provider, d.model, d.usage, d.latency_ms = call.provider, call.model, call.usage, call.latency_ms
        cycle.calls[call_key] = d

    answers = d.answers if d.jev_ok else None  # a partial / invalid answer is not a decision
    if holding:
        verdict = decide_manage(answers, holding=holding, engine_decision=engine_decision)
    else:
        verdict = decide_entry(answers, engine_decision=engine_decision)
    executed, by = execute(verdict, holding=holding)
    run_it = execution_enabled()
    if not run_it:
        executed, by = ("HOLD" if holding else "ABSTAIN"), "observation"
    d.eve_action, d.eve_label, d.decisive = verdict.action, verdict.label, verdict.decisive
    d.coherence, d.p_up, d.reasons = verdict.coherence, verdict.p_up, verdict.reasons
    d.engine_action = engine_action(engine_decision, holding)
    d.executed_action, d.decided_by = executed, by
    session.add(d)
    session.flush()
    return EveOutcome(pipeline_decision_for(executed, holding) or "NO_TRADE", _close_reason(d), d, execute=run_it)


def _close_reason(d: EveDossier) -> str | None:
    return "eve_close" if d.holding and d.executed_action == "CLOSE" else None


def record_execution(d: EveDossier, *, before: PaperPosition | None, result: PaperPosition | None) -> None:
    """What the paper broker actually did with the circuit's decision (Risk Kernel may have refused an open)."""
    if d.executed_result is not None and result is None:
        return  # later cycles on the same bar keep the first observed result
    if result is None:
        d.executed_result = "held" if before is not None else "none"
        return
    d.position_id = result.id
    if result.status == "OPEN":
        d.executed_result = "opened"
    else:
        d.executed_result = "closed_" + (result.exit_reason or "unknown")[:24]


def fill_outcomes(session: Session, bars_by_key: dict[str, Sequence], *, n_bars: int = OUTCOME_BARS) -> int:
    """Observed result: close-to-close return from the decided bar to ``n_bars`` later, from the loop's candles."""
    since = datetime.now(timezone.utc) - timedelta(days=14)
    pending = session.execute(
        select(EveDossier).where(EveDossier.outcome_return.is_(None), EveDossier.created_at >= since)
    ).scalars().all()
    filled = 0
    for d in pending:
        candles = bars_by_key.get(f"{d.symbol}:{d.timeframe}") or []
        if not candles:
            continue
        tf_s = TF_SECONDS.get(d.timeframe, 3600)
        by_open = {int(c.time): c for c in candles}
        start = by_open.get(d.bar_time - tf_s)
        end = by_open.get(d.bar_time + (n_bars - 1) * tf_s)
        if start is None or end is None or not start.close:
            continue
        d.outcome_bars = n_bars
        d.outcome_close = float(end.close)
        d.outcome_return = (float(end.close) - float(start.close)) / float(start.close)
        d.outcome_at = datetime.now(timezone.utc)
        filled += 1
    if filled:
        session.flush()
    return filled


# ---- calibration & comparison (buberlo/jev-trader idea: Brier, ECE, reliability; QuantDinger: per-decision audit)


def directional_return(action: str | None, holding: str | None, r: float | None) -> float | None:
    """Return earned over the outcome window by taking ``action`` (ignores fees; 0 when out of the market)."""
    if r is None or action is None or action == "UNAVAILABLE":
        return None
    if action == "LONG":
        return r
    if action == "SHORT":
        return -r
    if action == "HOLD" and holding:
        return r if holding == "LONG" else -r
    return 0.0


def _summary(values: list[float]) -> dict[str, Any]:
    n = len(values)
    if not n:
        return {"n": 0, "mean": None, "std": None, "total": None, "hit_rate": None, "in_market": 0}
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    active = [v for v in values if v != 0.0]
    return {
        "n": n,
        "mean": mean,
        "std": math.sqrt(var),  # variance of results, shown as standard deviation
        "total": sum(values),
        "hit_rate": (sum(1 for v in active if v > 0) / len(active)) if active else None,
        "in_market": len(active),
    }


def calibration(session: Session, *, portfolio_code: str | None = None, days: int = 30, bins: int = 10) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(EveDossier).where(EveDossier.created_at >= since, EveDossier.outcome_return.is_not(None))
    if portfolio_code:
        stmt = stmt.where(EveDossier.portfolio_code == portfolio_code)
    rows = session.execute(stmt).scalars().all()

    # Calibration of P(long) against the realised direction — one point per JEV call, not per portfolio.
    seen: set[str] = set()
    pts: list[tuple[float, int]] = []
    for d in rows:
        if d.p_up is None or d.reused or d.call_key in seen or d.outcome_return == 0:
            continue
        seen.add(d.call_key)
        pts.append((float(d.p_up), 1 if d.outcome_return > 0 else 0))
    brier = sum((p - y) ** 2 for p, y in pts) / len(pts) if pts else None
    base = sum(y for _, y in pts) / len(pts) if pts else None
    brier_ref = sum((base - y) ** 2 for _, y in pts) / len(pts) if pts else None  # always predicting the base rate
    rel = []
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        inside = [(p, y) for p, y in pts if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if not inside:
            continue
        mp = sum(p for p, _ in inside) / len(inside)
        fy = sum(y for _, y in inside) / len(inside)
        ece += len(inside) / len(pts) * abs(mp - fy)
        rel.append({"lo": lo, "hi": hi, "n": len(inside), "mean_p": mp, "freq_up": fy})

    eve_r, eng_r, exe_r = [], [], []
    agree = disagree = 0
    by_who: dict[str, int] = {"eve": 0, "eve_indecise": 0}
    for d in rows:
        e = directional_return(d.eve_action if d.decisive else None, d.holding, d.outcome_return)
        g = directional_return(d.engine_action, d.holding, d.outcome_return)
        x = directional_return(d.executed_action, d.holding, d.outcome_return)
        if e is not None:
            eve_r.append(e)
        if g is not None:
            eng_r.append(g)
        if x is not None:
            exe_r.append(x)
        by_who[d.decided_by] = by_who.get(d.decided_by, 0) + 1
        if d.decisive and d.eve_action != "UNAVAILABLE":
            if d.eve_action == d.engine_action:
                agree += 1
            else:
                disagree += 1
    return {
        "days": days,
        "portfolio_code": portfolio_code,
        "outcome_bars": OUTCOME_BARS,
        "dossiers": len(rows),
        "calibration": {"n": len(pts), "brier": brier, "brier_base_rate": brier_ref, "base_rate_up": base,
                        "ece": ece if pts else None, "reliability": rel},
        "comparison": {"eve_when_decisive": _summary(eve_r), "engine_alone": _summary(eng_r),
                       "circuit": _summary(exe_r)},
        "decided_by": by_who,
        "agreement": {"agree": agree, "disagree": disagree},
    }
