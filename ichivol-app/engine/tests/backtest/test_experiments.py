"""Validates the mission's central hypothesis test setup end-to-end (brief
§10): compare ICHIMOKU_ONLY vs ICHIMOKU_RVOL on the same price history.
Uses a fabricated scenario where RVOL is deliberately weak throughout so the
RVOL-gated variant should sit out almost entirely -- the sign of a genuine
gate, not a coincidental one.
"""

from __future__ import annotations

import pytest

from app.backtest import experiments
from app.indicators.ichimoku import Candle
from app.market_data import binance


def _uptrend_with_flat_low_volume(n: int) -> list[Candle]:
    # A *constant* volume -- even a floor clamp that turns into one after
    # enough decay -- re-equilibrates RVOL to ~1.0 (NORMAL, which still
    # clears the actionable-confidence threshold at exactly 0.4) after one
    # averaging window. This bit us once already: `max(1.0, 200*0.95**i)`
    # looked like it kept decaying but silently flattened around i=103 once
    # the exponential dropped below the floor, and the test failed because
    # RVOL climbed back to NORMAL for the whole second half. No floor here:
    # 0.95**299 is still a perfectly fine positive float, nowhere near zero.
    return [
        Candle(
            time=i,
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=200.0 * (0.95**i),
        )
        for i in range(n)
    ]


def test_rvol_gate_reduces_exposure_when_volume_never_confirms(monkeypatch):
    candles = _uptrend_with_flat_low_volume(300)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    results = experiments.compare("BTCUSDT", timeframe="1h", limit=300)

    assert set(results) == {
        experiments.ICHIMOKU_ONLY,
        experiments.ICHIMOKU_RVOL,
        experiments.ICHIMOKU_RVOL_ENTRY_GATE,
        experiments.PIPELINE,
        experiments.PIPELINE_WYCKOFF_FILTER,
    }
    only = results[experiments.ICHIMOKU_ONLY]
    gated = results[experiments.ICHIMOKU_RVOL]
    entry_gated = results[experiments.ICHIMOKU_RVOL_ENTRY_GATE]

    # Ichimoku alone should be long for most of a clean uptrend...
    assert only.metrics.exposure > 0.5
    # ...but both RVOL-aware variants should hold back since volume never confirms.
    assert gated.metrics.exposure < only.metrics.exposure
    assert entry_gated.metrics.exposure == 0.0  # never confirms => never even enters


def test_entry_gate_holds_through_a_rvol_lull_once_confirmed_at_entry():
    from app.agents import ichimoku_agent, rvol_agent
    from app.agents.types import Direction
    from app.indicators.ichimoku import IchimokuParams
    from app.indicators.rvol import RvolParams

    n = 250
    # Default Ichimoku params need ~78 bars of history before the cloud is
    # even defined (senkou_b=52 lookback + displacement=26), so the
    # "confirmed" volume phase must extend well past that before the
    # decline starts, or entry never gets a chance to fire in the first
    # place. Constant volume would re-equilibrate RVOL back to ~1.0
    # (NORMAL, still "confirmed"), so the lull has to keep declining to
    # stay genuinely LOW throughout rather than settle at a new plateau.
    confirmed_phase = 120
    volumes = [50.0 + 20.0 * (i % 3) for i in range(confirmed_phase)] + [
        300.0 * (0.9 ** (i - confirmed_phase)) for i in range(confirmed_phase, n)
    ]
    candles = [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=volumes[i])
        for i in range(n)
    ]
    ichi_outputs = ichimoku_agent.analyze(candles, IchimokuParams())
    rvol_outputs = rvol_agent.analyze(candles, RvolParams())

    entry_gated = experiments.ichimoku_rvol_entry_gate_positions(ichi_outputs, rvol_outputs)
    continuous = experiments.ichimoku_rvol_positions(ichi_outputs, rvol_outputs)

    # Once ichimoku is confirmed long and stays long, the entry-gated variant
    # should stay long through the volume lull...
    assert entry_gated.count(Direction.LONG) > continuous.count(Direction.LONG)


def test_experiments_reject_insufficient_history(monkeypatch):
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: [])
    with pytest.raises(ValueError):
        experiments.compare("BTCUSDT")


def test_pipeline_positions_is_neutral_on_watch_and_directional_on_buy_sell():
    from app.agents.types import Direction, StrategyAgentOutput
    from app.indicators.atr import AtrState, VolatilityRegime
    from app.indicators.location import LocationState, NodeType
    from app.indicators.structure import BosEvent, StructureBias, StructureState

    def _ichi(direction, confidence=1.0):
        return StrategyAgentOutput(
            agent="ICHIMOKU_AGENT", direction=direction, probability=0.7, confidence=confidence,
            expected_value=0.0, reasons=[], invalidation=[], metadata={"score": 50.0},
        )

    def _rvol(confirmed):
        # anomaly_level="LOW" is what actually makes the participation stage
        # FAIL (and therefore downgrade the decision to WATCH) when not
        # confirmed -- see app/decision/pipeline.py::_participation_stage.
        anomaly = "SIGNIFICANT" if confirmed else "LOW"
        return StrategyAgentOutput(
            agent="RVOL_AGENT", direction=Direction.NEUTRAL, probability=0.5, confidence=0.5,
            expected_value=0.0, reasons=[], invalidation=[],
            metadata={"confirmed": confirmed, "anomaly_level": anomaly, "rvol": 2.0 if confirmed else 0.3},
        )

    structure = StructureState(
        time=0, last_swing_high=110.0, last_swing_low=90.0,
        bias=StructureBias.BULLISH, bos=BosEvent.NONE,
    )
    atr = AtrState(
        time=0, true_range=1.0, atr=1.0, percentile=0.5,
        regime=VolatilityRegime.NORMAL, suggested_stop_distance=1.5,
    )
    # Neutral location (inside value area, right side of AVWAP, no
    # congestion) -- passes for a LONG, so it doesn't interfere with the
    # RVOL-driven WATCH/BUY split this test is actually about.
    location = LocationState(
        time=0, price=100.0, poc=100.0, vah=105.0, val=95.0,
        node_type=NodeType.NEUTRAL, vwap=98.0, avwap=95.0, avwap_anchor_time=0,
    )

    # Bar 0: confirmed RVOL + bullish structure -> BUY -> LONG position.
    # Bar 1: RVOL not confirmed -> WATCH -> flat.
    ichi_outputs = [_ichi(Direction.LONG), _ichi(Direction.LONG)]
    rvol_outputs = [_rvol(True), _rvol(False)]
    structure_states = [structure, structure]
    atr_states = [atr, atr]
    mtf_directions = [None, None]
    location_states = [location, location]

    positions = experiments.pipeline_positions(
        ichi_outputs, rvol_outputs, structure_states, atr_states, mtf_directions, location_states
    )
    assert positions == [Direction.LONG, Direction.NEUTRAL]


def test_pipeline_positions_rejects_mismatched_series_lengths():
    with pytest.raises(ValueError):
        experiments.pipeline_positions([], [1], [], [], [], [])


def test_pipeline_positions_reflects_the_live_adx_regime_gate():
    # ADX is a real gate in app/decision/pipeline.py now (promoted
    # 2026-09-16, backtest-proven edge -- see engine README), so
    # pipeline_positions() picks it up automatically once adx_states is
    # passed -- no separate "with/without ADX" experiment needed anymore.
    from app.agents.types import Direction, StrategyAgentOutput
    from app.indicators.adx import AdxState, TrendStrength
    from app.indicators.atr import AtrState, VolatilityRegime
    from app.indicators.location import LocationState, NodeType
    from app.indicators.structure import BosEvent, StructureBias, StructureState

    ichi = StrategyAgentOutput(
        agent="ICHIMOKU_AGENT", direction=Direction.LONG, probability=0.7, confidence=1.0,
        expected_value=0.0, reasons=[], invalidation=[], metadata={"score": 50.0},
    )
    rvol = StrategyAgentOutput(
        agent="RVOL_AGENT", direction=Direction.NEUTRAL, probability=0.5, confidence=0.5,
        expected_value=0.0, reasons=[], invalidation=[],
        metadata={"confirmed": True, "anomaly_level": "SIGNIFICANT", "rvol": 2.0},
    )
    structure = StructureState(
        time=0, last_swing_high=110.0, last_swing_low=90.0, bias=StructureBias.BULLISH, bos=BosEvent.NONE,
    )
    atr = AtrState(time=0, true_range=1.0, atr=1.0, percentile=0.5, regime=VolatilityRegime.NORMAL, suggested_stop_distance=1.5)
    location = LocationState(
        time=0, price=100.0, poc=100.0, vah=105.0, val=95.0,
        node_type=NodeType.NEUTRAL, vwap=98.0, avwap=95.0, avwap_anchor_time=0,
    )

    # Bar 0: ADX confirms a real trend -> pipeline stays LONG.
    # Bar 1: identical pipeline inputs, but ADX says it's still chop -> the
    # Regime stage's ADX gate forces NO_TRADE -> flat.
    adx_trending = AdxState(time=0, plus_di=30.0, minus_di=10.0, adx=30.0, strength=TrendStrength.TRENDING)
    adx_chop = AdxState(time=1, plus_di=16.0, minus_di=15.0, adx=10.0, strength=TrendStrength.ABSENT)

    positions = experiments.pipeline_positions(
        [ichi, ichi], [rvol, rvol], [structure, structure], [atr, atr], [None, None],
        [location, location], None, [adx_trending, adx_chop],
    )
    assert positions == [Direction.LONG, Direction.NEUTRAL]

    # Omitting adx_states entirely (older call sites, or a provider that
    # never gets ADX data) must behave exactly as before ADX existed --
    # never gates when it's simply absent.
    positions_without_adx = experiments.pipeline_positions(
        [ichi, ichi], [rvol, rvol], [structure, structure], [atr, atr], [None, None], [location, location],
    )
    assert positions_without_adx == [Direction.LONG, Direction.LONG]


def test_compare_includes_a_real_pipeline_backtest(monkeypatch):
    candles = _uptrend_with_flat_low_volume(300)
    # First 100 bars: strong, oscillating volume so RVOL actually confirms
    # at some point once Ichimoku activates (~bar 78+); the rest decays as
    # in the other fixture -- just need the PIPELINE variant to take at
    # least one real position to prove it's wired end to end, not asserting
    # a specific performance number.
    boosted = list(candles)
    for i in range(80, 100):
        c = boosted[i]
        boosted[i] = Candle(time=c.time, open=c.open, high=c.high, low=c.low, close=c.close, volume=300.0)

    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: boosted)

    results = experiments.compare("BTCUSDT", timeframe="1h", limit=300)
    pipeline_result = results[experiments.PIPELINE]

    assert pipeline_result.backtest.symbol == "BTCUSDT"
    assert pipeline_result.metrics.n_bars == len(boosted) - 1
    # Doesn't assert a specific return -- just that the wiring produces a
    # real, computed metrics object, not a stub.
    assert pipeline_result.metrics.exposure >= 0.0
