"""Validates the staged pipeline's core rule (docs/TRADING_ARCHITECTURE_V2.md
§7): every stage after Direction can only downgrade the outcome to
WATCH/NO_TRADE -- none of them ever flips LONG into SHORT or vice versa.
"""

from __future__ import annotations

from app.agents.types import Direction, StrategyAgentOutput
from app.decision.pipeline import StageId, StageStatus, build_pipeline
from app.indicators.adx import AdxState, TrendStrength
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.cvd import CvdBias, CvdState
from app.indicators.donchian import DonchianBreakout, DonchianState
from app.indicators.location import LocationState, NodeType
from app.indicators.oi_funding import FundingBias, OiFundingState, OiTrend
from app.indicators.structure import BosEvent, StructureBias, StructureState


def _agent_output(agent: str, direction: Direction, confidence: float, **metadata) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent=agent,
        direction=direction,
        probability=0.7,
        confidence=confidence,
        expected_value=0.0,
        reasons=[],
        invalidation=[],
        metadata=metadata,
    )


def _ichi(direction: Direction, confidence: float = 1.0, score: float = 50.0) -> StrategyAgentOutput:
    return _agent_output("ICHIMOKU_AGENT", direction, confidence, score=score)


def _rvol(confirmed: bool, anomaly: str = "SIGNIFICANT", rvol: float = 2.0) -> StrategyAgentOutput:
    return _agent_output(
        "RVOL_AGENT", Direction.NEUTRAL, 0.5, confirmed=confirmed, anomaly_level=anomaly, rvol=rvol
    )


def _structure(bias: StructureBias, bos: BosEvent = BosEvent.NONE) -> StructureState:
    return StructureState(time=0, last_swing_high=110.0, last_swing_low=90.0, bias=bias, bos=bos)


def _atr(regime: VolatilityRegime) -> AtrState:
    return AtrState(
        time=0, true_range=1.0, atr=1.0, percentile=0.5, regime=regime, suggested_stop_distance=1.5
    )


def _location(
    price: float = 100.0,
    vah: float | None = 105.0,
    val: float | None = 95.0,
    avwap: float | None = 100.0,
    node_type: NodeType = NodeType.NEUTRAL,
) -> LocationState:
    return LocationState(
        time=0, price=price, poc=100.0, vah=vah, val=val, node_type=node_type,
        vwap=100.0, avwap=avwap, avwap_anchor_time=0,
    )


def test_full_confirmation_across_every_stage_yields_buy():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BULLISH, BosEvent.BULLISH),
        atr=_atr(VolatilityRegime.NORMAL),
        mtf_aligned=True,
    )
    assert result.decision == "BUY"
    assert result.direction == Direction.LONG
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.DIRECTION].status == StageStatus.PASS
    assert stages[StageId.PARTICIPATION].status == StageStatus.PASS
    assert stages[StageId.STRUCTURE].status == StageStatus.PASS
    assert stages[StageId.LOCATION].status == StageStatus.PENDING
    assert stages[StageId.REGIME].status == StageStatus.PASS


def test_short_direction_is_never_flipped_to_buy_by_other_stages():
    result = build_pipeline(
        ichimoku=_ichi(Direction.SHORT),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BEARISH, BosEvent.BEARISH),
        atr=_atr(VolatilityRegime.NORMAL),
    )
    assert result.decision == "SELL"
    assert result.direction == Direction.SHORT


def test_dead_regime_forces_no_trade_regardless_of_direction():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BULLISH, BosEvent.BULLISH),
        atr=_atr(VolatilityRegime.DEAD),
    )
    assert result.decision == "NO_TRADE"
    # ...but direction itself is preserved for display, never mutated to NEUTRAL
    assert result.direction == Direction.LONG


def test_extreme_regime_also_forces_no_trade():
    result = build_pipeline(
        ichimoku=_ichi(Direction.SHORT),
        rvol=_rvol(confirmed=True),
        structure=None,
        atr=_atr(VolatilityRegime.EXTREME),
    )
    assert result.decision == "NO_TRADE"


def test_neutral_direction_is_always_watch():
    result = build_pipeline(ichimoku=_ichi(Direction.NEUTRAL), rvol=_rvol(confirmed=True))
    assert result.decision == "WATCH"


def test_bos_invalidating_direction_downgrades_to_watch_not_a_flip():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BEARISH, BosEvent.BEARISH),  # invalidates LONG
        atr=_atr(VolatilityRegime.NORMAL),
    )
    assert result.decision == "WATCH"
    assert result.direction == Direction.LONG  # still LONG, just not actionable


def test_low_participation_downgrades_to_watch():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=False, anomaly="LOW", rvol=0.3),
        structure=_structure(StructureBias.BULLISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
    )
    assert result.decision == "WATCH"


def test_missing_structure_and_atr_report_pending_not_a_crash():
    result = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True))
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.STRUCTURE].status == StageStatus.PENDING
    assert stages[StageId.REGIME].status == StageStatus.PENDING
    # Direction+participation alone are enough to still reach an actionable label.
    assert result.decision == "BUY"


def test_location_breakout_beyond_value_area_passes_for_long():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BULLISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
        location=_location(price=110.0, vah=105.0, val=95.0, avwap=100.0),
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.LOCATION].status == StageStatus.PASS
    assert "beyond_value_area" in stages[StageId.LOCATION].codes
    assert result.decision == "BUY"


def test_location_wrong_side_of_anchored_vwap_downgrades_long_to_watch():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BULLISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
        # Inside the value area (95 < 98 < 105) but below AVWAP -- "attendre
        # reclaim AVWAP" per docs/METHODS-ROADMAP.md §3 example.
        location=_location(price=98.0, vah=105.0, val=95.0, avwap=100.0),
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.LOCATION].status == StageStatus.FAIL
    assert "avwap_opposed" in stages[StageId.LOCATION].codes
    assert result.decision == "WATCH"
    assert result.direction == Direction.LONG  # downgraded, never flipped


def test_location_congestion_in_a_high_volume_node_downgrades_regardless_of_direction():
    result = build_pipeline(
        ichimoku=_ichi(Direction.SHORT),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BEARISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
        location=_location(price=100.0, vah=105.0, val=95.0, avwap=100.0, node_type=NodeType.HVN),
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.LOCATION].status == StageStatus.FAIL
    assert "congestion_hvn" in stages[StageId.LOCATION].codes
    assert result.decision == "WATCH"


def test_location_logic_is_symmetric_for_short_direction():
    result = build_pipeline(
        ichimoku=_ichi(Direction.SHORT),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BEARISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
        # Below the value area and below AVWAP -- the "good" side for a SHORT.
        location=_location(price=90.0, vah=105.0, val=95.0, avwap=100.0),
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.LOCATION].status == StageStatus.PASS
    assert "beyond_value_area" in stages[StageId.LOCATION].codes
    assert result.decision == "SELL"


def test_location_neutral_direction_is_not_qualified():
    result = build_pipeline(
        ichimoku=_ichi(Direction.NEUTRAL),
        rvol=_rvol(confirmed=True),
        location=_location(),
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.LOCATION].status == StageStatus.PASS
    assert stages[StageId.LOCATION].codes == []


def test_cvd_enriches_participation_without_ever_changing_its_status():
    cvd_bullish = CvdState(time=0, delta=10.0, cumulative=10.0, rolling_delta=10.0, bias=CvdBias.BULLISH)

    # Same RVOL confirmation state (True), only CVD differs -- status must
    # stay identical (PASS): CVD is context, never a gate on its own.
    result_with_cvd = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), cvd=cvd_bullish
    )
    result_without_cvd = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True))

    stages_with = {s.id: s for s in result_with_cvd.stages}
    stages_without = {s.id: s for s in result_without_cvd.stages}
    assert stages_with[StageId.PARTICIPATION].status == stages_without[StageId.PARTICIPATION].status
    assert "cvd_buy_pressure" in stages_with[StageId.PARTICIPATION].codes
    assert result_with_cvd.decision == result_without_cvd.decision == "BUY"


def test_cvd_bearish_pressure_does_not_downgrade_a_confirmed_long():
    # Even strong opposing CVD never forces a downgrade by itself -- RVOL's
    # own confirmed/anomaly reading is still what decides pass/fail/watch.
    cvd_bearish = CvdState(time=0, delta=-10.0, cumulative=-10.0, rolling_delta=-10.0, bias=CvdBias.BEARISH)
    result = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), cvd=cvd_bearish)
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.PARTICIPATION].status == StageStatus.PASS
    assert "cvd_sell_pressure" in stages[StageId.PARTICIPATION].codes
    assert result.decision == "BUY"


def test_missing_cvd_is_not_an_error():
    result = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), cvd=None)
    stages = {s.id: s for s in result.stages}
    assert not any(c.startswith("cvd_") for c in stages[StageId.PARTICIPATION].codes)


def test_oi_funding_enriches_participation_without_ever_changing_its_status():
    crowded = OiFundingState(
        time=0, open_interest=1000.0, oi_trend=OiTrend.RISING,
        funding_rate=0.001, funding_bias=FundingBias.CROWDED_LONG,
    )
    result_with = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), oi_funding=crowded)
    result_without = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True))

    stages_with = {s.id: s for s in result_with.stages}
    stages_without = {s.id: s for s in result_without.stages}
    assert stages_with[StageId.PARTICIPATION].status == stages_without[StageId.PARTICIPATION].status
    assert "oi_rising" in stages_with[StageId.PARTICIPATION].codes
    assert "funding_crowded_long" in stages_with[StageId.PARTICIPATION].codes
    assert result_with.decision == result_without.decision == "BUY"


def test_crowded_short_funding_does_not_downgrade_a_confirmed_long():
    crowded_short = OiFundingState(
        time=0, open_interest=1000.0, oi_trend=OiTrend.FALLING,
        funding_rate=-0.001, funding_bias=FundingBias.CROWDED_SHORT,
    )
    result = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), oi_funding=crowded_short)
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.PARTICIPATION].status == StageStatus.PASS
    assert "oi_falling" in stages[StageId.PARTICIPATION].codes
    assert "funding_crowded_short" in stages[StageId.PARTICIPATION].codes
    assert result.decision == "BUY"


def test_missing_oi_funding_is_not_an_error():
    result = build_pipeline(ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), oi_funding=None)
    stages = {s.id: s for s in result.stages}
    assert not any(c.startswith("oi_") or c.startswith("funding_") for c in stages[StageId.PARTICIPATION].codes)


def test_adx_enriches_regime_without_ever_changing_its_status():
    strong_trend = AdxState(time=0, plus_di=35.0, minus_di=10.0, adx=42.0, strength=TrendStrength.STRONG)

    result_with = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), adx=strong_trend,
    )
    result_without = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True), atr=_atr(VolatilityRegime.NORMAL)
    )

    stages_with = {s.id: s for s in result_with.stages}
    stages_without = {s.id: s for s in result_without.stages}
    assert stages_with[StageId.REGIME].status == stages_without[StageId.REGIME].status
    assert "adx_strong_trend" in stages_with[StageId.REGIME].codes
    assert result_with.decision == result_without.decision == "BUY"


def test_adx_no_confirmed_trend_downgrades_a_normal_atr_regime_to_no_trade():
    # Promoted to a real gate 2026-09-16 (docs/METHODS-ROADMAP.md's bar
    # "garder seulement si backtest prouve un edge" -- a real 3-window
    # backtest proved it, see engine README). ABSENT/DEVELOPING now force
    # NO_TRADE via the same REGIME-FAIL path as ATR DEAD/EXTREME -- still
    # never votes direction, only downgrades.
    no_trend = AdxState(time=0, plus_di=15.0, minus_di=14.0, adx=12.0, strength=TrendStrength.ABSENT)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), adx=no_trend,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.FAIL
    assert "regime_no_trend" in stages[StageId.REGIME].codes
    assert "adx_no_trend" in stages[StageId.REGIME].codes
    assert result.decision == "NO_TRADE"
    assert result.direction == Direction.LONG  # downgraded, never flipped


def test_adx_developing_trend_also_downgrades_to_no_trade():
    developing = AdxState(time=0, plus_di=22.0, minus_di=15.0, adx=22.0, strength=TrendStrength.DEVELOPING)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), adx=developing,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.FAIL
    assert result.decision == "NO_TRADE"


def test_adx_trending_does_not_downgrade():
    trending = AdxState(time=0, plus_di=30.0, minus_di=10.0, adx=28.0, strength=TrendStrength.TRENDING)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), adx=trending,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.PASS
    assert result.decision == "BUY"


def test_missing_adx_is_not_an_error():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), adx=None,
    )
    stages = {s.id: s for s in result.stages}
    assert not any(c.startswith("adx_") for c in stages[StageId.REGIME].codes)


def test_donchian_confirming_breakout_does_not_downgrade():
    # Promoted to a real gate 2026-09-16 (same bar as ADX: "garder seulement
    # si backtest prouve un edge" -- proved on 3 real windows, see engine
    # README §Donchian + Wyckoff). A LONG with a genuine UP breakout passes.
    up_breakout = DonchianState(time=0, upper=100.0, lower=90.0, breakout=DonchianBreakout.UP)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), donchian=up_breakout,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.PASS
    assert result.decision == "BUY"


def test_donchian_unconfirmed_breakout_downgrades_a_normal_atr_regime_to_no_trade():
    inside_range = DonchianState(time=0, upper=100.0, lower=90.0, breakout=DonchianBreakout.INSIDE)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), donchian=inside_range,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.FAIL
    assert "regime_no_breakout" in stages[StageId.REGIME].codes
    assert result.decision == "NO_TRADE"
    assert result.direction == Direction.LONG  # downgraded, never flipped


def test_donchian_breakout_in_the_wrong_direction_also_downgrades():
    # A SHORT direction call, but Donchian shows an UP breakout -- not the
    # direction being traded, so it doesn't confirm it either.
    up_breakout = DonchianState(time=0, upper=100.0, lower=90.0, breakout=DonchianBreakout.UP)
    result = build_pipeline(
        ichimoku=_ichi(Direction.SHORT), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), donchian=up_breakout,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.FAIL
    assert result.decision == "NO_TRADE"


def test_missing_donchian_is_not_an_error():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), donchian=None,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.PASS
    assert "regime_no_breakout" not in stages[StageId.REGIME].codes
    assert result.decision == "BUY"


def test_unknown_donchian_breakout_is_treated_like_missing_data():
    # Not enough history to form a range yet -- must never gate, same
    # graceful-degradation convention as ADX's UNKNOWN strength.
    unknown = DonchianState(time=0, upper=None, lower=None, breakout=DonchianBreakout.UNKNOWN)
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG), rvol=_rvol(confirmed=True),
        atr=_atr(VolatilityRegime.NORMAL), donchian=unknown,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.REGIME].status == StageStatus.PASS
    assert result.decision == "BUY"


def test_mtf_opposed_downgrades_even_with_bullish_local_structure():
    result = build_pipeline(
        ichimoku=_ichi(Direction.LONG),
        rvol=_rvol(confirmed=True),
        structure=_structure(StructureBias.BULLISH, BosEvent.NONE),
        atr=_atr(VolatilityRegime.NORMAL),
        mtf_aligned=False,
    )
    stages = {s.id: s for s in result.stages}
    assert stages[StageId.STRUCTURE].status == StageStatus.WATCH
    assert "mtf_opposed" in stages[StageId.STRUCTURE].codes
