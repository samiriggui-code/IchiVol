"""Cluster levels from multiple detectors into ATR zones."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.structure.params import StructureEngineParams
from app.structure.types import DetectorSource, LevelSide, MarketStructure, PivotPoint, PriceZone


@dataclass
class StructureConsensusEngine:
    params: StructureEngineParams = StructureEngineParams()

    def merge(self, structures: Sequence[MarketStructure], atr: float | None) -> MarketStructure:
        return build_consensus(structures, self.params, atr=atr)


def build_consensus(
    structures: Sequence[MarketStructure],
    params: StructureEngineParams = StructureEngineParams(),
    *,
    atr: float | None = None,
) -> MarketStructure:
    supports: list[PriceZone] = []
    resistances: list[PriceZone] = []
    pivots: list[PivotPoint] = []
    for s in structures:
        supports.extend(s.support_zones)
        resistances.extend(s.resistance_zones)
        # Propagate confirmation metadata from source pivots (T1f mark-only).
        pivots.extend(s.pivots)

    merged_s = _cluster_zones(supports, LevelSide.SUPPORT, atr, params)
    merged_r = _cluster_zones(resistances, LevelSide.RESISTANCE, atr, params)

    score = 0.0
    all_z = merged_s + merged_r
    if all_z:
        score = sum(z.score for z in all_z) / len(all_z)

    return MarketStructure(
        source=DetectorSource.CONSENSUS,
        pivots=tuple(pivots),
        support_zones=tuple(merged_s),
        resistance_zones=tuple(merged_r),
        structure_score=score,
        meta={
            "detectors": [s.source.value for s in structures],
            "raw_support_zones": len(supports),
            "raw_resistance_zones": len(resistances),
            "atr": atr,
        },
    )


def _cluster_zones(
    zones: Sequence[PriceZone],
    side: LevelSide,
    atr: float | None,
    params: StructureEngineParams,
) -> list[PriceZone]:
    if not zones:
        return []
    tol = (atr or abs(zones[0].mid) * 0.01) * params.consensus_atr_mult
    ordered = sorted(zones, key=lambda z: z.mid)
    clusters: list[list[PriceZone]] = [[ordered[0]]]
    for z in ordered[1:]:
        if abs(z.mid - clusters[-1][-1].mid) <= tol:
            clusters[-1].append(z)
        else:
            clusters.append([z])

    out: list[PriceZone] = []
    for cluster in clusters:
        sources = tuple(sorted({src for z in cluster for src in z.sources}, key=lambda s: s.value))
        if len(sources) < params.min_detectors_agree and len(cluster) < 1:
            continue
        mids = [z.mid for z in cluster]
        mid = sum(mids) / len(mids)
        half = (atr or abs(mid) * 0.002) * params.zone_atr_mult
        # Expand to cover member zones
        low = min(z.low for z in cluster)
        high = max(z.high for z in cluster)
        low = min(low, mid - half)
        high = max(high, mid + half)
        touch = max(z.touch_count for z in cluster)
        # Score: agreement × touches × mean member score
        agree = len(sources)
        mean_score = sum(z.score for z in cluster) / len(cluster)
        score = agree * 10.0 + touch + mean_score * 0.01
        out.append(
            PriceZone(
                side=side,
                low=low,
                high=high,
                mid=mid,
                score=score,
                touch_count=touch,
                sources=sources,
                atr_width=high - low,
            )
        )

    out.sort(key=lambda z: z.score, reverse=True)
    return out[: params.max_lines_per_side]
