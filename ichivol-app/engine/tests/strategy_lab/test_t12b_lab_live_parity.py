"""T12b — Lab FeatureBar stage_pass == live pipeline stage statuses."""

from __future__ import annotations

from app.agents import ichimoku_agent, rvol_agent
from app.decision.pipeline import StageId, build_pipeline
from app.indicators.registry import REGISTRY
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.live_parity import PARITY_STAGE_FIELDS
from tests.indicators.test_ichimoku_lookahead import _make_candles

T12B_NEW_FIELDS = (
    "chikou_state",
    "future_kumo",
    "ichimoku_score",
    "ichimoku_direction",
    "adx",
    "plus_di",
    "minus_di",
    "donchian_breakout",
    "regime_trending",
    "regime_ranging",
    "regime_high_volatility",
    "regime_low_volatility",
    "regime_normal_volatility",
    "regime_bull",
    "regime_bear",
    "regime_sideways",
    "regime_stage_pass",
    "above_vwap",
    "below_vwap",
    "avwap_aligned",
    "avwap_opposed",
    "inside_value_area",
    "beyond_value_area",
    "wrong_side_value_area",
    "congestion_hvn",
    "location_stage_pass",
    "cvd_bias",
    "rvol_faible",
    "rvol_normal",
    "rvol_eleve",
    "rvol_fort",
    "rvol_extreme",
    "participation_stage_pass",
)


def _pipeline_over_candles_full(candles):
    """Same indicators as live scan_symbol (no OI/MTF — enrichment-only)."""
    ichi_outputs = ichimoku_agent.analyze(candles)
    rvol_outputs = rvol_agent.analyze(candles)
    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "cvd", "adx", "donchian"],
        candles,
    )
    return [
        build_pipeline(
            ichimoku=ichi_outputs[i],
            rvol=rvol_outputs[i],
            structure=computed["structure"][i],
            atr=computed["atr"][i],
            location=computed["location"][i],
            cvd=computed["cvd"][i],
            adx=computed["adx"][i],
            donchian=computed["donchian"][i],
        )
        for i in range(len(candles))
    ]


def test_lab_stage_pass_matches_live_pipeline():
    candles = _make_candles(280, seed=17)
    series = build_feature_series(candles)
    pipelines = _pipeline_over_candles_full(candles)
    assert len(series.bars) == len(pipelines)
    for i, (bar, pipe) in enumerate(zip(series.bars, pipelines)):
        by_id = {s.id: s for s in pipe.stages}
        for stage_id, field in PARITY_STAGE_FIELDS:
            lab = getattr(bar, field)
            live = by_id[stage_id].status.value
            assert lab == live, (
                f"bar {i}: {field} Lab={lab!r} live={live!r} "
                f"(decision={pipe.decision})"
            )


def test_t12b_feature_fields_are_causal():
    candles = _make_candles(260, seed=53)
    full = build_feature_series(candles)
    for t in (40, 80, 120, 200, 259):
        trunc = build_feature_series(candles[:t])
        for name in T12B_NEW_FIELDS:
            assert getattr(trunc.bars[-1], name) == getattr(full.bars[t - 1], name), (
                f"FeatureBar.{name} changed when future candles were added (T={t})"
            )


def test_rvol_bands_thresholds():
    from app.strategy_lab.live_parity import rvol_band_flags

    assert rvol_band_flags(0.5)["rvol_faible"] is True
    assert rvol_band_flags(0.9)["rvol_normal"] is True
    assert rvol_band_flags(1.3)["rvol_eleve"] is True
    assert rvol_band_flags(1.7)["rvol_fort"] is True
    assert rvol_band_flags(2.0)["rvol_fort"] is True
    assert rvol_band_flags(2.1)["rvol_extreme"] is True
    assert rvol_band_flags(None)["rvol_faible"] is False


def test_coverage_warning_under_two_days_shows_missing_bars():
    from app.strategy_lab.deep_history import _coverage_warning
    from app.indicators.ichimoku import Candle

    tf = 3600
    # Request ~5 days, deliver ~4 days → shortfall < 2 days → missing-bars msg.
    req = 5 * 86400
    n = 4 * 24  # 4 days of 1h bars
    start = 1_700_000_000
    candles = [
        Candle(
            time=start + i * tf,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=10.0,
        )
        for i in range(n)
    ]
    span, warn = _coverage_warning(candles, requested_seconds=req, tf_seconds=tf)
    assert warn is not None
    assert "bougie" in warn
