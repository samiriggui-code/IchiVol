"""T12b — Lab mirrors of live pipeline stage verdicts (observation only).

Reuses ``decision.pipeline`` stage helpers and agent converters — no duplicated
threshold math. FeatureBar fields are ADD-ONLY; live gates unchanged.
"""

from __future__ import annotations

from typing import Any

from app.agents.ichimoku_agent import state_to_agent_output as ichimoku_state_to_output
from app.agents.rvol_agent import state_to_agent_output as rvol_state_to_output
from app.agents.types import Direction
from app.decision.pipeline import (
    StageId,
    StageStatus,
    _donchian_confirmed,
    _location_stage,
    _participation_stage,
    _regime_stage,
)
from app.indicators.adx import AdxState
from app.indicators.atr import AtrState
from app.indicators.cvd import CvdState
from app.indicators.donchian import DonchianState
from app.indicators.ichimoku import IchimokuState
from app.indicators.location import LocationState, NodeType
from app.indicators.rvol import RvolState
from app.strategy_lab.regime import (
    RegimeTags,
    _direction_from_di,
    _structure_from_adx,
    _vol_from_atr,
)

# Lab RVOL boolean bands (T12b / rév.51) — ADD-ONLY; not live AnomalyLevel cutoffs.
_RVOL_FAIBLE_LT = 0.7
_RVOL_NORMAL_LT = 1.2
_RVOL_ELEVE_LT = 1.5
_RVOL_FORT_LE = 2.0


def rvol_band_flags(rvol: float | None) -> dict[str, bool]:
    """Boolean RVOL bands for Lab DSL / T10c (faible…extrême)."""
    if rvol is None:
        return {
            "rvol_faible": False,
            "rvol_normal": False,
            "rvol_eleve": False,
            "rvol_fort": False,
            "rvol_extreme": False,
        }
    return {
        "rvol_faible": rvol < _RVOL_FAIBLE_LT,
        "rvol_normal": _RVOL_FAIBLE_LT <= rvol < _RVOL_NORMAL_LT,
        "rvol_eleve": _RVOL_NORMAL_LT <= rvol < _RVOL_ELEVE_LT,
        "rvol_fort": _RVOL_ELEVE_LT <= rvol <= _RVOL_FORT_LE,
        "rvol_extreme": rvol > _RVOL_FORT_LE,
    }


def _status_value(status: StageStatus) -> str:
    return status.value


def live_parity_kwargs(
    *,
    ichi: IchimokuState,
    rvol: RvolState,
    atr: AtrState,
    adx: AdxState,
    donchian: DonchianState,
    location: LocationState,
    cvd: CvdState,
) -> dict[str, Any]:
    """FeatureBar kwargs mirroring live Ichimoku / regime / location / participation."""
    ichi_out = ichimoku_state_to_output(ichi)
    rvol_out = rvol_state_to_output(rvol)
    direction = ichi_out.direction

    regime_stage = _regime_stage(
        atr, adx, _donchian_confirmed(direction, donchian)
    )
    location_stage = _location_stage(direction, location)
    participation_stage = _participation_stage(rvol_out, cvd)

    structure_tag = _structure_from_adx(adx.strength)
    vol_tag = _vol_from_atr(atr.regime)
    dir_tag = _direction_from_di(adx.plus_di, adx.minus_di, structure_tag)
    tags = RegimeTags(
        structure=structure_tag, volatility=vol_tag, direction=dir_tag
    )

    price = location.price
    above_vwap = location.vwap is not None and price > location.vwap
    below_vwap = location.vwap is not None and price <= location.vwap
    is_long = direction == Direction.LONG
    is_short = direction == Direction.SHORT

    avwap_aligned = False
    avwap_opposed = False
    if location.avwap is not None and direction != Direction.NEUTRAL:
        wrong = price < location.avwap if is_long else price > location.avwap
        avwap_opposed = wrong
        avwap_aligned = not wrong

    congestion_hvn = location.node_type == NodeType.HVN
    inside_value_area = False
    beyond_value_area = False
    wrong_side_value_area = False
    if direction != Direction.NEUTRAL:
        breakout = (
            (location.vah is not None and price > location.vah)
            if is_long
            else (location.val is not None and price < location.val)
        )
        breakdown = (
            (location.val is not None and price < location.val)
            if is_long
            else (location.vah is not None and price > location.vah)
        )
        if breakout:
            beyond_value_area = True
        elif breakdown:
            wrong_side_value_area = True
        else:
            inside_value_area = True

    bands = rvol_band_flags(rvol.rvol)
    cvd_bias = cvd.bias.value

    return {
        # Ichimoku live (reuse agent path)
        "chikou_state": ichi.chikou_state.value,
        "future_kumo": ichi.future_kumo.value,
        "ichimoku_score": ichi.score,
        "ichimoku_direction": direction.value,
        # Regime scalars / labels
        "adx": adx.adx,
        "plus_di": adx.plus_di,
        "minus_di": adx.minus_di,
        "donchian_breakout": donchian.breakout.value,
        "regime_trending": tags.structure.value == "TRENDING",
        "regime_ranging": tags.structure.value == "RANGING",
        "regime_high_volatility": tags.volatility.value == "HIGH_VOLATILITY",
        "regime_low_volatility": tags.volatility.value == "LOW_VOLATILITY",
        "regime_normal_volatility": tags.volatility.value == "NORMAL_VOLATILITY",
        "regime_bull": tags.direction.value == "BULL",
        "regime_bear": tags.direction.value == "BEAR",
        "regime_sideways": tags.direction.value == "SIDEWAYS",
        "regime_stage_pass": _status_value(regime_stage.status),
        # Location
        "above_vwap": above_vwap,
        "below_vwap": below_vwap,
        "avwap_aligned": avwap_aligned,
        "avwap_opposed": avwap_opposed,
        "inside_value_area": inside_value_area,
        "beyond_value_area": beyond_value_area,
        "wrong_side_value_area": wrong_side_value_area,
        "congestion_hvn": congestion_hvn,
        "location_stage_pass": _status_value(location_stage.status),
        # Participation
        "cvd_bias": cvd_bias,
        **bands,
        "participation_stage_pass": _status_value(participation_stage.status),
    }


# Stage ids used by the parity test
PARITY_STAGE_FIELDS = (
    (StageId.REGIME, "regime_stage_pass"),
    (StageId.LOCATION, "location_stage_pass"),
    (StageId.PARTICIPATION, "participation_stage_pass"),
)

__all__ = [
    "PARITY_STAGE_FIELDS",
    "live_parity_kwargs",
    "rvol_band_flags",
]
