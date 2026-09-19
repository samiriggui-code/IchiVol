"""AnalysisStage — common handoff contract for IchiVol's deterministic lab.

Inspired by GPTHEIST ownership → handoff → PASS/VETO → audit, but mapped
onto IchiVol stage IDs (never city agent names). This module is additive:
it does not replace ``decision.pipeline.PipelineResult``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AnalysisStageId(str, Enum):
    DATA_QUALITY = "data_quality"
    REGIME = "regime"
    ICHIMOKU = "ichimoku"
    VOLUME = "volume"
    STRUCTURE = "structure"
    MOMENTUM = "momentum"
    LOCATION = "location"
    RISK = "risk"
    DECISION = "decision"


class AnalysisStatus(str, Enum):
    """Handoff outcome.

    PASS / FAIL / WATCH / PENDING / SKIP mirror ``PipelineStage``.
    VETO is an explicit hard block (Palermo-style) — never upgraded by later stages.
    NEUTRAL / NOT_APPLICABLE cover optional modules in ablation configs.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    VETO = "VETO"
    NEUTRAL = "NEUTRAL"
    WATCH = "WATCH"
    PENDING = "PENDING"
    SKIP = "SKIP"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class AnalysisStage:
    """One deterministic analysis handoff — JSON-serializable."""

    stage_id: AnalysisStageId
    stage_version: str
    status: AnalysisStatus
    reason: str
    symbol: str = ""
    timeframe: str = ""
    timestamp: float | None = None
    confidence: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["stage_id"] = self.stage_id.value
        body["status"] = self.status.value
        return body

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisStage:
        return cls(
            stage_id=AnalysisStageId(data["stage_id"]),
            stage_version=str(data["stage_version"]),
            status=AnalysisStatus(data["status"]),
            reason=str(data.get("reason") or ""),
            symbol=str(data.get("symbol") or ""),
            timeframe=str(data.get("timeframe") or ""),
            timestamp=data.get("timestamp"),
            confidence=data.get("confidence"),
            metrics=dict(data.get("metrics") or {}),
            evidence=list(data.get("evidence") or []),
            warnings=list(data.get("warnings") or []),
            inputs=dict(data.get("inputs") or {}),
        )


@dataclass(frozen=True)
class AnalysisHandoff:
    """Ordered stage list for one symbol/timeframe snapshot (suggest-only)."""

    run_id: str
    engine_version: str
    symbol: str
    timeframe: str
    stages: tuple[AnalysisStage, ...]
    market_data_hash: str | None = None
    decision: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "engine_version": self.engine_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "market_data_hash": self.market_data_hash,
            "decision": self.decision,
            "config": dict(self.config),
            "stages": [s.to_dict() for s in self.stages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnalysisHandoff:
        stages = tuple(AnalysisStage.from_dict(s) for s in (data.get("stages") or []))
        return cls(
            run_id=str(data["run_id"]),
            engine_version=str(data["engine_version"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            stages=stages,
            market_data_hash=data.get("market_data_hash"),
            decision=data.get("decision"),
            config=dict(data.get("config") or {}),
        )

    def has_veto(self) -> bool:
        return any(s.status == AnalysisStatus.VETO for s in self.stages)

    def veto_reasons(self) -> list[str]:
        return [s.reason for s in self.stages if s.status == AnalysisStatus.VETO]
