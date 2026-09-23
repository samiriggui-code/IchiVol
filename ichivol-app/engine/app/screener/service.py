"""Multi-asset screener: run ICHIMOKU_AGENT + RVOL_AGENT + the Decision
combiner over a watchlist. Mission brief §7 requirements this satisfies:
multi-asset, ranking by score, real market data (no synthetic fixtures).
Incremental caching (§7's "ne pas recalculer inutilement tout l'historique")
is not implemented yet -- every scan currently re-fetches live klines; see
app/screener/persistence.py for the DB-backed history this will eventually
read from instead.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction, StrategyAgentOutput
from app.decision.combiner import DecisionResult, combine_ichimoku_rvol
from app.decision.pipeline import PipelineResult, build_pipeline
from app.evidence.catalog import build_in_window_catalog
from app.evidence.context import SignalContext, build_signal_context
from app.evidence.engine import EvidenceEngine, EvidenceReport
from app.indicators.atr import AtrParams, AtrState
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.location import LocationParams
from app.indicators.oi_funding import OiFundingState, compute_oi_funding
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams
from app.indicators.structure import StructureParams
from app.market_data import binance_futures
from app.market_data.accumulator import fetch_with_accumulation, needs_accumulation
from app.market_data.resolve import resolve_and_fetch
from app.config import settings
from app.market_data.quality import closed_candles
from app.screener.timing import compute_signal_timing
from app.market_data.timeframes import HIGHER_TIMEFRAME, TF_SECONDS
from app.universe.catalog import default_watchlist, get_instrument
from app.universe.types import AssetClass
logger = logging.getLogger(__name__)

_OI_PERIODS = {"15m", "1h", "4h", "1d"}


def _oi_funding_state(
    provider_id: str, symbol: str, provider_symbol: str, timeframe: str, candles: list[Candle]
) -> OiFundingState | None:
    # Binance USD-M Futures only -- forex/metal/equity (twelve_data/biquote)
    # have no open interest or funding concept the same way, and an
    # uncatalogued symbol resolved to "binance" spot has no guarantee a
    # matching futures market even exists.
    if provider_id != "binance" or timeframe not in _OI_PERIODS:
        return None
    try:
        oi_points = binance_futures.fetch_open_interest_hist(provider_symbol, timeframe, limit=500)
        funding_points = binance_futures.fetch_funding_rate_hist(provider_symbol, limit=200)
        if not oi_points and not funding_points:
            return None
        return compute_oi_funding(candles, oi_points, funding_points)[-1]
    except Exception:
        logger.warning(
            "screener: OI/funding fetch failed for %s %s", provider_symbol, timeframe, exc_info=True
        )
        return None


def _closed_only(candles: list[Candle], timeframe: str, now: int | None = None) -> list[Candle]:
    """Drop the still-forming bar (when enabled and possible). Unknown timeframes
    and series that would become too short are returned unchanged."""
    tf = TF_SECONDS.get(timeframe)
    if not settings.decide_on_closed_candles or tf is None:
        return candles
    closed = closed_candles(candles, tf, int(time.time()) if now is None else now)
    return closed if len(closed) >= 2 else candles


def _mtf_direction(
    provider, symbol: str, provider_symbol: str, timeframe: str, ichi_params: IchimokuParams
) -> Direction | None:
    higher_tf = HIGHER_TIMEFRAME.get(timeframe)
    if higher_tf is None:
        return None
    try:
        htf_candles = (
            fetch_with_accumulation(provider, symbol, provider_symbol, higher_tf, 300)
            if needs_accumulation(provider.id)
            else provider.fetch_ohlcv(provider_symbol, higher_tf, 300)
        )
        htf_candles = _closed_only(htf_candles, higher_tf)
        if len(htf_candles) < 2:
            return None
        return ichimoku_agent.analyze(htf_candles, ichi_params)[-1].direction
    except Exception:
        logger.warning(
            "screener: MTF fetch failed for %s %s", provider_symbol, higher_tf, exc_info=True
        )
        return None

# Sourced from the universe catalog now (app/universe/catalog.py) instead of
# a second hardcoded copy -- same 20 symbols as before (and as
# ichivol-app/src/lib/binance.ts::WATCHLIST on the TS side), just with one
# place that names them. Evaluated once at import time, same as the literal
# tuple this replaces.
DEFAULT_WATCHLIST: tuple[str, ...] = tuple(default_watchlist())

_RANKED_DECISIONS = ("STRONG_BUY", "STRONG_SELL", "BUY", "SELL")


@dataclass(frozen=True)
class ScreenerRow:
    symbol: str
    exchange: str
    timeframe: str
    price: float
    candles: list[Candle] = field(repr=False)
    ichimoku: StrategyAgentOutput
    rvol: StrategyAgentOutput
    decision: DecisionResult
    pipeline: PipelineResult
    atr: AtrState | None = None
    """Raw ATR state behind the Régime stage's summary text -- surfaced
    separately (not just embedded in `pipeline.stages[].summary`'s French
    string) so a caller acting on a decision (paper trading, a future
    broker) has a machine-readable `suggested_stop_distance` instead of
    having to parse prose. Optional only for backward-compat with call sites
    that fabricate a ScreenerRow without one (tests)."""
    context: SignalContext | None = None
    """Canonical SignalContext at the last bar (Evidence Engine input)."""
    evidence: EvidenceReport | None = None
    """Evidence pack (historical matches + explainable contradictions)."""
    signal_timing: dict | None = None
    """See app/screener/timing.py: closed bar used, computation time, live price, lateness."""


def scan_symbol(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    exchange: str = "binance",
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
    structure_params: StructureParams = StructureParams(),
    atr_params: AtrParams = AtrParams(),
    location_params: LocationParams = LocationParams(),
) -> ScreenerRow:
    provider, provider_symbol, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles returned for {symbol} {timeframe}")
    # Live price = last traded (forming bar close); every signal uses closed bars only.
    live_price = candles[-1].close
    candles = _closed_only(candles, timeframe)

    ichimoku_output = ichimoku_agent.analyze(candles, ichi_params)[-1]
    rvol_output = rvol_agent.analyze(candles, rvol_params)[-1]
    decision = combine_ichimoku_rvol(ichimoku_output, rvol_output)

    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "cvd", "adx", "donchian"],
        candles,
        params_by_id={
            "structure": structure_params,
            "atr": atr_params,
            "location": location_params,
        },
    )
    structure_states = computed["structure"]
    structure_state = structure_states[-1]
    atr_state = computed["atr"][-1]
    location_state = computed["location"][-1]
    cvd_state = computed["cvd"][-1]
    adx_state = computed["adx"][-1]
    donchian_state = computed["donchian"][-1]
    oi_funding_state = _oi_funding_state(provider.id, symbol, provider_symbol, timeframe, candles)
    # Twelve Data free tier: skip MTF second fetch (saves 1 credit per decision).
    mtf_direction = (
        None
        if provider.id == "twelve_data"
        else _mtf_direction(provider, symbol, provider_symbol, timeframe, ichi_params)
    )
    mtf_aligned = (
        mtf_direction == ichimoku_output.direction
        if mtf_direction is not None
        and mtf_direction != Direction.NEUTRAL
        and ichimoku_output.direction != Direction.NEUTRAL
        else None
    )
    pipeline = build_pipeline(
        ichimoku=ichimoku_output,
        rvol=rvol_output,
        structure=structure_state,
        atr=atr_state,
        mtf_aligned=mtf_aligned,
        location=location_state,
        cvd=cvd_state,
        oi_funding=oi_funding_state,
        adx=adx_state,
        donchian=donchian_state,
    )

    instrument = get_instrument(symbol)
    asset_class = instrument.asset_class if instrument else AssetClass.CRYPTO
    context = build_signal_context(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        provider=provider.id,
        asset_class=asset_class,
        ichimoku=ichimoku_output,
        rvol=rvol_output,
        pipeline=pipeline,
        structure=structure_state,
        atr=atr_state,
    )
    # In-window catalog for historical matching (same series, past bars only).
    # step=3 keeps scan latency bounded on large windows.
    catalog = build_in_window_catalog(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        provider=provider.id,
        asset_class=asset_class.value,
        ichi_params=ichi_params,
        rvol_params=rvol_params,
        structure_params=structure_params,
        atr_params=atr_params,
        step=3,
    )
    evidence = EvidenceEngine(strategy_version=pipeline.strategy_version).evaluate(
        context,
        catalog,
        extra_invalidation=decision.invalidation,
    )

    return ScreenerRow(
        symbol=symbol,
        exchange=provider.id,
        timeframe=timeframe,
        price=live_price,
        signal_timing=(
            compute_signal_timing(
                candles, TF_SECONDS[timeframe], int(time.time()), live_price, timeframe,
                settings.decide_on_closed_candles,
            ).to_dict()
            if timeframe in TF_SECONDS
            else None
        ),
        candles=candles,
        ichimoku=ichimoku_output,
        rvol=rvol_output,
        decision=decision,
        pipeline=pipeline,
        atr=atr_state,
        context=context,
        evidence=evidence,
    )

def scan_watchlist(
    symbols: Sequence[str] = DEFAULT_WATCHLIST,
    timeframe: str = "1h",
    limit: int = 300,
    concurrency: int = 6,
    rvol_params: RvolParams = RvolParams(),
    atr_params: AtrParams = AtrParams(),
    location_params: LocationParams = LocationParams(),
) -> list[ScreenerRow]:
    """Scans symbols concurrently (I/O-bound: each is one Binance HTTP call) --
    sequential scanning of a 20-symbol watchlist was measured to exceed the
    Express proxy's request timeout in practice. `concurrency` mirrors the
    same mapPool(4) pattern already used by the TS screener
    (ichivol-app/src/lib/binance.ts), just slightly higher since this runs
    server-side rather than in a browser tab.
    """
    rows: list[ScreenerRow] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(
                scan_symbol,
                symbol,
                timeframe,
                limit,
                rvol_params=rvol_params,
                atr_params=atr_params,
                location_params=location_params,
            ): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.append(future.result())
            except Exception:
                logger.warning("screener: skipping %s (%s)", symbol, timeframe, exc_info=True)

    rows.sort(
        key=lambda r: (r.decision.decision not in _RANKED_DECISIONS, -r.decision.confidence)
    )
    return rows
