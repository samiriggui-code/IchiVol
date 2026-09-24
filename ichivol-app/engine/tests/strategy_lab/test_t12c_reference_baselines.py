"""T12c — reference baselines: buy&hold, Donchian alone, structure BOS alone."""

from __future__ import annotations

from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.reference_baselines import (
    DEFAULT_COMMISSION_BPS,
    DEFAULT_SLIPPAGE_BPS,
    REF_BUY_HOLD_ID,
    REF_DONCHIAN_ID,
    REF_STRUCTURE_BOS_ID,
    catalog_reference_ruleset_ids,
    run_reference_baselines_on_candles,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_catalog_includes_t12c_reference_rulesets():
    ids = {r.id for r in list_builtin_rulesets()}
    for rid in catalog_reference_ruleset_ids():
        assert rid in ids
        rs = get_builtin_ruleset(rid)
        assert rs.meta.get("reference") is True
        assert rs.meta.get("t12c") is True


def test_reference_baselines_shared_fees_and_bars():
    candles = _make_candles(220, seed=42)
    report = run_reference_baselines_on_candles(
        candles,
        symbol="TEST",
        timeframe="1h",
        commission_bps=DEFAULT_COMMISSION_BPS,
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
    )
    assert report.n_bars == len(candles)
    assert report.commission_bps == DEFAULT_COMMISSION_BPS
    assert report.slippage_bps == DEFAULT_SLIPPAGE_BPS
    assert len(report.baselines) == 3

    by_id = {b.id: b for b in report.baselines}
    assert REF_BUY_HOLD_ID in by_id
    assert REF_DONCHIAN_ID in by_id
    assert REF_STRUCTURE_BOS_ID in by_id

    for row in report.baselines:
        assert row.commission_bps == DEFAULT_COMMISSION_BPS
        assert row.slippage_bps == DEFAULT_SLIPPAGE_BPS
        assert row.n_bars == len(candles)
        assert "total_return" in row.metrics
        assert row.metrics["metrics_basis"] == "net_v1"

    assert by_id[REF_BUY_HOLD_ID].kind == "buy_hold"
    assert by_id[REF_BUY_HOLD_ID].engine == "run_backtest"
    assert by_id[REF_DONCHIAN_ID].kind == "donchian_breakout"
    assert by_id[REF_STRUCTURE_BOS_ID].kind == "structure_bos"


def test_reference_baselines_empty_series_raises():
    import pytest

    with pytest.raises(ValueError, match="at least 2"):
        run_reference_baselines_on_candles([], symbol="X")


def test_reference_baselines_fee_override_propagates():
    candles = _make_candles(180, seed=7)
    report = run_reference_baselines_on_candles(
        candles,
        symbol="TEST",
        timeframe="1h",
        commission_bps=10.0,
        slippage_bps=8.0,
    )
    assert report.commission_bps == 10.0
    assert report.slippage_bps == 8.0
    for row in report.baselines:
        assert row.commission_bps == 10.0
        assert row.slippage_bps == 8.0


def test_reference_baselines_edge_one_bar_raises():
    import pytest
    from app.indicators.ichimoku import Candle

    one = [
        Candle(time=0, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
    ]
    with pytest.raises(ValueError, match="at least 2"):
        run_reference_baselines_on_candles(one)


def test_buy_hold_exposure_high_on_trending_series():
    """Sonde : série parfaite (drift haussier) → buy&hold exposé et return > 0."""
    candles = _make_candles(200, seed=1)
    # _make_candles already has mild upward drift in the helper
    report = run_reference_baselines_on_candles(candles, symbol="BTC", timeframe="1h")
    bh = next(b for b in report.baselines if b.id == REF_BUY_HOLD_ID)
    assert bh.metrics["exposure"] > 0.9
    assert bh.metrics["num_trades"] >= 1
