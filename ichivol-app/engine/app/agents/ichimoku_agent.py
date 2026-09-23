"""ICHIMOKU_AGENT: wraps app.indicators.ichimoku into a StrategyAgentOutput.

This is the Ichimoku half of the mission's "Ichimoku x RVOL" decision
engine, reshaped to already speak the StrategyAgentOutput contract from
docs/TRADING_ARCHITECTURE_V2.md so a future multi-agent Consensus Engine
(RVOL_AGENT, MOMENTUM_AGENT, ...) can consume it unchanged. It does not
implement consensus, edge, or risk logic itself -- see that doc for why
those stay out of scope here.

`probability` and `confidence` are deliberately cheap heuristics derived
from the causal structured state (see app/indicators/ichimoku.py), not a
calibrated model: turning them into a real P(direction) requires backtest
calibration (docs/INTEGRATION_PLAN.md Phase 1/2), which this module does
not attempt. `expected_value` is left at 0.0 for the same reason -- a
non-zero value here would be fabricated, not measured.
"""

from __future__ import annotations

from typing import Sequence

from app.indicators.ichimoku import (
    Candle,
    ChikouState,
    CrossState,
    IchimokuParams,
    IchimokuState,
    PriceVsKumo,
)
from app.indicators.registry import REGISTRY

from .types import Direction, StrategyAgentOutput

AGENT_NAME = "ICHIMOKU_AGENT"

_CAUSAL_DIMENSIONS = (
    "price_vs_kumo",
    "tk_cross",
    "future_kumo",
    "chikou_state",
    "kumo_breakout",
)


def _is_known(state: IchimokuState, dimension: str) -> bool:
    value = getattr(state, dimension)
    unknown_members = {PriceVsKumo.UNKNOWN, CrossState.UNKNOWN, ChikouState.UNKNOWN}
    return value not in unknown_members


def _confidence(state: IchimokuState) -> float:
    known = sum(1 for d in _CAUSAL_DIMENSIONS if _is_known(state, d))
    return known / len(_CAUSAL_DIMENSIONS)


def _direction(state: IchimokuState) -> Direction:
    if state.score is None:
        return Direction.NEUTRAL
    if state.price_vs_kumo == PriceVsKumo.ABOVE and state.score > 0:
        return Direction.LONG
    if state.price_vs_kumo == PriceVsKumo.BELOW and state.score < 0:
        return Direction.SHORT
    return Direction.NEUTRAL


def _probability(state: IchimokuState, direction: Direction) -> float:
    if direction == Direction.NEUTRAL or state.score is None:
        return 0.5
    magnitude = min(abs(state.score), 100.0) / 100.0
    return round(0.5 + magnitude * 0.5, 4)


def _reasons(state: IchimokuState, direction: Direction) -> list[str]:
    if direction == Direction.LONG:
        checks = [
            (state.price_vs_kumo == PriceVsKumo.ABOVE, "price_above_kumo"),
            (state.tk_cross == CrossState.BULLISH, "bullish_tk_cross"),
            (state.future_kumo == CrossState.BULLISH, "bullish_future_kumo"),
            (state.chikou_state == ChikouState.CLEAR_BULLISH, "chikou_confirmation"),
            (state.kumo_breakout == CrossState.BULLISH, "kumo_breakout_bullish"),
        ]
    elif direction == Direction.SHORT:
        checks = [
            (state.price_vs_kumo == PriceVsKumo.BELOW, "price_below_kumo"),
            (state.tk_cross == CrossState.BEARISH, "bearish_tk_cross"),
            (state.future_kumo == CrossState.BEARISH, "bearish_future_kumo"),
            (state.chikou_state == ChikouState.CLEAR_BEARISH, "chikou_confirmation"),
            (state.kumo_breakout == CrossState.BEARISH, "kumo_breakout_bearish"),
        ]
    else:
        return ["insufficient_confluence"] if state.score is not None else ["insufficient_history"]
    return [label for present, label in checks if present]


def _invalidation(direction: Direction) -> list[str]:
    if direction == Direction.LONG:
        return ["close_back_inside_kumo", "bearish_tk_cross"]
    if direction == Direction.SHORT:
        return ["close_back_inside_kumo", "bullish_tk_cross"]
    return []


def _metadata(state: IchimokuState) -> dict:
    return {
        "time": state.time,
        "tenkan": state.tenkan,
        "kijun": state.kijun,
        "senkou_a": state.senkou_a,
        "senkou_b": state.senkou_b,
        "cloud_top": state.cloud_top,
        "cloud_bot": state.cloud_bot,
        "kumo_thickness": state.kumo_thickness,
        "score": state.score,
        "price_vs_kumo": state.price_vs_kumo.value,
        "tk_cross": state.tk_cross.value,
        "tk_strength": state.tk_strength.value,
        "future_kumo": state.future_kumo.value,
        "chikou_state": state.chikou_state.value,
        "kumo_breakout": state.kumo_breakout.value,
        "trend_strength": state.trend_strength.value,
    }


def state_to_agent_output(state: IchimokuState) -> StrategyAgentOutput:
    direction = _direction(state)
    return StrategyAgentOutput(
        agent=AGENT_NAME,
        direction=direction,
        probability=_probability(state, direction),
        confidence=round(_confidence(state), 4),
        expected_value=0.0,
        reasons=_reasons(state, direction),
        invalidation=_invalidation(direction),
        metadata=_metadata(state),
    )


def analyze(
    candles: Sequence[Candle],
    params: IchimokuParams = IchimokuParams(),
) -> list[StrategyAgentOutput]:
    states = REGISTRY.compute("ichimoku", candles, params)
    return [state_to_agent_output(s) for s in states]
