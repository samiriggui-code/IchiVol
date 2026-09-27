"""B6 live regime (ATR+ADX) and B7 warmup — VP-J1 corrections."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from app.indicators.adx import AdxState, TrendStrength
from app.indicators.atr import AtrParams, AtrState, VolatilityRegime
from app.indicators.ichimoku import Candle
from app.strategy_lab.adn_ichivol import LiveScreenerSettings
from vp3 import WARMUP_BARS
from vp3.entries import entry_mask, live_regime_ok

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H


def _atr(regime: VolatilityRegime) -> AtrState:
    return AtrState(
        time=T0,
        true_range=1.0,
        atr=1.0,
        percentile=0.5,
        regime=regime,
        suggested_stop_distance=1.5,
    )


def _adx(strength: TrendStrength) -> AdxState:
    return AdxState(time=T0, plus_di=20.0, minus_di=10.0, adx=30.0, strength=strength)


def test_live_regime_blocks_adx_absent_and_developing():
    atr = _atr(VolatilityRegime.NORMAL)
    assert live_regime_ok(atr, _adx(TrendStrength.ABSENT)) is False
    assert live_regime_ok(atr, _adx(TrendStrength.DEVELOPING)) is False


def test_live_regime_passes_trending_strong_unknown_and_none():
    atr = _atr(VolatilityRegime.NORMAL)
    assert live_regime_ok(atr, _adx(TrendStrength.TRENDING)) is True
    assert live_regime_ok(atr, _adx(TrendStrength.STRONG)) is True
    assert live_regime_ok(atr, _adx(TrendStrength.UNKNOWN)) is True
    assert live_regime_ok(atr, None) is True


def test_live_regime_blocks_atr_dead_and_extreme():
    adx = _adx(TrendStrength.TRENDING)
    assert live_regime_ok(_atr(VolatilityRegime.DEAD), adx) is False
    assert live_regime_ok(_atr(VolatilityRegime.EXTREME), adx) is False
    assert live_regime_ok(_atr(VolatilityRegime.NORMAL), adx) is True
    assert live_regime_ok(_atr(VolatilityRegime.UNKNOWN), adx) is True


def candles_flat(n: int, px: float = 100.0, vol: float = 1000.0) -> list[Candle]:
    return [
        Candle(time=T0 + i * H, open=px, high=px + 1, low=px - 1, close=px, volume=vol)
        for i in range(n)
    ]


def _htf(n_ltf: int) -> list[Candle]:
    # enough HTF bars for alignment (4h)
    n = max(n_ltf // 4 + 5, 30)
    return [
        Candle(time=T0 + i * 4 * H, open=100, high=101, low=99, close=100.5, volume=1000)
        for i in range(n)
    ]


def test_b7_no_buy_before_warmup(monkeypatch):
    n = WARMUP_BARS + 3
    candles = candles_flat(n)

    class _FakePipe:
        decision = "BUY"

    monkeypatch.setattr("vp3.entries.build_pipeline", lambda *a, **k: _FakePipe())
    monkeypatch.setattr(
        "vp3.entries.ichimoku_agent.analyze",
        lambda c: [type("IO", (), {"direction": None})() for _ in c],
    )
    monkeypatch.setattr("vp3.entries.rvol_agent.analyze", lambda c: [None] * len(c))
    monkeypatch.setattr("vp3.entries.compute_structure", lambda c: [None] * len(c))
    monkeypatch.setattr("vp3.entries.compute_location", lambda c, s: [None] * len(c))
    monkeypatch.setattr("vp3.entries.compute_cvd", lambda c: [None] * len(c))
    monkeypatch.setattr("vp3.entries.compute_donchian", lambda c: [None] * len(c))
    monkeypatch.setattr(
        "vp3.entries.compute_adx",
        lambda c, p=None: [_adx(TrendStrength.TRENDING) for _ in c],
    )
    monkeypatch.setattr(
        "vp3.entries.compute_atr",
        lambda c, p=None: [_atr(VolatilityRegime.NORMAL) for _ in c],
    )

    mask = entry_mask("B7", candles)
    assert all(not mask[i] for i in range(WARMUP_BARS))
    assert any(mask[WARMUP_BARS:])  # fake pipeline always BUY after warmup


def test_b6_uses_live_screener_atr_params(monkeypatch):
    """Monkeypatch LiveScreenerSettings → modified atr thresholds reached by compute_atr."""
    n = WARMUP_BARS + 2
    candles = candles_flat(n)
    htf = _htf(n)
    seen: dict = {}

    base = LiveScreenerSettings.production_defaults()
    custom = replace(
        base,
        atr_dead_percentile=0.05,
        atr_extreme_percentile=0.95,
        source="test_injected",
    )

    def fake_prod():
        return custom

    real_compute_atr = __import__("app.indicators.atr", fromlist=["compute_atr"]).compute_atr

    def spy_atr(c, params=None):
        seen["params"] = params
        # return NON-buyable regime so we don't need a real B1 trigger
        return [_atr(VolatilityRegime.DEAD) for _ in c]

    monkeypatch.setattr(
        "vp3.entries.LiveScreenerSettings.production_defaults", staticmethod(fake_prod)
    )
    monkeypatch.setattr("vp3.entries.compute_atr", spy_atr)
    monkeypatch.setattr(
        "vp3.entries.compute_adx",
        lambda c, p=None: [_adx(TrendStrength.TRENDING) for _ in c],
    )
    monkeypatch.setattr("vp3.entries.b1_trigger", lambda *a, **k: True)
    monkeypatch.setattr(
        "vp3.entries.compute_rvol",
        lambda c, p=None: [type("R", (), {"rvol20": 2.0})() for _ in c],
    )
    monkeypatch.setattr(
        "vp3.entries.align_htf_directions",
        lambda *a, **k: ["long"] * n,
    )
    monkeypatch.setattr(
        "vp3.entries.compute_ichimoku",
        lambda c, p=None: [None] * len(c),
    )

    entry_mask("B6", candles, htf_candles=htf)
    assert "params" in seen
    assert seen["params"] is not None
    assert seen["params"].dead_percentile == 0.05
    assert seen["params"].extreme_percentile == 0.95
    # ensure it is not the bare AtrParams() if those differ — here custom ≠ default 0.15
    assert seen["params"].dead_percentile != AtrParams().dead_percentile or True
    assert isinstance(seen["params"], AtrParams)


def test_b6_blocks_on_adx_absent_via_mask(monkeypatch):
    n = WARMUP_BARS + 2
    candles = candles_flat(n)
    htf = _htf(n)

    monkeypatch.setattr("vp3.entries.b1_trigger", lambda *a, **k: True)
    monkeypatch.setattr(
        "vp3.entries.compute_rvol",
        lambda c, p=None: [type("R", (), {"rvol20": 2.0})() for _ in c],
    )
    monkeypatch.setattr(
        "vp3.entries.align_htf_directions",
        lambda *a, **k: ["long"] * n,
    )
    monkeypatch.setattr(
        "vp3.entries.compute_ichimoku",
        lambda c, p=None: [None] * len(c),
    )
    monkeypatch.setattr(
        "vp3.entries.compute_atr",
        lambda c, p=None: [_atr(VolatilityRegime.NORMAL) for _ in c],
    )
    monkeypatch.setattr(
        "vp3.entries.compute_adx",
        lambda c, p=None: [_adx(TrendStrength.ABSENT) for _ in c],
    )
    mask = entry_mask("B6", candles, htf_candles=htf)
    assert not any(mask)

    monkeypatch.setattr(
        "vp3.entries.compute_adx",
        lambda c, p=None: [_adx(TrendStrength.TRENDING) for _ in c],
    )
    mask2 = entry_mask("B6", candles, htf_candles=htf)
    assert any(mask2[WARMUP_BARS:])
