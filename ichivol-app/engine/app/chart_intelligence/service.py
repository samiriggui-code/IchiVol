"""Assemble Chart Intelligence payload from live engine producers.

Observe-only: reuses ChartObjects + Ichimoku + RVOL/ATR. Does not write
orders or mutate the decision pipeline. ``as_of`` truncates candles so
overlays match what was knowable at that bar (anti-lookahead).
"""

from __future__ import annotations

from typing import Any

from app.agents import ichimoku_agent, rvol_agent
from app.chart_objects.collect import parse_sources
from app.chart_objects.from_breaks import breaks_to_chart_objects
from app.chart_objects.from_fibonacci import fibonacci_to_chart_objects
from app.chart_objects.from_fvg import fvg_to_chart_objects
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.store import list_chart_objects
from app.chart_objects.types import ChartObjectSource
from app.db.session import SessionLocal
from app.decision.combiner import combine_ichimoku_rvol
from app.indicators.atr import VolatilityRegime
from app.indicators.ichimoku import Candle, compute_projected_kumo
from app.indicators.registry import REGISTRY
from app.market_data import twelve_data
from app.market_data.resolve import resolve_and_fetch
from app.market_data.timeframes import TF_SECONDS
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure


def _candle_dict(c: Candle) -> dict[str, Any]:
    return {
        "time": int(c.time),
        "open": float(c.open),
        "high": float(c.high),
        "low": float(c.low),
        "close": float(c.close),
        "volume": float(c.volume) if c.volume is not None else 0.0,
    }


def _enrich_object(obj: dict[str, Any], *, known_at: int | None) -> dict[str, Any]:
    """Additive origin keys expected by Chart Intelligence UI."""
    origin = dict(obj.get("origin") or {})
    if known_at is not None and origin.get("known_at") is None:
        origin["known_at"] = int(known_at)
    if origin.get("producer") is None and obj.get("source") == "engine":
        layer = obj.get("layer")
        if layer == "fibonacci":
            origin["producer"] = "fibonacci_engine"
        elif layer == "fvg":
            origin["producer"] = "fvg_engine"
        elif layer == "breaks":
            origin["producer"] = "structure_engine"
        else:
            origin["producer"] = "structure_engine"
    obj = dict(obj)
    obj["origin"] = origin
    return obj


def _structure_label(objects: list[dict[str, Any]]) -> str:
    swings = [
        (o.get("origin") or {}).get("swing")
        for o in objects
        if (o.get("origin") or {}).get("kind") == "swing"
    ]
    swings = [s for s in swings if s]
    if not swings:
        return "MIXED"
    # Last few swing labels → compact structure tag.
    tail = swings[-4:]
    if all(s in ("HH", "HL") for s in tail):
        return "HH_HL"
    if all(s in ("LH", "LL") for s in tail):
        return "LH_LL"
    return "MIXED"


def _vol_label(regime: str | None) -> str:
    if regime == VolatilityRegime.DEAD.value:
        return "dead"
    if regime == VolatilityRegime.EXTREME.value:
        return "extreme"
    return "normal"


def _trend_label(*, close: float | None, tenkan: float | None, kijun: float | None) -> str:
    if close is None or tenkan is None or kijun is None:
        return "range"
    if close > tenkan > kijun:
        return "bullish"
    if close < tenkan < kijun:
        return "bearish"
    return "range"


def build_chart_intelligence(
    *,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    as_of: int | None = None,
    sources: str | list[str] | None = "engine,user,claude",
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    sym = symbol.upper()
    requested = parse_sources(sources)
    tf_sec = int(TF_SECONDS.get(timeframe, 3600))

    definition = REGISTRY.get("ichimoku")
    ichi_params = definition.build_params({})
    warmup = int(definition.warmup(ichi_params))
    fetch_limit = max(1, min(int(limit) + warmup, 5000))

    twelve_data.set_api_key_override(x_twelve_data_key)
    provider, provider_symbol, raw_candles = resolve_and_fetch(sym, timeframe, fetch_limit)
    if not raw_candles:
        raise ValueError(f"no_candles:{sym}")

    replay_first = int(raw_candles[0].time)
    replay_last = int(raw_candles[-1].time)

    candles = list(raw_candles)
    if as_of is not None:
        cut = int(as_of)
        candles = [c for c in candles if int(c.time) <= cut]
        if not candles:
            raise ValueError(f"no_candles_at_as_of:{sym}:{cut}")

    window = candles[-int(limit) :] if len(candles) > int(limit) else candles
    effective_as_of = int(window[-1].time)

    objects: list[dict[str, Any]] = []
    if ChartObjectSource.ENGINE.value in requested:
        params = StructureEngineParams(window_bars=min(len(window), 500))
        snap = detect_market_structure(
            window, params, include_pytrendline=include_pytrendline
        )
        objects.extend(
            o.to_dict()
            for o in structure_to_chart_objects(snap, sym, timeframe, window)
        )
        objects.extend(
            o.to_dict()
            for o in breaks_to_chart_objects(window, sym, timeframe, snapshot=snap)
        )
        objects.extend(o.to_dict() for o in fvg_to_chart_objects(window, sym, timeframe))
        objects.extend(
            o.to_dict()
            for o in fibonacci_to_chart_objects(window, sym, timeframe, key_only=True)
        )

    persist_sources = [
        s
        for s in requested
        if s in (ChartObjectSource.USER.value, ChartObjectSource.CLAUDE.value)
    ]
    if persist_sources:
        session = SessionLocal()
        try:
            stored = list_chart_objects(
                session, symbol=sym, timeframe=timeframe, sources=persist_sources
            )
            # Replay: only overlays known by as_of.
            for o in stored:
                if int(o.as_of) <= effective_as_of:
                    objects.append(o.to_dict())
        finally:
            session.close()

    objects = [_enrich_object(o, known_at=effective_as_of) for o in objects]

    # Ichimoku on full truncated series (warmup), slice to window.
    ichi_states = REGISTRY.compute("ichimoku", candles, ichi_params)
    window_start = int(window[0].time)
    ichimoku = [
        {
            "time": int(s.time),
            "tenkan": s.tenkan,
            "kijun": s.kijun,
        }
        for s in ichi_states
        if int(s.time) >= window_start
    ]

    projection_raw = [
        p
        for p in compute_projected_kumo(candles, ichi_params)
        if int(p["time_projected"]) >= window_start
    ]
    projection = [
        {
            "time": int(p["time_projected"]),
            "senkouA": p["senkou_a"],
            "senkouB": p["senkou_b"],
        }
        for p in projection_raw
        if p.get("senkou_a") is not None and p.get("senkou_b") is not None
    ]

    # Market state + analysis from existing agents (no new formula).
    rvol_out = rvol_agent.analyze(window)[-1]
    ichi_out = ichimoku_agent.analyze(window)[-1]
    decision = combine_ichimoku_rvol(ichi_out, rvol_out)
    atr_states = REGISTRY.compute("atr", window, REGISTRY.get("atr").build_params({}))
    atr_last = atr_states[-1] if atr_states else None
    last_ichi = ichi_states[-1] if ichi_states else None
    close = float(window[-1].close)

    rvol_val = rvol_out.metadata.get("rvol")
    rvol_f = float(rvol_val) if rvol_val is not None else 0.0
    regime_val = atr_last.regime.value if atr_last is not None else None
    market_state = {
        "trend": _trend_label(
            close=close,
            tenkan=getattr(last_ichi, "tenkan", None),
            kijun=getattr(last_ichi, "kijun", None),
        ),
        "structure": _structure_label(objects),
        "volatility": _vol_label(regime_val),
        "rvol": rvol_f,
    }

    waiting: list[str] = []
    if rvol_f < 1.5:
        waiting.append("RVOL > 1.5")
    confluence_lines = [r for r in (decision.reasons or []) if r][:6]
    analysis = {
        "state": decision.decision,
        "confidence": float(decision.confidence),
        "summary": "; ".join(confluence_lines) if confluence_lines else decision.decision,
        "confluence": confluence_lines,
        "waiting": waiting,
        "producer": "engine",
    }

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "as_of": effective_as_of,
        "sources": requested,
        "candles": [_candle_dict(c) for c in window],
        "ichimoku": ichimoku,
        "projection": projection,
        "market_state": market_state,
        "objects": objects,
        "count": len(objects),
        "analysis": analysis,
        "replay": {
            "first": replay_first,
            "last": replay_last if as_of is None else effective_as_of,
            "bar_seconds": tf_sec,
        },
        "mock": False,
    }
