"""T9f — observation-only Lab context snapshot for screener / watchlist.

Surfaces CHoCH / FVG / Fib / impulse flags from the last closed bar without
touching the decision pipeline, combiner confidence, or paper gates.

T11b — short TTL process cache (same last bar + params) to cut the ~49 %
overhead measured on 20-symbol cycles. Observation only; never imported by
pipeline/combiner.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Sequence

from app.indicators.fvg import FvgParams
from app.indicators.ichimoku import Candle
from app.indicators.impulse import ImpulseParams
from app.indicators.registry import REGISTRY
from app.indicators.structure import StructureParams
from app.strategy_lab.features import (
    _break_quality,
    _choch_bearish,
    _choch_bullish,
    _fib_kwargs_from_impulse,
    _fvg_bearish,
    _fvg_bullish,
    _impulse_bearish,
    _impulse_bullish,
    _impulse_disp,
)

_DISCLAIMER = (
    "Lab context observation (T9f) — does not alter decision or confidence."
)

# T11b — bar-stable cache (one observation per last closed bar + params).
_CACHE_TTL_SEC = 55.0
_cache: dict[tuple, tuple[float, "LabContextObservation"]] = {}
_cache_lock = threading.Lock()
_cache_hits = 0
_cache_misses = 0


@dataclass(frozen=True)
class LabContextObservation:
    choch_bullish: bool
    choch_bearish: bool
    break_quality: str | None
    impulse_bullish: bool
    impulse_bearish: bool
    impulse_displacement_atr: float | None
    fvg_bullish: bool
    fvg_bearish: bool
    fvg_active: bool
    fvg_active_bullish: bool
    fvg_active_bearish: bool
    fvg_status: str | None
    fib_confluence: bool
    fib_key_confluence: bool
    fib_impulse_up: bool
    fib_impulse_down: bool
    fib_anchor_impulse: bool
    fib_nearest_ratio: float | None
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "choch_bullish": self.choch_bullish,
            "choch_bearish": self.choch_bearish,
            "break_quality": self.break_quality,
            "impulse_bullish": self.impulse_bullish,
            "impulse_bearish": self.impulse_bearish,
            "impulse_displacement_atr": self.impulse_displacement_atr,
            "fvg_bullish": self.fvg_bullish,
            "fvg_bearish": self.fvg_bearish,
            "fvg_active": self.fvg_active,
            "fvg_active_bullish": self.fvg_active_bullish,
            "fvg_active_bearish": self.fvg_active_bearish,
            "fvg_status": self.fvg_status,
            "fib_confluence": self.fib_confluence,
            "fib_key_confluence": self.fib_key_confluence,
            "fib_impulse_up": self.fib_impulse_up,
            "fib_impulse_down": self.fib_impulse_down,
            "fib_anchor_impulse": self.fib_anchor_impulse,
            "fib_nearest_ratio": self.fib_nearest_ratio,
            "disclaimer": self.disclaimer,
        }


def clear_lab_context_cache() -> None:
    """Test / ops helper — drop all cached observations."""
    global _cache_hits, _cache_misses
    with _cache_lock:
        _cache.clear()
        _cache_hits = 0
        _cache_misses = 0


def lab_context_cache_stats() -> dict[str, int]:
    with _cache_lock:
        return {"hits": _cache_hits, "misses": _cache_misses, "size": len(_cache)}


def _cache_key(
    candles: Sequence[Candle],
    structure_params: StructureParams,
    impulse_params: ImpulseParams,
    fvg_params: FvgParams,
) -> tuple:
    last = candles[-1]
    return (
        int(last.time),
        len(candles),
        float(last.close),
        repr(structure_params),
        repr(impulse_params),
        repr(fvg_params),
    )


def observe_lab_context(
    candles: Sequence[Candle],
    *,
    structure_params: StructureParams = StructureParams(),
    impulse_params: ImpulseParams = ImpulseParams(),
    fvg_params: FvgParams = FvgParams(),
) -> LabContextObservation | None:
    """Last-bar Lab snapshot. Returns None on empty series."""
    global _cache_hits, _cache_misses
    if not candles:
        return None
    key = _cache_key(candles, structure_params, impulse_params, fvg_params)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[0] < _CACHE_TTL_SEC:
            _cache_hits += 1
            return hit[1]
        _cache_misses += 1

    computed = REGISTRY.compute_many(
        ["structure", "impulse", "fvg"],
        candles,
        params_by_id={
            "structure": structure_params,
            "impulse": impulse_params,
            "fvg": fvg_params,
        },
    )
    i = len(candles) - 1
    structure = computed["structure"][i]
    impulse = computed["impulse"][i]
    fvg = computed["fvg"][i]
    fib = _fib_kwargs_from_impulse(impulse, candles, i)
    active = fvg.active
    obs = LabContextObservation(
        choch_bullish=_choch_bullish(structure),
        choch_bearish=_choch_bearish(structure),
        break_quality=_break_quality(structure),
        impulse_bullish=_impulse_bullish(impulse),
        impulse_bearish=_impulse_bearish(impulse),
        impulse_displacement_atr=_impulse_disp(impulse),
        fvg_bullish=_fvg_bullish(fvg),
        fvg_bearish=_fvg_bearish(fvg),
        fvg_active=len(active) > 0,
        fvg_active_bullish=any(ev.direction == "bullish" for ev in active),
        fvg_active_bearish=any(ev.direction == "bearish" for ev in active),
        fvg_status=fvg.event.status if fvg.event is not None else None,
        fib_confluence=bool(fib["fib_confluence"]),
        fib_key_confluence=bool(fib["fib_key_confluence"]),
        fib_impulse_up=bool(fib["fib_impulse_up"]),
        fib_impulse_down=bool(fib["fib_impulse_down"]),
        fib_anchor_impulse=bool(fib["fib_anchor_impulse"]),
        fib_nearest_ratio=fib["fib_nearest_ratio"],
    )
    with _cache_lock:
        _cache[key] = (time.monotonic(), obs)
    return obs


def lab_context_observation_dict(
    obs: LabContextObservation | None,
) -> dict | None:
    if obs is None:
        return None
    return obs.to_dict()
