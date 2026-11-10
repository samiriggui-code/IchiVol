"""T13b — Risk Kernel (pure evaluate) for paper opens.

Observation of fees / quality / spread as codes where useful; **defaults match
current ``gates.entry_gate`` + ``size_position`` behavior** — no tighter limits.

``evaluate(plan, portfolio_state, market_state) → RiskDecision`` is the single
gate used by opening paths (via ``sync_position`` / API refuse detail).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.paper.gates import GATE_KEYS, has_gates
from app.paper.margin import buying_power
from app.paper.risk import SizedOrder, size_position
from app.paper.strategy_profiles import short_allowed

INTENT_KERNEL_VERSION = "risk_kernel_v1"


@dataclass(frozen=True)
class OpenLotSnap:
    symbol: str
    notional: float
    risk_amount: float
    direction: str = ""  # LONG | SHORT ; vide = inconnu (ignoré par le plafond de paris corrélés)


@dataclass(frozen=True)
class OpenPlan:
    symbol: str
    timeframe: str
    direction: str  # LONG | SHORT
    price: float
    stop_distance: float | None
    run_id: int | None = None
    stale: bool = False
    manual_notional: float | None = None
    take_profit_r: float | None = None
    data_quality_gate: str | None = None  # pass|watch|fail — codes only, never rejects
    # Ève's engagement (app/eve/engagement.py): replaces the profile's risk and lot cap for this order only.
    risk_pct: float | None = None
    max_notional_pct: float | None = None


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    equity: float
    profile: Mapping[str, Any]
    open_positions: tuple[OpenLotSnap, ...]
    day_start_equity: float
    traded_run_id: int | None = None  # for one_entry_per_signal_run
    # T13c — persisted locks (human reopen only)
    kill_switch_armed: bool = False
    daily_loss_locked: bool = False
    # Garde-fous du 2026-11-10 : symbole -> secondes écoulées depuis son dernier stop (``gates.recent_stop_ages``).
    recent_stop_ages: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketState:
    commission_bps: float
    spread_bps: float
    slippage_bps: float
    min_fill_fraction: float = 0.25
    min_notional: float = 10.0


@dataclass(frozen=True)
class RiskDecision:
    accepted: bool
    codes: tuple[str, ...]
    sized: SizedOrder | None = None
    kernel_version: str = INTENT_KERNEL_VERSION

    def primary_code(self) -> str | None:
        return self.codes[0] if self.codes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "codes": list(self.codes),
            "sized": None
            if self.sized is None
            else {
                "qty": self.sized.qty,
                "notional": self.sized.notional,
                "stop_price": self.sized.stop_price,
                "take_profit_price": self.sized.take_profit_price,
                "risk_pct": self.sized.risk_pct,
                "risk_amount": self.sized.risk_amount,
                "entry_fill": self.sized.entry_fill,
            },
            "kernel_version": self.kernel_version,
        }


def _reject(*codes: str) -> RiskDecision:
    return RiskDecision(accepted=False, codes=tuple(c for c in codes if c), sized=None)


def _accept(sized: SizedOrder | None = None, *extra_codes: str) -> RiskDecision:
    return RiskDecision(accepted=True, codes=tuple(extra_codes), sized=sized)


def _bet_side(direction: str, sign: Any) -> int:
    """+1 / -1 : le sens du pari sur le facteur commun du groupe ; 0 si le sens du lot est inconnu."""
    side = {"LONG": 1, "SHORT": -1}.get(str(direction).upper(), 0)
    return side if float(sign or 1) >= 0 else -side


def correlated_bet_refused(plan: OpenPlan, opens: Sequence[OpenLotSnap], groups: Any) -> bool:
    """Un groupe de ``correlation_groups`` porte-t-il déjà ``max_same_side`` lots dans le sens du nouveau ?

    EURUSD, GBPUSD et l'or vendus ensemble sont un seul pari sur le dollar : le plafond par symbole ne le voit pas.
    Un lot de sens opposé dans le même groupe (une couverture) ne compte pas."""
    if not isinstance(groups, Mapping):
        return False
    for group in groups.values():
        symbols = (group or {}).get("symbols") or {}
        if plan.symbol not in symbols:
            continue
        side = _bet_side(plan.direction, symbols[plan.symbol])
        same = sum(
            1 for o in opens
            if o.symbol in symbols and o.symbol != plan.symbol and side and _bet_side(o.direction, symbols[o.symbol]) == side
        )
        if same >= int(group.get("max_same_side", 1)):
            return True
    return False


def evaluate_entry_codes(
    plan: OpenPlan,
    state: PortfolioState,
) -> str | None:
    """Pure port of ``gates.entry_gate`` first-failing reason (or None).

    Same order and thresholds — do not tighten. ``reentry_cooldown_hours`` and ``correlation_groups`` only act on
    profiles that declare them (2026-11-10).
    """
    p: Mapping[str, Any] = state.profile or {}
    stop_distance = plan.stop_distance
    if not stop_distance or stop_distance <= 0:
        return "no_atr_stop"
    opens = state.open_positions
    if p.get("one_position_per_symbol") and any(o.symbol == plan.symbol for o in opens):
        return "position_already_open"
    if p.get("reentry_cooldown_hours"):
        age = state.recent_stop_ages.get(plan.symbol)
        if age is not None and age < float(p["reentry_cooldown_hours"]) * 3600.0:
            return "reentry_cooldown"
    if correlated_bet_refused(plan, opens, p.get("correlation_groups")):
        return "correlated_exposure_cap"
    if p.get("one_entry_per_signal_run") and plan.run_id is not None:
        if state.traded_run_id == plan.run_id:
            return "signal_already_processed"
    if len(opens) >= int(p.get("max_open_positions", 5)):
        return "max_positions"
    risk_pct = float(plan.risk_pct if plan.risk_pct is not None else p.get("risk_pct", 0.01))
    max_notional_pct = float(
        plan.max_notional_pct if plan.max_notional_pct is not None else p.get("max_notional_pct", 0.25)
    )
    equity = state.equity
    price = plan.price
    est_qty = min(equity * risk_pct / stop_distance, equity * max_notional_pct / price)
    if p.get("max_open_risk_pct"):
        cur = sum(float(o.risk_amount or 0.0) for o in opens)
        if cur + est_qty * stop_distance > equity * float(p["max_open_risk_pct"]) + 1e-9:
            return "open_risk_cap"
    if p.get("max_symbol_notional_pct"):
        cur = sum(float(o.notional or 0.0) for o in opens if o.symbol == plan.symbol)
        symbol_cap = max(float(p["max_symbol_notional_pct"]), float(plan.max_notional_pct or 0.0))
        if cur + est_qty * price > equity * symbol_cap + 1e-9:
            return "symbol_exposure_cap"
    if p.get("daily_loss_limit_pct"):
        start = state.day_start_equity
        if start > 0 and equity <= start * (1 - float(p["daily_loss_limit_pct"])):
            return "daily_loss_halt"
    return None


def evaluate(
    plan: OpenPlan,
    portfolio_state: PortfolioState,
    market_state: MarketState,
    *,
    apply_gates: bool | None = None,
    check_size: bool = True,
) -> RiskDecision:
    """Accept / reject a paper open. Defaults ≡ current engine behavior.

    ``apply_gates``: when None, follows ``has_gates(profile)`` (baseline ON).
    Quality gate codes are informational only (T11a observation).
    """
    info: list[str] = []
    if plan.data_quality_gate and plan.data_quality_gate != "pass":
        info.append(f"quality_{plan.data_quality_gate}")

    # T13c — locks first; always apply (including manual_notional / ungated)
    if portfolio_state.kill_switch_armed:
        return _reject("kill_switch", *info)
    if portfolio_state.daily_loss_locked:
        return _reject("daily_loss_halt", *info)

    if plan.stale:
        return _reject("stale_data", *info)

    profile = dict(portfolio_state.profile or {})
    if plan.direction == "SHORT" and not short_allowed(profile, plan.symbol):
        return _reject("short_not_allowed", *info)

    gated = has_gates(profile) if apply_gates is None else bool(apply_gates)
    # Manual notional path historically skips entry_gate in sync_position.
    if gated and plan.manual_notional is None:
        code = evaluate_entry_codes(plan, portfolio_state)
        if code is not None:
            return _reject(code, *info)
    elif plan.stop_distance is None or plan.stop_distance <= 0:
        # Ungated profiles still need ATR for capital opens when require_atr.
        if bool(profile.get("require_atr_stop", True)):
            return _reject("no_atr_stop", *info)

    sized: SizedOrder | None = None
    if check_size and plan.stop_distance and plan.stop_distance > 0:
        take_r = (
            float(plan.take_profit_r)
            if plan.take_profit_r is not None
            else float(profile.get("take_profit_r", 2.0))
        )
        spendable = buying_power(
            profile,
            plan.symbol,
            cash=portfolio_state.cash,
            equity=portfolio_state.equity,
            open_lots=portfolio_state.open_positions,
        )
        sized = size_position(
            equity=portfolio_state.equity,
            cash=spendable,
            direction=plan.direction,
            entry_price=plan.price,
            stop_distance=float(plan.stop_distance),
            risk_pct=float(plan.risk_pct if plan.risk_pct is not None else profile.get("risk_pct", 0.01)),
            take_profit_r=take_r,
            max_notional_pct=float(
                plan.max_notional_pct if plan.max_notional_pct is not None else profile.get("max_notional_pct", 0.25)
            ),
            commission_bps=market_state.commission_bps,
            spread_bps=market_state.spread_bps,
            slippage_bps=market_state.slippage_bps,
            min_fill_fraction=market_state.min_fill_fraction,
            min_notional=market_state.min_notional,
            manual_notional=plan.manual_notional,
        )
        if sized is None:
            opens = portfolio_state.open_positions
            if len(opens) >= int(profile.get("max_open_positions", 5)):
                return _reject("max_positions", *info)
            return _reject("insufficient_cash_or_size", *info)
        # Fee + notional vs buying power (same as broker.open_capital_position)
        fee = sized.notional * (market_state.commission_bps / 10_000.0)
        if sized.notional + fee > spendable + 1e-9:
            return _reject("insufficient_cash_or_size", *info)

    return _accept(sized, *info)


def market_state_from_profile(profile: Mapping[str, Any] | None, symbol: str = "") -> MarketState:
    p = dict(profile or {})
    spread = float(p.get("spread_bps", 2.0))
    slip = float(p.get("slippage_bps", 3.0))
    by_sym = p.get("friction_bps_by_symbol") or {}
    if isinstance(by_sym, Mapping) and symbol and symbol.upper() in by_sym:
        # Same as broker._friction: the table is the combined per-side friction.
        spread = float(by_sym[symbol.upper()])
        slip = 0.0
    commission = float(p.get("commission_bps", 5.0))
    by_c = p.get("commission_bps_by_symbol") or {}
    if isinstance(by_c, Mapping) and symbol and symbol.upper() in by_c:
        commission = float(by_c[symbol.upper()])
    return MarketState(
        commission_bps=commission,
        spread_bps=spread,
        slippage_bps=slip,
        min_fill_fraction=float(p.get("min_fill_fraction", 0.25)),
        min_notional=float(p.get("min_notional", 10.0)),
    )


def open_lots_from_positions(opens: Sequence[Any]) -> tuple[OpenLotSnap, ...]:
    out: list[OpenLotSnap] = []
    for o in opens:
        out.append(
            OpenLotSnap(
                symbol=str(o.symbol),
                notional=float(o.notional or 0.0),
                risk_amount=float(o.risk_amount or 0.0),
                direction=str(getattr(o, "direction", "") or ""),
            )
        )
    return tuple(out)


# Re-export for callers that check gate keys
__all__ = [
    "GATE_KEYS",
    "OpenLotSnap",
    "OpenPlan",
    "PortfolioState",
    "MarketState",
    "RiskDecision",
    "evaluate",
    "evaluate_entry_codes",
    "market_state_from_profile",
    "open_lots_from_positions",
    "has_gates",
    "INTENT_KERNEL_VERSION",
]
