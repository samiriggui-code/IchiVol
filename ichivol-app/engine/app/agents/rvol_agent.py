"""RVOL_AGENT: wraps app.indicators.rvol into a StrategyAgentOutput.

Deliberate design choice, per the mission brief §6 ("le RVOL ne doit pas
simplement devenir un indicateur supplementaire donnant BUY/SELL"): RVOL
measures participation/conviction, not direction. This agent therefore
always reports `direction = NEUTRAL` and `probability = 0.5` -- it never
votes on which way price should go, only on how much weight a directional
signal from another agent (e.g. ICHIMOKU_AGENT) deserves.

`confidence` is where the real information lives: it is a direct,
deterministic function of `anomaly_level` (itself a function of configurable
thresholds -- see app/indicators/rvol.py), so a future Consensus Engine can
use it to scale up or down another agent's directional conviction, exactly
as the mission describes ("RVOL = 0.55 -> WATCH / LOW CONFIDENCE",
"RVOL = 2.8 -> BUY / HIGH CONFIDENCE").
"""

from __future__ import annotations

from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.rvol import AnomalyLevel, RvolParams, RvolState, compute_rvol

from .types import Direction, StrategyAgentOutput

AGENT_NAME = "RVOL_AGENT"

_CONFIDENCE_BY_ANOMALY_LEVEL = {
    AnomalyLevel.LOW: 0.1,
    AnomalyLevel.NORMAL: 0.4,
    AnomalyLevel.SIGNIFICANT: 0.65,
    AnomalyLevel.STRONG: 0.85,
    AnomalyLevel.ANOMALY: 1.0,
    AnomalyLevel.UNKNOWN: 0.0,
}


def _reasons(state: RvolState) -> list[str]:
    reasons = []
    if state.anomaly_level == AnomalyLevel.LOW:
        reasons.append("low_participation")
    elif state.anomaly_level == AnomalyLevel.SIGNIFICANT:
        reasons.append("significant_relative_volume")
    elif state.anomaly_level == AnomalyLevel.STRONG:
        reasons.append("strong_relative_volume")
    elif state.anomaly_level == AnomalyLevel.ANOMALY:
        reasons.append("volume_anomaly")
    if state.vol_accel is not None and state.vol_accel > 0.5:
        reasons.append("volume_accelerating")
    if not reasons:
        reasons.append("normal_participation" if state.anomaly_level != AnomalyLevel.UNKNOWN else "insufficient_history")
    return reasons


def _metadata(state: RvolState) -> dict:
    return {
        "time": state.time,
        "volume": state.volume,
        "avg_volume": state.avg_volume,
        "rvol": state.rvol,
        "rvol5": state.rvol5,
        "rvol10": state.rvol10,
        "rvol20": state.rvol20,
        "vol_accel": state.vol_accel,
        "percentile": state.percentile,
        "anomaly_level": state.anomaly_level.value,
        "confirmed": state.confirmed,
        "spike": state.spike,
    }


def state_to_agent_output(state: RvolState) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent=AGENT_NAME,
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=_CONFIDENCE_BY_ANOMALY_LEVEL[state.anomaly_level],
        expected_value=0.0,
        reasons=_reasons(state),
        invalidation=[],
        metadata=_metadata(state),
    )


def analyze(
    candles: Sequence[Candle],
    params: RvolParams = RvolParams(),
) -> list[StrategyAgentOutput]:
    states = compute_rvol(candles, params)
    return [state_to_agent_output(s) for s in states]
