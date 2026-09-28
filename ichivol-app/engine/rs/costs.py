"""Profils de coûts RS-03 §6 (bps par côté)."""

from __future__ import annotations

from dataclasses import dataclass

from rs import (
    ADVERSE_COMMISSION_BPS,
    ADVERSE_MIN_SPREAD_BPS,
    ADVERSE_SLIPPAGE_BPS,
    PAPER_COMMISSION_BPS,
    PAPER_FRICTION_BPS,
)


@dataclass(frozen=True)
class SymbolCost:
    commission_bps: float
    friction_bps: float  # spread + slippage, appliqué au prix d'exécution

    def fill(self, raw: float, side: str) -> float:
        f = self.friction_bps / 10_000.0
        return raw * (1 + f) if side == "buy" else raw * (1 - f)

    def fee(self, notional: float) -> float:
        return abs(notional) * self.commission_bps / 10_000.0


def cost_profile(profile: str) -> dict[str, SymbolCost]:
    if profile == "paper":
        return {s: SymbolCost(PAPER_COMMISSION_BPS, fr) for s, fr in PAPER_FRICTION_BPS.items()}
    if profile == "adverse":
        return {
            s: SymbolCost(ADVERSE_COMMISSION_BPS, max(fr, ADVERSE_MIN_SPREAD_BPS) + ADVERSE_SLIPPAGE_BPS)
            for s, fr in PAPER_FRICTION_BPS.items()
        }
    raise ValueError(f"unknown cost profile: {profile}")
