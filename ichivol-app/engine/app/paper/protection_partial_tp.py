"""Paper partial take-profit gate — T0-MANAGE-d.

Reuses ``app.strategy_lab.partial_tp`` (single calculation path with Lab).
Opt-in only: ``user_confirmed`` + explicit ``protection_partial_tp`` on
``entry_signal`` or portfolio ``strategy_profile``. Legacy / auto excluded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.agents.types import Direction
from app.db.models import PaperPartialExit, PaperPortfolio, PaperPosition
from app.strategy_lab.partial_tp import PartialTpStep, mfe_r, partial_level

PARTIAL_TP_KEY = "protection_partial_tp"
PARTIAL_TP_EVENT = "PROTECTION_PARTIAL_TP"


@dataclass(frozen=True)
class PaperPartialTpConfig:
    steps: tuple[PartialTpStep, ...]
    initial_stop: float
    initial_qty: float


def _parse_steps(raw_steps: Any) -> tuple[PartialTpStep, ...] | None:
    if not isinstance(raw_steps, list) or not raw_steps:
        return None
    steps: list[PartialTpStep] = []
    prev_r = 0.0
    frac_sum = 0.0
    for item in raw_steps:
        if not isinstance(item, Mapping):
            return None
        rm = item.get("r_multiple")
        fr = item.get("fraction")
        if isinstance(rm, bool) or not isinstance(rm, (int, float)) or float(rm) <= 0:
            return None
        if isinstance(fr, bool) or not isinstance(fr, (int, float)):
            return None
        r_multiple = float(rm)
        fraction = float(fr)
        if not (0.0 < fraction < 1.0):
            return None
        if r_multiple <= prev_r:
            return None
        prev_r = r_multiple
        frac_sum += fraction
        steps.append(PartialTpStep(r_multiple=r_multiple, fraction=fraction))
    if frac_sum > 1.0 + 1e-12:
        return None
    return tuple(steps)


def _raw_from(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> Mapping[str, Any] | None:
    if position.source != "user_confirmed":
        return None
    sig = position.entry_signal if isinstance(position.entry_signal, dict) else {}
    raw = sig.get(PARTIAL_TP_KEY)
    if isinstance(raw, list):
        return {"steps": raw}
    if isinstance(raw, Mapping):
        return raw
    prof = (portfolio.strategy_profile if portfolio is not None else None) or {}
    if isinstance(prof, dict):
        raw = prof.get(PARTIAL_TP_KEY)
        if isinstance(raw, list):
            return {"steps": raw}
        if isinstance(raw, Mapping):
            return raw
    return None


def resolve_paper_partial_tp(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> PaperPartialTpConfig | None:
    """Eligible when user_confirmed + explicit partial_tp config."""
    raw = _raw_from(position, portfolio)
    if raw is None:
        return None
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list):
        return None
    steps = _parse_steps(steps_raw)
    if steps is None:
        return None
    if position.stop_price is None or position.entry_price is None or not position.qty:
        return None
    initial_stop = float(raw.get("initial_stop", position.stop_price))
    initial_qty = float(raw.get("initial_qty", position.qty))
    if initial_qty <= 0:
        return None
    return PaperPartialTpConfig(
        steps=steps,
        initial_stop=initial_stop,
        initial_qty=initial_qty,
    )


def freeze_partial_tp_anchor(
    position: PaperPosition,
    config: PaperPartialTpConfig,
) -> None:
    """Persist initial_stop / initial_qty / steps on entry_signal."""
    sig = dict(position.entry_signal or {})
    blob = dict(sig.get(PARTIAL_TP_KEY) or {})
    if isinstance(sig.get(PARTIAL_TP_KEY), list):
        blob = {"steps": list(sig[PARTIAL_TP_KEY])}
    changed = False
    if "steps" not in blob:
        blob["steps"] = [
            {"r_multiple": s.r_multiple, "fraction": s.fraction} for s in config.steps
        ]
        changed = True
    if "initial_stop" not in blob:
        blob["initial_stop"] = config.initial_stop
        changed = True
    if "initial_qty" not in blob:
        blob["initial_qty"] = config.initial_qty
        changed = True
    if changed:
        sig[PARTIAL_TP_KEY] = blob
        position.entry_signal = sig


def fired_r_multiples(exits: Sequence[PaperPartialExit]) -> set[float]:
    return {float(e.r_multiple) for e in exits}


def pending_steps(
    config: PaperPartialTpConfig,
    fired: set[float],
) -> list[PartialTpStep]:
    return [s for s in config.steps if s.r_multiple not in fired]


def qty_for_step(config: PaperPartialTpConfig, step: PartialTpStep, remaining_qty: float) -> float:
    """Absolute qty for this step (fraction of original), capped by remaining."""
    want = config.initial_qty * step.fraction
    return min(want, remaining_qty)


def direction_enum(direction: str) -> Direction:
    return Direction.LONG if direction.upper() == "LONG" else Direction.SHORT


def level_for_step(
    direction: str,
    entry: float,
    config: PaperPartialTpConfig,
    step: PartialTpStep,
) -> float:
    return partial_level(
        direction_enum(direction),
        entry,
        config.initial_stop,
        step.r_multiple,
    )


def bar_hits_step(
    direction: str,
    entry: float,
    config: PaperPartialTpConfig,
    step: PartialTpStep,
    high: float,
    low: float,
) -> bool:
    return (
        mfe_r(
            direction_enum(direction),
            entry,
            config.initial_stop,
            high,
            low,
        )
        + 1e-12
        >= step.r_multiple
    )
