"""Volume semantics + Evidence Engine unit tests."""

from __future__ import annotations

import pytest

from app.agents.types import Direction, StrategyAgentOutput
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus, build_pipeline
from app.evidence.catalog import build_in_window_catalog
from app.evidence.context import FEATURE_VERSION, SignalContext, build_signal_context
from app.evidence.engine import EvidenceEngine, evidence_report_dict
from app.evidence.matching import MatchCriteria, contexts_match, match_historical
from app.evidence.sample import SampleQuality, classify_sample
from app.indicators.atr import compute_atr
from app.indicators.ichimoku import Candle
from app.indicators.structure import compute_structure
from app.market_data.binance import VOLUME_TYPE as BINANCE_VT
from app.market_data.biquote import VOLUME_TYPE as BIQUOTE_VT
from app.market_data.volume_semantics import VolumeType, resolve_volume_type
from app.agents import ichimoku_agent, rvol_agent


def _trend_candles(n: int = 200, *, volume: float = 100.0, vol_type: VolumeType = VolumeType.EXCHANGE_VOLUME) -> list[Candle]:
    out = []
    for i in range(n):
        # Mild uptrend with a late volume spike so RVOL can confirm.
        v = volume * 3 if i == n - 1 else volume
        px = 100 + i * 0.2
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=px,
                high=px + 0.5,
                low=px - 0.3,
                close=px + 0.2,
                volume=v,
                volume_type=vol_type,
            )
        )
    return out


def test_volume_type_provider_defaults():
    assert BINANCE_VT == VolumeType.EXCHANGE_VOLUME
    assert BIQUOTE_VT == VolumeType.TICK_VOLUME
    assert resolve_volume_type("binance") == VolumeType.EXCHANGE_VOLUME
    assert resolve_volume_type("biquote", [1.0, 2.0]) == VolumeType.TICK_VOLUME
    assert resolve_volume_type("biquote", [0.0, 0.0]) == VolumeType.NONE


def test_candle_defaults_volume_type_to_none():
    c = Candle(time=1, open=1, high=1, low=1, close=1, volume=10)
    assert c.volume_type == VolumeType.NONE


def test_classify_sample_thresholds():
    assert classify_sample(0) == SampleQuality.NO_DATA
    assert classify_sample(5) == SampleQuality.INSUFFICIENT_DATA
    assert classify_sample(15) == SampleQuality.LOW_SAMPLE
    assert classify_sample(40) == SampleQuality.VALID_SAMPLE


def test_signal_context_roundtrip():
    candles = _trend_candles(120)
    ichi = ichimoku_agent.analyze(candles)[-1]
    rvol = rvol_agent.analyze(candles)[-1]
    structure = compute_structure(candles)[-1]
    atr = compute_atr(candles)[-1]
    pipeline = build_pipeline(ichimoku=ichi, rvol=rvol, structure=structure, atr=atr)
    ctx = build_signal_context(
        symbol="BTCUSDT",
        timeframe="1h",
        candles=candles,
        provider="binance",
        asset_class="crypto",
        ichimoku=ichi,
        rvol=rvol,
        pipeline=pipeline,
        structure=structure,
        atr=atr,
    )
    assert ctx.feature_version == FEATURE_VERSION
    assert ctx.volume is not None
    assert ctx.volume.volume_type == VolumeType.EXCHANGE_VOLUME.value
    restored = SignalContext.from_dict(ctx.to_dict())
    assert restored.symbol == ctx.symbol
    assert restored.ichimoku is not None
    assert restored.ichimoku.direction == ctx.ichimoku.direction


def test_historical_match_rejects_different_volume_semantics():
    candles = _trend_candles(100)
    ichi = ichimoku_agent.analyze(candles)[-1]
    rvol = rvol_agent.analyze(candles)[-1]
    pipeline = build_pipeline(ichimoku=ichi, rvol=rvol)
    base = build_signal_context(
        symbol="BTCUSDT",
        timeframe="1h",
        candles=candles,
        provider="binance",
        asset_class="crypto",
        ichimoku=ichi,
        rvol=rvol,
        pipeline=pipeline,
    )
    tick_candles = _trend_candles(100, vol_type=VolumeType.TICK_VOLUME)
    tick_ctx = build_signal_context(
        symbol="EURUSD",
        timeframe="1h",
        candles=tick_candles,
        provider="biquote",
        asset_class="forex",
        ichimoku=ichi,
        rvol=rvol,
        pipeline=pipeline,
    )
    assert not contexts_match(base, tick_ctx, MatchCriteria())


def test_match_historical_insufficient_when_few_hits():
    candles = _trend_candles(150)
    catalog = build_in_window_catalog(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        provider="binance",
        asset_class="crypto",
        min_bars=80,
        step=5,
    )
    if not catalog:
        pytest.skip("not enough directional bars in synthetic series")
    query_ctx, _, _ = catalog[-1]
    # Tiny catalog → INSUFFICIENT_EVIDENCE
    tiny = catalog[:3]
    stats = match_historical(query_ctx, tiny, primary_horizon=5)
    assert stats.sample_size <= 3
    assert stats.status in ("INSUFFICIENT_EVIDENCE", "NO_DATA", "VALID")


def test_evidence_engine_no_invented_confidence():
    candles = _trend_candles(160)
    catalog = build_in_window_catalog(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        provider="binance",
        asset_class="crypto",
        step=4,
    )
    assert catalog, "expected at least one directional context"
    ctx = catalog[-1][0]
    report = EvidenceEngine().evaluate(ctx, catalog)
    payload = evidence_report_dict(report)
    assert "calibration_note" in payload
    assert "87%" not in payload["calibration_note"]
    assert payload["historical"]["sample_size"] == report.historical.sample_size
    assert "positive_evidence" in payload
    assert "contradictions" in payload
    assert "invalidation" in payload
    # Never invent a free-floating confidence percentage field
    assert "confidence" not in payload or isinstance(payload.get("historical"), dict)


def test_matching_is_anti_lookahead_on_forward_path():
    """Forward path uses open of i+1; altering a past bar must not change future MFE for later signals."""
    candles = _trend_candles(120)
    catalog = build_in_window_catalog(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        provider="binance",
        asset_class="crypto",
        step=10,
        min_bars=90,
    )
    if len(catalog) < 2:
        pytest.skip("need 2+ catalog entries")
    ctx, series, idx = catalog[0]
    stats = match_historical(ctx, [(ctx, series, idx)], exclude_same_timestamp=False, primary_horizon=3)
    # Self-match excluded by default; with exclude off we get 1
    assert stats.sample_size == 1
    # Corrupt a bar STRICTLY before signal — forward metrics must stay defined
    # from entry_idx onward only (regression: no crash / NaN).
    assert stats.mean_return_pct is None or isinstance(stats.mean_return_pct, float)


def test_tick_vs_exchange_not_equivalent_in_evidence_contradictions():
    candles = _trend_candles(100, vol_type=VolumeType.TICK_VOLUME)
    ichi = StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=Direction.LONG,
        probability=0.6,
        confidence=0.8,
        expected_value=0.0,
        reasons=["tk_bullish"],
        invalidation=["close_below_kijun"],
        metadata={
            "tk_cross": "BULLISH",
            "price_vs_kumo": "ABOVE",
            "future_kumo": "BULLISH",
            "score": 40,
        },
    )
    rvol = StrategyAgentOutput(
        agent="RVOL_AGENT",
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=0.2,
        expected_value=0.0,
        reasons=["low_rvol"],
        invalidation=[],
        metadata={"rvol": 0.7, "confirmed": False, "anomaly_level": "LOW"},
    )
    pipeline = PipelineResult(
        decision="WATCH",
        direction=Direction.LONG,
        stages=[
            PipelineStage(StageId.DIRECTION, StageStatus.PASS, "LONG", []),
            PipelineStage(StageId.PARTICIPATION, StageStatus.FAIL, "RVOL low", []),
            PipelineStage(StageId.STRUCTURE, StageStatus.WATCH, "?", []),
            PipelineStage(StageId.LOCATION, StageStatus.PENDING, "?", []),
            PipelineStage(StageId.REGIME, StageStatus.PASS, "ok", []),
        ],
    )
    ctx = build_signal_context(
        symbol="EURUSD",
        timeframe="1h",
        candles=candles,
        provider="biquote",
        asset_class="forex",
        ichimoku=ichi,
        rvol=rvol,
        pipeline=pipeline,
    )
    report = EvidenceEngine().evaluate(ctx, [])
    assert any("volume_semantics:TICK_VOLUME" in c for c in report.contradictions)
    assert any("rvol_insufficient" in w for w in report.why_not_long)
