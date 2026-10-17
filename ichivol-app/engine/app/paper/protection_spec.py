"""Unified ProtectionSpec (QuantDinger strategy_v2) adapted to IchiVol paper.

Maps % / trail knobs onto existing ``protection_trail`` + Lab ``TrailSpec``.
Never enables live brokers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


def _ratio(value: object, *, maximum: float) -> float:
    try:
        n = float(value if value is not None else 0.0)
    except (TypeError, ValueError):
        return 0.0
    if n < 0:
        return 0.0
    return min(n, maximum)


def _boolean(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


@dataclass(frozen=True)
class ProtectionSpec:
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    trailing_stop_pct: float = 0.0
    trailing_activation_pct: float = 0.0
    time_limit_seconds: int = 0
    trailing_rebase_on_scale_in: bool = True
    # IchiVol fee-aware trail (bps) — QuantDinger fee-aware trail analogue.
    commission_bps: float = 5.0
    slippage_bps: float = 3.0
    # Lab trail (R-multiple / ATR) — preferred when set.
    breakeven_at_r: float | None = None
    atr_trail_mult: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stop_loss_pct", _ratio(self.stop_loss_pct, maximum=1.0))
        object.__setattr__(self, "take_profit_pct", _ratio(self.take_profit_pct, maximum=5.0))
        object.__setattr__(self, "trailing_stop_pct", _ratio(self.trailing_stop_pct, maximum=1.0))
        object.__setattr__(
            self,
            "trailing_activation_pct",
            _ratio(self.trailing_activation_pct, maximum=5.0),
        )
        object.__setattr__(self, "time_limit_seconds", max(0, int(self.time_limit_seconds or 0)))
        object.__setattr__(
            self,
            "trailing_rebase_on_scale_in",
            _boolean(self.trailing_rebase_on_scale_in, default=True),
        )
        object.__setattr__(self, "commission_bps", max(0.0, float(self.commission_bps or 0.0)))
        object.__setattr__(self, "slippage_bps", max(0.0, float(self.slippage_bps or 0.0)))
        if self.breakeven_at_r is not None:
            object.__setattr__(self, "breakeven_at_r", max(0.0, float(self.breakeven_at_r)))
        if self.atr_trail_mult is not None:
            object.__setattr__(self, "atr_trail_mult", max(0.0, float(self.atr_trail_mult)))

    @property
    def enabled(self) -> bool:
        return any(
            (
                self.stop_loss_pct > 0,
                self.take_profit_pct > 0,
                self.trailing_stop_pct > 0,
                self.time_limit_seconds > 0,
                self.breakeven_at_r is not None and self.breakeven_at_r > 0,
                self.atr_trail_mult is not None and self.atr_trail_mult > 0,
            )
        )

    def metadata(self) -> dict[str, Any]:
        return asdict(self)

    def to_protection_trail_dict(self) -> dict[str, Any] | None:
        """Payload for ``entry_signal.protection_trail`` (IchiVol paper)."""
        if self.breakeven_at_r is None and self.atr_trail_mult is None:
            # Percent trail → approximate Lab trail via breakeven_at_r from activation.
            if self.trailing_stop_pct <= 0:
                return None
            # Without R geometry, require explicit Lab fields — do not invent.
            return None
        out: dict[str, Any] = {
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
        }
        if self.breakeven_at_r is not None and self.breakeven_at_r > 0:
            out["breakeven_at_r"] = self.breakeven_at_r
        if self.atr_trail_mult is not None and self.atr_trail_mult > 0:
            out["atr_trail_mult"] = self.atr_trail_mult
        return out

    @classmethod
    def from_value(cls, value: object = None, **overrides: Any) -> ProtectionSpec | None:
        source: dict[str, Any] = {}
        if isinstance(value, ProtectionSpec):
            source.update(value.metadata())
        elif isinstance(value, Mapping):
            source.update(dict(value))
        source.update({k: v for k, v in overrides.items() if v is not None})
        trailing = source.get("trailing")
        if isinstance(trailing, Mapping):
            source.setdefault("trailing_stop_pct", trailing.get("pct"))
            source.setdefault("trailing_activation_pct", trailing.get("activation_pct"))
            source.setdefault("breakeven_at_r", trailing.get("breakeven_at_r"))
            source.setdefault("atr_trail_mult", trailing.get("atr_trail_mult"))
        spec = cls(
            stop_loss_pct=source.get("stop_loss_pct") or 0.0,
            take_profit_pct=source.get("take_profit_pct") or 0.0,
            trailing_stop_pct=source.get("trailing_stop_pct") or 0.0,
            trailing_activation_pct=source.get("trailing_activation_pct") or 0.0,
            time_limit_seconds=source.get("time_limit_seconds") or 0,
            trailing_rebase_on_scale_in=source.get("trailing_rebase_on_scale_in", True),
            commission_bps=source.get("commission_bps", 5.0),
            slippage_bps=source.get("slippage_bps", 3.0),
            breakeven_at_r=source.get("breakeven_at_r"),
            atr_trail_mult=source.get("atr_trail_mult"),
        )
        return spec if spec.enabled else None
