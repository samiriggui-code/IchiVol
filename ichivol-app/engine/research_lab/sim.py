"""Closed-candle portfolio simulator (paper only, candle_only execution model).

Execution model (documented hypotheses, identical for every variant):
  * decisions use bars that are fully closed; an order decided at the close of
    bar t is filled at the OPEN of bar t+1 (latency >= 1 bar), never better;
  * fills carry adverse friction (spread+slippage bps, same formula as
    app/paper/risk.py: long pays up, short sells down); commission is a
    separate cash leg. Spread lives only in the fill price -> counted once;
  * stop/target are checked on each bar's high/low AFTER the entry instant; if
    both are inside one bar the STOP is assumed first (prudent); a bar that
    opens beyond a level fills at the open (gap), not at the level;
  * signal exits (decision no longer supports the position) fill at the next open;
  * every cash movement is posted to app.brokerage.ledger.Ledger (idempotent
    keys) and reconciled against the simulator's cash at the end.
Never places an order: it only reads cached public market data.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from app.brokerage.ledger import Cause, Leg, Ledger
from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal

CCY = "EUR"  # USDT treated as EUR proxy, same as the live paper broker


@dataclass(frozen=True)
class CostModel:
    name: str
    commission_bps: float  # per side, on notional
    spread_bps: float  # per side, embedded in the fill price
    slippage_bps: float  # per side, embedded in the fill price
    short_financing_bps_per_day: float = 0.0
    min_commission: float = 0.0  # Binance spot has no minimum fee


BASE_COST = CostModel("base", 5.0, 2.0, 3.0)  # = ICHIVOL_BASELINE_V1 profile
# 0.10% standard spot fee (no BNB discount), wider spread, ~2.7x slippage, shorts pay financing
ADVERSE_COST = CostModel("adverse", 10.0, 4.0, 8.0, short_financing_bps_per_day=3.0)


def scaled_cost(mult: float) -> CostModel:
    return CostModel(f"x{mult:g}", 5.0 * mult, 2.0 * mult, 3.0 * mult)


@dataclass(frozen=True)
class Rules:
    name: str
    risk_pct: float = 0.01
    take_profit_r: float = 2.0
    max_open: int = 5
    max_notional_pct: float = 0.25  # per order (current baseline rule)
    max_symbol_notional_pct: float = 0.25  # aggregate per instrument (research hypothesis)
    max_open_risk_pct: float = 0.04  # cumulative risk to stops (research hypothesis)
    daily_loss_limit_pct: float = 0.03  # halt new entries for the UTC day (research hypothesis)
    one_entry_per_signal_run: bool = True
    allow_short: bool = True
    liquidity_cap_pct: float = 0.02  # order notional <= 2% of entry-bar quote volume
    min_notional: float = 10.0
    # C-type hook: maps a bar signal to the decision actually used ("BUY"/"SELL"/other)
    decision_hook: Callable[[BarSignal], str] | None = field(default=None, compare=False)
    hook_label: str = ""
    # exit rule: "decision" = baseline (leave when the effective decision stops supporting the position);
    # "direction" = leave only on stop/target or when the Ichimoku direction no longer matches (experiment E);
    # "levels_only" = VP2 common exit — stop / TP / time-stop only (never pipeline/direction flip)
    exit_mode: str = "decision"
    # live-replica mode: decide and fill in the same step at the step's price (old intrabar behaviour)
    immediate_fill: bool = False
    bar_seconds: int = 3600
    # VP2 §6 time-stop: close at bar close after N bars held (None = disabled)
    time_stop_bars: int | None = None
    # VP2 §6: size = 100 % of available cash (1 position); stop_distance still sets SL/TP levels
    full_cash: bool = False
    # VP §5.1.8: force exit open positions at the last bar's close
    force_flat_at_end: bool = False


@dataclass
class Trade:
    symbol: str
    direction: str
    signal_time: int
    entry_time: int
    exit_time: int
    entry_raw: float
    exit_raw: float
    entry_fill: float
    exit_fill: float
    qty: float
    notional: float
    risk_amount: float
    gross: float  # raw-price pnl before every cost
    commission: float
    friction_cost: float  # spread+slippage embedded in fills (informational, NOT deducted twice)
    financing: float
    net: float
    exit_reason: str
    stop_gap: bool = False


@dataclass
class Position:
    symbol: str
    direction: str
    signal_time: int
    entry_time: int
    entry_raw: float
    entry_fill: float
    qty: float
    notional: float
    entry_fee: float
    stop: float
    tp: float
    risk_amount: float
    pid: str


def _dec(x: float) -> Decimal:
    return round(Decimal(repr(float(x))), 8)


def _ts(sec: int) -> datetime:
    return datetime.fromtimestamp(sec, timezone.utc)


def _fill(raw: float, direction: str, side: str, cost: CostModel) -> float:
    """side 'in' or 'out'; always adverse for the taker."""
    f = (cost.spread_bps + cost.slippage_bps) / 10_000.0
    buy = (direction == "LONG") == (side == "in")
    return raw * (1 + f) if buy else raw * (1 - f)


def _fee(notional: float, cost: CostModel) -> float:
    return max(notional * cost.commission_bps / 10_000.0, cost.min_commission if notional > 0 else 0.0)


@dataclass
class RunResult:
    rules: Rules
    cost: CostModel
    window: tuple[int, int]
    symbols: list[str]
    initial: float
    trades: list[Trade]
    equity: list[tuple[int, float, float]]  # (bar_time, equity, gross_exposure)
    rejections: Counter
    signals_seen: int
    open_at_end: list[dict]
    ledger_diff: dict
    cash_end: float
    ledger: Ledger = field(repr=False, default=None)


def simulate(
    data: dict[str, dict[int, tuple[Candle, BarSignal]]],
    rules: Rules,
    cost: CostModel,
    window: tuple[int, int],
    initial: float = 5000.0,
    seed: int = 7,
) -> RunResult:
    """data[symbol][bar_open_time_s] = (closed candle, signal computed at that bar's close).
    window = [start_s, end_s): bars with open time inside are traded."""
    symbols = sorted(data)
    times = sorted({t for s in symbols for t in data[s] if window[0] <= t < window[1]})
    rng = random.Random(seed)
    ledger = Ledger()
    ledger.post("deposit", _ts(times[0]), [Leg(CCY, _dec(initial), Cause.DEPOSIT, "initial capital")])
    cash = initial
    positions: dict[str, Position] = {}
    pending_exit: dict[str, str] = {}
    pending_entry: dict[str, tuple[BarSignal, str]] = {}
    pending_risk: dict[str, float] = {}
    trades: list[Trade] = []
    equity_curve: list[tuple[int, float, float]] = []
    rej: Counter = Counter()
    seen = 0
    last_close: dict[str, float] = {}
    run_state: dict[str, tuple[str, int]] = {}
    entered_runs: set[tuple[str, int]] = set()
    day_key = None
    day_start_equity = initial
    halted_day = False
    pid_n = 0

    def eff(sig: BarSignal) -> str:
        return rules.decision_hook(sig) if rules.decision_hook else sig.decision

    def equity_now() -> float:
        v = cash
        for p in positions.values():
            px = last_close.get(p.symbol, p.entry_fill)
            v += p.qty * px if p.direction == "LONG" else p.notional + p.qty * (p.entry_fill - px)
        return v

    def open_risk() -> float:
        return sum(p.risk_amount for p in positions.values()) + sum(pending_risk.values())

    def close_position(p: Position, raw: float, t: int, reason: str, gap: bool = False) -> None:
        nonlocal cash
        exit_fill = _fill(raw, p.direction, "out", cost)
        out_notional = p.qty * exit_fill
        fee = _fee(out_notional, cost)
        days = max(0.0, (t - p.entry_time) / 86400.0)
        fin = p.notional * cost.short_financing_bps_per_day / 10_000.0 * days if p.direction == "SHORT" else 0.0
        if p.direction == "LONG":
            pnl_exec = out_notional - p.notional
            cash_in = out_notional - fee
        else:
            pnl_exec = p.qty * (p.entry_fill - exit_fill)
            cash_in = p.notional + pnl_exec - fee
        cash_in -= fin
        cash += cash_in
        legs = [
            Leg(CCY, _dec(cash_in + fee + fin), Cause.EXECUTION, f"close {p.symbol} ({reason})"),
            Leg(CCY, _dec(-fee), Cause.COMMISSION, "exit commission"),
        ]
        if fin:
            legs.append(Leg(CCY, _dec(-fin), Cause.FINANCING, "short financing"))
        ledger.post(f"close:{p.pid}", _ts(t), legs, ref=p.pid)
        gross = p.qty * (raw - p.entry_raw) if p.direction == "LONG" else p.qty * (p.entry_raw - raw)
        friction = p.qty * abs(p.entry_fill - p.entry_raw) + p.qty * abs(exit_fill - raw)
        net = pnl_exec - p.entry_fee - fee - fin
        trades.append(
            Trade(p.symbol, p.direction, p.signal_time, p.entry_time, t, p.entry_raw, raw, p.entry_fill, exit_fill,
                  p.qty, p.notional, p.risk_amount, gross, p.entry_fee + fee, friction, fin, net, reason, gap)
        )
        del positions[p.symbol]

    def fill_entry(sym, sig, direction, raw, c, t):
        nonlocal cash, pid_n
        eq = equity_now()
        fill = _fill(raw, direction, "in", cost)
        sd = sig.stop_distance
        if rules.full_cash:
            # §6: 100 % cash after entry commission (stop_distance only for levels)
            aff = cash / (1 + cost.commission_bps / 10_000.0)
            if aff <= 0:
                rej["insufficient_cash"] += 1
                return
            qty = aff / fill
            notional = qty * fill
            fee = _fee(notional, cost)
        else:
            qty = eq * rules.risk_pct / sd
            notional = qty * fill
            cap = eq * rules.max_notional_pct
            if notional > cap:
                qty = cap / fill
                notional = qty * fill
            fee = _fee(notional, cost)
            if notional + fee > cash:
                aff = cash / (1 + cost.commission_bps / 10_000.0)
                if aff <= 0:
                    rej["insufficient_cash"] += 1
                    return
                qty = aff / fill
                notional = qty * fill
                fee = _fee(notional, cost)
        if notional < rules.min_notional:
            rej["below_min_notional"] += 1
            return
        sc = data[sym].get(sig.time, (c,))[0]  # liquidity is judged on the SIGNAL bar (known at decision time), not the entry bar
        if notional > rules.liquidity_cap_pct * sc.volume * sc.close:
            rej["liquidity_cap"] += 1
            return
        stop = fill - sd if direction == "LONG" else fill + sd
        tp = fill + sd * rules.take_profit_r if direction == "LONG" else fill - sd * rules.take_profit_r
        if stop <= 0 or tp <= 0:
            rej["invalid_levels"] += 1
            return
        pid_n += 1
        pid = f"{sym}-{t}-{pid_n}"
        cash -= notional + fee
        side = "BUY" if direction == "LONG" else "SELL"
        ledger.post(
            f"open:{pid}", _ts(t),
            [Leg(CCY, _dec(-notional), Cause.EXECUTION, f"{side} {sym}"),
             Leg(CCY, _dec(-fee), Cause.COMMISSION, "entry commission")],
            ref=pid,
        )
        positions[sym] = Position(sym, direction, sig.time, t, raw, fill, qty, notional, fee, stop, tp,
                                  qty * sd, pid)

    for t in times:
        # 1) signal exits decided at the previous close fill at this open
        for sym in list(pending_exit):
            p = positions.get(sym)
            item = data[sym].get(t)
            if p is not None and item is not None:
                close_position(p, item[0].open, t, pending_exit[sym])
            if item is not None or p is None:
                pending_exit.pop(sym, None)
        # 2) entries decided at the previous close fill at this open
        for sym in list(pending_entry):
            sig, direction = pending_entry.pop(sym)
            pending_risk.pop(sym, None)
            item = data[sym].get(t)
            if item is None:
                rej["no_bar_at_fill"] += 1
                continue
            fill_entry(sym, sig, direction, item[0].open, item[0], t)
        # 3) protections on this bar (after the entry instant)
        for sym in list(positions):
            p = positions[sym]
            item = data[sym].get(t)
            if item is None:
                continue
            c = item[0]
            long = p.direction == "LONG"
            if t != p.entry_time:
                if (c.open <= p.stop) if long else (c.open >= p.stop):
                    close_position(p, c.open, t, "stop_hit_gap", gap=True)
                    continue
                if (c.open >= p.tp) if long else (c.open <= p.tp):
                    close_position(p, c.open, t, "take_profit_hit_gap", gap=True)
                    continue
            hit_stop = c.low <= p.stop if long else c.high >= p.stop
            hit_tp = c.high >= p.tp if long else c.low <= p.tp
            if hit_stop:  # includes the ambiguous "both" case -> stop first
                close_position(p, p.stop, t, "stop_hit_ambiguous" if hit_tp else "stop_hit")
            elif hit_tp:
                close_position(p, p.tp, t, "take_profit_hit")
            elif (
                rules.time_stop_bars is not None
                and t != p.entry_time
                and (t - p.entry_time) // rules.bar_seconds >= rules.time_stop_bars
            ):
                # §6: time-stop exits at this bar's close (not next open)
                close_position(p, c.close, t, "time_stop")
        # 4) mark to market at this bar's close
        for sym in symbols:
            item = data[sym].get(t)
            if item is not None:
                last_close[sym] = item[0].close
        eq = equity_now()
        gross_exp = sum(p.qty * last_close.get(p.symbol, p.entry_fill) for p in positions.values())
        equity_curve.append((t, eq, gross_exp))
        dk = _ts(t + rules.bar_seconds - 1).date()
        if dk != day_key:
            day_key, day_start_equity, halted_day = dk, eq, False
        if not halted_day and rules.daily_loss_limit_pct and eq <= day_start_equity * (1 - rules.daily_loss_limit_pct):
            halted_day = True
        # 5) decisions at this close, executed at the next open
        order = [s for s in symbols if t in data[s]]
        rng.shuffle(order)  # neutral priority when capacity is scarce
        for sym in order:
            sig = data[sym][t][1]
            d = eff(sig)
            prev = run_state.get(sym)
            if prev is None or prev[0] != d:
                run_state[sym] = (d, t)
            run_start = run_state[sym][1]
            p = positions.get(sym)
            if p is not None:
                if rules.exit_mode == "levels_only":
                    # VP2: no pipeline / direction exits — SL/TP/time-stop only.
                    continue
                want = "BUY" if p.direction == "LONG" else "SELL"
                if rules.exit_mode == "direction":
                    leave = sig.direction.value != p.direction
                    why = "direction_flipped" if leave else ""
                else:
                    leave = d != want
                    why = "pipeline_flipped" if d in ("BUY", "SELL") else "pipeline_downgraded"
                if leave and rules.immediate_fill:
                    close_position(p, last_close[sym], t, why)
                elif leave and sym not in pending_exit:
                    pending_exit[sym] = why
                continue
            if d not in ("BUY", "SELL"):
                continue
            seen += 1
            direction = "LONG" if d == "BUY" else "SHORT"
            if sym in pending_entry:
                rej["pending_entry_exists"] += 1
                continue
            if direction == "SHORT" and not rules.allow_short:
                rej["short_not_allowed"] += 1
                continue
            if rules.one_entry_per_signal_run and (sym, run_start) in entered_runs:
                rej["signal_already_processed"] += 1
                continue
            if sig.stop_distance is None:
                rej["no_atr_stop"] += 1
                continue
            if halted_day:
                rej["daily_loss_halt"] += 1
                continue
            if len(positions) + len(pending_entry) >= rules.max_open:
                rej["max_positions"] += 1
                continue
            eq = equity_now()
            px = last_close[sym]
            if rules.full_cash:
                if cash < rules.min_notional:
                    rej["insufficient_cash"] += 1
                    continue
                est_qty = cash / px
                est_risk = est_qty * sig.stop_distance
            else:
                est_qty = min(eq * rules.risk_pct / sig.stop_distance, eq * rules.max_notional_pct / px)
                est_risk = est_qty * sig.stop_distance
                if open_risk() + est_risk > eq * rules.max_open_risk_pct + 1e-9:
                    rej["open_risk_cap"] += 1
                    continue
                if est_qty * px > eq * rules.max_symbol_notional_pct + 1e-9:
                    rej["symbol_exposure_cap"] += 1
                    continue
                if est_qty * px > cash:
                    rej["insufficient_cash"] += 1
                    continue
            entered_runs.add((sym, run_start))
            if rules.immediate_fill:
                fill_entry(sym, sig, direction, last_close[sym], data[sym][t][0], t)
                continue
            pending_entry[sym] = (sig, direction)
            pending_risk[sym] = est_risk
    if rules.force_flat_at_end and times:
        t_end = times[-1]
        for sym in list(positions):
            p = positions[sym]
            item = data[sym].get(t_end)
            if item is None:
                continue
            close_position(p, item[0].close, t_end, "window_end")
    open_end = [
        {
            "symbol": p.symbol, "direction": p.direction, "entry_time": p.entry_time, "qty": p.qty,
            "entry_fill": p.entry_fill, "mark": last_close.get(p.symbol),
            "unrealized": p.qty * (
                (last_close.get(p.symbol, p.entry_fill) - p.entry_fill) if p.direction == "LONG"
                else (p.entry_fill - last_close.get(p.symbol, p.entry_fill))
            ),
        }
        for p in positions.values()
    ]
    diff = ledger.reconcile({CCY: _dec(cash)})
    return RunResult(rules, cost, window, symbols, initial, trades, equity_curve, rej, seen, open_end,
                     {k: str(v) for k, v in diff.items()}, cash, ledger)
