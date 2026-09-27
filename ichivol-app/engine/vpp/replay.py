"""C3 — replay the simulator's decisions through the REAL paper engine (amendement VP0-2026-09-28 Q.3).

Dev Postgres only, on a disposable portfolio that is deleted afterwards. At each bar open t, symbols are visited in
the simulator's random order (same seed): ``engine.sync_position`` gets the bar t−1 decision at price open(t) —
stop/target check at that price, then the direction exit, else the Risk Kernel + sizing + open. Then the
protections of bar t go through ``resolve_bar_exit`` + ``close_capital_position``, as the 1-minute monitor does.
``daily_loss_limit_pct = 0`` on both sides (the engine's lock reads the wall clock).
"""

from __future__ import annotations

import random
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from app.agents.types import Direction
from app.brokerage.execution import resolve_bar_exit
from app.db.models import (
    LedgerLeg,
    LedgerTransaction,
    PaperEquitySnapshot,
    PaperJournalEvent,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
)
from app.db.session import SessionLocal
from app.decision.pipeline import PipelineResult
from app.indicators.ichimoku import Candle
from app.paper import broker as paper_broker
from app.paper import engine as paper_engine
from app.paper import gates as paper_gates
from app.paper.strategy_profiles import BASELINE_PROFILE
from research_lab.signals import BarSignal
from research_lab.sim import BASE_COST, simulate

from vpp import INITIAL_CAPITAL, SEED
from vpp.paper import paper_costs, paper_rules

TF = "1h"
SOURCE = "auto_watchlist"
_REASON = {"stop_hit": "stop_hit", "stop_gap": "stop_hit_gap", "target_hit": "take_profit_hit",
           "target_gap": "take_profit_hit_gap"}


def _profile() -> dict[str, Any]:
    p = dict(BASELINE_PROFILE)
    p["daily_loss_limit_pct"] = 0.0
    p["code"] = f"VPP_REPLAY_{uuid.uuid4().hex[:8]}"
    return p


def _purge(session, pf_id: str) -> None:
    tx = [t.id for t in session.execute(select(LedgerTransaction).where(LedgerTransaction.portfolio_id == pf_id)).scalars()]
    if tx:
        session.execute(delete(LedgerLeg).where(LedgerLeg.transaction_id.in_(tx)))
        session.execute(delete(LedgerTransaction).where(LedgerTransaction.id.in_(tx)))
    for model in (PaperJournalEvent, PaperOrder, PaperEquitySnapshot, PaperPosition):
        session.execute(delete(model).where(model.portfolio_id == pf_id))
    session.execute(delete(PaperPortfolio).where(PaperPortfolio.id == pf_id))
    session.commit()


def replay_window(feeds: dict[str, dict[int, tuple[Candle, BarSignal]]], window: tuple[int, int]) -> dict[str, Any]:
    symbols = sorted(feeds)
    times = sorted({t for s in symbols for t in feeds[s] if window[0] <= t < window[1]})
    rng = random.Random(SEED)
    orders: dict[int, list[str]] = {}
    for t in times:  # identical shuffle sequence to research_lab.sim (one shuffle per bar, same membership)
        o = [s for s in symbols if t in feeds[s]]
        rng.shuffle(o)
        orders[t] = o

    profile = _profile()
    session = SessionLocal()
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code=profile["code"], label="VP-P replay (disposable)", currency="EUR",
                        valuation_mode="USDT_AS_EUR_PROXY", initial_cash=INITIAL_CAPITAL, cash=INITIAL_CAPITAL,
                        realized_pnl=0.0, strategy_profile=profile, is_active=False,
                        started_at=now, created_at=now, updated_at=now)
    session.add(pf)
    session.commit()
    paper_gates.reset_run_memory()
    opened: dict[str, dict[str, Any]] = {}  # position id -> info
    trades: list[dict[str, Any]] = []
    try:
        prev_t = None
        for t in times:
            if prev_t is not None:
                for sym in orders[prev_t]:
                    item_prev = feeds[sym].get(prev_t)
                    item = feeds[sym].get(t)
                    if item_prev is None or item is None:
                        continue
                    sig = item_prev[1]
                    run_id = paper_gates.observe_decision(pf.id, sym, TF, sig.decision)
                    before = {p.id for p in paper_gates.open_positions(session, pf.id)}
                    pos = paper_engine.sync_position(
                        session, symbol=sym, timeframe=TF, source=SOURCE, user_id=None, price=item[0].open,
                        pipeline=PipelineResult(decision=sig.decision, direction=sig.direction, stages=[]),
                        stop_distance=sig.stop_distance, portfolio=pf, run_id=run_id,
                    )
                    session.commit()
                    if pos is not None and pos.status == "OPEN" and pos.id not in before:
                        opened[pos.id] = {"symbol": sym, "entry_time": t}
                    elif pos is not None and pos.status == "CLOSED" and pos.id in opened:
                        trades.append(_trade(pos, opened.pop(pos.id), t))
            # protections inside bar t (entry bar included: the fill is at its open)
            for pos in paper_gates.open_positions(session, pf.id):
                item = feeds[pos.symbol].get(t)
                if item is None:
                    continue
                c = item[0]
                ex = resolve_bar_exit(pos.direction, pos.stop_price, pos.take_profit_price, c.open, c.high, c.low)
                if ex.reason is None:
                    continue
                paper_broker.close_capital_position(session, pos, price=float(ex.price), reason=_REASON[ex.reason])
                session.commit()
                trades.append(_trade(pos, opened.pop(pos.id), t))
            prev_t = t
        session.refresh(pf)
        last_close = {s: feeds[s][max(x for x in feeds[s] if x < window[1])][0].close for s in symbols}
        opens = paper_gates.open_positions(session, pf.id)
        equity_end = float(pf.cash) + sum(float(p.qty) * last_close[p.symbol] for p in opens)
        rej = {}
        for ev in session.execute(select(PaperJournalEvent).where(
                PaperJournalEvent.portfolio_id == pf.id, PaperJournalEvent.event_type == "SIGNAL_REJECTED")).scalars():
            r = (ev.payload or {}).get("reason", "?")
            rej[r] = rej.get(r, 0) + 1
        return {"trades": trades, "open_at_end": len(opens), "equity_end": equity_end, "rejections": rej}
    finally:
        session.rollback()
        _purge(session, pf.id)
        session.close()
        paper_gates.reset_run_memory()


def _trade(pos: PaperPosition, info: dict[str, Any], exit_t: int) -> dict[str, Any]:
    return {
        "symbol": info["symbol"], "entry_time": info["entry_time"], "exit_time": exit_t,
        "qty": float(pos.qty), "notional": float(pos.notional), "entry_fill": float(pos.entry_price),
        "stop": float(pos.stop_price), "tp": float(pos.take_profit_price), "exit_reason": pos.exit_reason,
        "exit_fill": float(pos.exit_price), "fees": float((pos.entry_fee or 0) + (pos.exit_fee or 0)),
        "realized": float(pos.realized_pnl or 0.0),
    }


def compare_window(feeds, window) -> dict[str, Any]:
    rules = replace(paper_rules(), daily_loss_limit_pct=0.0)
    res = simulate(feeds, rules, BASE_COST, window, initial=INITIAL_CAPITAL, seed=SEED,
                   cost_by_symbol=paper_costs(sorted(feeds)))
    eng = replay_window(feeds, window)
    sim_t = {(t.symbol, t.entry_time): t for t in res.trades}
    eng_t = {(t["symbol"], t["entry_time"]): t for t in eng["trades"]}
    keys = sorted(set(sim_t) | set(eng_t))
    rows, ok = [], 0
    for k in keys:
        s, e = sim_t.get(k), eng_t.get(k)
        if s is None or e is None:
            rows.append({"key": [k[0], _iso(k[1])], "only_in": "sim" if e is None else "engine"})
            continue
        m = {
            "qty_rel": abs(e["qty"] / s.qty - 1),
            "entry_fill_rel": abs(e["entry_fill"] / s.entry_fill - 1),
            "stop_rel": abs(e["stop"] / s.stop_level - 1),
            "tp_rel": abs(e["tp"] / s.tp_level - 1),
            "same_exit_bar": e["exit_time"] == s.exit_time,
            "same_reason": _norm(e["exit_reason"]) == _norm(s.exit_reason),
            "exit_fill_rel": abs(e["exit_fill"] / s.exit_fill - 1),
            "fees_abs": abs(e["fees"] - s.commission),
            "realized_abs": abs(e["realized"] - s.net),
        }
        good = m["qty_rel"] <= 0.005 and m["same_exit_bar"] and m["same_reason"]
        ok += good
        if not good:
            rows.append({"key": [k[0], _iso(k[1])], **m, "sim_reason": s.exit_reason,
                         "engine_reason": e["exit_reason"], "sim_exit": _iso(s.exit_time),
                         "engine_exit": _iso(e["exit_time"])})
    matched = [k for k in keys if k in sim_t and k in eng_t]
    return {
        "window": [_iso(window[0]), _iso(window[1])],
        "sim_trades": len(res.trades), "engine_trades": len(eng["trades"]),
        "matched_same_entry": len(matched),
        "matched_ok": ok,
        "match_rate_pct": 100 * ok / len(sim_t) if sim_t else None,
        "max_qty_rel": max((abs(eng_t[k]["qty"] / sim_t[k].qty - 1) for k in matched), default=None),
        "max_stop_rel": max((abs(eng_t[k]["stop"] / sim_t[k].stop_level - 1) for k in matched), default=None),
        "max_realized_abs_eur": max((abs(eng_t[k]["realized"] - sim_t[k].net) for k in matched), default=None),
        "sim_equity_end": res.equity[-1][1],
        "engine_equity_end": eng["equity_end"],
        "equity_end_rel_diff": abs(eng["equity_end"] / res.equity[-1][1] - 1),
        "sim_open_at_end": len(res.open_at_end), "engine_open_at_end": eng["open_at_end"],
        "sim_rejections": dict(res.rejections), "engine_rejections": eng["rejections"],
        "differences": rows,
    }


def _norm(reason: str) -> str:
    """Same economic exit, different label: the engine closes a gap at the open through check_stop_or_tp
    ("stop_hit"), the simulator calls it "stop_hit_gap"; a two-level bar is "stop_hit_ambiguous" in the sim."""
    return {"stop_hit_gap": "stop_hit", "stop_hit_ambiguous": "stop_hit",
            "take_profit_hit_gap": "take_profit_hit"}.get(reason, reason)


def _iso(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")
