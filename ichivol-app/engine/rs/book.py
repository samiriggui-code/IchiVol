"""RS-D1 — état et étapes par barre, **seule** implémentation des règles RS-03.

Extraction sans changement de comportement de ``rs.donchian.simulate`` (RS-09 §1) : le backtest et le
paper live appellent les mêmes méthodes, dans le même ordre, pour chaque barre ``t`` :

1. ``fill_pending(t)``  : sorties de canal puis entrées décidées à une clôture antérieure, à l'open ;
2. ``check_stops(t)``   : stop intrabarre (barre d'entrée comprise) ;
3. ``on_close(t)``      : valorisation, stop suiveur, décision de sortie de canal, equity, verrou journalier ;
4. ``decide(t)``        : entrées (ordre de traitement tiré par ``random.Random(seed)``).

Les indices de barre (``entry_idx``, ``fill_idx``) sont ceux de la série par symbole fournie au ``Book`` :
le live fournit toujours la série depuis une origine fixe pour qu'ils restent stables.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from app.indicators.atr import AtrParams, compute_atr
from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle

from rs import (
    ATR_PERIOD,
    BAR_SECONDS,
    DAILY_LOSS_LIMIT_PCT,
    ENTRY_PERIOD,
    EXIT_PERIOD,
    MAX_NOTIONAL_PCT,
    MAX_OPEN,
    MAX_OPEN_RISK_PCT,
    MIN_FILL_FRACTION,
    MIN_NOTIONAL,
    RISK_PCT,
    STOP_ATR_MULT,
)
from rs.costs import SymbolCost


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


def size_entry(
    eq_cost: float, cash: float, fill: float, dist: float, c: SymbolCost
) -> tuple[float, float, float] | str:
    """Taille RS-03 §5 → (qty, notionnel, commission) ou motif de refus.

    qty = 0,5 % × equity_coût / (fill − S₀), plafonnée à 10 % d'equity_coût ; limitée au cash
    (commission comprise), refusée sous 25 % de la taille visée ; notionnel minimum 10.
    """
    if dist <= 0 or fill - dist <= 0:
        return "invalid_stop"
    qty = eq_cost * RISK_PCT / dist
    if qty * fill > eq_cost * MAX_NOTIONAL_PCT:
        qty = eq_cost * MAX_NOTIONAL_PCT / fill
    intended = qty * fill
    notional = intended
    fee = c.fee(notional)
    if notional + fee > cash:
        aff = cash / (1 + c.commission_bps / 10_000.0)
        if aff <= 0 or aff < intended * MIN_FILL_FRACTION:
            return "insufficient_cash"
        notional = aff
        qty = notional / fill
        fee = c.fee(notional)
    if notional < MIN_NOTIONAL:
        return "below_min_notional"
    return qty, notional, fee


def day_key(t: int) -> str:
    """Jour UTC de la **fin** de barre (clé du verrou de perte journalière)."""
    return datetime.fromtimestamp(t + BAR_SECONDS - 1, tz=timezone.utc).date().isoformat()


@dataclass
class Event:
    """Effet observable d'une étape, pour le live (écritures paper, journal). Ignoré par le backtest."""

    kind: str  # entry_filled | exit_filled | entry_rejected | exit_ordered | entry_ordered | stop_moved | rejected
    symbol: str | None
    t: int
    data: dict[str, Any] = field(default_factory=dict)


class Book:
    """État RS-D1 d'un portefeuille à capital commun + indicateurs de la série fournie."""

    def __init__(
        self,
        candles_by_sym: dict[str, Sequence[Candle]],
        costs: dict[str, SymbolCost],
        *,
        initial: float,
        score_start: int,
        exec_delay: int = 1,
        seed: int,
    ) -> None:
        self.symbols = sorted(candles_by_sym)
        self.costs = costs
        self.score_start = score_start
        self.exec_delay = exec_delay
        self.rng = random.Random(seed)
        self.set_market(candles_by_sym)

        self.cash = initial
        self.positions: dict[str, _Pos] = {}
        self.pending_entry: dict[str, tuple[int, int, float]] = {}  # sym -> (fill_idx, signal_time, atr_signal)
        self.pending_exit: dict[str, int] = {}  # sym -> fill_idx
        self.last_exit_time: dict[str, int] = {}
        self.last_close: dict[str, float] = {}
        self.trades: list[Trade] = []
        self.equity: list[tuple[int, float, float]] = []
        self.stop_log: dict[str, list[tuple[int, float]]] = {s: [] for s in self.symbols}
        self.orders: list[tuple[int, str, str]] = []
        self.rej: dict[str, int] = {}
        self.day_key: str | None = None
        self.day_start_eq = initial
        self.prev_eq_mark = initial  # equity marquée à la clôture de la barre précédente
        self.halted = False
        self.halt_days = 0
        self.events: list[Event] = []

    # --- marché -------------------------------------------------------------------------------

    def set_market(self, candles_by_sym: dict[str, Sequence[Candle]]) -> None:
        """(Re)charge les séries et leurs indicateurs. Causal : la valeur à l'indice i ne dépend que de ≤ i."""
        self.bars = {s: list(candles_by_sym[s]) for s in self.symbols}
        self.idx_of = {s: {c.time: i for i, c in enumerate(self.bars[s])} for s in self.symbols}
        self.upper = {s: [d.upper for d in compute_donchian(self.bars[s], DonchianParams(period=ENTRY_PERIOD))] for s in self.symbols}
        self.lower = {s: [d.lower for d in compute_donchian(self.bars[s], DonchianParams(period=EXIT_PERIOD))] for s in self.symbols}
        self.atr = {
            s: [a.atr if i >= ATR_PERIOD - 1 else None for i, a in enumerate(compute_atr(self.bars[s], AtrParams(period=ATR_PERIOD)))]
            for s in self.symbols
        }

    def present(self, t: int) -> list[str]:
        return [s for s in self.symbols if t in self.idx_of[s]]

    # --- helpers ------------------------------------------------------------------------------

    def _reject(self, k: str, s: str | None = None, t: int = 0) -> None:
        self.rej[k] = self.rej.get(k, 0) + 1
        self.events.append(Event("rejected", s, t, {"reason": k}))

    def equity_cost(self) -> float:
        # §5 : cash + notionnels ouverts au coût (définition paper)
        return self.cash + sum(p.notional for p in self.positions.values())

    def equity_mark(self) -> float:
        return self.cash + sum(p.qty * self.last_close.get(p.symbol, p.entry_fill) for p in self.positions.values())

    def close(self, p: _Pos, raw: float, t: int, idx: int, reason: str) -> Trade:
        c = self.costs[p.symbol]
        fill = c.fill(raw, "sell")
        out_notional = p.qty * fill
        fee = c.fee(out_notional)
        self.cash += out_notional - fee
        gross = p.qty * (raw - p.entry_raw)
        friction = p.qty * (p.entry_fill - p.entry_raw) + p.qty * (raw - fill)
        net = out_notional - p.notional - p.entry_fee - fee
        tr = Trade(p.symbol, p.signal_time, p.entry_time, t, p.entry_raw, p.entry_fill, raw, fill, p.qty, p.notional,
                   p.initial_stop, p.risk_amount, p.entry_fee + fee, friction, gross, net, reason, idx - p.entry_idx + 1)
        self.trades.append(tr)
        del self.positions[p.symbol]
        self.pending_exit.pop(p.symbol, None)
        self.last_exit_time[p.symbol] = t
        self.events.append(Event("exit_filled", p.symbol, t, {"raw": raw, "fill": fill, "fee": fee, "reason": reason, "net": net}))
        return tr

    # --- étapes -------------------------------------------------------------------------------

    def fill_pending(self, t: int, open_of: Callable[[str, int], float] | None = None) -> None:
        """1) sorties de canal puis 2) entrées, à l'open de ``t`` (§3, §4 priorité, taille §5).

        ``open_of(symbol, idx)`` remplace l'open de la barre (live : premier prix après la clôture) ;
        par défaut, l'open de la série."""
        bars, idx_of = self.bars, self.idx_of
        get_open = open_of or (lambda s, i: bars[s][i].open)
        for s in list(self.pending_exit):
            i = idx_of[s].get(t)
            if i is None or i < self.pending_exit[s]:
                continue
            p = self.positions.get(s)
            self.pending_exit.pop(s)
            if p is None:
                continue
            o = get_open(s, i)
            self.close(p, o, t, i, "stop_gap" if o <= p.stop else "channel")
        for s in list(self.pending_entry):
            i = idx_of[s].get(t)
            fill_idx, sig_t, atr_sig = self.pending_entry[s]
            if i is None or i < fill_idx:
                continue
            self.pending_entry.pop(s)
            if s in self.positions:
                continue
            c = self.costs[s]
            raw = get_open(s, i)
            fill = c.fill(raw, "buy")
            dist = STOP_ATR_MULT * atr_sig
            stop0 = fill - dist
            sized = size_entry(self.equity_cost(), self.cash, fill, dist, c)
            if isinstance(sized, str):
                self._reject(sized, s, t)
                continue
            qty, notional, fee = sized
            self.cash -= notional + fee
            self.positions[s] = _Pos(s, sig_t, t, i, raw, fill, qty, notional, fee, stop0, stop0, qty * dist, float("-inf"))
            self.events.append(Event("entry_filled", s, t, {"raw": raw, "fill": fill, "qty": qty, "notional": notional,
                                                             "fee": fee, "stop": stop0, "signal_time": sig_t}))

    def check_stops(self, t: int) -> None:
        """3) protections pendant la barre (§4 exécution du stop), barre d'entrée comprise."""
        for s in list(self.positions):
            i = self.idx_of[s].get(t)
            if i is None:
                continue
            p = self.positions[s]
            b = self.bars[s][i]
            reason = "stop_initial" if p.stop == p.initial_stop else "stop_trail"
            if t != p.entry_time and b.open <= p.stop:
                self.close(p, b.open, t, i, "stop_gap")
            elif b.low <= p.stop:
                self.close(p, p.stop, t, i, reason)

    def on_close(self, t: int) -> None:
        """4) clôture : valorisation, stop suiveur (appliqué dès la barre suivante), sortie de canal, verrou."""
        bars = self.bars
        for s in self.present(t):
            i = self.idx_of[s][t]
            self.last_close[s] = bars[s][i].close
            p = self.positions.get(s)
            if p is None:
                continue
            p.highest_close = max(p.highest_close, bars[s][i].close)
            a = self.atr[s][i]
            before = p.stop
            if a is not None:
                p.stop = max(p.stop, p.highest_close - STOP_ATR_MULT * a)
            self.stop_log[s].append((t, p.stop))
            if p.stop != before:
                self.events.append(Event("stop_moved", s, t, {"from": before, "to": p.stop}))
            lo = self.lower[s][i]
            # La décision ne dépend que des barres <= t (jamais de la longueur de la série) :
            # s'il n'existe pas de barre d'exécution, l'ordre reste simplement non exécuté.
            if lo is not None and bars[s][i].close < lo and s not in self.pending_exit:
                self.pending_exit[s] = i + self.exec_delay
                self.orders.append((t, s, "exit"))
                self.events.append(Event("exit_ordered", s, t, {"close": bars[s][i].close, "l20": lo}))
        eq_m = self.equity_mark()
        if t >= self.score_start:
            gross_exp = sum(p.qty * self.last_close.get(p.symbol, p.entry_fill) for p in self.positions.values())
            self.equity.append((t, eq_m, gross_exp))
        # verrou perte journalière (définition paper : equity au coût contre début de jour marqué).
        # Début de jour = equity marquée à la dernière clôture de la veille (avant toute barre du jour).
        dk = day_key(t)
        if dk != self.day_key:
            self.day_key, self.day_start_eq, self.halted = dk, self.prev_eq_mark, False
        self.prev_eq_mark = eq_m
        if not self.halted and self.equity_cost() <= self.day_start_eq * (1 - DAILY_LOSS_LIMIT_PCT):
            self.halted = True
            self.halt_days += 1

    def decide(self, t: int) -> None:
        """5) décisions à la clôture de t (§3) ; exécution à open(t + exec_delay)."""
        bars = self.bars
        order = self.present(t)
        self.rng.shuffle(order)
        for s in order:
            i = self.idx_of[s][t]
            if t + self.exec_delay * BAR_SECONDS < self.score_start:
                continue  # warm-up : aucune position avant la fenêtre de score
            up, a = self.upper[s][i], self.atr[s][i]
            if up is None or a is None or not (bars[s][i].close > up):
                continue
            if s in self.positions or s in self.pending_entry:
                continue
            if self.last_exit_time.get(s, -1) >= t:
                self._reject("reentry_same_bar", s, t)
                continue
            if self.halted:
                self._reject("daily_loss_halt", s, t)
                continue
            if len(self.positions) + len(self.pending_entry) >= MAX_OPEN:
                self._reject("max_positions", s, t)
                continue
            eq = self.equity_cost()
            dist = STOP_ATR_MULT * a
            est_qty = min(eq * RISK_PCT / dist, eq * MAX_NOTIONAL_PCT / bars[s][i].close)
            open_risk = sum(p.risk_amount for p in self.positions.values()) + sum(
                min(eq * RISK_PCT / (STOP_ATR_MULT * pa), eq * MAX_NOTIONAL_PCT / self.last_close[ps]) * STOP_ATR_MULT * pa
                for ps, (_, _, pa) in self.pending_entry.items()
            )
            if open_risk + est_qty * dist > eq * MAX_OPEN_RISK_PCT + 1e-9:
                self._reject("open_risk_cap", s, t)
                continue
            self.pending_entry[s] = (i + self.exec_delay, t, a)
            self.orders.append((t, s, "entry"))
            self.events.append(Event("entry_ordered", s, t, {"close": bars[s][i].close, "u55": up, "atr": a}))

    def step(self, t: int) -> None:
        """Une barre complète, dans l'ordre de ``simulate`` (backtest)."""
        self.fill_pending(t)
        self.check_stops(t)
        self.on_close(t)
        self.decide(t)

    def finalize(self) -> None:
        """Fin de fenêtre : pas de vente forcée ; positions valorisées au dernier close (§4)."""
        for s, p in list(self.positions.items()):
            raw = self.last_close[s]
            gross = p.qty * (raw - p.entry_raw)
            net = p.qty * raw - p.notional - p.entry_fee
            self.trades.append(
                Trade(s, p.signal_time, p.entry_time, None, p.entry_raw, p.entry_fill, raw, None, p.qty, p.notional,
                      p.initial_stop, p.risk_amount, p.entry_fee, p.qty * (p.entry_fill - p.entry_raw), gross, net,
                      "open_at_end", len(self.bars[s]) - p.entry_idx)
            )

    # --- persistance (live) -------------------------------------------------------------------

    def state_dict(self) -> dict[str, Any]:
        """État sérialisable (JSON) : tout sauf le marché, l'historique d'equity et les événements."""
        return {
            "cash": self.cash,
            "positions": {s: _pos_to_json(p) for s, p in self.positions.items()},
            "pending_entry": {s: list(v) for s, v in self.pending_entry.items()},
            "pending_exit": dict(self.pending_exit),
            "last_exit_time": dict(self.last_exit_time),
            "last_close": dict(self.last_close),
            "rej": dict(self.rej),
            "day_key": self.day_key,
            "day_start_eq": self.day_start_eq,
            "prev_eq_mark": self.prev_eq_mark,
            "halted": self.halted,
            "halt_days": self.halt_days,
            "rng": _rng_to_json(self.rng.getstate()),
        }

    def load_state(self, d: dict[str, Any]) -> None:
        self.cash = float(d["cash"])
        self.positions = {s: _Pos(**_pos_from_json(p)) for s, p in d["positions"].items()}
        self.pending_entry = {s: (int(v[0]), int(v[1]), float(v[2])) for s, v in d["pending_entry"].items()}
        self.pending_exit = {s: int(v) for s, v in d["pending_exit"].items()}
        self.last_exit_time = {s: int(v) for s, v in d["last_exit_time"].items()}
        self.last_close = {s: float(v) for s, v in d["last_close"].items()}
        self.rej = {k: int(v) for k, v in d["rej"].items()}
        self.day_key = d["day_key"]
        self.day_start_eq = float(d["day_start_eq"])
        self.prev_eq_mark = float(d["prev_eq_mark"])
        self.halted = bool(d["halted"])
        self.halt_days = int(d["halt_days"])
        self.rng.setstate(_rng_from_json(d["rng"]))


def _pos_to_json(p: _Pos) -> dict[str, Any]:
    d = asdict(p)
    if d["highest_close"] == float("-inf"):
        d["highest_close"] = None
    return d


def _pos_from_json(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    if out.get("highest_close") is None:  # -inf n'existe pas en JSON strict
        out["highest_close"] = float("-inf")
    return out


def _rng_to_json(state: tuple) -> list:
    version, internal, gauss = state
    return [version, list(internal), gauss]


def _rng_from_json(d: list) -> tuple:
    return (d[0], tuple(d[1]), d[2])
