"""Assemble Chart Intelligence payload from live engine producers.

Observe-only: reuses ChartObjects + Ichimoku + pipeline stages. Does not write
orders or mutate paper. ``as_of`` truncates candles before computing overlays.

CI-R1: progressive replay uses ``build_chart_intelligence_replay`` (walk-forward).
CI-R7: frames omit candles/ichimoku/projection (sent once at pack root).
CI-R8: ``known_at`` / ``status_history`` keyed by ``origin.lineage_key``.
CI-R9: replay cache is an LRU of 32 with expired purge on write.
Client-side filtering of a live snapshot by anchor ``known_at`` is NOT safe —
do not claim anti-lookahead for that path.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from app.agents import ichimoku_agent, rvol_agent
from app.chart_objects.collect import parse_sources
from app.chart_objects.from_breaks import breaks_to_chart_objects
from app.chart_objects.from_fibonacci import fibonacci_to_chart_objects
from app.chart_objects.from_fvg import fvg_to_chart_objects
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.store import list_chart_objects
from app.chart_objects.types import ChartObjectSource
from app.config import settings
from app.db.session import SessionLocal
from app.decision.pipeline import build_pipeline
from app.indicators.atr import VolatilityRegime
from app.indicators.ichimoku import Candle, compute_projected_kumo
from app.indicators.registry import REGISTRY
from app.market_data import twelve_data
from app.market_data.quality import closed_candles
from app.market_data.resolve import resolve_and_fetch
from app.market_data.timeframes import TF_SECONDS
from app.strategy_lab.adn_ichivol import LiveScreenerSettings
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure

# (symbol, timeframe, last_bar_time, from_ts, to_ts, lookback) → (expires_at, payload)
_REPLAY_CACHE: OrderedDict[tuple[Any, ...], tuple[float, dict[str, Any]]] = OrderedDict()
_REPLAY_CACHE_LOCK = threading.Lock()
_REPLAY_CACHE_TTL_S = 60.0
_REPLAY_CACHE_MAX = 32
_DEFAULT_REPLAY_LOOKBACK = 48


def _candle_dict(c: Candle) -> dict[str, Any]:
    return {
        "time": int(c.time),
        "open": float(c.open),
        "high": float(c.high),
        "low": float(c.low),
        "close": float(c.close),
        "volume": float(c.volume) if c.volume is not None else 0.0,
    }


def _closed_only(
    candles: list[Candle], timeframe: str, now: int | None = None
) -> list[Candle]:
    """Drop the still-forming bar (CI-R2), same rule as screener/cycle."""
    tf = TF_SECONDS.get(timeframe)
    if tf is None:
        return candles
    if not settings.decide_on_closed_candles:
        return candles
    closed = closed_candles(candles, int(tf), int(time.time()) if now is None else int(now))
    return closed if len(closed) >= 2 else candles


def _lineage_key(obj: dict[str, Any]) -> str:
    """Stable identity for known_at / status_history (CI-R8). Falls back to id."""
    origin = obj.get("origin") or {}
    lk = origin.get("lineage_key")
    if lk is not None and str(lk).strip():
        return str(lk)
    return str(obj.get("id") or "")


def _enrich_object(obj: dict[str, Any], *, known_at: int | None = None) -> dict[str, Any]:
    """Additive origin keys for the UI.

    Does NOT invent known_at from anchor point times (CI-R1) — that leaked
    final Fib/BOS/FVG before detection. known_at is set only when the
    walk-forward replay (or an explicit producer field) provides it.
    """
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


def _status_snapshot(obj: dict[str, Any], *, at: int) -> dict[str, Any]:
    origin = obj.get("origin") or {}
    return {
        "at": int(at),
        "status": origin.get("status"),
        "touch_count": origin.get("touch_count"),
        "confidence": obj.get("confidence"),
        "price_low": obj.get("price_low"),
        "price_high": obj.get("price_high"),
    }


def _purge_expired_replay_cache(now_m: float) -> None:
    """Drop expired entries. Caller must hold ``_REPLAY_CACHE_LOCK``."""
    dead = [k for k, (exp, _) in _REPLAY_CACHE.items() if exp <= now_m]
    for k in dead:
        _REPLAY_CACHE.pop(k, None)


def _replay_cache_get(cache_key: tuple[Any, ...], now_m: float) -> dict[str, Any] | None:
    with _REPLAY_CACHE_LOCK:
        _purge_expired_replay_cache(now_m)
        hit = _REPLAY_CACHE.get(cache_key)
        if hit is None or hit[0] <= now_m:
            return None
        _REPLAY_CACHE.move_to_end(cache_key)
        cached = dict(hit[1])
        cached["cached"] = True
        return cached


def _replay_cache_put(
    cache_key: tuple[Any, ...], payload: dict[str, Any], now_m: float
) -> None:
    """CI-R9: purge expired, insert, trim LRU to ``_REPLAY_CACHE_MAX``."""
    with _REPLAY_CACHE_LOCK:
        _purge_expired_replay_cache(now_m)
        _REPLAY_CACHE[cache_key] = (now_m + _REPLAY_CACHE_TTL_S, dict(payload))
        _REPLAY_CACHE.move_to_end(cache_key)
        while len(_REPLAY_CACHE) > _REPLAY_CACHE_MAX:
            _REPLAY_CACHE.popitem(last=False)


def _collect_engine_objects(
    window: list[Candle],
    *,
    sym: str,
    timeframe: str,
    include_pytrendline: bool,
) -> list[dict[str, Any]]:
    params = StructureEngineParams(window_bars=min(len(window), 500))
    snap = detect_market_structure(window, params, include_pytrendline=include_pytrendline)
    objects: list[dict[str, Any]] = []
    objects.extend(o.to_dict() for o in structure_to_chart_objects(snap, sym, timeframe, window))
    objects.extend(
        o.to_dict() for o in breaks_to_chart_objects(window, sym, timeframe, snapshot=snap)
    )
    objects.extend(o.to_dict() for o in fvg_to_chart_objects(window, sym, timeframe))
    objects.extend(
        o.to_dict() for o in fibonacci_to_chart_objects(window, sym, timeframe, key_only=True)
    )
    return objects


def _build_analysis_and_state(
    window: list[Candle],
    objects: list[dict[str, Any]],
    *,
    ichi_params: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pipeline Option B verdict (same family as lib/verdict.ts) + market_state."""
    live = LiveScreenerSettings.production_defaults()
    rvol_params = live.rvol_params()
    atr_params = live.atr_params()

    rvol_out = rvol_agent.analyze(window, rvol_params)[-1]
    ichi_out = ichimoku_agent.analyze(window, ichi_params)[-1]
    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "cvd", "adx", "donchian"],
        window,
        params_by_id={"atr": atr_params},
    )
    pipeline = build_pipeline(
        ichimoku=ichi_out,
        rvol=rvol_out,
        structure=computed["structure"][-1] if computed["structure"] else None,
        atr=computed["atr"][-1] if computed["atr"] else None,
        location=computed["location"][-1] if computed["location"] else None,
        cvd=computed["cvd"][-1] if computed["cvd"] else None,
        adx=computed["adx"][-1] if computed["adx"] else None,
        donchian=computed["donchian"][-1] if computed["donchian"] else None,
    )

    atr_last = computed["atr"][-1] if computed["atr"] else None
    ichi_states = REGISTRY.compute("ichimoku", window, ichi_params)
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

    threshold = float(live.rvol_significant)
    waiting: list[str] = []
    if rvol_f < threshold:
        waiting.append(f"RVOL > {threshold:g}")

    stage_lines = [
        f"{s.id.value}: {s.status.value} — {s.summary}" for s in pipeline.stages
    ][:6]
    analysis = {
        "state": pipeline.decision,
        "confidence": float(ichi_out.confidence),
        "summary": "; ".join(stage_lines) if stage_lines else pipeline.decision,
        "confluence": stage_lines,
        "waiting": waiting,
        "producer": "engine",
        "kind": "pipeline",
        "strategy_version": pipeline.strategy_version,
    }
    return analysis, market_state


def _payload_from_candles(
    *,
    sym: str,
    timeframe: str,
    provider_id: str,
    provider_symbol: str,
    candles: list[Candle],
    limit: int,
    requested: list[str],
    include_pytrendline: bool,
    replay_first: int,
    replay_last: int,
    tf_sec: int,
    known_at_by_lineage: dict[str, int] | None = None,
    status_history_by_lineage: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if not candles:
        raise ValueError(f"no_candles:{sym}")

    definition = REGISTRY.get("ichimoku")
    ichi_params = definition.build_params({})
    window = candles[-int(limit) :] if len(candles) > int(limit) else candles
    effective_as_of = int(window[-1].time)

    objects: list[dict[str, Any]] = []
    if ChartObjectSource.ENGINE.value in requested:
        objects.extend(
            _collect_engine_objects(
                window, sym=sym, timeframe=timeframe, include_pytrendline=include_pytrendline
            )
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
            for o in stored:
                if int(o.as_of) <= effective_as_of:
                    objects.append(o.to_dict())
        finally:
            session.close()

    enriched: list[dict[str, Any]] = []
    for o in objects:
        lk = _lineage_key(o)
        ka = None
        if known_at_by_lineage is not None and lk in known_at_by_lineage:
            ka = known_at_by_lineage[lk]
        row = _enrich_object(o, known_at=ka)
        if status_history_by_lineage is not None and lk in status_history_by_lineage:
            origin = dict(row.get("origin") or {})
            origin["status_history"] = list(status_history_by_lineage[lk])
            row["origin"] = origin
        enriched.append(row)
    objects = enriched

    ichi_states = REGISTRY.compute("ichimoku", candles, ichi_params)
    window_start = int(window[0].time)
    ichimoku = [
        {"time": int(s.time), "tenkan": s.tenkan, "kijun": s.kijun}
        for s in ichi_states
        if int(s.time) >= window_start
    ]
    projection_raw = [
        p
        for p in compute_projected_kumo(candles, ichi_params)
        if int(p["time_projected"]) >= window_start
    ]
    # CI-R5: a projected kumo point at time t is known when (t - 25 bars) <= as_of.
    # When building at as_of=effective_as_of (candles already truncated), keep points
    # whose computation bar is in-range — filter by known bar explicitly for safety.
    bar_lag = 25 * tf_sec
    projection = [
        {
            "time": int(p["time_projected"]),
            "senkouA": p["senkou_a"],
            "senkouB": p["senkou_b"],
        }
        for p in projection_raw
        if p.get("senkou_a") is not None
        and p.get("senkou_b") is not None
        and int(p["time_projected"]) - bar_lag <= effective_as_of
    ]

    analysis, market_state = _build_analysis_and_state(window, objects, ichi_params=ichi_params)

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "provider": provider_id,
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
            "last": replay_last,
            "bar_seconds": tf_sec,
        },
        "mock": False,
    }


def build_chart_intelligence(
    *,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    as_of: int | None = None,
    sources: str | list[str] | None = "engine,user,claude",
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """Live (or as_of-truncated) Chart Intelligence snapshot."""
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

    candles = _closed_only(list(raw_candles), timeframe, now=now)
    if not candles:
        raise ValueError(f"no_candles:{sym}")

    replay_first = int(candles[0].time)
    replay_last = int(candles[-1].time)

    if as_of is not None:
        cut = int(as_of)
        candles = [c for c in candles if int(c.time) <= cut]
        if not candles:
            raise ValueError(f"no_candles_at_as_of:{sym}:{cut}")

    return _payload_from_candles(
        sym=sym,
        timeframe=timeframe,
        provider_id=provider.id,
        provider_symbol=provider_symbol,
        candles=candles,
        limit=limit,
        requested=requested,
        include_pytrendline=include_pytrendline,
        replay_first=replay_first,
        replay_last=replay_last if as_of is None else int(candles[-1].time),
        tf_sec=tf_sec,
    )


def build_chart_intelligence_replay(
    *,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    from_ts: int | None = None,
    to_ts: int | None = None,
    lookback_bars: int = _DEFAULT_REPLAY_LOOKBACK,
    sources: str | list[str] | None = "engine",
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """Walk-forward replay (CI-R1a).

    Recalculates objects bar-by-bar on candles ≤ T. Sets ``origin.known_at`` to
    the first bar where the object's ``lineage_key`` appears (CI-R8), plus
    ``status_history``. Candles / ichimoku / projection are sent once at pack
    root (CI-R7); frames keep only ``as_of``, ``objects``, ``market_state``.
    Cache: LRU 32, TTL 60 s, purge on write (CI-R9).
    """
    sym = symbol.upper()
    requested = parse_sources(sources)
    tf_sec = int(TF_SECONDS.get(timeframe, 3600))
    lookback = max(2, min(int(lookback_bars), 120))

    definition = REGISTRY.get("ichimoku")
    ichi_params = definition.build_params({})
    warmup = int(definition.warmup(ichi_params))
    fetch_limit = max(1, min(int(limit) + warmup + lookback, 5000))

    twelve_data.set_api_key_override(x_twelve_data_key)
    provider, provider_symbol, raw_candles = resolve_and_fetch(sym, timeframe, fetch_limit)
    if not raw_candles:
        raise ValueError(f"no_candles:{sym}")

    series = _closed_only(list(raw_candles), timeframe, now=now)
    if len(series) < 2:
        raise ValueError(f"no_candles:{sym}")

    end_t = int(to_ts) if to_ts is not None else int(series[-1].time)
    series = [c for c in series if int(c.time) <= end_t]
    if not series:
        raise ValueError(f"no_candles_at_as_of:{sym}:{end_t}")

    times = [int(c.time) for c in series]
    if from_ts is not None:
        start_t = int(from_ts)
    else:
        start_t = times[max(0, len(times) - lookback)]

    walk_times = [t for t in times if start_t <= t <= end_t]
    if not walk_times:
        walk_times = times[-lookback:]

    cache_key = (sym, timeframe, int(series[-1].time), start_t, end_t, lookback)
    now_m = time.monotonic()
    cached = _replay_cache_get(cache_key, now_m)
    if cached is not None:
        return cached

    known_at_by_lineage: dict[str, int] = {}
    status_history_by_lineage: dict[str, list[dict[str, Any]]] = {}
    frames: list[dict[str, Any]] = []

    for t in walk_times:
        truncated = [c for c in series if int(c.time) <= t]
        snap = _payload_from_candles(
            sym=sym,
            timeframe=timeframe,
            provider_id=provider.id,
            provider_symbol=provider_symbol,
            candles=truncated,
            limit=limit,
            requested=requested,
            include_pytrendline=include_pytrendline,
            replay_first=int(series[0].time),
            replay_last=int(series[-1].time),
            tf_sec=tf_sec,
        )
        for o in snap["objects"]:
            lk = _lineage_key(o)
            if not lk:
                continue
            if lk not in known_at_by_lineage:
                known_at_by_lineage[lk] = int(t)
            hist = status_history_by_lineage.setdefault(lk, [])
            snap_row = _status_snapshot(o, at=t)
            if not hist or any(
                hist[-1].get(k) != snap_row.get(k)
                for k in ("status", "touch_count", "confidence", "price_low", "price_high")
            ):
                hist.append(snap_row)
        frame_objects = []
        for o in snap["objects"]:
            lk = _lineage_key(o)
            frame_objects.append(
                _enrich_object(o, known_at=known_at_by_lineage.get(lk))
            )
        # CI-R7: slim frame — series sent once at pack root; front truncates by as_of.
        frames.append(
            {
                "as_of": int(t),
                "objects": frame_objects,
                "market_state": snap["market_state"],
            }
        )

    # Final enriched live-at-end payload (candles/ichi/proj once for the pack).
    final = _payload_from_candles(
        sym=sym,
        timeframe=timeframe,
        provider_id=provider.id,
        provider_symbol=provider_symbol,
        candles=series,
        limit=limit,
        requested=requested,
        include_pytrendline=include_pytrendline,
        replay_first=int(series[0].time),
        replay_last=int(series[-1].time),
        tf_sec=tf_sec,
        known_at_by_lineage=known_at_by_lineage,
        status_history_by_lineage=status_history_by_lineage,
    )
    payload = {
        **final,
        "from": int(walk_times[0]),
        "to": int(walk_times[-1]),
        "lookback_bars": lookback,
        "frames": frames,
        "cached": False,
        "replay_mode": "walk_forward",
    }
    _replay_cache_put(cache_key, payload, now_m)
    return payload
