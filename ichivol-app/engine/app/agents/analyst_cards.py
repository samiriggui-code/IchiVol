"""AG-S1 — fiches analystes déterministes (observe-only).

Une fiche par indicateur lu par Chart Intelligence. Aucun appel LLM.
``used_by_decision=False`` partout — n'affecte ni pipeline, ni paper, ni gates.
Ne jamais importer ``app.paper`` ni appeler ``/screener`` (sync paper, bug #161).

Règle T1e : indicateurs via ``REGISTRY`` / ``ichimoku_agent`` / ``rvol_agent``.
OI/funding reste hors REGISTRY (flux futures) — fetch Binance Futures direct.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.fibonacci.context import compute_fib_context
from app.indicators.ichimoku import Candle
from app.indicators.oi_funding import OiFundingState, compute_oi_funding
from app.indicators.registry import REGISTRY, FeatureStatus
from app.market_data import binance_futures, twelve_data
from app.market_data.quality import closed_candles
from app.market_data.resolve import resolve_and_fetch
from app.market_data.timeframes import TF_SECONDS
from app.strategy_lab.adn_ichivol import LiveScreenerSettings

logger = logging.getLogger(__name__)

ENGINE_VERSION = "ag-s1-v1"

# Univers fixe pour les snapshots de session (AG-S1).
SNAPSHOT_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SNAPSHOT_TIMEFRAMES: tuple[str, ...] = ("1h", "4h")

# RS-01 — usage paper réel (rôle documentaire). Les fiches restent observe-only.
# Valeurs : F / W / D / I / S / T / A / L / aucun (+ combinaisons documentées).
DECISION_ROLE_BY_FEATURE: dict[str, str] = {
    "ichimoku": "D+S",
    "rvol": "F",
    "atr": "F+T+S",
    "adx": "F",
    "donchian": "F",
    "structure": "I",
    "fvg": "aucun",
    "impulse": "aucun",
    "location": "F",
    "oi_funding": "aucun",
    "cvd": "aucun",
    "liquidity": "aucun",
    "confluence": "aucun",
}

# Ordre d'émission des fiches (Chart Intelligence + RS-01).
CARD_FEATURES: tuple[str, ...] = (
    "ichimoku",
    "rvol",
    "atr",
    "adx",
    "donchian",
    "structure",
    "fvg",
    "impulse",
    "location",
    "oi_funding",
    "cvd",
)


def _enum_val(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    return v


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Enum):
        return v.value
    if is_dataclass(v) and not isinstance(v, type):
        return {k: _jsonable(x) for k, x in asdict(v).items()}
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return str(v)


def _feature_status(feature_id: str) -> str:
    if feature_id == "oi_funding":
        return "HORS_REGISTRE"
    try:
        return REGISTRY.get(feature_id).status.value
    except KeyError:
        return FeatureStatus.CANDIDATE.value


def _decision_role(feature_id: str) -> str:
    return DECISION_ROLE_BY_FEATURE.get(feature_id, "aucun")


def _card(
    *,
    feature: str,
    symbol: str,
    timeframe: str,
    as_of: int,
    value: Any,
    state: str,
    known_at: int | None,
    text: str,
) -> dict[str, Any]:
    role = _decision_role(feature)
    return {
        "feature": feature,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "as_of": as_of,
        "value": _jsonable(value),
        "state": state,
        "known_at": known_at if known_at is not None else as_of,
        "feature_status": _feature_status(feature),
        "decision_role": role,
        "used_by_decision": False,
        "validation_status": "NON_VALIDE",
        "text": text,
        "engine_version": ENGINE_VERSION,
    }


def _closed_window(
    candles: Sequence[Candle], timeframe: str, *, now: int | None = None
) -> list[Candle]:
    tf = TF_SECONDS.get(timeframe)
    if tf is None:
        return list(candles)
    closed = closed_candles(
        candles, int(tf), int(time.time()) if now is None else int(now)
    )
    return closed if len(closed) >= 2 else list(candles)


def _truncate_at(candles: Sequence[Candle], as_of: int) -> list[Candle]:
    return [c for c in candles if int(c.time) <= int(as_of)]


def _ichimoku_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    out = ichimoku_agent.analyze(candles)[-1]
    meta = out.metadata
    direction = out.direction.value
    score = meta.get("score")
    pvk = meta.get("price_vs_kumo", "UNKNOWN")
    text = (
        f"Ichimoku {direction} · prix vs nuage {pvk}"
        + (f" · score {score}" if score is not None else "")
    )
    return _card(
        feature="ichimoku",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "direction": direction,
            "score": score,
            "price_vs_kumo": pvk,
            "tk_cross": meta.get("tk_cross"),
            "confidence": out.confidence,
        },
        state=direction,
        known_at=int(meta.get("time") or as_of),
        text=text,
    )


def _rvol_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    live = LiveScreenerSettings.production_defaults()
    out = rvol_agent.analyze(candles, live.rvol_params())[-1]
    meta = out.metadata
    level = str(meta.get("anomaly_level") or "UNKNOWN")
    rvol = meta.get("rvol")
    text = f"RVOL {rvol if rvol is not None else '—'} · niveau {level}"
    return _card(
        feature="rvol",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "rvol": rvol,
            "anomaly_level": level,
            "percentile": meta.get("percentile"),
            "confidence": out.confidence,
        },
        state=level,
        known_at=int(meta.get("time") or as_of),
        text=text,
    )


def _atr_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    live = LiveScreenerSettings.production_defaults()
    states = REGISTRY.compute("atr", candles, live.atr_params())
    st = states[-1]
    regime = _enum_val(st.regime)
    atr = st.atr
    text = f"ATR {atr if atr is not None else '—'} · régime {regime}"
    return _card(
        feature="atr",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "atr": atr,
            "regime": regime,
            "percentile": st.percentile,
            "suggested_stop_distance": st.suggested_stop_distance,
        },
        state=str(regime),
        known_at=int(st.time),
        text=text,
    )


def _adx_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("adx", candles)
    st = states[-1]
    strength = _enum_val(st.strength)
    text = f"ADX {st.adx if st.adx is not None else '—'} · {strength}"
    return _card(
        feature="adx",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "adx": st.adx,
            "plus_di": st.plus_di,
            "minus_di": st.minus_di,
            "strength": strength,
        },
        state=str(strength),
        known_at=int(st.time),
        text=text,
    )


def _donchian_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("donchian", candles)
    st = states[-1]
    br = _enum_val(st.breakout)
    text = f"Donchian 20 · breakout {br}"
    return _card(
        feature="donchian",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={"upper": st.upper, "lower": st.lower, "breakout": br},
        state=str(br),
        known_at=int(st.time),
        text=text,
    )


def _structure_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("structure", candles)
    st = states[-1]
    bias = _enum_val(st.bias)
    bos = _enum_val(st.bos)
    ev = st.event
    ev_type = _enum_val(ev.type) if ev is not None else None
    text = f"Structure biais {bias} · BOS {bos}"
    if ev_type:
        text += f" · événement {ev_type}"
    return _card(
        feature="structure",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "bias": bias,
            "bos": bos,
            "last_swing_high": st.last_swing_high,
            "last_swing_low": st.last_swing_low,
            "event_type": ev_type,
            "break_quality": _enum_val(ev.break_quality) if ev is not None else None,
        },
        state=str(bias),
        known_at=int(st.time),
        text=text,
    )


def _fvg_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("fvg", candles)
    st = states[-1]
    n_active = len(st.active)
    ev = st.event
    if ev is not None:
        state = f"new_{ev.direction}"
        text = f"FVG {ev.direction} découvert · actifs {n_active}"
    elif n_active:
        state = "active"
        text = f"FVG actifs {n_active} · aucun nouveau"
    else:
        state = "none"
        text = "Aucun FVG actif"
    return _card(
        feature="fvg",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "active_count": n_active,
            "new_event": _jsonable(ev) if ev is not None else None,
        },
        state=state,
        known_at=int(st.time),
        text=text,
    )


def _impulse_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("impulse", candles)
    st = states[-1]
    active = st.active
    fib = compute_fib_context(candles, anchor="auto")
    if active is not None:
        state = active.direction
        text = (
            f"Impulsion {active.direction} · disp {active.displacement_atr:.2f}×ATR"
        )
    else:
        state = "none"
        text = "Aucune impulsion active"
    if fib is not None and fib.nearest_ratio is not None:
        text += f" · Fib {fib.nearest_ratio:g} ({fib.anchor_source})"
    return _card(
        feature="impulse",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "impulse": _jsonable(active) if active is not None else None,
            "fibonacci": fib.to_payload() if fib is not None else None,
        },
        state=state,
        known_at=int(st.time),
        text=text,
    )


def _location_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    computed = REGISTRY.compute_many(["structure", "location"], candles)
    st = computed["location"][-1]
    node = _enum_val(st.node_type)
    text = f"Location {node} · POC {st.poc if st.poc is not None else '—'}"
    return _card(
        feature="location",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "node_type": node,
            "poc": st.poc,
            "vah": st.vah,
            "val": st.val,
            "vwap": st.vwap,
            "avwap": st.avwap,
        },
        state=str(node),
        known_at=int(st.time),
        text=text,
    )


def _cvd_card(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> dict[str, Any]:
    states = REGISTRY.compute("cvd", candles)
    st = states[-1]
    bias = _enum_val(st.bias)
    text = f"CVD {bias}"
    return _card(
        feature="cvd",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "bias": bias,
            "delta": st.delta,
            "rolling_delta": st.rolling_delta,
            "cumulative": st.cumulative,
        },
        state=str(bias),
        known_at=int(st.time),
        text=text,
    )


def _oi_funding_for_candles(
    candles: list[Candle],
    *,
    provider_id: str,
    provider_symbol: str,
    timeframe: str,
) -> OiFundingState | None:
    if provider_id != "binance" or timeframe not in {"15m", "1h", "4h", "1d"}:
        return None
    try:
        oi_points = binance_futures.fetch_open_interest_hist(
            provider_symbol, timeframe, limit=500
        )
        funding_points = binance_futures.fetch_funding_rate_hist(
            provider_symbol, limit=200
        )
        if not oi_points and not funding_points:
            return None
        series = compute_oi_funding(candles, oi_points, funding_points)
        return series[-1] if series else None
    except Exception:
        logger.warning(
            "analyst_cards: OI/funding fetch failed for %s %s",
            provider_symbol,
            timeframe,
            exc_info=True,
        )
        return None


def _oi_funding_card(
    candles: list[Candle],
    *,
    symbol: str,
    timeframe: str,
    as_of: int,
    provider_id: str | None,
    provider_symbol: str | None,
) -> dict[str, Any]:
    st: OiFundingState | None = None
    if provider_id and provider_symbol:
        st = _oi_funding_for_candles(
            candles,
            provider_id=provider_id,
            provider_symbol=provider_symbol,
            timeframe=timeframe,
        )
    if st is None:
        return _card(
            feature="oi_funding",
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of,
            value=None,
            state="UNKNOWN",
            known_at=as_of,
            text="OI/funding indisponible",
        )
    oi_trend = _enum_val(st.oi_trend)
    funding_bias = _enum_val(st.funding_bias)
    text = f"OI {oi_trend} · funding {funding_bias}"
    return _card(
        feature="oi_funding",
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        value={
            "open_interest": st.open_interest,
            "oi_trend": oi_trend,
            "funding_rate": st.funding_rate,
            "funding_bias": funding_bias,
        },
        state=str(oi_trend),
        known_at=int(st.time),
        text=text,
    )


def _optional_liq_conf_cards(
    candles: list[Candle], *, symbol: str, timeframe: str, as_of: int
) -> list[dict[str, Any]]:
    """Liquidity / Confluence seulement si CI-LIQ-CONF est présent dans le REGISTRY."""
    out: list[dict[str, Any]] = []
    for feature in ("liquidity", "confluence"):
        try:
            REGISTRY.get(feature)
        except KeyError:
            continue
        states = REGISTRY.compute(feature, candles)
        if not states:
            continue
        st = states[-1]
        state = str(_enum_val(getattr(st, "status", None) or getattr(st, "state", "ok")))
        text = f"{feature} · {state}"
        out.append(
            _card(
                feature=feature,
                symbol=symbol,
                timeframe=timeframe,
                as_of=as_of,
                value=_jsonable(st),
                state=state,
                known_at=int(getattr(st, "time", as_of)),
                text=text,
            )
        )
    return out


def build_analyst_cards_from_candles(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    as_of: int | None = None,
    provider_id: str | None = None,
    provider_symbol: str | None = None,
    now: int | None = None,
) -> list[dict[str, Any]]:
    """Construit les fiches à partir d'une série OHLCV (anti-lookahead si as_of)."""
    window = _closed_window(list(candles), timeframe, now=now)
    if not window:
        return []
    cut = int(as_of) if as_of is not None else int(window[-1].time)
    window = _truncate_at(window, cut)
    if not window:
        return []
    as_of_bar = int(window[-1].time)
    sym = symbol.upper()

    cards = [
        _ichimoku_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _rvol_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _atr_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _adx_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _donchian_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _structure_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _fvg_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _impulse_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _location_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
        _oi_funding_card(
            window,
            symbol=sym,
            timeframe=timeframe,
            as_of=as_of_bar,
            provider_id=provider_id,
            provider_symbol=provider_symbol,
        ),
        _cvd_card(window, symbol=sym, timeframe=timeframe, as_of=as_of_bar),
    ]
    cards.extend(
        _optional_liq_conf_cards(
            window, symbol=sym, timeframe=timeframe, as_of=as_of_bar
        )
    )
    return cards


def build_analyst_cards(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 500,
    as_of: int | None = None,
    now: int | None = None,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """Fetch OHLCV (sans screener) + fiches. Observe-only."""
    twelve_data.set_api_key_override(x_twelve_data_key)
    provider, provider_symbol, candles = resolve_and_fetch(
        symbol.upper(), timeframe, min(limit, 1000)
    )
    cards = build_analyst_cards_from_candles(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        as_of=as_of,
        provider_id=provider.id,
        provider_symbol=provider_symbol,
        now=now,
    )
    as_of_bar = cards[0]["as_of"] if cards else as_of
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "as_of": as_of_bar,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "engine_version": ENGINE_VERSION,
        "used_by_decision": False,
        "observe_only": True,
        "cards": cards,
        "count": len(cards),
    }
