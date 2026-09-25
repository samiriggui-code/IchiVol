"""Shared CycleState types — mathematical description only (no BUY/SELL)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CycleRegime(str, Enum):
    TREND = "TREND"
    CYCLE = "CYCLE"
    TRANSITION = "TRANSITION"
    NOISE = "NOISE"


@dataclass(frozen=True)
class CycleState:
    """Causal cycle snapshot at one bar. Never contains buy/sell/long/short."""

    time: int
    dominant_period_candles: float | None
    secondary_period_candles: float | None
    phase: float | None
    """Fraction of cycle in [0, 1), or None if undefined."""
    phase_deg: float | None
    amplitude_normalized: float | None
    spectral_power: float | None
    spectral_concentration: float | None
    cycle_strength: float
    cycle_stability: float
    regime: CycleRegime
    bars_to_next_phase: float | None
    quality: float
    methods_agreement: float
    methods: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "dominant_period_candles": self.dominant_period_candles,
            "secondary_period_candles": self.secondary_period_candles,
            "phase": self.phase,
            "phase_deg": self.phase_deg,
            "amplitude_normalized": self.amplitude_normalized,
            "spectral_power": self.spectral_power,
            "spectral_concentration": self.spectral_concentration,
            "cycle_strength": self.cycle_strength,
            "cycle_stability": self.cycle_stability,
            "regime": self.regime.value,
            "bars_to_next_phase": self.bars_to_next_phase,
            "quality": self.quality,
            "methods_agreement": self.methods_agreement,
            "methods": self.methods,
        }
