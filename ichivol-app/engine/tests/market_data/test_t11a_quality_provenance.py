"""T11a — data quality gate + provenance observation (no pipeline vote)."""

from __future__ import annotations

from app.agents.types import Direction
from app.analysis import analysis_stage_from_data_quality, handoff_from_pipeline
from app.analysis.stage import AnalysisStageId, AnalysisStatus
from app.decision.pipeline import (
    PipelineResult,
    PipelineStage,
    StageId,
    StageStatus,
)
from app.indicators.ichimoku import Candle
from app.market_data.observe_quality import (
    DATA_PROVENANCE_VERSION,
    DATA_QUALITY_VERSION,
    dataset_fingerprint,
    observe_data_provenance,
    observe_data_quality,
)
from app.screener.timing import SignalTiming

H = 3600


def _c(t: int, o=100.0, h=101.0, l=99.0, cl=100.0, v=1.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl, volume=v)


def _clean(n: int = 5) -> list[Candle]:
    return [_c(i * H, cl=100.0 + i * 0.1) for i in range(n)]


def test_clean_series_gate_pass():
    obs = observe_data_quality(_clean(), H, now=5 * H)
    assert obs.ok
    assert obs.gate == "pass"
    assert obs.version == DATA_QUALITY_VERSION
    assert "alter decision" in obs.disclaimer


def test_fail_codes_gate_fail():
    bad = [_c(0), _c(0), _c(H)]  # duplicate
    obs = observe_data_quality(bad, H)
    assert obs.gate == "fail"
    assert "duplicate" in obs.issue_codes


def test_gap_gate_watch():
    series = [_c(0), _c(5 * H)]
    obs = observe_data_quality(series, H)
    assert obs.gate == "watch"
    assert "gap" in obs.issue_codes


def test_stale_timing_forces_fail():
    series = _clean(3)
    timing = SignalTiming(
        timeframe="1h",
        signal_bar_open=2 * H,
        signal_bar_close=3 * H,
        computed_at=10 * H,
        live_price=100.0,
        expected_bar_close=10 * H,
        lag_bars=2,
        data_late=True,
        stale=True,
        closed_only=True,
    )
    obs = observe_data_quality(series, H, now=10 * H, timing=timing)
    assert obs.gate == "fail"
    assert obs.stale is True


def test_provenance_fingerprint_stable():
    candles = _clean(8)
    a = observe_data_provenance(
        candles,
        provider="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        closed_only=True,
        transforms=("closed_only",),
    )
    b = observe_data_provenance(
        candles,
        provider="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        closed_only=True,
        transforms=("closed_only",),
    )
    assert a.dataset_fingerprint == b.dataset_fingerprint == dataset_fingerprint(candles)
    assert a.version == DATA_PROVENANCE_VERSION
    assert a.n_bars == 8
    assert "audit stamp" in a.disclaimer


def test_analysis_stage_from_quality_and_handoff_prepend():
    obs = observe_data_quality(_clean(), H, now=5 * H)
    stage = analysis_stage_from_data_quality(obs, symbol="BTCUSDT", timeframe="1h")
    assert stage.stage_id == AnalysisStageId.DATA_QUALITY
    assert stage.status == AnalysisStatus.PASS

    pipeline = PipelineResult(
        decision="WATCH",
        direction=Direction.NEUTRAL,
        strategy_version="test",
        stages=[
            PipelineStage(
                id=StageId.DIRECTION,
                status=StageStatus.WATCH,
                summary="neutral",
                codes=[],
            ),
        ],
    )
    handoff = handoff_from_pipeline(
        pipeline,
        symbol="BTCUSDT",
        timeframe="1h",
        market_data_hash=obs.to_dict()["version"],
        data_quality_stage=stage,
    )
    assert handoff.stages[0].stage_id == AnalysisStageId.DATA_QUALITY
    assert handoff.decision == "WATCH"  # unchanged


def test_quality_does_not_mutate_decision_label():
    """Guard: observation path never invents a pipeline decision."""
    obs = observe_data_quality([_c(0), _c(0)], H)  # fail
    assert obs.gate == "fail"
    d = obs.to_dict()
    assert "decision" not in d
    assert "confidence" not in d
