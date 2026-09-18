"""Unit tests for Market Structure Phase 2."""

from __future__ import annotations

import random

from app.indicators.ichimoku import Candle
from app.structure.adapters import (
    MvppStructureAdapter,
    PyTrendlineStructureAdapter,
)
from app.structure.breakout import evaluate_breakout
from app.structure.consensus import build_consensus
from app.structure.params import StructureEngineParams
from app.structure.retest import RetestOutcome, evaluate_retest
from app.structure.service import detect_market_structure
from app.structure.types import DetectorSource, LevelSide, PriceZone


def _make_candles(n: int, seed: int = 7) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    out: list[Candle] = []
    for i in range(n):
        # Mild uptrend with noise so pivots / lines can form
        drift = 0.15 + rng.uniform(-1.2, 1.2)
        o = price
        c = max(1.0, price + drift)
        h = max(o, c) + rng.uniform(0.1, 1.5)
        l = min(o, c) - rng.uniform(0.1, 1.5)
        v = rng.uniform(50, 500)
        if i % 17 == 0:
            v *= 3.0  # occasional high-volume bar
        out.append(Candle(time=i, open=o, high=h, low=l, close=c, volume=v))
        price = c
    return out


def test_mvpp_adapter_returns_structure():
    candles = _make_candles(180)
    result = MvppStructureAdapter().detect(candles, StructureEngineParams(window_bars=180))
    assert result.source == DetectorSource.MVPP
    assert result.meta.get("implementation") == "clean_room_causal"
    assert isinstance(result.pivots, tuple)


def test_mvpp_is_causal_truncation():
    candles = _make_candles(160, seed=3)
    params = StructureEngineParams(window_bars=160, fractal_left=3, fractal_right=3)
    full = MvppStructureAdapter().detect(candles, params)
    t = 120
    trunc = MvppStructureAdapter().detect(candles[:t], params)
    # Pivot bars that are confirmed in both must match prices for shared indices
    full_map = {p.bar_index: p.price for p in full.pivots if p.bar_index < t - params.fractal_right}
    trunc_map = {p.bar_index: p.price for p in trunc.pivots if p.bar_index < t - params.fractal_right}
    shared = set(full_map) & set(trunc_map)
    assert shared, "expected some confirmed pivots in both windows"
    for idx in shared:
        assert abs(full_map[idx] - trunc_map[idx]) < 1e-9


def test_trendln_and_consensus():
    candles = _make_candles(200, seed=9)
    params = StructureEngineParams(window_bars=200, min_detectors_agree=1)
    snap = detect_market_structure(candles, params, include_pytrendline=False)
    assert snap.consensus.source == DetectorSource.CONSENSUS
    assert "mvpp" in snap.by_detector
    assert "trendln" in snap.by_detector
    assert snap.atr is None or snap.atr > 0


def test_pytrendline_capped_offline():
    candles = _make_candles(400, seed=2)
    params = StructureEngineParams(pytrendline_max_bars=80, window_bars=400)
    result = PyTrendlineStructureAdapter().detect(candles, params, allow_online=True)
    assert result.source == DetectorSource.PYTRENDLINE
    assert result.meta.get("bars", 0) <= 80


def test_breakout_and_retest():
    zone = PriceZone(
        side=LevelSide.RESISTANCE,
        low=99.0,
        high=101.0,
        mid=100.0,
        score=1.0,
        touch_count=3,
        sources=(DetectorSource.CONSENSUS,),
    )
    breakout_candle = Candle(time=10, open=100.5, high=103.0, low=100.0, close=102.5, volume=200)
    bos = evaluate_breakout(breakout_candle, [zone], atr=2.0, rvol=1.8)
    assert bos and bos[0].confirmed

    candles = [
        Candle(time=i, open=102, high=103, low=101.5, close=102.2, volume=100) for i in range(10)
    ]
    candles.append(breakout_candle)
    # Return to zone
    candles.append(Candle(time=11, open=101.5, high=102.0, low=100.2, close=100.5, volume=120))
    retest = evaluate_retest(
        candles, zone, breakout_bar=10, broken_side=LevelSide.RESISTANCE, atr=2.0
    )
    assert retest is not None
    assert retest.outcome in {RetestOutcome.HOLD, RetestOutcome.FAILURE, RetestOutcome.PENDING}


def test_consensus_clusters_nearby_levels():
    z1 = PriceZone(
        LevelSide.SUPPORT, 99.0, 101.0, 100.0, 5.0, 3, (DetectorSource.MVPP,), 2.0
    )
    z2 = PriceZone(
        LevelSide.SUPPORT, 99.5, 101.5, 100.4, 4.0, 2, (DetectorSource.TRENDLN,), 2.0
    )
    from app.structure.types import MarketStructure

    m1 = MarketStructure(DetectorSource.MVPP, support_zones=(z1,))
    m2 = MarketStructure(DetectorSource.TRENDLN, support_zones=(z2,))
    merged = build_consensus([m1, m2], StructureEngineParams(consensus_atr_mult=0.5), atr=2.0)
    assert len(merged.support_zones) == 1
    assert DetectorSource.MVPP in merged.support_zones[0].sources
    assert DetectorSource.TRENDLN in merged.support_zones[0].sources
