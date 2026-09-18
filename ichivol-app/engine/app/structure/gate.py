"""Optional Market Structure gate for experimental paper profiles.

Never mutates ICHIVOL_BASELINE_V1 behavior when ``structure_filter`` is None.
Downgrades only (BUY/SELL → NO_TRADE); never flips direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.decision.pipeline import PipelineResult, StageId, StageStatus
from app.indicators.ichimoku import Candle
from app.structure.adapters.mvpp import MvppStructureAdapter
from app.structure.adapters.pytrendline import PyTrendlineStructureAdapter
from app.structure.adapters.trendln import TrendlnStructureAdapter
from app.structure.atr_utils import last_atr
from app.structure.consensus import build_consensus
from app.structure.params import StructureEngineParams
from app.structure.types import MarketStructure, PriceZone


@dataclass(frozen=True)
class StructureGateResult:
    pipeline: PipelineResult
    blocked: bool
    reason: str | None
    structure_payload: dict[str, Any] | None
    raw_decision: str


def apply_structure_gate(
    pipeline: PipelineResult,
    candles: Sequence[Candle],
    profile: dict[str, Any],
    *,
    rvol: float | None = None,
) -> StructureGateResult:
    """If profile has no structure_filter, return pipeline unchanged."""
    raw = pipeline.decision
    filt = profile.get("structure_filter")
    if not filt or raw not in ("BUY", "SELL"):
        return StructureGateResult(
            pipeline=pipeline,
            blocked=False,
            reason=None,
            structure_payload=None,
            raw_decision=raw,
        )

    detectors = list(profile.get("structure_detectors") or [])
    include_py = bool(profile.get("structure_include_pytrendline"))
    block_mult = float(profile.get("structure_block_atr_mult", 1.0))
    params = StructureEngineParams(
        window_bars=min(len(candles), 300),
        pytrendline_offline_only=False,
    )
    atr = last_atr(candles, params.atr_period)
    parts: list[MarketStructure] = []

    if "mvpp" in detectors:
        parts.append(MvppStructureAdapter().detect(candles, params, atr=atr))
    if "trendln" in detectors:
        parts.append(TrendlnStructureAdapter().detect(candles, params, atr=atr))
    if "pytrendline" in detectors or include_py:
        parts.append(
            PyTrendlineStructureAdapter().detect(
                candles, params, atr=atr, allow_online=True
            )
        )

    if not parts:
        return StructureGateResult(
            pipeline=pipeline,
            blocked=False,
            reason="no_detectors",
            structure_payload=None,
            raw_decision=raw,
        )

    # Structure filter needs at least one bar; empty screener stubs must not crash.
    if not candles:
        return StructureGateResult(
            pipeline=pipeline,
            blocked=False,
            reason="insufficient_candles",
            structure_payload=None,
            raw_decision=raw,
        )

    consensus = build_consensus(parts, params, atr=atr)
    close = candles[-1].close
    opposing = _opposing_zones(raw, consensus.support_zones, consensus.resistance_zones)
    nearest = _nearest(opposing, close)

    payload: dict[str, Any] = {
        "filter": filt,
        "detectors": [p.source.value for p in parts],
        "atr": atr,
        "rvol": rvol,
        "support_zones": [_zone_brief(z) for z in consensus.support_zones[:3]],
        "resistance_zones": [_zone_brief(z) for z in consensus.resistance_zones[:3]],
    }

    blocked = False
    reason: str | None = None
    if filt == "block_near_opposing" and nearest is not None and atr and atr > 0:
        dist = nearest.distance(close)
        if dist <= atr * block_mult:
            blocked = True
            reason = (
                f"opposing_zone_within_{block_mult:.2f}_atr "
                f"(dist={dist:.4g} atr={atr:.4g} zone={nearest.low:.4g}-{nearest.high:.4g})"
            )
            payload["blocked_zone"] = _zone_brief(nearest)
            payload["distance"] = dist

    if not blocked:
        return StructureGateResult(
            pipeline=pipeline,
            blocked=False,
            reason=None,
            structure_payload=payload,
            raw_decision=raw,
        )

    # Downgrade only — attach a synthetic FAIL-ish note via stages copy
    from dataclasses import replace

    stages = list(pipeline.stages)
    # Annotate structure stage summary if present
    new_stages = []
    for stage in stages:
        if stage.id == StageId.STRUCTURE:
            new_stages.append(
                replace(
                    stage,
                    status=StageStatus.FAIL,
                    summary=f"{stage.summary} · MS block: {reason}",
                    codes=[*stage.codes, "market_structure_block"],
                )
            )
        else:
            new_stages.append(stage)
    gated = PipelineResult(
        decision="NO_TRADE",
        direction=pipeline.direction,
        stages=new_stages,
        strategy_version=pipeline.strategy_version,
    )
    return StructureGateResult(
        pipeline=gated,
        blocked=True,
        reason=reason,
        structure_payload=payload,
        raw_decision=raw,
    )


def _opposing_zones(
    decision: str,
    supports: Sequence[PriceZone],
    resistances: Sequence[PriceZone],
) -> list[PriceZone]:
    if decision == "BUY":
        return list(resistances)
    if decision == "SELL":
        return list(supports)
    return []


def _nearest(zones: Sequence[PriceZone], price: float) -> PriceZone | None:
    if not zones:
        return None
    return min(zones, key=lambda z: z.distance(price))


def _zone_brief(z: PriceZone) -> dict[str, Any]:
    return {
        "side": z.side.value,
        "low": z.low,
        "high": z.high,
        "mid": z.mid,
        "score": z.score,
        "sources": [s.value for s in z.sources],
    }
