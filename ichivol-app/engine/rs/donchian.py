"""RS-D1 — cassure Donchian 55 / stop suiveur 3 ATR / sortie canal 20, portefeuille à capital commun.

Implémentation normative de docs/RS-03-DONCHIAN-4H-SPEC.md. Chaque règle renvoie à sa section.
Causal par construction : à la clôture de la barre ``t``, seules les barres ``<= t`` sont lues ;
les indicateurs viennent de ``app/indicators`` (Donchian exclut la barre signal, ATR = moyenne simple).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from app.indicators.atr import AtrParams, compute_atr
from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle

from rs import (
    ATR_PERIOD,
    BAR_SECONDS,
    DAILY_LOSS_LIMIT_PCT,
    ENTRY_PERIOD,
    EXIT_PERIOD,
    INITIAL_CAPITAL,
    MAX_NOTIONAL_PCT,
    MAX_OPEN,
    MAX_OPEN_RISK_PCT,
    MIN_FILL_FRACTION,
    MIN_NOTIONAL,
    RISK_PCT,
    SCORE_START,
    SEED,
    STOP_ATR_MULT,
)
from rs.costs import SymbolCost
from rs.data import assert_no_reserved


@dataclass
class Trade:
    symbol: str
    signal_time: int
    entry_time: int
    exit_time: int | None
    entry_raw: float
    entry_fill: float
    exit_raw: float | None
    exit_fill: float | None
    qty: float
    notional: float
    initial_stop: float
    risk_amount: float
    fees: float
    friction: float
    gross: float
    net: float
    exit_reason: str  # stop_initial | stop_trail | stop_gap | channel | open_at_end
    bars_held: int


@dataclass
class _Pos:
    symbol: str
    signal_time: int
    entry_time: int
    entry_idx: int
    entry_raw: float
    entry_fill: float
    qty: float
    notional: float
    entry_fee: float
    stop: float
    initial_stop: float
    risk_amount: float
    highest_close: float  # plus haute clôture depuis l'entrée (barre d'entrée comprise)


@dataclass
class RunOutput:
    trades: list[Trade]
    equity: list[tuple[int, float, float]]  # (bar_open_time, equity marquée au close, exposition brute)
    stop_log: dict[str, list[tuple[int, float]]]  # symbole -> [(barre, stop applicable à la barre suivante)]
    orders: list[tuple[int, str, str]]  # (barre de décision, symbole, "entry"|"exit")
    rejections: dict[str, int] = field(default_factory=dict)
    halt_days: int = 0


def _day(t: int) -> str:
    return datetime.fromtimestamp(t + BAR_SECONDS - 1, tz=timezone.utc).date().isoformat()


def simulate(
    candles_by_sym: dict[str, Sequence[Candle]],
    costs: dict[str, SymbolCost],
    *,
    initial: float = INITIAL_CAPITAL,
    score_start: int = SCORE_START,
    exec_delay: int = 1,
    seed: int = SEED,
) -> RunOutput:
    """``exec_delay`` = barres entre la décision et l'exécution (1 = open t+1 ; 2 = stress §9)."""
    symbols = sorted(candles_by_sym)
    bars = {s: list(candles_by_sym[s]) for s in symbols}
    for s in symbols:
        assert_no_reserved(bars[s])
    idx_of = {s: {c.time: i for i, c in enumerate(bars[s])} for s in symbols}
    upper = {s: [d.upper for d in compute_donchian(bars[s], DonchianParams(period=ENTRY_PERIOD))] for s in symbols}
    lower = {s: [d.lower for d in compute_donchian(bars[s], DonchianParams(period=EXIT_PERIOD))] for s in symbols}
    atr = {s: [a.atr if i >= ATR_PERIOD - 1 else None for i, a in enumerate(compute_atr(bars[s], AtrParams(period=ATR_PERIOD)))] for s in symbols}

    times = sorted({c.time for s in symbols for c in bars[s]})
    rng = random.Random(seed)

    cash = initial
    positions: dict[str, _Pos] = {}
    pending_entry: dict[str, tuple[int, int, float]] = {}  # sym -> (fill_idx, signal_time, atr_signal)
    pending_exit: dict[str, int] = {}  # sym -> fill_idx
    last_exit_time: dict[str, int] = {}
    last_close: dict[str, float] = {}
    trades: list[Trade] = []
    equity: list[tuple[int, float, float]] = []
    stop_log: dict[str, list[tuple[int, float]]] = {s: [] for s in symbols}
    orders: list[tuple[int, str, str]] = []
    rej: dict[str, int] = {}
    day_key: str | None = None
    day_start_eq = initial
    halted = False
    halt_days = 0

    def reject(k: str) -> None:
        rej[k] = rej.get(k, 0) + 1

    def equity_cost() -> float:
        # §5 : cash + notionnels ouverts au coût (définition paper)
        return cash + sum(p.notional for p in positions.values())

    def equity_mark() -> float:
        return cash + sum(p.qty * last_close.get(p.symbol, p.entry_fill) for p in positions.values())

    def close(p: _Pos, raw: float, t: int, idx: int, reason: str) -> None:
        nonlocal cash
        c = costs[p.symbol]
        fill = c.fill(raw, "sell")
        out_notional = p.qty * fill
        fee = c.fee(out_notional)
        cash += out_notional - fee
        gross = p.qty * (raw - p.entry_raw)
        friction = p.qty * (p.entry_fill - p.entry_raw) + p.qty * (raw - fill)
        net = out_notional - p.notional - p.entry_fee - fee
        trades.append(
            Trade(p.symbol, p.signal_time, p.entry_time, t, p.entry_raw, p.entry_fill, raw, fill, p.qty, p.notional,
                  p.initial_stop, p.risk_amount, p.entry_fee + fee, friction, gross, net, reason, idx - p.entry_idx + 1)
        )
        del positions[p.symbol]
        pending_exit.pop(p.symbol, None)
        last_exit_time[p.symbol] = t

    for t in times:
        present = [s for s in symbols if t in idx_of[s]]
        # 1) sorties de canal décidées à une clôture antérieure → open (§4 priorité : gap sous stop = stop_gap)
        for s in list(pending_exit):
            i = idx_of[s].get(t)
            if i is None or i < pending_exit[s]:
                continue
            p = positions.get(s)
            pending_exit.pop(s)
            if p is None:
                continue
            o = bars[s][i].open
            close(p, o, t, i, "stop_gap" if o <= p.stop else "channel")
        # 2) entrées décidées à une clôture antérieure → open (§3, taille §5)
        for s in list(pending_entry):
            i = idx_of[s].get(t)
            fill_idx, sig_t, atr_sig = pending_entry[s]
            if i is None or i < fill_idx:
                continue
            pending_entry.pop(s)
            if s in positions:
                continue
            c = costs[s]
            raw = bars[s][i].open
            fill = c.fill(raw, "buy")
            dist = STOP_ATR_MULT * atr_sig
            stop0 = fill - dist
            if stop0 <= 0:
                reject("invalid_stop")
                continue
            eq = equity_cost()
            qty = eq * RISK_PCT / dist
            if qty * fill > eq * MAX_NOTIONAL_PCT:
                qty = eq * MAX_NOTIONAL_PCT / fill
            intended = qty * fill
            notional = intended
            fee = c.fee(notional)
            if notional + fee > cash:
                aff = cash / (1 + c.commission_bps / 10_000.0)
                if aff <= 0 or aff < intended * MIN_FILL_FRACTION:
                    reject("insufficient_cash")
                    continue
                notional = aff
                qty = notional / fill
                fee = c.fee(notional)
            if notional < MIN_NOTIONAL:
                reject("below_min_notional")
                continue
            cash -= notional + fee
            positions[s] = _Pos(s, sig_t, t, i, raw, fill, qty, notional, fee, stop0, stop0, qty * dist, float("-inf"))
        # 3) protections pendant la barre (§4 exécution du stop), barre d'entrée comprise
        for s in list(positions):
            i = idx_of[s].get(t)
            if i is None:
                continue
            p = positions[s]
            b = bars[s][i]
            reason = "stop_initial" if p.stop == p.initial_stop else "stop_trail"
            if t != p.entry_time and b.open <= p.stop:
                close(p, b.open, t, i, "stop_gap")
            elif b.low <= p.stop:
                close(p, p.stop, t, i, reason)
        # 4) clôture : valorisation, stop suiveur (appliqué dès la barre suivante), sortie de canal
        for s in present:
            i = idx_of[s][t]
            last_close[s] = bars[s][i].close
            p = positions.get(s)
            if p is None:
                continue
            p.highest_close = max(p.highest_close, bars[s][i].close)
            a = atr[s][i]
            if a is not None:
                p.stop = max(p.stop, p.highest_close - STOP_ATR_MULT * a)
            stop_log[s].append((t, p.stop))
            lo = lower[s][i]
            if lo is not None and bars[s][i].close < lo and s not in pending_exit:
                if i + exec_delay < len(bars[s]):
                    pending_exit[s] = i + exec_delay
                    orders.append((t, s, "exit"))
        eq_m = equity_mark()
        if t >= score_start:
            gross_exp = sum(p.qty * last_close.get(p.symbol, p.entry_fill) for p in positions.values())
            equity.append((t, eq_m, gross_exp))
        # verrou perte journalière (définition paper : equity au coût contre début de jour marqué)
        dk = _day(t)
        if dk != day_key:
            day_key, day_start_eq, halted = dk, eq_m, False
        if not halted and equity_cost() <= day_start_eq * (1 - DAILY_LOSS_LIMIT_PCT):
            halted = True
            halt_days += 1
        # 5) décisions à la clôture de t (§3) ; exécution à open(t + exec_delay)
        order = list(present)
        rng.shuffle(order)
        for s in order:
            i = idx_of[s][t]
            if t + exec_delay * BAR_SECONDS < score_start:
                continue  # warm-up : aucune position avant la fenêtre de score
            up, a = upper[s][i], atr[s][i]
            if up is None or a is None or not (bars[s][i].close > up):
                continue
            if s in positions or s in pending_entry:
                continue
            if last_exit_time.get(s, -1) >= t:
                reject("reentry_same_bar")
                continue
            if halted:
                reject("daily_loss_halt")
                continue
            if len(positions) + len(pending_entry) >= MAX_OPEN:
                reject("max_positions")
                continue
            if i + exec_delay >= len(bars[s]):
                continue
            eq = equity_cost()
            dist = STOP_ATR_MULT * a
            est_qty = min(eq * RISK_PCT / dist, eq * MAX_NOTIONAL_PCT / bars[s][i].close)
            open_risk = sum(p.risk_amount for p in positions.values()) + sum(
                min(eq * RISK_PCT / (STOP_ATR_MULT * pa), eq * MAX_NOTIONAL_PCT / last_close[ps]) * STOP_ATR_MULT * pa
                for ps, (_, _, pa) in pending_entry.items()
            )
            if open_risk + est_qty * dist > eq * MAX_OPEN_RISK_PCT + 1e-9:
                reject("open_risk_cap")
                continue
            pending_entry[s] = (i + exec_delay, t, a)
            orders.append((t, s, "entry"))

    # Fin de fenêtre : pas de vente forcée ; positions valorisées au dernier close (§4)
    for s, p in list(positions.items()):
        raw = last_close[s]
        gross = p.qty * (raw - p.entry_raw)
        net = p.qty * raw - p.notional - p.entry_fee
        trades.append(
            Trade(s, p.signal_time, p.entry_time, None, p.entry_raw, p.entry_fill, raw, None, p.qty, p.notional,
                  p.initial_stop, p.risk_amount, p.entry_fee, p.qty * (p.entry_fill - p.entry_raw), gross, net,
                  "open_at_end", len(bars[s]) - p.entry_idx)
        )
    return RunOutput(trades, equity, stop_log, orders, rej, halt_days)
