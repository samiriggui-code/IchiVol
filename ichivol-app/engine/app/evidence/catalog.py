"""Build an in-window historical catalog from one OHLCV series.

Used by EvidenceEngine when the Evidence DB is empty: replay the same
indicator stack causally at each past bar and keep contexts that look
like actionable setups. Strictly anti-lookahead (only candles[0..i]).
"""

from __future__ import annotations

from typing import Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.decision.pipeline import build_pipeline
from app.evidence.context import SignalContext, build_signal_context
from app.indicators.atr import AtrParams
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams
from app.indicators.structure import StructureParams


def build_in_window_catalog(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    provider: str,
    asset_class: str,
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    atr_params: AtrParams = AtrParams(),
    min_bars: int = 80,
    step: int = 1,
    require_directional: bool = True,
) -> list[tuple[SignalContext, Sequence[Candle], int]]:
    """Return (context_at_i, full_candles, i) for each eligible bar i.

    Forward metrics in matching use candles after i; contexts use only
    candles[: i + 1] via indicator recomputation on the prefix.
    """
    n = len(candles)
    out: list[tuple[SignalContext, Sequence[Candle], int]] = []
    if n < min_bars + 5:
        return out

    # Precompute full series once; slice states by index (causal by construction).
    ichi_series = ichimoku_agent.analyze(list(candles), ichi_params)
    rvol_series = rvol_agent.analyze(list(candles), rvol_params)
    computed = REGISTRY.compute_many(
        ["structure", "atr"],
        candles,
        params_by_id={
            "structure": structure_params,
            "atr": atr_params,
        },
    )
    structure_series = computed["structure"]
    atr_series = computed["atr"]

    for i in range(min_bars, n - 2, max(1, step)):
        ichi = ichi_series[i]
        rvol = rvol_series[i]
        if require_directional and ichi.direction == Direction.NEUTRAL:
            continue
        pipeline = build_pipeline(
            ichimoku=ichi,
            rvol=rvol,
            structure=structure_series[i],
            atr=atr_series[i],
        )
        ctx = build_signal_context(
            symbol=symbol,
            timeframe=timeframe,
            candles=list(candles[: i + 1]),
            provider=provider,
            asset_class=asset_class,
            ichimoku=ichi,
            rvol=rvol,
            pipeline=pipeline,
            structure=structure_series[i],
            atr=atr_series[i],
        )
        out.append((ctx, candles, i))
    return out
