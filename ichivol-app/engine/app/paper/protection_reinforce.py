"""Paper reinforce (scale-in) gate — T0-MANAGE-f.

Reuses ``app.strategy_lab.reinforce`` (single risk path with Lab).
Opt-in: ``user_confirmed`` + explicit ``protection_reinforce`` on
``entry_signal`` or portfolio ``strategy_profile``. Auto / legacy excluded.
Mutually exclusive with ``protection_partial_tp`` (same as Lab parse).

Paper trigger is price-based ``at_r_multiple`` (bar MFE), because the
protection watcher does not build FeatureBars; Lab keeps ConditionGroup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.agents.types import Direction
from app.db.models import PaperPortfolio, PaperPosition, PaperReinforceAdd
from app.strategy_lab.partial_tp import mfe_r, partial_level
from app.strategy_lab.reinforce import RiskPolicy, open_risk
from app.paper.protection_partial_tp import PARTIAL_TP_KEY

REINFORCE_KEY = "protection_reinforce"
REINFORCE_EVENT = "PROTECTION_REINFORCE"


@dataclass(frozen=True)
class PaperReinforceConfig:
    add_fraction: float
    max_adds: int
    risk_policy: RiskPolicy
    max_exposure: float
    at_r_multiple: float
    initial_stop: float
    initial_qty: float
    initial_risk: float


def _raw_from(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> Mapping[str, Any] | None:
    if position.source != "user_confirmed":
        return None
    sig = position.entry_signal if isinstance(position.entry_signal, dict) else {}
    # Mutual exclusion with partial TP (Lab rule).
    if isinstance(sig.get(PARTIAL_TP_KEY), (dict, list)):
        return None
    raw = sig.get(REINFORCE_KEY)
    if isinstance(raw, Mapping):
        return raw
    prof = (portfolio.strategy_profile if portfolio is not None else None) or {}
    if isinstance(prof, dict):
        if isinstance(prof.get(PARTIAL_TP_KEY), (dict, list)):
            return None
        raw = prof.get(REINFORCE_KEY)
        if isinstance(raw, Mapping):
            return raw
    return None


def resolve_paper_reinforce(
    position: PaperPosition,
    portfolio: PaperPortfolio | None,
) -> PaperReinforceConfig | None:
    raw = _raw_from(position, portfolio)
    if raw is None:
        return None
    af = raw.get("add_fraction")
    if isinstance(af, bool) or not isinstance(af, (int, float)):
        return None
    add_fraction = float(af)
    if not (0.0 < add_fraction <= 1.0):
        return None
    rm = raw.get("at_r_multiple")
    if isinstance(rm, bool) or not isinstance(rm, (int, float)) or float(rm) <= 0:
        return None
    at_r = float(rm)
    max_adds = int(raw.get("max_adds", 1))
    if max_adds < 1:
        return None
    policy_raw = raw.get("risk_policy", "tighten_stop")
    if policy_raw not in ("tighten_stop", "reduce_qty"):
        return None
    me = raw.get("max_exposure", 1.0)
    if isinstance(me, bool) or not isinstance(me, (int, float)) or float(me) <= 0:
        return None
    max_exposure = float(me)
    if position.stop_price is None or position.entry_price is None or not position.qty:
        return None
    initial_stop = float(raw.get("initial_stop", position.stop_price))
    if "initial_qty" in raw and raw["initial_qty"] is not None:
        initial_qty = float(raw["initial_qty"])
    else:
        col = getattr(position, "initial_qty", None)
        initial_qty = float(col) if col is not None else float(position.qty)
    if initial_qty <= 0:
        return None
    direction = Direction.LONG if position.direction == "LONG" else Direction.SHORT
    if "initial_risk" in raw and raw["initial_risk"] is not None:
        initial_risk = float(raw["initial_risk"])
    else:
        initial_risk = open_risk(
            direction, float(position.entry_price), initial_stop, initial_qty
        )
    if initial_risk <= 0:
        return None
    return PaperReinforceConfig(
        add_fraction=add_fraction,
        max_adds=max_adds,
        risk_policy=policy_raw,  # type: ignore[arg-type]
        max_exposure=max_exposure,
        at_r_multiple=at_r,
        initial_stop=initial_stop,
        initial_qty=initial_qty,
        initial_risk=initial_risk,
    )


def freeze_reinforce_anchor(
    position: PaperPosition,
    config: PaperReinforceConfig,
) -> None:
    sig = dict(position.entry_signal or {})
    blob = dict(sig.get(REINFORCE_KEY) or {})
    changed = False
    for key, val in (
        ("add_fraction", config.add_fraction),
        ("max_adds", config.max_adds),
        ("risk_policy", config.risk_policy),
        ("max_exposure", config.max_exposure),
        ("at_r_multiple", config.at_r_multiple),
        ("initial_stop", config.initial_stop),
        ("initial_qty", config.initial_qty),
        ("initial_risk", config.initial_risk),
    ):
        if key not in blob:
            blob[key] = val
            changed = True
    if getattr(position, "initial_qty", None) is None:
        try:
            position.initial_qty = config.initial_qty
        except AttributeError:
            pass
    if changed:
        sig[REINFORCE_KEY] = blob
        position.entry_signal = sig


def reinforce_prev_match(position: PaperPosition) -> bool:
    """Persisted rising-edge latch (Lab ConditionGroup rising-edge analogue)."""
    sig = position.entry_signal if isinstance(position.entry_signal, dict) else {}
    blob = sig.get(REINFORCE_KEY) if isinstance(sig.get(REINFORCE_KEY), dict) else {}
    return bool(blob.get("prev_match", False))


def persist_reinforce_prev_match(position: PaperPosition, prev_match: bool) -> None:
    sig = dict(position.entry_signal or {})
    blob = dict(sig.get(REINFORCE_KEY) or {})
    flag = bool(prev_match)
    if "prev_match" in blob and bool(blob["prev_match"]) == flag:
        return
    blob["prev_match"] = flag
    sig[REINFORCE_KEY] = blob
    position.entry_signal = sig


def adds_done(rows: Sequence[PaperReinforceAdd]) -> int:
    return len(rows)


def level_for_reinforce(
    direction: str,
    entry: float,
    config: PaperReinforceConfig,
) -> float:
    return partial_level(
        Direction.LONG if direction.upper() == "LONG" else Direction.SHORT,
        entry,
        config.initial_stop,
        config.at_r_multiple,
    )


def bar_hits_reinforce(
    direction: str,
    entry: float,
    config: PaperReinforceConfig,
    high: float,
    low: float,
) -> bool:
    return (
        mfe_r(
            Direction.LONG if direction.upper() == "LONG" else Direction.SHORT,
            entry,
            config.initial_stop,
            high,
            low,
        )
        + 1e-12
        >= config.at_r_multiple
    )
