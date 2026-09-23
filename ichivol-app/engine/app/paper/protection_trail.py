"""Paper trailing / breakeven gate — T0-MANAGE-b.

Reuses ``app.strategy_lab.stop_trail.TrailSpec`` (single calculation path with Lab).
Opt-in only: ``user_confirmed`` + explicit ``protection_trail`` on the
position ``entry_signal`` or portfolio ``strategy_profile``. Never enabled
by default on legacy / auto lots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.db.models import PaperPortfolio, PaperPosition
from app.strategy_lab.stop_trail import TrailSpec

TRAIL_KEY = "protection_trail"
TRAIL_EVENT = "PROTECTION_TRAIL_UPDATED"


@dataclass(frozen=True)
class PaperTrailConfig:
    trail: TrailSpec
    initial_stop: float
    atr_ref: float | None
    commission_bps: float
    slippage_bps: float


def _parse_trail_raw(raw: Mapping[str, Any]) -> TrailSpec | None:
    be = raw.get("breakeven_at_r")
    am = raw.get("atr_trail_mult")
    breakeven = float(be) if be is not None else None
    atr_mult = float(am) if am is not None else None
    if breakeven is not None and breakeven <= 0:
        return None
    if atr_mult is not None and atr_mult <= 0:
        return None
    trail = TrailSpec(breakeven_at_r=breakeven, atr_trail_mult=atr_mult)
    if trail.is_empty():
        return None
    return trail


def _trail_raw_from(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> Mapping[str, Any] | None:
    if position.source != "user_confirmed":
        return None
    sig = position.entry_signal if isinstance(position.entry_signal, dict) else {}
    raw = sig.get(TRAIL_KEY)
    if isinstance(raw, Mapping):
        return raw
    prof = (portfolio.strategy_profile if portfolio is not None else None) or {}
    if isinstance(prof, dict):
        raw = prof.get(TRAIL_KEY)
        if isinstance(raw, Mapping):
            return raw
    return None


def resolve_paper_trail(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> PaperTrailConfig | None:
    """Return trail config when the position is eligible; else None.

    Gate: ``source == user_confirmed`` and an explicit ``protection_trail``
    object on ``entry_signal`` (wins) or ``strategy_profile`` (portfolio).
    """
    raw = _trail_raw_from(position, portfolio)
    if raw is None:
        return None
    trail = _parse_trail_raw(raw)
    if trail is None:
        return None
    if position.stop_price is None or position.entry_price is None:
        return None

    initial = raw.get("initial_stop")
    initial_stop = float(initial) if initial is not None else float(position.stop_price)
    atr_raw = raw.get("atr_ref")
    if atr_raw is not None:
        atr_ref = float(atr_raw)
    else:
        atr_ref = abs(float(position.entry_price) - initial_stop)

    prof = (portfolio.strategy_profile if portfolio is not None else None) or {}
    if isinstance(prof, dict):
        default_comm = float(prof.get("commission_bps", 5.0))
        default_slip = float(prof.get("slippage_bps", 3.0))
    else:
        default_comm, default_slip = 5.0, 3.0
    comm = float(raw.get("commission_bps", default_comm))
    slip = float(raw.get("slippage_bps", default_slip))
    return PaperTrailConfig(
        trail=trail,
        initial_stop=initial_stop,
        atr_ref=atr_ref if atr_ref > 0 else None,
        commission_bps=comm,
        slippage_bps=slip,
    )


def freeze_trail_anchor(position: PaperPosition, config: PaperTrailConfig) -> None:
    """Persist ``initial_stop`` / atr on ``entry_signal`` so risk stays fixed after ratchets."""
    sig = dict(position.entry_signal or {})
    trail = dict(sig.get(TRAIL_KEY) or {})
    changed = False
    if "initial_stop" not in trail:
        trail["initial_stop"] = config.initial_stop
        changed = True
    if config.atr_ref is not None and "atr_ref" not in trail:
        trail["atr_ref"] = config.atr_ref
        changed = True
    if config.trail.breakeven_at_r is not None and "breakeven_at_r" not in trail:
        trail["breakeven_at_r"] = config.trail.breakeven_at_r
        changed = True
    if config.trail.atr_trail_mult is not None and "atr_trail_mult" not in trail:
        trail["atr_trail_mult"] = config.trail.atr_trail_mult
        changed = True
    if "commission_bps" not in trail:
        trail["commission_bps"] = config.commission_bps
        changed = True
    if "slippage_bps" not in trail:
        trail["slippage_bps"] = config.slippage_bps
        changed = True
    if changed:
        sig[TRAIL_KEY] = trail
        position.entry_signal = sig
