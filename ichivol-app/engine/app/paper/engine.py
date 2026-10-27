"""Paper trading -- virtual positions only.

Phase 1 PaperBroker: ATR sizing against portfolio capital.
Phase 2: multi-portfolio sync + optional Market Structure gates on
experimental profiles only. ICHIVOL_BASELINE_V1 never gains structure filters.
Never a real order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.decision.pipeline import PipelineResult
from app.context.gate import apply_context_gate
from app.fibonacci.gate import apply_fibonacci_gate
from app.market_data.timeframes import TF_SECONDS
from app.paper import broker as paper_broker
from app.paper import counters as paper_counters
from app.paper import futures_crypto
from app.paper.strategy_profiles import WIDE_EXTRA_SYMBOLS, explicit_universe, wants_wide_universe
from app.paper import gates as paper_gates
from app.paper.risk_kernel import (
    OpenPlan,
    PortfolioState,
    evaluate as risk_kernel_evaluate,
    market_state_from_profile,
    open_lots_from_positions,
)
from app.paper.portfolio import ensure_main_portfolio, ensure_syncable_portfolios
from app.sessions.decision_windows import decision_event_for_bar
from app.shadow import broker as shadow_broker
from app.structure.gate import apply_structure_gate


def _direction_for(decision: str) -> str | None:
    if decision == "BUY":
        return "LONG"
    if decision == "SELL":
        return "SHORT"
    return None


def _signal_payload(pipeline: PipelineResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": pipeline.decision,
        "direction": getattr(pipeline.direction, "value", str(pipeline.direction)),
        "stages": [
            {
                "id": getattr(getattr(s, "id", None), "value", getattr(s, "id", None)),
                "status": getattr(getattr(s, "status", None), "value", str(getattr(s, "status", ""))),
                "summary": getattr(s, "summary", None),
                "codes": getattr(s, "codes", None),
            }
            for s in (pipeline.stages or [])
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def _get_open_position(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    portfolio_id: str | None = None,
) -> PaperPosition | None:
    stmt = select(PaperPosition).where(
        PaperPosition.symbol == symbol,
        PaperPosition.timeframe == timeframe,
        PaperPosition.source == source,
        PaperPosition.user_id == user_id,
        PaperPosition.status == "OPEN",
    )
    if portfolio_id is not None:
        stmt = stmt.where(PaperPosition.portfolio_id == portfolio_id)
    return session.execute(stmt).scalar_one_or_none()


def _lock_symbol(session: Session, portfolio_id: str | None, symbol: str) -> None:
    """Serialise concurrent opens for one (portfolio, symbol).

    ``SELECT ... FOR UPDATE`` only locks rows that already exist, so two
    simultaneous confirmations on a symbol with no open lot would both insert.
    A transaction-scoped advisory lock closes that race without a schema change;
    it is released at commit/rollback."""
    if portfolio_id is None:
        return
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(
            text("select pg_advisory_xact_lock(hashtext(:k))"), {"k": f"open:{portfolio_id}:{symbol}"}
        )


def _get_open_by_symbol(
    session: Session,
    *,
    symbol: str,
    portfolio_id: str,
    for_update: bool = False,
) -> PaperPosition | None:
    """Any open lot on this symbol in the portfolio (any TF / source).

    Prevents double-investing the same asset via a second click or a second
    timeframe while one lot is already open.
    """
    stmt = select(PaperPosition).where(
        PaperPosition.symbol == symbol,
        PaperPosition.portfolio_id == portfolio_id,
        PaperPosition.status == "OPEN",
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.execute(stmt).scalars().first()


def _close_legacy(position: PaperPosition, *, price: float, reason: str) -> None:
    position.status = "CLOSED"
    position.exit_time = datetime.now(timezone.utc)
    position.exit_price = price
    position.exit_reason = reason
    from app.paper.broker import short_pnl_pct

    position.pnl_pct = (
        (price / position.entry_price) - 1.0
        if position.direction == "LONG"
        else short_pnl_pct(position.entry_price, price)
    )


def _open_legacy(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    direction: str,
    price: float,
    decision: str,
    portfolio_id: str | None = None,
) -> PaperPosition:
    position = PaperPosition(
        portfolio_id=portfolio_id,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        direction=direction,
        status="OPEN",
        entry_time=datetime.now(timezone.utc),
        entry_price=price,
        entry_decision=decision,
    )
    session.add(position)
    return position


def sync_position(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    price: float,
    pipeline: PipelineResult,
    stop_distance: float | None = None,
    signal_extra: dict[str, Any] | None = None,
    portfolio: PaperPortfolio | None = None,
    decision_id: str | None = None,
    evidence_id: str | None = None,
    run_id: int | None = None,
    manual_notional: float | None = None,
    take_profit_r: float | None = None,
    signal_actions: bool = True,
    open_refusal: str | None = None,
) -> PaperPosition | None:
    """One symbol open/hold/close for one portfolio. Capital sizing when stop set.

    ``open_refusal`` (ex. ``illiquid_24h_volume``) : le lot déjà ouvert reste géré (stop, objectif, signal),
    mais aucune nouvelle ouverture ; le refus est journalisé avec ce code.

    ``signal_actions=False`` (outside a profile's ``decision_windows``): stop/target still close a lot, but the
    signal neither opens nor closes anything."""
    if portfolio is None:
        try:
            portfolio = ensure_main_portfolio(session)
        except Exception:
            portfolio = None

    portfolio_id = portfolio.id if portfolio is not None else None
    _lock_symbol(session, portfolio_id, symbol)
    existing = _get_open_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )
    # One open lot per symbol per portfolio — blocks a second TF/source invest.
    if existing is None and portfolio_id is not None:
        existing = _get_open_by_symbol(session, symbol=symbol, portfolio_id=portfolio_id)
    direction = _direction_for(pipeline.decision)
    signal = _signal_payload(pipeline, signal_extra)

    if existing is not None:
        paper_broker.update_excursions(existing, price)
        stop_reason = paper_broker.check_stop_or_tp(existing, price)
        if stop_reason is not None:
            if existing.qty:
                paper_broker.close_capital_position(
                    session, existing, price=price, reason=stop_reason, signal=signal
                )
            else:
                _close_legacy(existing, price=price, reason=stop_reason)
            session.flush()
            return existing

        if not signal_actions:
            return None

        _prof = (portfolio.strategy_profile or {}) if portfolio is not None else {}
        if _prof.get("exit_mode") == "direction" and existing.source == source:
            # Long-only forward test (FWD_E_LONG): a lot closes on stop/target (above) or when the
            # Ichimoku DIRECTION of the last closed bar is no longer the lot's direction. A decision that
            # merely falls back to WATCH/NO_TRADE never closes it.
            if existing.timeframe != timeframe:
                return None  # a lot is only managed by the row of its own timeframe
            _pdir = getattr(pipeline.direction, "value", str(pipeline.direction))
            if _pdir == existing.direction:
                return None
            if existing.qty:
                paper_broker.close_capital_position(
                    session, existing, price=price, reason="direction_flipped", signal=signal
                )
            else:
                _close_legacy(existing, price=price, reason="direction_flipped")
            session.flush()
            return existing

        if direction == existing.direction:
            # A signal blocked by a lot opened from another source/timeframe is a real rejection; the same lot
            # seen again every cycle is not (it would inflate the counter), so only the former is journaled.
            pf_profile = (portfolio.strategy_profile or {}) if portfolio is not None else {}
            if pf_profile.get("log_rejections") and (existing.source != source or existing.timeframe != timeframe):
                paper_counters.record_rejection(
                    session, portfolio, symbol=symbol, timeframe=timeframe, reason="position_already_open",
                    detail={"held_source": existing.source, "held_timeframe": existing.timeframe},
                )
            return None

        if existing.source != source:
            # A lot opened from another source (e.g. user_confirmed) is NOT managed by this loop's
            # signal: a signal downgrade must never close a manual position. Only its stop/target
            # (checked above, and by app/paper/protection.py) or the user can close it.
            return None

        reason = "pipeline_flipped" if direction is not None else "pipeline_downgraded"
        if existing.qty:
            paper_broker.close_capital_position(
                session, existing, price=price, reason=reason, signal=signal
            )
        else:
            _close_legacy(existing, price=price, reason=reason)
        session.flush()
        return existing

    if direction is None or not signal_actions:
        return None

    profile = (portfolio.strategy_profile or {}) if portfolio is not None else {}
    log_rej = bool(profile.get("log_rejections")) and portfolio is not None
    if open_refusal is not None:
        if log_rej:
            paper_counters.record_rejection(session, portfolio, symbol=symbol, timeframe=timeframe, reason=open_refusal)
        return None
    if direction == "SHORT" and portfolio is not None and profile.get("allow_short", True) is False:
        # No short selling on this portfolio, ever. Does not consume the signal run (no gate call).
        if log_rej:
            paper_counters.record_rejection(session, portfolio, symbol=symbol, timeframe=timeframe, reason="short_not_allowed")
        return None
    if portfolio is not None:
        # T13b/T13c — Risk Kernel for every open (kill/daily lock always; gates when enabled).
        from app.paper import kill_switch as paper_kill

        traded = None
        if run_id is not None:
            traded = paper_gates.traded_run_id(portfolio.id, symbol, timeframe)
        apply_gates = paper_gates.has_gates(profile) and manual_notional is None

        def _kernel_decision():
            equity = paper_broker.estimate_equity(session, portfolio)
            paper_kill.maybe_trip_daily_loss_lock(session, portfolio, equity)
            opens = paper_gates.open_positions(session, portfolio.id)
            return risk_kernel_evaluate(
                OpenPlan(
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=direction,
                    price=price,
                    stop_distance=stop_distance,
                    run_id=run_id,
                    stale=False,
                    manual_notional=manual_notional,
                    take_profit_r=take_profit_r,
                ),
                PortfolioState(
                    cash=float(portfolio.cash),
                    equity=float(equity),
                    profile=profile,
                    open_positions=open_lots_from_positions(opens),
                    day_start_equity=paper_gates.day_start_equity(session, portfolio),
                    traded_run_id=traded,
                    kill_switch_armed=bool(getattr(portfolio, "kill_switch_armed", False)),
                    daily_loss_locked=bool(getattr(portfolio, "daily_loss_locked", False)),
                ),
                market_state_from_profile(profile, symbol),
                apply_gates=apply_gates,
                check_size=apply_gates,  # sizing still done in broker when gates skipped (manual)
            )

        # Pre-check on a fresh (unlocked) read: most refusals end here without locking the account, so the
        # scan loop does not hold every portfolio row for the rest of its transaction.
        session.flush()  # never let the reload drop this transaction's own pending changes
        session.refresh(portfolio)
        decision_rk = _kernel_decision()
        if decision_rk.accepted:
            # Accepted: lock the account (the broker would lock it anyway) and decide again on the locked
            # balance, positions and kill/daily locks — a concurrent open, close or kill switch committed
            # since the pre-check must count. The broker then debits that same locked balance.
            paper_broker.lock_portfolio(session, portfolio)
            decision_rk = _kernel_decision()
        if not decision_rk.accepted:
            reason = decision_rk.primary_code() or "rejected"
            if log_rej or reason in ("kill_switch", "daily_loss_halt"):
                paper_counters.record_rejection(
                    session, portfolio, symbol=symbol, timeframe=timeframe, reason=reason,
                    detail={"codes": list(decision_rk.codes)},
                )
            return None

    if portfolio is not None and stop_distance and stop_distance > 0:
        require_atr = bool(profile.get("require_atr_stop", True))
        position = paper_broker.open_capital_position(
            session,
            portfolio=portfolio,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            user_id=user_id,
            direction=direction,
            price=price,
            decision=pipeline.decision,
            stop_distance=stop_distance,
            signal=signal,
            decision_id=decision_id,
            evidence_id=evidence_id,
            manual_notional=manual_notional,
            take_profit_r=take_profit_r,
        )
        if position is not None:
            session.flush()
            if run_id is not None:
                paper_gates.mark_run_traded(portfolio.id, symbol, timeframe, run_id)
            return position
        if log_rej:
            opened = paper_gates.open_positions(session, portfolio.id)
            paper_counters.record_rejection(
                session, portfolio, symbol=symbol, timeframe=timeframe,
                reason="max_positions" if len(opened) >= int(profile.get("max_open_positions", 5))
                else "insufficient_cash_or_size",
            )
        if require_atr:
            return None

    position = _open_legacy(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        direction=direction,
        price=price,
        decision=pipeline.decision,
        portfolio_id=portfolio_id,
    )
    session.flush()
    return position


BEHAVIOR_CHANGE_EVENT = "BEHAVIOR_CHANGE"
AUTO_TIMEFRAMES_CHANGE = "auto_timeframes_only"


def auto_timeframes(profile: dict[str, Any] | None) -> tuple[str, ...]:
    """Timeframes a profile trades automatically. Missing key = the 1h strategy only (2026-09-28)."""
    return tuple((profile or {}).get("auto_timeframes") or ("1h",))


def mark_auto_timeframes_change() -> bool:
    """Journal once per syncable portfolio the date from which UI scans stopped driving the paper strategy.

    History is left untouched: earlier positions keep their real timeframe/source. Returns False on a DB error
    (the caller retries on the next cycle)."""
    from app.db.models import PaperJournalEvent
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        for pf in ensure_syncable_portfolios(session):
            payloads = session.execute(
                select(PaperJournalEvent.payload).where(
                    PaperJournalEvent.portfolio_id == pf.id,
                    PaperJournalEvent.event_type == BEHAVIOR_CHANGE_EVENT,
                )
            ).scalars().all()
            if any((p or {}).get("change") == AUTO_TIMEFRAMES_CHANGE for p in payloads):
                continue
            session.add(PaperJournalEvent(
                portfolio_id=pf.id, position_id=None, event_type=BEHAVIOR_CHANGE_EVENT,
                payload={
                    "change": AUTO_TIMEFRAMES_CHANGE,
                    "auto_timeframes": list(auto_timeframes(pf.strategy_profile)),
                    "effective_at": datetime.now(timezone.utc).isoformat(),
                    "before": "a screener scan on any timeframe (UI / agent channel) also synced paper positions",
                    "after": "only the background loop on the profile's auto_timeframes opens/closes auto positions; "
                             "stop/target protection and explicit manual actions unchanged",
                    "doc": "docs/VP-P-PAPER-REEL.md",
                },
                created_at=datetime.now(timezone.utc),
            ))
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def trades_symbol(profile: dict[str, Any] | None, symbol: str) -> bool:
    """Which rows a portfolio acts on. A dedicated account (Futures & Crypto) trades only its own markets; every
    other account trades the shared watchlist and never an instrument reserved to a dedicated account."""
    from app.universe.catalog import dedicated_only_ids

    universe = explicit_universe(profile)
    if universe is not None:
        # Portefeuille unique : univers explicite (règle de liquidité statique déjà appliquée au profil).
        return symbol in universe
    if futures_crypto.is_dedicated(profile):
        return symbol in futures_crypto.traded_symbols(profile)
    if symbol in WIDE_EXTRA_SYMBOLS and not wants_wide_universe(profile):
        # The wide-universe pairs belong to ICHIVOL_WIDE_V1 only: the baseline never sees them.
        return False
    return symbol not in dedicated_only_ids()


def quote_volume_24h(row: Any) -> float | None:
    """Volume échangé des dernières 24 h (devise de cotation) d'une ligne à volume réel, sinon None.

    Seules les paires Binance spot ont un vrai volume d'échange ; les CFD (biquote) ont un volume de ticks."""
    if getattr(row, "exchange", None) != "binance":
        return None
    candles = getattr(row, "candles", None) or []
    tf_s = TF_SECONDS.get(getattr(row, "timeframe", "1h"), 3600)
    n = max(1, 86_400 // tf_s)
    if len(candles) < n:
        return None
    return float(sum(float(c.close) * float(c.volume) for c in candles[-n:]))


def liquidity_refusal(profile: dict[str, Any] | None, row: Any) -> str | None:
    """Règle de liquidité dynamique du profil (``min_quote_volume_24h``) : code de refus ou None."""
    minimum = (profile or {}).get("min_quote_volume_24h")
    if not minimum:
        return None
    vol = quote_volume_24h(row)
    if vol is None:
        return None
    return "illiquid_24h_volume" if vol < float(minimum) else None


def engine_proposal(
    session: Session,
    *,
    portfolio: PaperPortfolio,
    symbol: str,
    timeframe: str,
    pipeline: PipelineResult,
    signal_actions: bool,
    allow_open: bool = True,
) -> dict[str, Any] | None:
    """What the engine alone would do on this book for this row, without doing it.

    Mirrors the signal branches of ``sync_position`` (stop/target excluded: those still close on their own).
    Returns ``{"action": "OPEN", "direction": ...}``, ``{"action": "CLOSE", "position_id": ...}`` or ``None``."""
    if not signal_actions:
        return None
    profile = portfolio.strategy_profile or {}
    direction = _direction_for(pipeline.decision)
    existing = _get_open_by_symbol(session, symbol=symbol, portfolio_id=portfolio.id)
    if existing is None:
        if direction is None or not allow_open:
            return None
        if direction == "SHORT" and profile.get("allow_short", True) is False:
            return None
        return {"action": "OPEN", "direction": direction}
    if existing.timeframe != timeframe:
        return None
    if existing.source != "auto_watchlist":
        # Arbitrage : comme sync_position, le signal du scan ne ferme jamais le lot d'un autre décideur
        # (Ève, manuel) ; seuls son stop, son objectif ou un ordre explicite le ferment.
        return None
    if profile.get("exit_mode") == "direction":
        pdir = getattr(pipeline.direction, "value", str(pipeline.direction))
        if pdir == existing.direction:
            return None
        return {"action": "CLOSE", "position_id": existing.id, "reason": "direction_flipped"}
    if direction == existing.direction:
        return None
    reason = "pipeline_flipped" if direction is not None else "pipeline_downgraded"
    return {"action": "CLOSE", "position_id": existing.id, "reason": reason}


def sync_auto_watchlist(
    session: Session,
    rows: Sequence,
    *,
    proposals: list[dict[str, Any]] | None = None,
) -> list[PaperPosition]:
    """Reuse screener rows; size when ATR stop is present; sync all syncable portfolios.

    A portfolio only acts on rows of its ``auto_timeframes`` (default 1h): other timeframes never open, close or
    manage its positions here (their stop/target stays watched by app/paper/protection.py).

    ``proposals`` (Ève decides, EVE_PAPER_AUTONOMY on): the engine still computes every book's decision and still
    closes on stop/target, but its signal opens or closes nothing. Each would-be open/close is appended to
    ``proposals`` for Ève to accept or refuse (app/eve/autopilot.py)."""
    try:
        portfolios = ensure_syncable_portfolios(session)
    except Exception:
        portfolios = []
        try:
            portfolios = [ensure_main_portfolio(session)]
        except Exception:
            portfolios = []

    marks: dict[str, float] = {}
    touched: list[PaperPosition] = []
    # Cache structure gate by (symbol,tf, detectors key) within this cycle
    gate_cache: dict[tuple[str, str, str], Any] = {}
    funnel_portfolio = next((pf for pf in portfolios if (pf.strategy_profile or {}).get("log_rejections")), None)
    funnels: dict[str, paper_counters.FunnelAccumulator] = {}
    bars_by_key: dict[str, Sequence] = {}
    now_s = datetime.now(timezone.utc).timestamp()

    for row in rows:
        bars_by_key[f"{row.symbol}:{row.timeframe}"] = getattr(row, "candles", None) or []
        # The funnel journal stays the reference account's: only rows that account itself acts on.
        funnel_profile = (funnel_portfolio.strategy_profile or {}) if funnel_portfolio is not None else {}
        if (
            funnel_portfolio is not None
            and getattr(row, "candles", None)
            and row.timeframe in auto_timeframes(funnel_profile)
            and (row.symbol not in WIDE_EXTRA_SYMBOLS or wants_wide_universe(funnel_profile))
        ):
            tf_s = TF_SECONDS.get(row.timeframe, 3600)
            last_open = row.candles[-1].time
            funnels.setdefault(row.timeframe, paper_counters.FunnelAccumulator()).add(
                paper_counters.classify_row(
                    row.pipeline,
                    bar_forming=last_open + tf_s > now_s,
                    stale=now_s - (last_open + tf_s) > 2 * tf_s,
                )
            )
        if (getattr(row, "signal_timing", None) or {}).get("stale"):
            # Frozen/late provider data (e.g. TONUSDT candles stopped 2026-06-30): do not open,
            # do not close on the signal, do not mark open lots to a stale price. Protections
            # are watched separately by app/paper/protection.py.
            continue
        stop = None
        if getattr(row, "atr", None) is not None:
            stop = getattr(row.atr, "suggested_stop_distance", None)
        rvol_val = None
        rvol_out = getattr(row, "rvol", None)
        if rvol_out is not None:
            meta = getattr(rvol_out, "metadata", None) or {}
            rvol_val = meta.get("rvol")
            if rvol_val is None:
                rvol_val = getattr(rvol_out, "value", None)
        candles = getattr(row, "candles", None) or []

        if not portfolios:
            result = sync_position(
                session,
                symbol=row.symbol,
                timeframe=row.timeframe,
                source="auto_watchlist",
                user_id=None,
                price=row.price,
                pipeline=row.pipeline,
                stop_distance=stop,
                signal_extra={"rvol": rvol_val, "atr_stop": stop},
            )
            marks[f"{row.symbol}:{row.timeframe}"] = row.price
            if result is not None:
                touched.append(result)
            continue

        for portfolio in portfolios:
            profile = portfolio.strategy_profile or {}
            if row.timeframe not in auto_timeframes(profile):
                continue
            if not trades_symbol(profile, row.symbol):
                continue
            det_key = (
                ",".join(profile.get("structure_detectors") or []),
                str(profile.get("structure_filter")),
                str(profile.get("structure_include_pytrendline")),
            )
            cache_key = (row.symbol, row.timeframe, "|".join(det_key))
            if profile.get("structure_filter") and cache_key in gate_cache:
                struct_gate = gate_cache[cache_key]
            else:
                struct_gate = apply_structure_gate(
                    row.pipeline,
                    candles,
                    profile,
                    rvol=rvol_val if isinstance(rvol_val, (int, float)) else None,
                )
                if profile.get("structure_filter"):
                    gate_cache[cache_key] = struct_gate

            # Fibonacci runs after structure (swings), then context
            fib_gate = apply_fibonacci_gate(struct_gate.pipeline, candles, profile)
            ctx_gate = apply_context_gate(fib_gate.pipeline, candles, profile)

            blocked = struct_gate.blocked or fib_gate.blocked or ctx_gate.blocked
            final_pipeline = ctx_gate.pipeline
            raw_decision = struct_gate.raw_decision
            # Portefeuille unique : filtres en observation. Ils sont calculés et enregistrés sur le signal
            # (« aurait refusé »), mais la décision reste celle du pipeline Ichimoku x RVOL.
            # (Futur VWAP : un filtre de plus ici, après le contexte, d'abord en observation.)
            observe_filters = profile.get("filters_mode") == "observe"
            would_block = blocked if observe_filters else False
            if observe_filters:
                final_pipeline = row.pipeline
                blocked = False
            if ctx_gate.blocked:
                block_reason, block_source = ctx_gate.reason, "context"
            elif fib_gate.blocked:
                block_reason, block_source = fib_gate.reason, "fibonacci"
            elif struct_gate.blocked:
                block_reason, block_source = struct_gate.reason, "structure"
            else:
                block_reason, block_source = None, None

            if blocked and profile.get("shadow_on_block"):
                shadow_broker.open_shadow(
                    session,
                    portfolio=portfolio,
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    raw_decision=raw_decision,
                    price=row.price,
                    stop_distance=stop if isinstance(stop, (int, float)) else None,
                    block_source=block_source or "unknown",
                    block_reason=block_reason,
                    meta={
                        "market_structure": struct_gate.structure_payload,
                        "fibonacci": fib_gate.fibonacci_payload,
                        "context": ctx_gate.context_payload,
                    },
                )

            extra: dict[str, Any] = {
                "rvol": rvol_val,
                "atr_stop": stop,
                "portfolio_code": portfolio.code,
            }
            if struct_gate.structure_payload is not None:
                extra["market_structure"] = struct_gate.structure_payload
            if fib_gate.fibonacci_payload is not None:
                extra["fibonacci"] = fib_gate.fibonacci_payload
            if ctx_gate.context_payload is not None:
                extra["context"] = ctx_gate.context_payload
            mtf = getattr(row, "mtf_matrix", None)
            if mtf is not None:
                # MTF-1: what the engine knew about every horizon at this decision (observe-only, never read
                # back by the strategy). Persisted so a historical marker shows it without a recompute.
                extra["mtf_matrix"] = mtf.to_dict()
            if would_block:
                extra["filters_observed"] = {
                    "would_block": True,
                    "structure_blocked": struct_gate.blocked,
                    "fibonacci_blocked": fib_gate.blocked,
                    "context_blocked": ctx_gate.blocked,
                    "block_source": block_source,
                    "block_reason": block_reason,
                }
            elif observe_filters and raw_decision in ("BUY", "SELL"):
                extra["filters_observed"] = {"would_block": False}
            if blocked:
                extra["structure_blocked"] = struct_gate.blocked
                extra["fibonacci_blocked"] = fib_gate.blocked
                extra["context_blocked"] = ctx_gate.blocked
                extra["block_source"] = block_source
                extra["block_reason"] = block_reason
                extra["raw_decision"] = raw_decision

            signal_actions = True
            windows = profile.get("decision_windows")
            if windows:
                # Market-session schedule: the signal acts only on the candle tied to a market open/close.
                bar_close = (getattr(row, "signal_timing", None) or {}).get("signal_bar_close")
                event = (
                    decision_event_for_bar(int(bar_close), windows, TF_SECONDS.get(row.timeframe, 3600))
                    if bar_close is not None
                    else None
                )
                extra["decision_event"] = event
                if profile.get("decision_windows_mode") == "observe":
                    # Fenêtres de sessions en observation : l'événement (ouverture/clôture Tokyo, Londres,
                    # New York) est enregistré, le signal agit à chaque bougie 1h comme avant.
                    extra["decision_window_observed"] = True
                else:
                    signal_actions = event is not None

            open_refusal = liquidity_refusal(profile, row)
            if open_refusal is not None:
                extra["quote_volume_24h"] = quote_volume_24h(row)

            if proposals is not None:
                proposal = engine_proposal(
                    session,
                    portfolio=portfolio,
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    pipeline=final_pipeline,
                    signal_actions=signal_actions,
                    allow_open=open_refusal is None,
                )
                if proposal is not None:
                    proposal.update(
                        portfolio_code=portfolio.code,
                        symbol=row.symbol,
                        timeframe=row.timeframe,
                        price=row.price,
                        stop_distance=stop if isinstance(stop, (int, float)) else None,
                        engine_decision=final_pipeline.decision,
                        signal_bar_close=(getattr(row, "signal_timing", None) or {}).get("signal_bar_close"),
                    )
                    proposals.append(proposal)
                # Engine signal acts on nothing: only stop/target can still close a lot.
                signal_actions = False

            run_id = None
            if paper_gates.has_gates(profile) and proposals is None:
                run_id = paper_gates.observe_decision(
                    portfolio.id, row.symbol, row.timeframe, final_pipeline.decision
                )
            result = sync_position(
                session,
                symbol=row.symbol,
                timeframe=row.timeframe,
                source="auto_watchlist",
                user_id=None,
                price=row.price,
                pipeline=final_pipeline,
                stop_distance=stop,
                signal_extra=extra,
                portfolio=portfolio,
                run_id=run_id,
                signal_actions=signal_actions,
                open_refusal=open_refusal,
            )
            if result is not None:
                touched.append(result)
            if futures_crypto.is_dedicated(profile):
                action = None
                if result is not None:
                    action = "opened" if result.status == "OPEN" else "closed"
                futures_crypto.remember_signal(row, final_pipeline, action=action)

        marks[f"{row.symbol}:{row.timeframe}"] = row.price

    if funnel_portfolio is not None:
        for tf, acc in funnels.items():
            paper_counters.record_funnel(session, funnel_portfolio, acc, tf)

    shadow_broker.mark_shadows(session, marks=marks)

    for portfolio in portfolios:
        paper_broker.snapshot_equity(session, portfolio, marks=marks)
    session.commit()
    return touched


def open_user_confirmed(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    user_id: str,
    price: float,
    pipeline: PipelineResult,
    stop_distance: float | None = None,
    decision_id: str | None = None,
    evidence_id: str | None = None,
    signal_extra: dict[str, Any] | None = None,
    manual_notional: float | None = None,
    take_profit_r: float | None = None,
    portfolio: PaperPortfolio | None = None,
) -> tuple[PaperPosition | None, bool]:
    """Open a user-confirmed paper lot.

    Returns ``(position, created)``. ``created=False`` means an open lot on
    this symbol already existed in the target portfolio — idempotent lock,
    no second notional spent.

    ``portfolio`` defaults to the baseline account; tests that need a clean
    (non-halted) book should pass a disposable clone instead of mutating baseline.
    """
    if portfolio is None:
        portfolio = ensure_main_portfolio(session)
    _lock_symbol(session, portfolio.id, symbol)
    existing_any = _get_open_by_symbol(
        session, symbol=symbol, portfolio_id=portfolio.id, for_update=True
    )
    if existing_any is not None:
        return existing_any, False

    existing = _get_open_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source="user_confirmed",
        user_id=user_id,
        portfolio_id=portfolio.id,
    )
    if existing is not None:
        return existing, False

    direction = _direction_for(pipeline.decision)
    if direction is None:
        return None, False

    position = sync_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source="user_confirmed",
        user_id=user_id,
        price=price,
        pipeline=pipeline,
        stop_distance=stop_distance,
        decision_id=decision_id,
        evidence_id=evidence_id,
        signal_extra=signal_extra,
        portfolio=portfolio,
        manual_notional=manual_notional,
        take_profit_r=take_profit_r,
    )
    session.commit()
    return position, position is not None


def close_manually(session: Session, position_id: str, *, price: float) -> PaperPosition | None:
    position = session.get(PaperPosition, position_id)
    if position is None or position.status != "OPEN":
        return None
    if position.qty:
        paper_broker.close_capital_position(
            session, position, price=price, reason="manual_close", signal=None
        )
    else:
        _close_legacy(position, price=price, reason="manual_close")
    session.commit()
    return position


def get_position(session: Session, position_id: str) -> PaperPosition | None:
    return session.get(PaperPosition, position_id)


def list_positions(
    session: Session,
    *,
    source: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    portfolio_id: str | None = None,
) -> list[PaperPosition]:
    stmt = select(PaperPosition).order_by(PaperPosition.entry_time.desc())
    if source is not None:
        stmt = stmt.where(PaperPosition.source == source)
    if user_id is not None:
        stmt = stmt.where(PaperPosition.user_id == user_id)
    if status is not None:
        stmt = stmt.where(PaperPosition.status == status)
    if portfolio_id is not None:
        stmt = stmt.where(PaperPosition.portfolio_id == portfolio_id)
    return list(session.execute(stmt).scalars().all())
