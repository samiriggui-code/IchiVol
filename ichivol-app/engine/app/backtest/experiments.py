"""Named backtest experiments -- this mission's central hypothesis (brief
§10) plus the north-star realignment's own open question (does the staged
pipeline actually beat the legacy combiner it's meant to replace?
docs/CAHIER-DES-CHARGES.md backlog: "Combiner x -> portes comme seule
verite produit (migration)" needs evidence first). This module produces
the numbers; it does not assert either hypothesis is true -- that's for
whoever reads the comparison.

- ICHIMOKU_ONLY: structure alone, no volume filter.
- ICHIMOKU_RVOL: RVOL re-checked every bar (strict, can churn -- an empirical
  run on real BTCUSDT 1h data showed this variant underperforming
  ICHIMOKU_ONLY specifically because of the extra trades this churn causes).
- ICHIMOKU_RVOL_ENTRY_GATE: RVOL confirms only at entry, position then held
  on structure alone (the more common "confirm the breakout" reading).
- PIPELINE: the staged Direction->Participation->Structure/MTF->Regime gate
  pipeline (app/decision/pipeline.py) -- in a LONG/SHORT position only when
  its label resolves to BUY/SELL, flat (NEUTRAL) on WATCH/NO_TRADE. This is
  the candidate meant to eventually replace the legacy combiner in
  production; the point of backtesting it here is to find out whether it
  actually should, not to assume it. Includes both the ADX regime gate (V3,
  promoted 2026-09-16) and the Donchian regime gate (V3, promoted
  2026-09-16 after its own 3-window backtest -- see engine README) since
  app/decision/pipeline.py itself now applies both; there is no separate
  "with/without ADX" or "with/without Donchian" variant here anymore.
- PIPELINE_WYCKOFF_FILTER (V3 experimental, docs/CAHIER-DES-CHARGES.md:
  "Wyckoff / Donchian -- backtest avant tout droit de vote"): same
  pre-promotion methodology ADX and Donchian went through -- filter
  PIPELINE's own positions on Wyckoff spring/upthrust and see if that
  actually helps. Unlike Donchian, Wyckoff's backtest showed no edge (see
  engine README), so it stays here as a documented negative result, not
  wired into app/decision/pipeline.py. Only ever downgrades a PIPELINE
  position to flat, never invents one of its own or flips its direction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction, StrategyAgentOutput
from app.backtest.engine import (
    ActionableDecisions,
    BacktestResult,
    desired_position_from_decision,
    run_backtest,
)
from app.backtest.metrics import Metrics, compute_metrics
from app.decision.combiner import combine_ichimoku_rvol
from app.decision.pipeline import build_pipeline
from app.indicators.adx import AdxParams, AdxState
from app.indicators.atr import AtrParams, AtrState
from app.indicators.cvd import CvdState
from app.indicators.donchian import DonchianParams, DonchianState
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.location import LocationParams, LocationState
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams
from app.indicators.structure import StructureParams, StructureState
from app.indicators.wyckoff import WyckoffParams, WyckoffPhase, WyckoffState
from app.market_data.accumulator import fetch_with_accumulation, needs_accumulation
from app.market_data.resolve import resolve_and_fetch
from app.market_data.timeframes import HIGHER_TIMEFRAME, TF_SECONDS

logger = logging.getLogger(__name__)

ICHIMOKU_ONLY = "ICHIMOKU_ONLY"
ICHIMOKU_RVOL = "ICHIMOKU_RVOL"
ICHIMOKU_RVOL_ENTRY_GATE = "ICHIMOKU_RVOL_ENTRY_GATE"
PIPELINE = "PIPELINE"
PIPELINE_WYCKOFF_FILTER = "PIPELINE_WYCKOFF_FILTER"


@dataclass(frozen=True)
class ExperimentResult:
    name: str
    backtest: BacktestResult
    metrics: Metrics


@dataclass(frozen=True)
class PreparedVariants:
    """Shared OHLCV + per-variant desired positions for backtest / event study."""

    symbol: str
    timeframe: str
    candles: list[Candle]
    atr_states: list[AtrState]
    positions: dict[str, list[Direction]]


def ichimoku_only_positions(ichi_outputs: Sequence[StrategyAgentOutput]) -> list[Direction]:
    return [o.direction for o in ichi_outputs]


def ichimoku_rvol_positions(
    ichi_outputs: Sequence[StrategyAgentOutput],
    rvol_outputs: Sequence[StrategyAgentOutput],
) -> list[Direction]:
    """RVOL re-checked on every bar: stays flat the instant confirmation
    lapses, even mid-trend. Strict reading of "un signal ne compte que s'il
    est confirme par le volume relatif", applied continuously rather than
    only at entry -- see ichimoku_rvol_entry_gate_positions for the other
    reading."""
    if len(ichi_outputs) != len(rvol_outputs):
        raise ValueError("ichimoku and rvol output series must be the same length")
    positions = []
    for ichi_o, rvol_o in zip(ichi_outputs, rvol_outputs):
        decision = combine_ichimoku_rvol(ichi_o, rvol_o)
        positions.append(desired_position_from_decision(decision.decision, decision.direction))
    return positions


def ichimoku_rvol_entry_gate_positions(
    ichi_outputs: Sequence[StrategyAgentOutput],
    rvol_outputs: Sequence[StrategyAgentOutput],
) -> list[Direction]:
    """RVOL confirms only at the moment of entry (matching the classic
    "confirm the breakout with volume" reading). Once in a position, it is
    held purely on Ichimoku structure -- RVOL is not re-checked while
    holding, so a lull in volume mid-trend does not force an exit. Causal:
    only ever reads ichi_outputs[i]/rvol_outputs[i] while walking forward,
    carrying `held` as state -- never looks ahead.
    """
    if len(ichi_outputs) != len(rvol_outputs):
        raise ValueError("ichimoku and rvol output series must be the same length")
    positions: list[Direction] = []
    held = Direction.NEUTRAL
    for ichi_o, rvol_o in zip(ichi_outputs, rvol_outputs):
        if held == Direction.NEUTRAL:
            decision = combine_ichimoku_rvol(ichi_o, rvol_o)
            if decision.decision in ActionableDecisions:
                held = decision.direction
        elif ichi_o.direction != held:
            held = Direction.NEUTRAL
        positions.append(held)
    return positions


def _align_mtf_directions(
    primary_candles: Sequence[Candle],
    htf_candles: Sequence[Candle],
    htf_outputs: Sequence[StrategyAgentOutput],
    htf_seconds: int,
) -> list[Direction | None]:
    """For each primary candle, the higher-timeframe direction from the most
    recent HTF bar that had FULLY CLOSED by that primary candle's own
    timestamp -- never a bar still "in progress" or in the future relative
    to the primary bar. A kline's `time` is its *open* time, so a bar opened
    at `h` is only closed once `h + htf_seconds` has elapsed; causal by
    construction (verified in tests/backtest/test_experiments.py), the same
    way every other indicator in this codebase is.
    """
    result: list[Direction | None] = []
    htf_idx = 0
    n_htf = len(htf_candles)
    for candle in primary_candles:
        while htf_idx + 1 < n_htf and (htf_candles[htf_idx + 1].time + htf_seconds) <= candle.time:
            htf_idx += 1
        if htf_idx < n_htf and (htf_candles[htf_idx].time + htf_seconds) <= candle.time:
            result.append(htf_outputs[htf_idx].direction)
        else:
            result.append(None)
    return result


def pipeline_positions(
    ichi_outputs: Sequence[StrategyAgentOutput],
    rvol_outputs: Sequence[StrategyAgentOutput],
    structure_states: Sequence[StructureState],
    atr_states: Sequence[AtrState],
    mtf_directions: Sequence[Direction | None],
    location_states: Sequence[LocationState],
    cvd_states: Sequence[CvdState] | None = None,
    adx_states: Sequence[AdxState] | None = None,
    donchian_states: Sequence[DonchianState] | None = None,
) -> list[Direction]:
    """In a position only while the staged pipeline (app/decision/pipeline.py)
    actually says BUY/SELL; flat on WATCH/NO_TRADE. `mtf_directions[i]` may
    be None (no higher timeframe, or it couldn't be fetched) -- the
    structure stage simply skips that contribution when so, same as the
    live screener path. `cvd_states` is optional context-only enrichment
    (never changes a stage's status); `adx_states` and `donchian_states`,
    when given, actively gate the Regime stage now (both promoted live
    2026-09-16 -- see engine README for the backtests that proved each
    edge). Omit any of them and every bar behaves exactly as before that
    signal existed."""
    series = [ichi_outputs, rvol_outputs, structure_states, atr_states, mtf_directions, location_states]
    if cvd_states is not None:
        series.append(cvd_states)
    if adx_states is not None:
        series.append(adx_states)
    if donchian_states is not None:
        series.append(donchian_states)
    if len({len(s) for s in series}) != 1:
        raise ValueError("all per-bar series passed to pipeline_positions must be the same length")

    cvd_iter = cvd_states if cvd_states is not None else [None] * len(ichi_outputs)
    adx_iter = adx_states if adx_states is not None else [None] * len(ichi_outputs)
    donchian_iter = donchian_states if donchian_states is not None else [None] * len(ichi_outputs)
    positions: list[Direction] = []
    for ichi_o, rvol_o, structure_s, atr_s, mtf_dir, location_s, cvd_s, adx_s, donchian_s in zip(
        ichi_outputs, rvol_outputs, structure_states, atr_states, mtf_directions, location_states,
        cvd_iter, adx_iter, donchian_iter,
    ):
        mtf_aligned = (
            mtf_dir == ichi_o.direction
            if mtf_dir is not None
            and mtf_dir != Direction.NEUTRAL
            and ichi_o.direction != Direction.NEUTRAL
            else None
        )
        result = build_pipeline(
            ichi_o, rvol_o, structure_s, atr_s, mtf_aligned, location_s, cvd_s, None, adx_s, donchian_s
        )
        positions.append(result.direction if result.decision in ("BUY", "SELL") else Direction.NEUTRAL)
    return positions


def pipeline_wyckoff_filter_positions(
    pipeline_positions_series: Sequence[Direction],
    wyckoff_states: Sequence[WyckoffState],
) -> list[Direction]:
    """Pre-promotion test (see module docstring): PIPELINE's own position,
    downgraded to flat only on the rare bar where an active Wyckoff test
    directly contradicts it -- a LONG while an UPTHRUST (bearish tell) is
    in play, or a SHORT while a SPRING (bullish tell) is in play. SPRING/
    UPTHRUST are single-bar events (see app/indicators/wyckoff.py), so this
    should affect very few bars either way -- the point of measuring it is
    finding out whether even that small a filter helps, not assuming it
    must. Never flips or invents a direction, only ever downgrades toward
    NEUTRAL.
    """
    if len(pipeline_positions_series) != len(wyckoff_states):
        raise ValueError("pipeline_positions_series and wyckoff_states must be the same length")
    out: list[Direction] = []
    for position, w in zip(pipeline_positions_series, wyckoff_states):
        if position == Direction.LONG and w.phase == WyckoffPhase.UPTHRUST:
            out.append(Direction.NEUTRAL)
        elif position == Direction.SHORT and w.phase == WyckoffPhase.SPRING:
            out.append(Direction.NEUTRAL)
        else:
            out.append(position)
    return out


def prepare_variants(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    exchange: str = "binance",
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    atr_params: AtrParams = AtrParams(),
    location_params: LocationParams = LocationParams(),
    adx_params: AdxParams = AdxParams(),
    donchian_params: DonchianParams = DonchianParams(),
    wyckoff_params: WyckoffParams = WyckoffParams(),
) -> PreparedVariants:
    """Fetch candles and build all named desired-position series (shared by
    backtest compare and Strategy Lab event study)."""
    provider, provider_symbol, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles returned for {symbol} {timeframe}")

    ichi_outputs = ichimoku_agent.analyze(candles, ichi_params)
    rvol_outputs = rvol_agent.analyze(candles, rvol_params)
    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "cvd", "adx", "donchian", "wyckoff"],
        candles,
        params_by_id={
            "structure": structure_params,
            "atr": atr_params,
            "location": location_params,
            "adx": adx_params,
            "donchian": donchian_params,
            "wyckoff": wyckoff_params,
        },
    )
    structure_states = computed["structure"]
    atr_states = computed["atr"]
    location_states = computed["location"]
    cvd_states = computed["cvd"]
    adx_states = computed["adx"]
    donchian_states = computed["donchian"]
    wyckoff_states = computed["wyckoff"]

    mtf_directions: list[Direction | None] = [None] * len(candles)
    higher_tf = HIGHER_TIMEFRAME.get(timeframe)
    if higher_tf is not None:
        try:
            htf_candles = (
                fetch_with_accumulation(provider, symbol, provider_symbol, higher_tf, limit)
                if needs_accumulation(provider.id)
                else provider.fetch_ohlcv(provider_symbol, higher_tf, limit)
            )
            if len(htf_candles) >= 2:
                htf_outputs = ichimoku_agent.analyze(htf_candles, ichi_params)
                mtf_directions = _align_mtf_directions(
                    candles, htf_candles, htf_outputs, TF_SECONDS[higher_tf]
                )
        except Exception:
            # MTF is best-effort here too (matches screener/service.py): absence
            # just means the structure stage skips that contribution for this run.
            logger.warning(
                "backtest: MTF fetch failed for %s %s", provider_symbol, higher_tf, exc_info=True
            )

    pipeline_series = pipeline_positions(
        ichi_outputs, rvol_outputs, structure_states, atr_states, mtf_directions,
        location_states, cvd_states, adx_states, donchian_states,
    )

    positions = {
        ICHIMOKU_ONLY: ichimoku_only_positions(ichi_outputs),
        ICHIMOKU_RVOL: ichimoku_rvol_positions(ichi_outputs, rvol_outputs),
        ICHIMOKU_RVOL_ENTRY_GATE: ichimoku_rvol_entry_gate_positions(ichi_outputs, rvol_outputs),
        PIPELINE: pipeline_series,
        PIPELINE_WYCKOFF_FILTER: pipeline_wyckoff_filter_positions(pipeline_series, wyckoff_states),
    }
    return PreparedVariants(
        symbol=symbol,
        timeframe=timeframe,
        candles=list(candles),
        atr_states=atr_states,
        positions=positions,
    )


def compare(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    exchange: str = "binance",
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    atr_params: AtrParams = AtrParams(),
    location_params: LocationParams = LocationParams(),
    adx_params: AdxParams = AdxParams(),
    donchian_params: DonchianParams = DonchianParams(),
    wyckoff_params: WyckoffParams = WyckoffParams(),
) -> dict[str, ExperimentResult]:
    prepared = prepare_variants(
        symbol,
        timeframe=timeframe,
        limit=limit,
        exchange=exchange,
        ichi_params=ichi_params,
        rvol_params=rvol_params,
        structure_params=structure_params,
        atr_params=atr_params,
        location_params=location_params,
        adx_params=adx_params,
        donchian_params=donchian_params,
        wyckoff_params=wyckoff_params,
    )
    results: dict[str, ExperimentResult] = {}
    for name, desired in prepared.positions.items():
        backtest = run_backtest(
            prepared.candles, desired, symbol=symbol, timeframe=timeframe
        )
        results[name] = ExperimentResult(
            name=name, backtest=backtest, metrics=compute_metrics(backtest)
        )
    return results
