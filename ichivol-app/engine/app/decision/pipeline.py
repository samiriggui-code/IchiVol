"""Staged decision pipeline -- the north-star replacement for
`combiner.py`'s MVP product rule (docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md,
docs/TRADING_ARCHITECTURE_V2.md §2).

Direction -> Participation -> Structure/MTF -> Location -> Regime/Risk ->
label. Each stage after Direction can only downgrade the outcome (WATCH or
NO_TRADE) -- none of them ever flips LONG into SHORT or vice versa
(TRADING_ARCHITECTURE_V2.md §7 rules 1-4). Location (V1.5, Volume Profile +
VWAP/AVWAP, app/indicators/location.py) reports "pending" only when no
`LocationState` is supplied -- same graceful-degradation convention as
Structure/ATR being optional.

The stage shape ({id, status, summary, codes}) matches
ichivol-app/src/lib/decisionPipeline.ts::NativePipelinePayload exactly, so
the frontend can render this natively instead of its current client-side
approximation the moment `/decisions/{symbol}` starts returning a
`pipeline` field (see app/api/routes.py).

This module does not replace `combiner.py`'s output in the API today --
see that module's docstring for why the migration is additive, not a
swap, for this pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.agents.types import Direction, StrategyAgentOutput
from app.indicators.adx import AdxState, TrendStrength
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.cvd import CvdBias, CvdState
from app.indicators.donchian import DonchianBreakout, DonchianState
from app.indicators.location import LocationState, NodeType
from app.indicators.oi_funding import FundingBias, OiFundingState, OiTrend
from app.indicators.structure import BosEvent, StructureBias, StructureState

STRATEGY_VERSION = "ichivol_pipeline_v1"


class StageId(str, Enum):
    DIRECTION = "direction"
    PARTICIPATION = "participation"
    STRUCTURE = "structure"
    LOCATION = "location"
    REGIME = "regime"


class StageStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WATCH = "watch"
    PENDING = "pending"
    SKIP = "skip"


@dataclass(frozen=True)
class PipelineStage:
    id: StageId
    status: StageStatus
    summary: str
    codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineResult:
    decision: str  # BUY | SELL | WATCH | NO_TRADE
    direction: Direction
    stages: list[PipelineStage]
    strategy_version: str = STRATEGY_VERSION


def _direction_stage(ichimoku: StrategyAgentOutput) -> PipelineStage:
    status = StageStatus.WATCH if ichimoku.direction == Direction.NEUTRAL else StageStatus.PASS
    score = ichimoku.metadata.get("score")
    summary = (
        f"{ichimoku.direction.value} · score {score:.0f} · conf {ichimoku.confidence:.0%}"
        if isinstance(score, (int, float))
        else f"{ichimoku.direction.value} · conf {ichimoku.confidence:.0%}"
    )
    return PipelineStage(StageId.DIRECTION, status, summary, list(ichimoku.reasons))


def _participation_stage(
    rvol: StrategyAgentOutput,
    cvd: CvdState | None = None,
    oi_funding: OiFundingState | None = None,
) -> PipelineStage:
    confirmed = rvol.metadata.get("confirmed")
    anomaly = rvol.metadata.get("anomaly_level")
    rvol_value = rvol.metadata.get("rvol")

    if confirmed:
        status = StageStatus.PASS
    elif anomaly == "LOW":
        status = StageStatus.FAIL
    else:
        status = StageStatus.WATCH

    summary = f"RVOL {rvol_value:.2f}×" if isinstance(rvol_value, (int, float)) else "RVOL indisponible"

    codes = list(rvol.reasons)
    # CVD + OI/Funding (V2 "participation avancée", docs/METHODS-ROADMAP.md)
    # enrich this stage's context only -- RVOL alone still decides
    # pass/fail/watch above. Neither ever adds a vote or changes `status`.
    if cvd is not None and cvd.bias != CvdBias.UNKNOWN:
        if cvd.bias == CvdBias.BULLISH:
            codes.append("cvd_buy_pressure")
        elif cvd.bias == CvdBias.BEARISH:
            codes.append("cvd_sell_pressure")
        else:
            codes.append("cvd_balanced")
        summary += f" · delta {cvd.rolling_delta:+.4g}"

    if oi_funding is not None:
        if oi_funding.oi_trend == OiTrend.RISING:
            codes.append("oi_rising")
        elif oi_funding.oi_trend == OiTrend.FALLING:
            codes.append("oi_falling")

        if oi_funding.funding_bias == FundingBias.CROWDED_LONG:
            codes.append("funding_crowded_long")
        elif oi_funding.funding_bias == FundingBias.CROWDED_SHORT:
            codes.append("funding_crowded_short")

        if oi_funding.funding_rate is not None:
            summary += f" · funding {oi_funding.funding_rate * 100:+.4f}%"

    return PipelineStage(StageId.PARTICIPATION, status, summary, codes)


def _structure_stage(
    direction: Direction,
    structure: StructureState | None,
    mtf_aligned: bool | None,
) -> PipelineStage:
    if structure is None:
        return PipelineStage(
            StageId.STRUCTURE, StageStatus.PENDING, "Price Action + MTF — pas encore calculé", []
        )

    codes: list[str] = []
    bullish_bias = structure.bias == StructureBias.BULLISH
    bearish_bias = structure.bias == StructureBias.BEARISH

    aligned_bias = (direction == Direction.LONG and bullish_bias) or (
        direction == Direction.SHORT and bearish_bias
    )
    opposed_bias = (direction == Direction.LONG and bearish_bias) or (
        direction == Direction.SHORT and bullish_bias
    )
    bos_confirms = (direction == Direction.LONG and structure.bos == BosEvent.BULLISH) or (
        direction == Direction.SHORT and structure.bos == BosEvent.BEARISH
    )
    bos_invalidates = (direction == Direction.LONG and structure.bos == BosEvent.BEARISH) or (
        direction == Direction.SHORT and structure.bos == BosEvent.BULLISH
    )

    if aligned_bias:
        codes.append("structure_aligned")
    if opposed_bias:
        codes.append("structure_opposed")
    if bos_confirms:
        codes.append("bos_confirms_direction")
    if bos_invalidates:
        codes.append("bos_invalidates_direction")
    if mtf_aligned is True:
        codes.append("mtf_aligned")
    elif mtf_aligned is False:
        codes.append("mtf_opposed")

    if bos_invalidates:
        status = StageStatus.FAIL
    elif opposed_bias or mtf_aligned is False:
        status = StageStatus.WATCH
    elif aligned_bias or bos_confirms:
        status = StageStatus.PASS
    else:
        status = StageStatus.WATCH

    summary = f"Structure {structure.bias.value}"
    if structure.bos not in (BosEvent.NONE, BosEvent.UNKNOWN):
        summary += f", BOS {structure.bos.value}"
    if mtf_aligned is not None:
        summary += f", MTF {'aligné' if mtf_aligned else 'opposé'}"

    return PipelineStage(StageId.STRUCTURE, status, summary, codes)


def _location_stage(direction: Direction, location: LocationState | None) -> PipelineStage:
    if location is None:
        return PipelineStage(
            StageId.LOCATION, StageStatus.PENDING, "Volume Profile + VWAP — pas encore calculé", []
        )
    if direction == Direction.NEUTRAL:
        return PipelineStage(
            StageId.LOCATION, StageStatus.PASS, "Direction neutre — emplacement non qualifié", []
        )

    price = location.price
    is_long = direction == Direction.LONG
    codes: list[str] = []

    if location.vwap is not None:
        codes.append("above_vwap" if price > location.vwap else "below_vwap")

    wrong_side_avwap = False
    if location.avwap is not None:
        wrong_side_avwap = price < location.avwap if is_long else price > location.avwap
        codes.append("avwap_opposed" if wrong_side_avwap else "avwap_aligned")

    congestion = location.node_type == NodeType.HVN
    if congestion:
        codes.append("congestion_hvn")
    elif location.node_type == NodeType.LVN:
        codes.append("thin_liquidity_lvn")

    # "Beyond" the value area in the direction of the trade = healthy value
    # migration (docs/METHODS-ROADMAP.md: "prix > VAH" = excellente config
    # for a LONG). The opposite side = the trade fighting where volume
    # actually traded -- a bad location, not just a neutral one.
    breakout = (location.vah is not None and price > location.vah) if is_long else (
        location.val is not None and price < location.val
    )
    breakdown = (location.val is not None and price < location.val) if is_long else (
        location.vah is not None and price > location.vah
    )
    if breakout:
        codes.append("beyond_value_area")
    elif breakdown:
        codes.append("wrong_side_value_area")
    else:
        codes.append("inside_value_area")

    # Congestion, wrong side of the value area, or wrong side of the
    # anchored VWAP all downgrade (never invert direction) --
    # docs/METHODS-ROADMAP.md §6 rule 2.
    status = StageStatus.FAIL if (congestion or breakdown or wrong_side_avwap) else StageStatus.PASS

    parts = [f"Prix {price:.4g}"]
    if location.poc is not None:
        parts.append(f"POC {location.poc:.4g}")
    if location.vah is not None and location.val is not None:
        parts.append(f"VA [{location.val:.4g}, {location.vah:.4g}]")
    if location.avwap is not None:
        parts.append(f"AVWAP {location.avwap:.4g}")
    summary = " · ".join(parts)

    return PipelineStage(StageId.LOCATION, status, summary, codes)


_ADX_CODE = {
    TrendStrength.ABSENT: "adx_no_trend",
    TrendStrength.DEVELOPING: "adx_developing",
    TrendStrength.TRENDING: "adx_trending",
    TrendStrength.STRONG: "adx_strong_trend",
}

# ADX absent/developing => not a confirmed trend -- gate live (promoted
# 2026-09-16, docs/METHODS-ROADMAP.md's own bar: "garder seulement si
# backtest prouve un edge"). Real backtest across 3 real windows (BTCUSDT
# 1h/4h, ETHUSDT 1h) showed PIPELINE's Sharpe improving and max drawdown
# shrinking in all three when entries were withheld below this same
# threshold (see ichivol-app/engine/README.md) -- proven, not assumed.
_ADX_TREND_CONFIRMED = (TrendStrength.TRENDING, TrendStrength.STRONG)


def _adx_codes_and_suffix(adx: AdxState | None) -> tuple[list[str], str]:
    if adx is None or adx.strength == TrendStrength.UNKNOWN:
        return [], ""
    return [_ADX_CODE[adx.strength]], f" · ADX {adx.adx:.3g}"


def _donchian_confirmed(direction: Direction, donchian: DonchianState | None) -> bool | None:
    if donchian is None or donchian.breakout == DonchianBreakout.UNKNOWN or direction == Direction.NEUTRAL:
        return None
    if direction == Direction.LONG:
        return donchian.breakout == DonchianBreakout.UP
    return donchian.breakout == DonchianBreakout.DOWN


def _regime_stage(
    atr: AtrState | None,
    adx: AdxState | None = None,
    donchian_confirmed: bool | None = None,
) -> PipelineStage:
    adx_codes, adx_suffix = _adx_codes_and_suffix(adx)

    if atr is None or atr.regime == VolatilityRegime.UNKNOWN:
        return PipelineStage(
            StageId.REGIME, StageStatus.PENDING, "ATR — historique insuffisant", []
        )
    if atr.regime == VolatilityRegime.DEAD:
        return PipelineStage(
            StageId.REGIME, StageStatus.FAIL,
            f"ATR {atr.atr:.4g} — régime mort{adx_suffix}", ["regime_dead", *adx_codes],
        )
    if atr.regime == VolatilityRegime.EXTREME:
        return PipelineStage(
            StageId.REGIME,
            StageStatus.FAIL,
            f"ATR {atr.atr:.4g} — volatilité extrême{adx_suffix}",
            ["regime_extreme", *adx_codes],
        )

    # V3 ADX gate: still never votes direction (rule unchanged) -- only
    # ever downgrades an otherwise-normal regime to FAIL, same as ATR
    # DEAD/EXTREME above. Missing ADX (short history) never gates -- it can
    # only veto when it actually has a confirmed reading.
    if adx is not None and adx.strength not in (TrendStrength.UNKNOWN, *_ADX_TREND_CONFIRMED):
        summary = f"ATR {atr.atr:.4g} — régime normal mais pas de tendance confirmée{adx_suffix}"
        return PipelineStage(StageId.REGIME, StageStatus.FAIL, summary, ["regime_no_trend", *adx_codes])

    # V3 Donchian gate, promoted 2026-09-16 after a real 3-window backtest
    # (BTCUSDT 1h/4h, ETHUSDT 1h, see ichivol-app/engine/README.md §Donchian
    # + Wyckoff): drawdown improved in all 3 windows, Sharpe in 2/3 --
    # PIPELINE's own BUY/SELL, withheld unless Donchian confirms a genuine
    # break of the prior `period`-bar range in the same direction (never a
    # vote of its own, only a veto on an otherwise-confirmed direction).
    # Missing/unknown Donchian (short history) never gates, same convention
    # as ADX above -- it can only downgrade when it actually has a reading.
    if donchian_confirmed is False:
        summary = f"ATR {atr.atr:.4g} — régime normal mais pas de vraie cassure de range{adx_suffix}"
        return PipelineStage(StageId.REGIME, StageStatus.FAIL, summary, ["regime_no_breakout", *adx_codes])

    stop = atr.suggested_stop_distance
    summary = f"ATR {atr.atr:.4g} — régime normal" + (
        f", stop suggéré ±{stop:.4g}" if stop is not None else ""
    ) + adx_suffix
    return PipelineStage(StageId.REGIME, StageStatus.PASS, summary, ["regime_normal", *adx_codes])


def _final_decision(direction: Direction, stages: dict[StageId, PipelineStage]) -> str:
    if stages[StageId.REGIME].status == StageStatus.FAIL:
        return "NO_TRADE"
    if direction == Direction.NEUTRAL:
        return "WATCH"
    if stages[StageId.STRUCTURE].status == StageStatus.FAIL:
        return "WATCH"
    if stages[StageId.PARTICIPATION].status == StageStatus.FAIL:
        return "WATCH"
    if stages[StageId.LOCATION].status == StageStatus.FAIL:
        return "WATCH"
    return "BUY" if direction == Direction.LONG else "SELL"


def build_pipeline(
    ichimoku: StrategyAgentOutput,
    rvol: StrategyAgentOutput,
    structure: StructureState | None = None,
    atr: AtrState | None = None,
    mtf_aligned: bool | None = None,
    location: LocationState | None = None,
    cvd: CvdState | None = None,
    oi_funding: OiFundingState | None = None,
    adx: AdxState | None = None,
    donchian: DonchianState | None = None,
) -> PipelineResult:
    direction = ichimoku.direction
    stages_list = [
        _direction_stage(ichimoku),
        _participation_stage(rvol, cvd, oi_funding),
        _structure_stage(direction, structure, mtf_aligned),
        _location_stage(direction, location),
        _regime_stage(atr, adx, _donchian_confirmed(direction, donchian)),
    ]
    by_id = {s.id: s for s in stages_list}
    decision = _final_decision(direction, by_id)
    return PipelineResult(decision=decision, direction=direction, stages=stages_list)
