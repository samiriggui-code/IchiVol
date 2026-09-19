"""EvidenceEngine — produce EvidenceReport around a SignalContext.

Does not emit BUY/SELL. Packages historical matches, optional ablation /
event-study summaries, and sample-quality metadata. Confidence here is
never an invented percentage: when present it is favorable_rate from
historical observations with an explicit sample_size.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from app.evidence.context import SignalContext
from app.evidence.matching import (
    DEFAULT_HORIZONS,
    MatchCriteria,
    MatchStats,
    match_historical,
    match_stats_dict,
)
from app.evidence.sample import SampleQuality
from app.evidence.versions import EVIDENCE_ENGINE_VERSION, RULES_VERSION
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class AblationSummaryRow:
    label: str
    sample_size: int
    favorable_rate: float | None
    mean_return_pct: float | None
    median_return_pct: float | None


@dataclass(frozen=True)
class EvidenceReport:
    context: SignalContext
    evidence_engine_version: str
    rules_version: str
    feature_version: str
    strategy_version: str

    historical: MatchStats
    ablation: list[AblationSummaryRow] = field(default_factory=list)
    event_study: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None

    positive_evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    why_not_long: list[str] = field(default_factory=list)
    why_not_short: list[str] = field(default_factory=list)

    def calibration_note(self) -> str:
        """Documented, reproducible statement — never a fake confidence %."""
        h = self.historical
        if h.sample_quality == SampleQuality.NO_DATA:
            return "NO_DATA: no comparable historical configurations found."
        if h.status == "INSUFFICIENT_EVIDENCE":
            return (
                f"INSUFFICIENT_EVIDENCE: n={h.sample_size} "
                f"({h.sample_quality.value}); do not treat rates as reliable."
            )
        if h.favorable_rate is None:
            return f"VALID sample n={h.sample_size} but no measurable forward returns."
        return (
            f"Historical favorable_rate={h.favorable_rate:.1%} "
            f"over n={h.sample_size} matches at horizon={h.horizon} "
            f"(mean={h.mean_return_pct}, median={h.median_return_pct}). "
            "This is an observation rate, not a predicted probability."
        )


def explain_from_context(
    ctx: SignalContext,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    positive: list[str] = []
    contradictions: list[str] = []
    why_not_long: list[str] = []
    why_not_short: list[str] = []

    if ctx.ichimoku:
        if ctx.ichimoku.direction == "LONG":
            positive.append(f"ichimoku_direction_long:{ctx.ichimoku.tk_state}")
            if ctx.ichimoku.price_vs_cloud == "ABOVE":
                positive.append("price_above_kumo")
        elif ctx.ichimoku.direction == "SHORT":
            positive.append(f"ichimoku_direction_short:{ctx.ichimoku.tk_state}")
            if ctx.ichimoku.price_vs_cloud == "BELOW":
                positive.append("price_below_kumo")
        else:
            contradictions.append("ichimoku_neutral")
            why_not_long.append("no_clear_ichimoku_bias")
            why_not_short.append("no_clear_ichimoku_bias")

    if ctx.volume:
        if ctx.volume.participation_state == "INSUFFICIENT":
            contradictions.append(f"rvol_insufficient:{ctx.volume.rvol}")
            why_not_long.append("rvol_insufficient")
            why_not_short.append("rvol_insufficient")
        elif ctx.volume.participation_state == "CONFIRMED":
            positive.append(f"rvol_confirmed:{ctx.volume.rvol}")
        if ctx.volume.volume_type in ("TICK_VOLUME", "NONE", "SYNTHETIC_VOLUME"):
            contradictions.append(f"volume_semantics:{ctx.volume.volume_type}")

    if ctx.structure:
        if ctx.structure.trend == "BULLISH":
            positive.append("structure_bullish")
            why_not_short.append("structure_opposed_to_short")
        elif ctx.structure.trend == "BEARISH":
            positive.append("structure_bearish")
            why_not_long.append("structure_opposed_to_long")

    if ctx.regime and ctx.regime.pipeline_regime == "fail":
        contradictions.append("regime_fail")
        why_not_long.append("regime_unfavorable")
        why_not_short.append("regime_unfavorable")

    if ctx.confluence:
        positive.extend(c for c in ctx.confluence.positive_codes if c not in positive)
        contradictions.extend(
            c for c in ctx.confluence.contradiction_codes if c not in contradictions
        )

    invalidation: list[str] = []
    if ctx.ichimoku and ctx.ichimoku.direction == "LONG":
        invalidation.extend(["close_below_kijun", "structure_break_bearish"])
    elif ctx.ichimoku and ctx.ichimoku.direction == "SHORT":
        invalidation.extend(["close_above_kijun", "structure_break_bullish"])
    else:
        invalidation.append("direction_unresolved")

    return positive, contradictions, why_not_long, why_not_short, invalidation


class EvidenceEngine:
    """Evaluate evidence for a SignalContext against an optional catalog."""

    def __init__(
        self,
        *,
        criteria: MatchCriteria | None = None,
        horizons: Sequence[int] = DEFAULT_HORIZONS,
        primary_horizon: int = 10,
        strategy_version: str = "ichivol_pipeline_v1",
    ) -> None:
        self.criteria = criteria or MatchCriteria()
        self.horizons = tuple(horizons)
        self.primary_horizon = primary_horizon
        self.strategy_version = strategy_version

    def evaluate(
        self,
        context: SignalContext,
        catalog: Sequence[tuple[SignalContext, Sequence[Candle], int]] = (),
        *,
        ablation: Sequence[AblationSummaryRow] | None = None,
        event_study: dict[str, Any] | None = None,
        walk_forward: dict[str, Any] | None = None,
        extra_invalidation: Sequence[str] | None = None,
    ) -> EvidenceReport:
        historical = match_historical(
            context,
            catalog,
            criteria=self.criteria,
            horizons=self.horizons,
            primary_horizon=self.primary_horizon,
        )
        positive, contradictions, why_not_long, why_not_short, invalidation = explain_from_context(
            context
        )
        if historical.status == "INSUFFICIENT_EVIDENCE":
            contradictions.append("insufficient_historical_evidence")
            why_not_long.append("insufficient_historical_evidence")
            why_not_short.append("insufficient_historical_evidence")
        elif (
            historical.status == "VALID"
            and historical.favorable_rate is not None
            and historical.favorable_rate < 0.45
        ):
            contradictions.append("poor_historical_expectancy")
            why_not_long.append("poor_historical_expectancy")
            why_not_short.append("poor_historical_expectancy")

        if extra_invalidation:
            invalidation = list(dict.fromkeys([*invalidation, *extra_invalidation]))

        return EvidenceReport(
            context=context,
            evidence_engine_version=EVIDENCE_ENGINE_VERSION,
            rules_version=RULES_VERSION,
            feature_version=context.feature_version,
            strategy_version=self.strategy_version,
            historical=historical,
            ablation=list(ablation or []),
            event_study=event_study,
            walk_forward=walk_forward,
            positive_evidence=positive,
            contradictions=contradictions,
            invalidation=invalidation,
            why_not_long=why_not_long,
            why_not_short=why_not_short,
        )


def evaluate_evidence(
    context: SignalContext,
    catalog: Sequence[tuple[SignalContext, Sequence[Candle], int]] = (),
    **kwargs: Any,
) -> EvidenceReport:
    return EvidenceEngine().evaluate(context, catalog, **kwargs)


def evidence_report_dict(report: EvidenceReport) -> dict[str, Any]:
    return {
        "evidence_engine_version": report.evidence_engine_version,
        "rules_version": report.rules_version,
        "feature_version": report.feature_version,
        "strategy_version": report.strategy_version,
        "context": report.context.to_dict(),
        "historical": match_stats_dict(report.historical),
        "calibration_note": report.calibration_note(),
        "ablation": [asdict(row) for row in report.ablation],
        "event_study": report.event_study,
        "walk_forward": report.walk_forward,
        "positive_evidence": report.positive_evidence,
        "contradictions": report.contradictions,
        "invalidation": report.invalidation,
        "why_not_long": report.why_not_long,
        "why_not_short": report.why_not_short,
    }
