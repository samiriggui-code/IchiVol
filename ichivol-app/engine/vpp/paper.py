"""Paper rules → research_lab.sim Rules / CostModel, read from the live profile itself (no copied numbers).

Every value comes from ``app.paper.strategy_profiles.BASELINE_PROFILE`` (identical to the production DB row,
checked 2026-09-27, see docs/VP-P-PAPER-REEL.md). Mapping per field:

  risk_pct, take_profit_r, max_open_positions, max_notional_pct, max_open_risk_pct, daily_loss_limit_pct,
  one_entry_per_signal_run, allow_short, exit_mode  -> same-name Rules fields
  min_fill_fraction / min_notional                  -> app/paper/broker defaults (0.25 / 10.0)
  max_symbol_notional_pct                           -> absent from the profile = gate off -> 1.0
  liquidity cap                                     -> the paper has none -> neutralized
  commission_bps + friction_bps_by_symbol           -> per-symbol CostModel (friction replaces spread+slippage,
                                                       exactly as app/paper/broker._friction)
"""

from __future__ import annotations

from typing import Any, Iterable

from app.paper.strategy_profiles import BASELINE_PROFILE
from research_lab.sim import CostModel, Rules

# app/paper/broker.open_capital_position defaults when the profile has no key
_BROKER_MIN_FILL_FRACTION = 0.25
_BROKER_MIN_NOTIONAL = 10.0


def paper_rules(profile: dict[str, Any] | None = None, *, name: str = "vpp_paper_1h") -> Rules:
    p = dict(BASELINE_PROFILE if profile is None else profile)
    if not p.get("one_position_per_symbol", False):
        raise ValueError("the simulator holds one position per symbol; profile must say so")
    if p.get("exit_mode") != "direction":
        raise ValueError(f"unexpected paper exit_mode: {p.get('exit_mode')!r}")
    return Rules(
        name=name,
        risk_pct=float(p["risk_pct"]),
        take_profit_r=float(p["take_profit_r"]),
        max_open=int(p["max_open_positions"]),
        max_notional_pct=float(p["max_notional_pct"]),
        max_symbol_notional_pct=float(p.get("max_symbol_notional_pct") or 1.0),
        max_open_risk_pct=float(p["max_open_risk_pct"]),
        daily_loss_limit_pct=float(p["daily_loss_limit_pct"]),
        one_entry_per_signal_run=bool(p["one_entry_per_signal_run"]),
        allow_short=bool(p["allow_short"]),
        liquidity_cap_pct=1e12,
        min_notional=float(p.get("min_notional", _BROKER_MIN_NOTIONAL)),
        exit_mode="direction",
        immediate_fill=False,
        bar_seconds=3600,
        time_stop_bars=None,
        full_cash=False,
        force_flat_at_end=False,
        levels_anchor="fill",
        gate_equity="cost",
        min_fill_fraction=float(p.get("min_fill_fraction", _BROKER_MIN_FILL_FRACTION)),
    )


def paper_costs(symbols: Iterable[str], profile: dict[str, Any] | None = None) -> dict[str, CostModel]:
    """Base ("paper") profile: commission per symbol + per-symbol friction in the fill, slippage 0."""
    p = dict(BASELINE_PROFILE if profile is None else profile)
    by_comm = p.get("commission_bps_by_symbol") or {}
    table = p.get("friction_bps_by_symbol") or {}
    out: dict[str, CostModel] = {}
    for s in symbols:
        comm = float(by_comm.get(s, p["commission_bps"]))
        if s in table:
            out[s] = CostModel(f"paper:{s}", comm, float(table[s]), 0.0)
        else:
            out[s] = CostModel(f"paper:{s}", comm, float(p["spread_bps"]), float(p["slippage_bps"]))
    return out


def adverse_costs(symbols: Iterable[str], profile: dict[str, Any] | None = None) -> dict[str, CostModel]:
    """Pre-registered stress: commission 10 bps + spread max(friction, 4) + slippage 8 bps per side."""
    base = paper_costs(symbols, profile)
    return {s: CostModel(f"adverse:{s}", 10.0, max(c.spread_bps, 4.0), 8.0) for s, c in base.items()}
