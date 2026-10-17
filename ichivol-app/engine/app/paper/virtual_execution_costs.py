"""Deterministic paper execution-cost assumptions (QuantDinger virtual_execution_costs).

Paper / signal-only only — rejects any live-mode flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_COMMISSION_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 3.0


@dataclass(frozen=True)
class VirtualExecutionCostPolicy:
    commission_bps: float = DEFAULT_COMMISSION_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS
    liquidity_role: str = "taker"
    mode: str = "paper"

    def __post_init__(self) -> None:
        if str(self.mode).lower() not in ("paper", "signal", "virtual", "sim"):
            raise ValueError("virtual_execution_rejects_live_mode")
        object.__setattr__(self, "commission_bps", max(0.0, float(self.commission_bps)))
        object.__setattr__(self, "slippage_bps", max(0.0, float(self.slippage_bps)))

    @property
    def commission_rate(self) -> float:
        return self.commission_bps / 10_000.0

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0

    def commission_for(self, *, quantity: float, fill_price: float) -> float:
        notional = max(0.0, float(quantity or 0.0)) * max(0.0, float(fill_price or 0.0))
        return notional * self.commission_rate

    def round_trip_cost_fraction(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0

    def metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "liquidity_role": self.liquidity_role,
            "round_trip_fraction": self.round_trip_cost_fraction(),
        }


def resolve_virtual_execution_cost_policy(
    *,
    payload: Mapping[str, Any] | None = None,
    strategy_profile: Mapping[str, Any] | None = None,
) -> VirtualExecutionCostPolicy:
    payload = payload or {}
    strategy_profile = strategy_profile or {}
    mode = str(
        payload.get("mode")
        or strategy_profile.get("execution_mode")
        or "paper"
    ).lower()
    if mode in ("live", "broker", "real"):
        raise ValueError("virtual_execution_rejects_live_mode")
    comm = payload.get("commission_bps", strategy_profile.get("commission_bps", DEFAULT_COMMISSION_BPS))
    slip = payload.get("slippage_bps", strategy_profile.get("slippage_bps", DEFAULT_SLIPPAGE_BPS))
    return VirtualExecutionCostPolicy(
        commission_bps=float(comm),
        slippage_bps=float(slip),
        liquidity_role=str(payload.get("liquidity_role") or "taker"),
        mode="paper",
    )
