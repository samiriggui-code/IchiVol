"""Stop / take-profit monitoring for open paper positions, independent of signals.

Why this exists: stops used to be evaluated only when the screener refreshed
(every few minutes) and only against one price sample, and manually confirmed
positions were not looked at at all. A protection must be watched between two
candle closes, whatever way the position was opened (auto, user-confirmed, any
portfolio).

Method (no look-ahead into the past of the position):
1. The remainder of the entry minute is checked tick by tick (aggregated
   trades from the exact entry time) -- a high/low of the entry candle that
   happened BEFORE the fill is never used.
2. Whole 1-minute bars strictly after the entry minute are checked with
   ``resolve_bar_exit`` (gap through a level fills at the open, not at the level).
3. If one 1-minute bar touches both levels the order is unknown: finer data
   (ticks of that minute) is used when available; otherwise the STOP is assumed
   first and the note says so.

Legacy positions (opened before monitoring existed) are NOT closed on the basis
of a reconstruction: they get a watermark "from now" and any historical breach
is only reported (see ``history_breach`` in the result).

Trailing / breakeven (T0-MANAGE-b): opt-in via ``protection_trail`` on
``entry_signal`` or portfolio ``strategy_profile``, ``user_confirmed`` only.
Uses ``app.strategy_lab.stop_trail.update_trailing_stop`` (same math as Lab);
check-then-ratchet per closed bar; watermark always advances on the trail path
so past bars are never re-scored against a ratcheted stop.

Partial TP (T0-MANAGE-d) / reinforce (T0-MANAGE-f): opt-in
``protection_partial_tp`` / ``protection_reinforce`` (mutually exclusive).
Manage priority matches Lab: stop > partials > target > reinforce > trail.
Reinforce paper trigger is price ``at_r_multiple`` (no FeatureBars).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.types import Direction
from app.brokerage.execution import resolve_bar_exit
from app.db.models import (
    PaperJournalEvent,
    PaperPartialExit,
    PaperPortfolio,
    PaperPosition,
    PaperReinforceAdd,
)
from app.market_data.binance import BASE_URL
from app.paper import broker as paper_broker
from app.paper.protection_partial_tp import (
    PaperPartialTpConfig,
    bar_hits_step,
    fired_r_multiples,
    freeze_partial_tp_anchor,
    level_for_step,
    pending_steps,
    qty_for_step,
    resolve_paper_partial_tp,
)
from app.paper.protection_reinforce import (
    PaperReinforceConfig,
    adds_done as reinforce_adds_done,
    bar_hits_reinforce,
    freeze_reinforce_anchor,
    level_for_reinforce,
    persist_reinforce_prev_match,
    reinforce_prev_match,
    resolve_paper_reinforce,
)
from app.paper.protection_trail import (
    TRAIL_EVENT,
    PaperTrailConfig,
    freeze_trail_anchor,
    resolve_paper_trail,
)
from app.strategy_lab.partial_tp import PartialTpStep
from app.strategy_lab.reinforce import apply_reinforce_add, cap_add_by_notional_equity
from app.strategy_lab.stop_trail import update_trailing_stop
from app.paper.risk import apply_entry_friction
from app.universe.catalog import get_instrument

logger = logging.getLogger(__name__)

MINUTE_MS = 60_000
CHECK_EVENT = "PROTECTION_CHECKED"
CHECK_EVENT_EVERY_MS = 15 * MINUTE_MS

# (symbol, start_ms, end_ms) -> rows
KlinesFn = Callable[[str, int, int], Sequence[Sequence[Any]]]
# (symbol, start_ms, end_ms) -> [(time_ms, price)] ascending
TradesFn = Callable[[str, int, int], Sequence[tuple[int, float]]]


@dataclass(frozen=True)
class Breach:
    reason: str  # stop_hit | stop_gap | take_profit_hit | target_gap
    price: float
    time_ms: int
    granularity: str  # tick | 1m
    note: str = ""


@dataclass(frozen=True)
class ScanResult:
    breach: Breach | None
    checked_through_ms: int
    bars_seen: int = 0
    bars_expected: int = 0


def _hit(direction: str, stop: float, target: float, price: float) -> str | None:
    long = direction.upper() == "LONG"
    if (price <= stop) if long else (price >= stop):
        return "stop"
    if (price >= target) if long else (price <= target):
        return "target"
    return None


def _scan_ticks(direction: str, stop: float, target: float, ticks: Sequence[tuple[int, float]]) -> Breach | None:
    for t, p in ticks:
        h = _hit(direction, stop, target, p)
        if h == "stop":
            gapped = (p < stop) if direction.upper() == "LONG" else (p > stop)
            return Breach("stop_hit", p if gapped else stop, t, "tick",
                          "tick beyond stop: filled at that tick" if gapped else "")
        if h == "target":
            return Breach("take_profit_hit", target, t, "tick")
    return None


def find_first_breach(
    direction: str,
    stop: float,
    target: float,
    *,
    symbol: str,
    since_ms: int,
    until_ms: int,
    klines_fn: KlinesFn,
    trades_fn: TradesFn | None,
) -> ScanResult:
    """First stop/target crossing strictly after ``since_ms`` and before ``until_ms``.

    ``until_ms`` bounds the scan to CLOSED minutes (a still-forming 1m bar is
    left for the next cycle)."""
    minute0 = since_ms - since_ms % MINUTE_MS
    checked = since_ms

    if since_ms % MINUTE_MS:
        entry_minute_end = minute0 + MINUTE_MS
        if trades_fn is not None and entry_minute_end <= until_ms:
            ticks = [(t, p) for t, p in trades_fn(symbol, since_ms, entry_minute_end) if t >= since_ms]
            b = _scan_ticks(direction, stop, target, ticks)
            if b:
                return ScanResult(b, entry_minute_end)
            checked = entry_minute_end
        # Without tick data the entry minute is skipped (blind spot < 60 s) rather
        # than guessed from a candle that mixes pre- and post-entry prices.
        start = entry_minute_end
    else:
        start = minute0

    end_closed = until_ms - until_ms % MINUTE_MS
    if start >= end_closed:
        return ScanResult(None, max(checked, min(start, end_closed)))

    rows = klines_fn(symbol, start, end_closed)
    expected = (end_closed - start) // MINUTE_MS
    seen = 0
    for k in rows:
        open_ms = int(k[0])
        if open_ms < start or open_ms + MINUTE_MS > end_closed:
            continue
        seen += 1
        o, h, l = float(k[1]), float(k[2]), float(k[3])
        r = resolve_bar_exit(direction, stop, target, o, h, l)
        checked = open_ms + MINUTE_MS
        if r.reason is None:
            continue
        if "both inside bar" in r.note and trades_fn is not None:
            ticks = list(trades_fn(symbol, open_ms, open_ms + MINUTE_MS))
            b = _scan_ticks(direction, stop, target, ticks)
            if b:
                return ScanResult(
                    Breach(b.reason, b.price, b.time_ms, "tick", "both levels in one minute; order resolved from ticks"),
                    checked,
                )
        reason = {"target_hit": "take_profit_hit", "target_gap": "take_profit_hit"}.get(r.reason, r.reason)
        return ScanResult(Breach(reason, float(r.price), open_ms, "1m", r.note), checked)
    return ScanResult(None, checked, seen, expected)  # only advanced by bars actually seen: no data != no breach


@dataclass(frozen=True)
class PendingPartial:
    time_ms: int
    price: float
    step: PartialTpStep


@dataclass(frozen=True)
class PendingReinforce:
    time_ms: int
    price: float
    r_multiple: float


@dataclass(frozen=True)
class ManageScanResult:
    breach: Breach | None
    checked_through_ms: int
    new_stop: float
    bars_seen: int = 0
    bars_expected: int = 0
    partials: tuple[PendingPartial, ...] = ()
    reinforces: tuple[PendingReinforce, ...] = ()
    reinforce_prev_match: bool = False


def _hit_stop_only(direction: str, stop: float, high: float, low: float) -> bool:
    long = direction.upper() == "LONG"
    return (low <= stop) if long else (high >= stop)


def _hit_target_only(direction: str, target: float, high: float, low: float) -> bool:
    long = direction.upper() == "LONG"
    return (high >= target) if long else (low <= target)


def find_breach_manage(
    direction: str,
    stop: float,
    target: float,
    *,
    entry: float,
    trail_cfg: PaperTrailConfig | None,
    partial_cfg: PaperPartialTpConfig | None,
    pending: Sequence[PartialTpStep],
    reinforce_cfg: PaperReinforceConfig | None = None,
    adds_already: int = 0,
    reinforce_prev: bool = False,
    open_qty: float | None = None,
    open_notional: float | None = None,
    equity: float | None = None,
    spread_bps: float = 0.0,
    slippage_bps: float = 0.0,
    symbol: str,
    since_ms: int,
    until_ms: int,
    klines_fn: KlinesFn,
    trades_fn: TradesFn | None,
) -> ManageScanResult:
    """Bar-by-bar: stop > partials (asc R) > target > reinforce > trail.

    Same no-lookahead contract as Lab / trail path. Reinforce uses rising-edge
    ``at_r_multiple`` on frozen ``initial_entry``; stop is simulated forward
    after each add with the same entry-friction fill as the broker.
    """
    dir_enum = _direction_enum(direction)
    minute0 = since_ms - since_ms % MINUTE_MS
    checked = since_ms
    cur_stop = stop
    remaining_steps = list(pending)
    found_partials: list[PendingPartial] = []
    found_reinforces: list[PendingReinforce] = []
    adds_done_n = int(adds_already)
    rf_prev = bool(reinforce_prev)
    sim_avg = float(entry)
    if reinforce_cfg is not None:
        sim_qty = (
            float(open_qty)
            if open_qty is not None and open_qty > 0
            else float(reinforce_cfg.initial_qty)
        )
        sim_notional = (
            float(open_notional)
            if open_notional is not None and open_notional > 0
            else sim_qty * sim_avg
        )
        sim_equity = float(equity) if equity is not None and equity > 0 else sim_notional
    else:
        sim_qty = 0.0
        sim_notional = 0.0
        sim_equity = 0.0

    if since_ms % MINUTE_MS:
        entry_minute_end = minute0 + MINUTE_MS
        start = entry_minute_end
        if trades_fn is not None and entry_minute_end <= until_ms:
            ticks = [
                (t, p)
                for t, p in trades_fn(symbol, since_ms, entry_minute_end)
                if t >= since_ms
            ]
            # Ticks: stop only (conservative); no partial/reinforce from incomplete minute.
            b = _scan_ticks(direction, cur_stop, target, ticks)
            if b and b.reason.startswith("stop"):
                return ManageScanResult(b, entry_minute_end, cur_stop)
            checked = entry_minute_end
            if ticks and trail_cfg is not None:
                highs = max(p for _, p in ticks)
                lows = min(p for _, p in ticks)
                close = ticks[-1][1]
                cur_stop = update_trailing_stop(
                    dir_enum,
                    cur_stop,
                    entry=sim_avg if reinforce_cfg is not None else entry,
                    initial_stop=trail_cfg.initial_stop,
                    high=highs,
                    low=lows,
                    close=close,
                    atr=trail_cfg.atr_ref,
                    trail=trail_cfg.trail,
                    commission_bps=trail_cfg.commission_bps,
                    slippage_bps=trail_cfg.slippage_bps,
                )
    else:
        start = minute0

    end_closed = until_ms - until_ms % MINUTE_MS
    if start >= end_closed:
        return ManageScanResult(
            None,
            max(checked, min(start, end_closed)),
            cur_stop,
            partials=tuple(found_partials),
            reinforces=tuple(found_reinforces),
            reinforce_prev_match=rf_prev,
        )

    rows = klines_fn(symbol, start, end_closed)
    expected = (end_closed - start) // MINUTE_MS
    seen = 0
    for k in rows:
        open_ms = int(k[0])
        if open_ms < start or open_ms + MINUTE_MS > end_closed:
            continue
        seen += 1
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        checked = open_ms + MINUTE_MS

        # 1) Stop first
        if _hit_stop_only(direction, cur_stop, h, l):
            gapped = (o < cur_stop) if direction.upper() == "LONG" else (o > cur_stop)
            reason = "stop_gap" if gapped else "stop_hit"
            price = float(o) if gapped else float(cur_stop)
            return ManageScanResult(
                Breach(reason, price, open_ms, "1m", ""),
                checked,
                cur_stop,
                seen,
                expected,
                tuple(found_partials),
                tuple(found_reinforces),
                rf_prev,
            )

        # 2) Partials ascending R
        while remaining_steps and partial_cfg is not None:
            step = remaining_steps[0]
            if not bar_hits_step(direction, entry, partial_cfg, step, h, l):
                break
            level = level_for_step(direction, entry, partial_cfg, step)
            found_partials.append(PendingPartial(open_ms, level, step))
            remaining_steps.pop(0)

        # If all scale-outs fired, no target left to chase this cycle
        if partial_cfg is not None and not remaining_steps and found_partials:
            # May still have remainder qty if sum(fractions) < 1 — fall through to target
            pass

        # 3) Target on remainder
        if _hit_target_only(direction, target, h, l):
            gapped = (o > target) if direction.upper() == "LONG" else (o < target)
            reason = "take_profit_hit"
            price = float(o) if gapped else float(target)
            return ManageScanResult(
                Breach(reason, price, open_ms, "1m", "target_gap" if gapped else ""),
                checked,
                cur_stop,
                seen,
                expected,
                tuple(found_partials),
                tuple(found_reinforces),
                rf_prev,
            )

        # 4) Reinforce (rising-edge at_r on frozen initial_entry) — before trail
        if (
            reinforce_cfg is not None
            and adds_done_n < reinforce_cfg.max_adds
        ):
            hit = bar_hits_reinforce(direction, reinforce_cfg, h, l)
            rising = hit and not rf_prev
            rf_prev = hit
            if rising:
                level = level_for_reinforce(direction, reinforce_cfg)
                # Same fill as broker.reinforce_add_capital_position
                fill = apply_entry_friction(
                    level,
                    direction=direction.upper(),
                    spread_bps=spread_bps,
                    slippage_bps=slippage_bps,
                )
                requested = cap_add_by_notional_equity(
                    open_notional=sim_notional,
                    requested_add_qty=float(reinforce_cfg.initial_qty)
                    * float(reinforce_cfg.add_fraction),
                    fill_price=float(fill),
                    equity=sim_equity,
                    max_exposure=float(reinforce_cfg.max_exposure),
                )
                if requested > 1e-15:
                    actual, sim_avg, new_stop, sim_qty, _clamped = apply_reinforce_add(
                        direction=dir_enum,
                        avg_entry=sim_avg,
                        qty=sim_qty,
                        stop=cur_stop,
                        add_price=float(fill),
                        requested_add=requested,
                        initial_risk=float(reinforce_cfg.initial_risk),
                        policy=reinforce_cfg.risk_policy,
                    )
                    if actual > 1e-15:
                        found_reinforces.append(
                            PendingReinforce(
                                open_ms, float(level), reinforce_cfg.at_r_multiple
                            )
                        )
                        adds_done_n += 1
                        cur_stop = new_stop
                        sim_notional = sim_qty * sim_avg
        elif reinforce_cfg is not None:
            rf_prev = bar_hits_reinforce(direction, reinforce_cfg, h, l)

        # 5) Trail after checks
        if trail_cfg is not None:
            cur_stop = update_trailing_stop(
                dir_enum,
                cur_stop,
                entry=sim_avg if reinforce_cfg is not None else entry,
                initial_stop=trail_cfg.initial_stop,
                high=h,
                low=l,
                close=c,
                atr=trail_cfg.atr_ref,
                trail=trail_cfg.trail,
                commission_bps=trail_cfg.commission_bps,
                slippage_bps=trail_cfg.slippage_bps,
            )

    return ManageScanResult(
        None,
        checked,
        cur_stop,
        seen,
        expected,
        tuple(found_partials),
        tuple(found_reinforces),
        rf_prev,
    )


def _load_partial_exits(session: Session, position_id: str) -> list[PaperPartialExit]:
    return list(
        session.execute(
            select(PaperPartialExit)
            .where(PaperPartialExit.position_id == position_id)
            .order_by(PaperPartialExit.seq)
        ).scalars()
    )


def _load_reinforce_adds(session: Session, position_id: str) -> list[PaperReinforceAdd]:
    return list(
        session.execute(
            select(PaperReinforceAdd)
            .where(PaperReinforceAdd.position_id == position_id)
            .order_by(PaperReinforceAdd.seq)
        ).scalars()
    )


def _direction_enum(direction: str) -> Direction:
    return Direction.LONG if direction.upper() == "LONG" else Direction.SHORT


def find_breach_with_trail(
    direction: str,
    stop: float,
    target: float,
    *,
    entry: float,
    config: PaperTrailConfig,
    symbol: str,
    since_ms: int,
    until_ms: int,
    klines_fn: KlinesFn,
    trades_fn: TradesFn | None,
) -> tuple[ScanResult, float]:
    """Bar-by-bar: check exit at current stop, then ratchet via ``stop_trail``.

    Same no-lookahead contract as Lab: trail update runs after the bar's exit
    check so the new stop applies from the next bar. Returns ``(scan, stop)``
    where ``stop`` is the (possibly ratcheted) level after all clear bars.
    """
    dir_enum = _direction_enum(direction)
    minute0 = since_ms - since_ms % MINUTE_MS
    checked = since_ms
    cur_stop = stop

    if since_ms % MINUTE_MS:
        entry_minute_end = minute0 + MINUTE_MS
        if trades_fn is not None and entry_minute_end <= until_ms:
            ticks = [
                (t, p)
                for t, p in trades_fn(symbol, since_ms, entry_minute_end)
                if t >= since_ms
            ]
            b = _scan_ticks(direction, cur_stop, target, ticks)
            if b:
                return ScanResult(b, entry_minute_end), cur_stop
            if ticks:
                highs = max(p for _, p in ticks)
                lows = min(p for _, p in ticks)
                close = ticks[-1][1]
                cur_stop = update_trailing_stop(
                    dir_enum,
                    cur_stop,
                    entry=entry,
                    initial_stop=config.initial_stop,
                    high=highs,
                    low=lows,
                    close=close,
                    atr=config.atr_ref,
                    trail=config.trail,
                    commission_bps=config.commission_bps,
                    slippage_bps=config.slippage_bps,
                )
            checked = entry_minute_end
        start = entry_minute_end
    else:
        start = minute0

    end_closed = until_ms - until_ms % MINUTE_MS
    if start >= end_closed:
        return ScanResult(None, max(checked, min(start, end_closed))), cur_stop

    rows = klines_fn(symbol, start, end_closed)
    expected = (end_closed - start) // MINUTE_MS
    seen = 0
    for k in rows:
        open_ms = int(k[0])
        if open_ms < start or open_ms + MINUTE_MS > end_closed:
            continue
        seen += 1
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        r = resolve_bar_exit(direction, cur_stop, target, o, h, l)
        checked = open_ms + MINUTE_MS
        if r.reason is not None:
            if "both inside bar" in r.note and trades_fn is not None:
                ticks = list(trades_fn(symbol, open_ms, open_ms + MINUTE_MS))
                b = _scan_ticks(direction, cur_stop, target, ticks)
                if b:
                    return (
                        ScanResult(
                            Breach(
                                b.reason,
                                b.price,
                                b.time_ms,
                                "tick",
                                "both levels in one minute; order resolved from ticks",
                            ),
                            checked,
                        ),
                        cur_stop,
                    )
            reason = {
                "target_hit": "take_profit_hit",
                "target_gap": "take_profit_hit",
            }.get(r.reason, r.reason)
            return (
                ScanResult(Breach(reason, float(r.price), open_ms, "1m", r.note), checked),
                cur_stop,
            )

        cur_stop = update_trailing_stop(
            dir_enum,
            cur_stop,
            entry=entry,
            initial_stop=config.initial_stop,
            high=h,
            low=l,
            close=c,
            atr=config.atr_ref,
            trail=config.trail,
            commission_bps=config.commission_bps,
            slippage_bps=config.slippage_bps,
        )

    return ScanResult(None, checked, seen, expected), cur_stop


def _persist_trail_stop(
    session: Session,
    pos: PaperPosition,
    old_stop: float,
    new_stop: float,
    *,
    now: datetime,
    through_ms: int,
) -> None:
    """Ratchet-only write: stop never moves against the position."""
    long = pos.direction.upper() == "LONG"
    if long and new_stop < old_stop:
        return
    if not long and new_stop > old_stop:
        return
    if new_stop == old_stop:
        return
    pos.stop_price = new_stop
    session.add(
        PaperJournalEvent(
            portfolio_id=pos.portfolio_id,
            position_id=pos.id,
            event_type=TRAIL_EVENT,
            payload={
                "from": old_stop,
                "to": new_stop,
                "through_ms": through_ms,
            },
            created_at=now,
        )
    )


# ── Binance data access ─────────────────────────────────────────────────────

def binance_klines_1m(symbol: str, start_ms: int, end_ms: int) -> list[list[Any]]:
    out: list[list[Any]] = []
    cur = start_ms
    while cur < end_ms:
        r = httpx.get(
            f"{BASE_URL}/api/v3/klines",
            params={"symbol": symbol, "interval": "1m", "startTime": cur, "endTime": end_ms - 1, "limit": 1000},
            timeout=20.0,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend(rows)
        cur = int(rows[-1][0]) + MINUTE_MS
        if len(rows) < 1000:
            break
    return out


def binance_agg_trades(symbol: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """Aggregated trades in [start_ms, end_ms). First page by time, next pages by ``fromId``
    (Binance forbids mixing both) so trades sharing a millisecond are never skipped."""
    out: list[tuple[int, float]] = []
    params: dict[str, Any] = {"symbol": symbol, "startTime": start_ms, "endTime": end_ms - 1, "limit": 1000}
    for _ in range(50):
        r = httpx.get(f"{BASE_URL}/api/v3/aggTrades", params=params, timeout=20.0)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        out.extend((int(x["T"]), float(x["p"])) for x in rows if start_ms <= int(x["T"]) < end_ms)
        if len(rows) < 1000 or int(rows[-1]["T"]) >= end_ms - 1:
            break
        params = {"symbol": symbol, "fromId": int(rows[-1]["a"]) + 1, "limit": 1000}
    return out


# ── Cycle over open positions ───────────────────────────────────────────────

def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _events(session: Session, position: PaperPosition, event_type: str) -> list[PaperJournalEvent]:
    return list(
        session.execute(
            select(PaperJournalEvent)
            .where(PaperJournalEvent.position_id == position.id, PaperJournalEvent.event_type == event_type)
            .order_by(PaperJournalEvent.created_at)
        ).scalars()
    )


def _seed(session: Session, position: PaperPosition) -> tuple[int | None, bool]:
    """(since_ms, is_legacy). Positions whose OPENED event declares monitoring
    start at their entry time; older ones are legacy (no closing from history)."""
    checks = _events(session, position, CHECK_EVENT)
    if checks:
        return int(checks[-1].payload["through_ms"]), bool(checks[-1].payload.get("legacy", False))
    opened = _events(session, position, "OPENED")
    if opened and (opened[-1].payload or {}).get("protection_monitored"):
        return _ms(position.entry_time), False
    return None, True


def _write_check(session: Session, position: PaperPosition, through_ms: int, legacy: bool, now: datetime) -> None:
    session.add(
        PaperJournalEvent(
            portfolio_id=position.portfolio_id,
            position_id=position.id,
            event_type=CHECK_EVENT,
            payload={"through_ms": through_ms, "legacy": legacy},
            created_at=now,
        )
    )


_FAILS: dict[str, int] = {}
FAIL_ALERT_AFTER = 5
NO_DATA_AFTER_MS = 5 * MINUTE_MS


def _report_breach(b: Breach) -> dict[str, Any]:
    return {
        "reason": b.reason, "price": b.price, "at": datetime.fromtimestamp(b.time_ms / 1000, timezone.utc).isoformat(),
        "granularity": b.granularity, "note": b.note,
    }


def _process_position(
    session: Session, pos: PaperPosition, row: dict[str, Any], *, klines_fn: KlinesFn, trades_fn: TradesFn | None,
    now: datetime, now_ms: int, dry_run: bool, enforce_legacy: bool,
) -> None:
    row.update(symbol=pos.symbol, source=pos.source)
    if not pos.qty or pos.stop_price is None or pos.take_profit_price is None:
        row["status"] = "unprotected_legacy_no_levels"
        return
    inst = get_instrument(pos.symbol)
    if inst is None or inst.provider != "binance" or not inst.provider_symbol:
        row["status"] = "unsupported_provider"
        return

    since_ms, legacy = _seed(session, pos)
    if since_ms is None:
        # Legacy lot, first sight: report what history says, never act on it; watermark = now.
        # Trail is never applied to historical reconstruction (gate: no default on history).
        hist = find_first_breach(
            pos.direction, pos.stop_price, pos.take_profit_price, symbol=inst.provider_symbol,
            since_ms=_ms(pos.entry_time), until_ms=now_ms, klines_fn=klines_fn, trades_fn=trades_fn,
        )
        row["status"] = "legacy_watermark_initialised"
        row["history_breach"] = None if hist.breach is None else _report_breach(hist.breach)
        if not dry_run:
            _write_check(session, pos, now_ms - now_ms % MINUTE_MS, True, now)
        return

    portfolio = session.get(PaperPortfolio, pos.portfolio_id)
    trail_cfg = None if legacy else resolve_paper_trail(pos, portfolio)
    partial_cfg = None if legacy else resolve_paper_partial_tp(pos, portfolio)
    reinforce_cfg = None if legacy else resolve_paper_reinforce(pos, portfolio)

    if trail_cfg is not None and not dry_run:
        freeze_trail_anchor(pos, trail_cfg)
        trail_cfg = resolve_paper_trail(pos, portfolio) or trail_cfg
    if partial_cfg is not None and not dry_run:
        freeze_partial_tp_anchor(pos, partial_cfg)
        partial_cfg = resolve_paper_partial_tp(pos, portfolio) or partial_cfg
    if reinforce_cfg is not None and not dry_run:
        freeze_reinforce_anchor(pos, reinforce_cfg)
        reinforce_cfg = resolve_paper_reinforce(pos, portfolio) or reinforce_cfg
    # Align R-base with trail's frozen initial_stop when both are active.
    if trail_cfg is not None:
        from dataclasses import replace as _dc_replace

        if partial_cfg is not None and abs(partial_cfg.initial_stop - trail_cfg.initial_stop) > 1e-12:
            partial_cfg = _dc_replace(partial_cfg, initial_stop=trail_cfg.initial_stop)
        if (
            reinforce_cfg is not None
            and abs(reinforce_cfg.initial_stop - trail_cfg.initial_stop) > 1e-12
        ):
            reinforce_cfg = _dc_replace(reinforce_cfg, initial_stop=trail_cfg.initial_stop)

    use_manage = partial_cfg is not None or reinforce_cfg is not None
    manage: ManageScanResult | None = None
    scan: ScanResult | None = None
    new_stop = float(pos.stop_price)
    scan_breach: Breach | None
    bars_seen = 0
    bars_expected = 0
    checked_through = since_ms

    if use_manage:
        existing_partials = _load_partial_exits(session, pos.id) if partial_cfg else []
        pending = (
            pending_steps(partial_cfg, fired_r_multiples(existing_partials))
            if partial_cfg is not None
            else []
        )
        existing_adds = _load_reinforce_adds(session, pos.id) if reinforce_cfg else []
        eq = None
        spr = 0.0
        slp = 0.0
        if reinforce_cfg is not None and portfolio is not None:
            eq = paper_broker.estimate_equity(session, portfolio)
            spr, slp = paper_broker.portfolio_friction_bps(portfolio, pos.symbol)
        manage = find_breach_manage(
            pos.direction,
            float(pos.stop_price),
            float(pos.take_profit_price),
            entry=float(pos.entry_price),
            trail_cfg=trail_cfg,
            partial_cfg=partial_cfg,
            pending=pending,
            reinforce_cfg=reinforce_cfg,
            adds_already=reinforce_adds_done(existing_adds),
            reinforce_prev=reinforce_prev_match(pos) if reinforce_cfg else False,
            open_qty=float(pos.qty) if pos.qty else None,
            open_notional=float(pos.notional) if pos.notional else None,
            equity=eq,
            spread_bps=spr,
            slippage_bps=slp,
            symbol=inst.provider_symbol,
            since_ms=since_ms,
            until_ms=now_ms,
            klines_fn=klines_fn,
            trades_fn=trades_fn,
        )
        new_stop = manage.new_stop
        row["checked_through_ms"] = manage.checked_through_ms
        scan_breach = manage.breach
        bars_seen, bars_expected = manage.bars_seen, manage.bars_expected
        checked_through = manage.checked_through_ms
    elif trail_cfg is not None:
        scan, new_stop = find_breach_with_trail(
            pos.direction,
            float(pos.stop_price),
            float(pos.take_profit_price),
            entry=float(pos.entry_price),
            config=trail_cfg,
            symbol=inst.provider_symbol,
            since_ms=since_ms,
            until_ms=now_ms,
            klines_fn=klines_fn,
            trades_fn=trades_fn,
        )
        row["checked_through_ms"] = scan.checked_through_ms
        scan_breach = scan.breach
        bars_seen, bars_expected = scan.bars_seen, scan.bars_expected
        checked_through = scan.checked_through_ms
    else:
        scan = find_first_breach(
            pos.direction, pos.stop_price, pos.take_profit_price, symbol=inst.provider_symbol,
            since_ms=since_ms, until_ms=now_ms, klines_fn=klines_fn, trades_fn=trades_fn,
        )
        row["checked_through_ms"] = scan.checked_through_ms
        scan_breach = scan.breach
        bars_seen, bars_expected = scan.bars_seen, scan.bars_expected
        checked_through = scan.checked_through_ms

    # Apply newly discovered partials (before any full close).
    applied_partials = 0
    if manage is not None and manage.partials and partial_cfg is not None:
        row["partials"] = [
            {
                "r_multiple": p.step.r_multiple,
                "fraction": p.step.fraction,
                "price": p.price,
                "at_ms": p.time_ms,
            }
            for p in manage.partials
        ]
        if dry_run:
            row["status"] = "would_partial" if scan_breach is None else "would_partial_then_close"
        elif not (legacy and not enforce_legacy):
            for pend in manage.partials:
                if pos.status != "OPEN" or not pos.qty:
                    break
                q = qty_for_step(partial_cfg, pend.step, float(pos.qty))
                if q <= 0:
                    continue
                at = datetime.fromtimestamp(pend.time_ms / 1000, timezone.utc)
                paper_broker.partial_close_capital_position(
                    session,
                    pos,
                    price=pend.price,
                    qty=q,
                    fraction=pend.step.fraction,
                    r_multiple=pend.step.r_multiple,
                    reason="partial_tp",
                    signal={
                        "protection": {
                            "reason": "partial_tp",
                            "r_multiple": pend.step.r_multiple,
                            "fraction": pend.step.fraction,
                        }
                    },
                    at=at,
                    time_ms=pend.time_ms,
                )
                applied_partials += 1
            if applied_partials:
                row["partials_applied"] = applied_partials

    # Apply newly discovered reinforces (after partials; before full close).
    applied_reinforces = 0
    if manage is not None and reinforce_cfg is not None:
        if manage.reinforces:
            row["reinforces"] = [
                {
                    "r_multiple": r.r_multiple,
                    "price": r.price,
                    "at_ms": r.time_ms,
                }
                for r in manage.reinforces
            ]
            if dry_run:
                if "status" not in row or row.get("status") in (None, "ok"):
                    row["status"] = (
                        "would_reinforce"
                        if scan_breach is None
                        else "would_reinforce_then_close"
                    )
            elif not (legacy and not enforce_legacy):
                for pend in manage.reinforces:
                    if pos.status != "OPEN" or not pos.qty:
                        break
                    at = datetime.fromtimestamp(pend.time_ms / 1000, timezone.utc)
                    added = paper_broker.reinforce_add_capital_position(
                        session,
                        pos,
                        price=pend.price,
                        add_fraction=reinforce_cfg.add_fraction,
                        r_multiple=pend.r_multiple,
                        initial_qty=reinforce_cfg.initial_qty,
                        initial_risk=reinforce_cfg.initial_risk,
                        max_exposure=reinforce_cfg.max_exposure,
                        risk_policy=reinforce_cfg.risk_policy,
                        reason="reinforce",
                        signal={
                            "protection": {
                                "reason": "reinforce",
                                "r_multiple": pend.r_multiple,
                                "fraction": reinforce_cfg.add_fraction,
                            }
                        },
                        at=at,
                        time_ms=pend.time_ms,
                    )
                    if added is not None:
                        applied_reinforces += 1
                if applied_reinforces:
                    row["reinforces_applied"] = applied_reinforces
                    # Broker stop is authoritative; keep scan stop only if trail may have
                    # ratcheted further after the add within the same walk.
                    new_stop = (
                        manage.new_stop
                        if trail_cfg is not None
                        else float(pos.stop_price)
                    )
        if not dry_run:
            if manage.reinforces and applied_reinforces == 0:
                # Broker refused (cash / exposure / risk) — do not consume rising edge.
                pass
            else:
                persist_reinforce_prev_match(pos, manage.reinforce_prev_match)

    if scan_breach is None:
        if bars_seen == 0 and bars_expected >= 5:
            row["status"] = "no_data"
            return
        if pos.status == "CLOSED":
            row["status"] = "closed"
            if not dry_run:
                _write_check(session, pos, checked_through, legacy, now)
            return
        if applied_partials and applied_reinforces:
            row["status"] = "partialed_reinforced"
        elif applied_partials:
            row["status"] = "partialed"
        elif applied_reinforces:
            row["status"] = "reinforced"
        else:
            row["status"] = "ok"
        if trail_cfg is not None and new_stop != float(pos.stop_price) and pos.status == "OPEN":
            old = float(pos.stop_price)
            row["trail_stop"] = {"from": old, "to": new_stop}
            if not dry_run:
                _persist_trail_stop(
                    session, pos, old, new_stop, now=now, through_ms=checked_through,
                )
        if not dry_run:
            # Trail / manage path always advances watermark (no re-walk against ratcheted state).
            if (
                trail_cfg is not None
                or partial_cfg is not None
                or reinforce_cfg is not None
                or now_ms - since_ms >= CHECK_EVENT_EVERY_MS
            ):
                _write_check(session, pos, checked_through, legacy, now)
        return

    b = scan_breach
    row["breach"] = _report_breach(b)
    if legacy and not enforce_legacy:
        row["status"] = "legacy_report_only"
        return
    if dry_run:
        row["status"] = "would_close"
        return
    if pos.status != "OPEN" or not pos.qty:
        row["status"] = "closed" if pos.status == "CLOSED" else "already_closed_elsewhere"
        if not dry_run:
            _write_check(session, pos, checked_through, legacy, now)
        return
    at = datetime.fromtimestamp(b.time_ms / 1000, timezone.utc)
    paper_broker.close_capital_position(
        session, pos, price=b.price, reason=b.reason,
        signal={"protection": {"reason": b.reason, "trigger_price": b.price, "breach_at": at.isoformat(),
                               "granularity": b.granularity, "note": b.note}},
        at=at,
    )
    row["status"] = "closed" if pos.status == "CLOSED" else "already_closed_elsewhere"
    if not dry_run and (
        trail_cfg is not None or partial_cfg is not None or reinforce_cfg is not None
    ):
        _write_check(session, pos, checked_through, legacy, now)


def run_protection_cycle(
    session: Session,
    *,
    klines_fn: KlinesFn = binance_klines_1m,
    trades_fn: TradesFn | None = binance_agg_trades,
    now: datetime | None = None,
    dry_run: bool = False,
    enforce_legacy: bool = False,
) -> list[dict[str, Any]]:
    """Check every open protected position; one report row each.

    Isolation: each position is processed in its own try/except and committed on its own, so one
    failing symbol (HTTP 400/429, bad data) never aborts or rolls back the others. ``dry_run`` scans
    and reports but writes and closes nothing. Legacy lots are report-only unless ``enforce_legacy``."""
    now = now or datetime.now(timezone.utc)
    now_ms = _ms(now)
    report: list[dict[str, Any]] = []
    session.flush()
    ids = [
        r[0] for r in session.execute(
            select(PaperPosition.id).where(PaperPosition.status == "OPEN").order_by(PaperPosition.entry_time)
        ).all()
    ]
    for pid in ids:
        row: dict[str, Any] = {"id": pid, "status": "skipped"}
        report.append(row)
        try:
            pos = session.get(PaperPosition, pid, populate_existing=True)  # fresh state per position
            if pos is None or pos.status != "OPEN":
                row["status"] = "no_longer_open"
                continue
            _process_position(
                session, pos, row, klines_fn=klines_fn, trades_fn=trades_fn, now=now, now_ms=now_ms,
                dry_run=dry_run, enforce_legacy=enforce_legacy,
            )
            if not dry_run:
                session.commit()
            _FAILS.pop(pid, None)
        except Exception as exc:  # noqa: BLE001 -- isolate: never let one position stop the others
            session.rollback()
            row.update(status="error", error=repr(exc)[:200])
            n = _FAILS[pid] = _FAILS.get(pid, 0) + 1
            logger.warning("protection: %s failed (%d consecutive): %r", pid, n, exc)
            if n == FAIL_ALERT_AFTER and not dry_run:
                try:
                    p2 = session.get(PaperPosition, pid)
                    session.add(PaperJournalEvent(
                        portfolio_id=p2.portfolio_id if p2 else None, position_id=pid, event_type="PROTECTION_ERROR",
                        payload={"consecutive_failures": n, "error": repr(exc)[:200]}, created_at=now,
                    ))
                    session.commit()
                except Exception:  # noqa: BLE001
                    session.rollback()
    return report


class ProtectionMonitor:
    """Background loop: checks protections every ``interval_s`` between candle closes."""

    def __init__(self, interval_s: float = 60.0) -> None:
        import threading

        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Any = None
        self._threading = threading

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = self._threading.Thread(target=self._loop, daemon=True, name="protection-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        from app.db.session import SessionLocal

        while not self._stop.is_set():
            session = SessionLocal()
            try:
                from app.paper.financing import apply_financing_all_portfolios

                n_fin = apply_financing_all_portfolios(session)
                if n_fin:
                    logger.info("financing: applied %s overnight charge(s)", n_fin)
                for row in run_protection_cycle(session):
                    if row["status"] in ("closed", "legacy_watermark_initialised"):
                        logger.info("protection: %s", row)
            except Exception:  # noqa: BLE001 -- a failed cycle must not kill the loop
                logger.warning("protection cycle failed", exc_info=True)
                session.rollback()
            finally:
                session.close()
            self._stop.wait(self.interval_s)


protection_monitor = ProtectionMonitor()


def _cli() -> None:
    """One-shot run: ``python -m app.paper.protection --dry-run`` (report only) or ``--apply``."""
    import argparse
    import json

    from app.db.session import SessionLocal

    ap = argparse.ArgumentParser(description="Check stops/targets of open paper positions once.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="scan and report, write/close nothing")
    mode.add_argument("--apply", action="store_true", help="enforce breaches and write watermarks")
    ap.add_argument("--enforce-legacy", action="store_true", help="also close legacy lots on breaches after their watermark (default: report only)")
    args = ap.parse_args()
    session = SessionLocal()
    try:
        print(json.dumps(run_protection_cycle(session, dry_run=args.dry_run, enforce_legacy=args.enforce_legacy), indent=1, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    _cli()
