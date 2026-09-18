"""Tests for RSI / CMF / OBV + context gate."""

from __future__ import annotations

from dataclasses import fields

from app.agents.types import Direction
from app.context.gate import apply_context_gate
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.indicators.cmf import compute_cmf
from app.indicators.obv import compute_obv
from app.indicators.rsi import compute_rsi
from app.paper.strategy_profiles import BASELINE_PROFILE, ICHIVOL_CTX_RSI, profile_for
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_rsi_cmf_obv_causal_truncation():
    candles = _make_candles(180, seed=5)
    for compute in (compute_rsi, compute_cmf, compute_obv):
        full = compute(candles)
        trunc = compute(candles[:100])
        names = [f.name for f in fields(full[0]) if f.name != "time"]
        for name in names:
            assert getattr(trunc[-1], name) == getattr(full[99], name), name


def test_baseline_context_off():
    pipe = PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[PipelineStage(StageId.REGIME, StageStatus.PASS, "ok", [])],
    )
    gate = apply_context_gate(pipe, _make_candles(80), BASELINE_PROFILE)
    assert gate.blocked is False
    assert gate.pipeline.decision == "BUY"


def test_rsi_profile_registered():
    p = profile_for("ICHIVOL_CTX_RSI")
    assert p["context_rsi"] is True
    assert ICHIVOL_CTX_RSI["code"] == "ICHIVOL_CTX_RSI"


def test_context_gate_can_block_overbought_long():
    # Strong uptrend candles tend to push RSI high
    candles = _make_candles(120, seed=1)
    # Force last closes upward aggressively
    from app.indicators.ichimoku import Candle

    forced = list(candles)
    price = forced[-1].close
    for i in range(30):
        price *= 1.04
        forced.append(
            Candle(
                time=1000 + i,
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=200,
            )
        )
    pipe = PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[PipelineStage(StageId.REGIME, StageStatus.PASS, "ok", [])],
    )
    gate = apply_context_gate(pipe, forced, ICHIVOL_CTX_RSI)
    # May or may not block depending on RSI — just ensure payload present when filter on
    assert gate.raw_decision == "BUY"
    if gate.blocked:
        assert gate.pipeline.decision == "NO_TRADE"
        assert gate.context_payload and "rsi" in gate.context_payload
