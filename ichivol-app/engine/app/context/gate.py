"""Optional Context gates (RSI / CMF / OBV / ATR regime) for paper profiles.

Downgrade only. Baseline keeps all context_* fields off/None.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

from app.decision.pipeline import PipelineResult, StageId, StageStatus
from app.indicators.atr import VolatilityRegime
from app.indicators.cmf import CmfBias
from app.indicators.ichimoku import Candle
from app.indicators.obv import ObvBias
from app.indicators.registry import REGISTRY
from app.indicators.rsi import RsiBias, RsiParams


@dataclass(frozen=True)
class ContextGateResult:
    pipeline: PipelineResult
    blocked: bool
    reason: str | None
    context_payload: dict[str, Any] | None
    raw_decision: str


def apply_context_gate(
    pipeline: PipelineResult,
    candles: Sequence[Candle],
    profile: dict[str, Any],
) -> ContextGateResult:
    raw = pipeline.decision
    if raw not in ("BUY", "SELL"):
        return ContextGateResult(pipeline, False, None, None, raw)

    want_rsi = bool(profile.get("context_rsi"))
    want_cmf = bool(profile.get("context_cmf"))
    want_obv = bool(profile.get("context_obv"))
    want_regime = bool(profile.get("context_regime_hard"))
    if not (want_rsi or want_cmf or want_obv or want_regime):
        return ContextGateResult(pipeline, False, None, None, raw)

    if not candles:
        return ContextGateResult(
            pipeline, False, "insufficient_candles", None, raw
        )

    payload: dict[str, Any] = {}
    reasons: list[str] = []

    ids: list[str] = []
    params_by_id: dict[str, Any] = {}
    rsi_params = RsiParams(
        overbought=float(profile.get("rsi_overbought", 70.0)),
        oversold=float(profile.get("rsi_oversold", 30.0)),
        mid=float(profile.get("rsi_mid", 50.0)),
    )
    if want_regime:
        ids.append("atr")
    if want_rsi:
        ids.append("rsi")
        params_by_id["rsi"] = rsi_params
    if want_cmf:
        ids.append("cmf")
    if want_obv:
        ids.append("obv")

    computed = REGISTRY.compute_many(ids, candles, params_by_id) if ids else {}

    if want_regime:
        atr_states = computed["atr"]
        atr = atr_states[-1] if atr_states else None
        if atr is not None:
            payload["atr_regime"] = atr.regime.value
            payload["atr"] = atr.atr
            if atr.regime in (VolatilityRegime.DEAD, VolatilityRegime.EXTREME):
                reasons.append(f"regime_{atr.regime.value.lower()}")

    if want_rsi:
        rsi_state = computed["rsi"][-1]
        payload["rsi"] = rsi_state.rsi
        payload["rsi_bias"] = rsi_state.bias.value
        if rsi_state.rsi is not None:
            if raw == "BUY" and rsi_state.bias == RsiBias.OVERBOUGHT:
                reasons.append("rsi_overbought_block_long")
            if raw == "SELL" and rsi_state.bias == RsiBias.OVERSOLD:
                reasons.append("rsi_oversold_block_short")
            if profile.get("rsi_require_alignment"):
                if raw == "BUY" and rsi_state.rsi < rsi_params.mid:
                    reasons.append("rsi_not_aligned_long")
                if raw == "SELL" and rsi_state.rsi > rsi_params.mid:
                    reasons.append("rsi_not_aligned_short")

    if want_cmf:
        cmf_state = computed["cmf"][-1]
        payload["cmf"] = cmf_state.cmf
        payload["cmf_bias"] = cmf_state.bias.value
        if cmf_state.bias != CmfBias.UNKNOWN:
            if raw == "BUY" and cmf_state.bias == CmfBias.NEGATIVE:
                reasons.append("cmf_negative_block_long")
            if raw == "SELL" and cmf_state.bias == CmfBias.POSITIVE:
                reasons.append("cmf_positive_block_short")

    if want_obv:
        obv_state = computed["obv"][-1]
        payload["obv"] = obv_state.obv
        payload["obv_bias"] = obv_state.bias.value
        payload["obv_slope"] = obv_state.slope
        if obv_state.bias not in (ObvBias.UNKNOWN, ObvBias.FLAT):
            if raw == "BUY" and obv_state.bias == ObvBias.FALLING:
                reasons.append("obv_falling_block_long")
            if raw == "SELL" and obv_state.bias == ObvBias.RISING:
                reasons.append("obv_rising_block_short")

    if not reasons:
        return ContextGateResult(pipeline, False, None, payload, raw)

    reason = ";".join(reasons)
    stages = []
    for stage in pipeline.stages:
        if stage.id == StageId.REGIME:
            stages.append(
                replace(
                    stage,
                    status=StageStatus.FAIL,
                    summary=f"{stage.summary} · CTX block: {reason}",
                    codes=[*stage.codes, "context_block", *reasons],
                )
            )
        else:
            stages.append(stage)
    gated = PipelineResult(
        decision="NO_TRADE",
        direction=pipeline.direction,
        stages=stages,
        strategy_version=pipeline.strategy_version,
    )
    return ContextGateResult(gated, True, reason, payload, raw)
