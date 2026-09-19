"""Canonical SignalContext — serializable snapshot of market state at t0.

Built from live screener outputs (Ichimoku agent, RVOL, structure, ATR,
pipeline stages). Versioned via FEATURE_VERSION so historical matching
never mixes incompatible feature schemas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.agents.types import Direction, StrategyAgentOutput
from app.decision.pipeline import PipelineResult, StageId, StageStatus
from app.indicators.atr import AtrState
from app.indicators.ichimoku import Candle
from app.indicators.structure import StructureState
from app.market_data.volume_semantics import VolumeType
from app.universe.types import AssetClass

FEATURE_VERSION = "signal_context_v1"


@dataclass(frozen=True)
class IchimokuContext:
    tk_state: str
    price_vs_cloud: str
    cloud_state: str
    direction: str
    score: float | None
    kumo_thickness: float | None = None
    chikou_state: str | None = None
    kumo_breakout: str | None = None


@dataclass(frozen=True)
class VolumeContext:
    rvol: float | None
    volume_type: str
    participation_state: str
    anomaly_level: str | None = None
    confirmed: bool | None = None


@dataclass(frozen=True)
class StructureContext:
    trend: str
    swing_state: str
    breakout_state: str
    bos: str | None = None


@dataclass(frozen=True)
class VolatilityContext:
    atr: float | None
    atr_percentile: float | None
    regime: str


@dataclass(frozen=True)
class RegimeContext:
    pipeline_regime: str
    codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConfluenceContext:
    pipeline_decision: str
    direction: str
    stage_statuses: dict[str, str] = field(default_factory=dict)
    positive_codes: list[str] = field(default_factory=list)
    contradiction_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SignalContext:
    """Versioned, serializable configuration that led to a decision."""

    symbol: str
    timeframe: str
    timestamp: int
    asset_class: str
    provider: str
    feature_version: str = FEATURE_VERSION

    ichimoku: IchimokuContext | None = None
    volume: VolumeContext | None = None
    structure: StructureContext | None = None
    volatility: VolatilityContext | None = None
    regime: RegimeContext | None = None
    confluence: ConfluenceContext | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "SignalContext":
        def _sub(cls, key: str):
            raw = data.get(key)
            return cls(**raw) if isinstance(raw, dict) else None

        return SignalContext(
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            timestamp=int(data["timestamp"]),
            asset_class=str(data.get("asset_class") or "crypto"),
            provider=str(data.get("provider") or "unknown"),
            feature_version=str(data.get("feature_version") or FEATURE_VERSION),
            ichimoku=_sub(IchimokuContext, "ichimoku"),
            volume=_sub(VolumeContext, "volume"),
            structure=_sub(StructureContext, "structure"),
            volatility=_sub(VolatilityContext, "volatility"),
            regime=_sub(RegimeContext, "regime"),
            confluence=_sub(ConfluenceContext, "confluence"),
        )


def _participation_state(rvol: StrategyAgentOutput) -> str:
    if rvol.metadata.get("confirmed"):
        return "CONFIRMED"
    anomaly = rvol.metadata.get("anomaly_level")
    if anomaly == "LOW":
        return "INSUFFICIENT"
    if anomaly == "HIGH":
        return "ELEVATED"
    return "NEUTRAL"


def _volume_type_from_candles(candles: list[Candle]) -> str:
    if not candles:
        return VolumeType.NONE.value
    return candles[-1].volume_type.value


def _stage_codes(pipeline: PipelineResult, stage_id: StageId) -> list[str]:
    for s in pipeline.stages:
        if s.id == stage_id:
            return list(s.codes)
    return []


def _stage_status(pipeline: PipelineResult, stage_id: StageId) -> str:
    for s in pipeline.stages:
        if s.id == stage_id:
            return s.status.value
    return StageStatus.PENDING.value


def build_signal_context(
    *,
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    provider: str,
    asset_class: str | AssetClass,
    ichimoku: StrategyAgentOutput,
    rvol: StrategyAgentOutput,
    pipeline: PipelineResult,
    structure: StructureState | None = None,
    atr: AtrState | None = None,
) -> SignalContext:
    """Assemble SignalContext from live scan outputs (no invented fields)."""
    ac = asset_class.value if isinstance(asset_class, AssetClass) else str(asset_class)
    meta = ichimoku.metadata
    rvol_val = rvol.metadata.get("rvol")
    rvol_f = float(rvol_val) if isinstance(rvol_val, (int, float)) else None

    positive: list[str] = []
    contradictions: list[str] = []
    for stage in pipeline.stages:
        if stage.status == StageStatus.PASS:
            positive.extend(stage.codes)
        elif stage.status in (StageStatus.FAIL, StageStatus.WATCH):
            contradictions.extend(stage.codes)

    ichi_ctx = IchimokuContext(
        tk_state=str(meta.get("tk_cross") or "NONE"),
        price_vs_cloud=str(meta.get("price_vs_kumo") or "UNKNOWN"),
        cloud_state=str(meta.get("future_kumo") or "UNKNOWN"),
        direction=ichimoku.direction.value,
        score=float(meta["score"]) if isinstance(meta.get("score"), (int, float)) else None,
        kumo_thickness=(
            float(meta["kumo_thickness"])
            if isinstance(meta.get("kumo_thickness"), (int, float))
            else None
        ),
        chikou_state=str(meta["chikou_state"]) if meta.get("chikou_state") else None,
        kumo_breakout=str(meta["kumo_breakout"]) if meta.get("kumo_breakout") else None,
    )

    vol_ctx = VolumeContext(
        rvol=rvol_f,
        volume_type=_volume_type_from_candles(candles),
        participation_state=_participation_state(rvol),
        anomaly_level=str(rvol.metadata["anomaly_level"])
        if rvol.metadata.get("anomaly_level")
        else None,
        confirmed=bool(rvol.metadata["confirmed"]) if "confirmed" in rvol.metadata else None,
    )

    struct_ctx = None
    if structure is not None:
        if structure.last_swing_high is not None and structure.last_swing_low is not None:
            swing_state = "DEFINED"
        elif structure.last_swing_high is not None or structure.last_swing_low is not None:
            swing_state = "PARTIAL"
        else:
            swing_state = "UNKNOWN"
        struct_ctx = StructureContext(
            trend=structure.bias.value,
            swing_state=swing_state,
            breakout_state=structure.bos.value,
            bos=structure.bos.value,
        )

    vola_ctx = None
    if atr is not None:
        vola_ctx = VolatilityContext(
            atr=atr.atr,
            atr_percentile=atr.percentile,
            regime=atr.regime.value,
        )

    regime_codes = _stage_codes(pipeline, StageId.REGIME)
    regime_ctx = RegimeContext(
        pipeline_regime=_stage_status(pipeline, StageId.REGIME),
        codes=regime_codes,
    )

    confluence = ConfluenceContext(
        pipeline_decision=pipeline.decision,
        direction=pipeline.direction.value
        if isinstance(pipeline.direction, Direction)
        else str(pipeline.direction),
        stage_statuses={s.id.value: s.status.value for s in pipeline.stages},
        positive_codes=positive,
        contradiction_codes=contradictions,
    )

    return SignalContext(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=int(candles[-1].time) if candles else 0,
        asset_class=ac,
        provider=provider,
        ichimoku=ichi_ctx,
        volume=vol_ctx,
        structure=struct_ctx,
        volatility=vola_ctx,
        regime=regime_ctx,
        confluence=confluence,
    )
