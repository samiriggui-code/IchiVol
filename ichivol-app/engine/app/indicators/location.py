"""Location: "is this a good place to act, not just the right direction?"
(docs/TRADING_ARCHITECTURE_V2.md ETAGE 4, docs/METHODS-ROADMAP.md V1.5).

Volume Profile (POC/VAH/VAL/HVN/LVN) is approximated from OHLCV -- no tick
data yet, matches METHODS-ROADMAP.md §2's own "OHLCV approx -> trades fin"
note for this method. Each bar's volume is assigned to a single histogram
bin at its typical price ((high+low+close)/3), not split across the bar's
full range -- a documented simplification, not an attempt at tick-accurate
profiling.

VWAP is a rolling window (crypto has no clean session boundary). Anchored
VWAP resets every time app/indicators/structure.py confirms a break of
structure (`bos` != NONE/UNKNOWN) -- a causal, already-available anchor,
instead of inventing a second swing-detector here.

Location never votes LONG/SHORT (TRADING_ARCHITECTURE_V2.md §7 rule 3):
this module only computes the raw numbers. app/decision/pipeline.py's
`_location_stage` is what interprets them against a direction Ichimoku
already decided.

Anti-lookahead by construction, same convention as every other indicator
here: everything at index i depends only on candles[0..i] and
structure_states[0..i]. See tests/indicators/test_location_lookahead.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.structure import BosEvent, StructureState


class NodeType(str, Enum):
    HVN = "HVN"
    LVN = "LVN"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VolumeProfileParams:
    lookback: int = 100
    num_bins: int = 24
    value_area_pct: float = 0.70
    hvn_ratio: float = 1.5
    """Current bar's bin volume >= hvn_ratio * average bin volume -> HVN."""
    lvn_ratio: float = 0.5
    """Current bar's bin volume <= lvn_ratio * average bin volume -> LVN."""


@dataclass(frozen=True)
class LocationParams:
    volume_profile: VolumeProfileParams = VolumeProfileParams()
    vwap_window: int = 20


@dataclass(frozen=True)
class LocationState:
    time: int
    price: float
    poc: float | None
    vah: float | None
    val: float | None
    node_type: NodeType
    vwap: float | None
    avwap: float | None
    avwap_anchor_time: int | None


def _typical_price(c: Candle) -> float:
    return (c.high + c.low + c.close) / 3.0


def _rolling_vwap(candles: Sequence[Candle], end: int, window: int) -> float | None:
    start = max(0, end - window + 1)
    pv = 0.0
    vol = 0.0
    for c in candles[start : end + 1]:
        pv += _typical_price(c) * c.volume
        vol += c.volume
    return pv / vol if vol > 0 else None


def _volume_profile(
    candles: Sequence[Candle], end: int, params: VolumeProfileParams
) -> tuple[float | None, float | None, float | None, NodeType]:
    start = max(0, end - params.lookback + 1)
    window = candles[start : end + 1]
    if len(window) < 2:
        return None, None, None, NodeType.UNKNOWN

    lo = min(c.low for c in window)
    hi = max(c.high for c in window)
    if hi <= lo:
        return None, None, None, NodeType.UNKNOWN

    num_bins = max(1, params.num_bins)
    bin_width = (hi - lo) / num_bins
    volumes = [0.0] * num_bins

    def bin_index(price: float) -> int:
        idx = int((price - lo) / bin_width)
        return min(max(idx, 0), num_bins - 1)

    for c in window:
        volumes[bin_index(_typical_price(c))] += c.volume

    total_volume = sum(volumes)
    if total_volume <= 0:
        return None, None, None, NodeType.UNKNOWN

    poc_idx = max(range(num_bins), key=lambda b: volumes[b])
    poc_price = lo + (poc_idx + 0.5) * bin_width

    # Standard Value Area algorithm: start at POC, expand to whichever
    # adjacent bin (above or below the current range) carries more volume,
    # until value_area_pct of total volume is covered.
    lo_idx, hi_idx = poc_idx, poc_idx
    covered = volumes[poc_idx]
    target = params.value_area_pct * total_volume
    while covered < target and (lo_idx > 0 or hi_idx < num_bins - 1):
        left_vol = volumes[lo_idx - 1] if lo_idx > 0 else -1.0
        right_vol = volumes[hi_idx + 1] if hi_idx < num_bins - 1 else -1.0
        if right_vol >= left_vol:
            hi_idx += 1
            covered += volumes[hi_idx]
        else:
            lo_idx -= 1
            covered += volumes[lo_idx]

    val_price = lo + lo_idx * bin_width
    vah_price = lo + (hi_idx + 1) * bin_width

    current_bin = bin_index(_typical_price(candles[end]))
    avg_bin_volume = total_volume / num_bins
    current_bin_volume = volumes[current_bin]
    if current_bin_volume >= params.hvn_ratio * avg_bin_volume:
        node_type = NodeType.HVN
    elif current_bin_volume <= params.lvn_ratio * avg_bin_volume:
        node_type = NodeType.LVN
    else:
        node_type = NodeType.NEUTRAL

    return poc_price, vah_price, val_price, node_type


def compute_location(
    candles: Sequence[Candle],
    structure_states: Sequence[StructureState],
    params: LocationParams = LocationParams(),
) -> list[LocationState]:
    if len(candles) != len(structure_states):
        raise ValueError("candles and structure_states must be the same length")

    out: list[LocationState] = []
    anchor_time: int | None = None
    anchor_pv = 0.0
    anchor_vol = 0.0

    for i, (candle, structure) in enumerate(zip(candles, structure_states)):
        if structure.bos in (BosEvent.BULLISH, BosEvent.BEARISH):
            anchor_time = structure.time
            anchor_pv = 0.0
            anchor_vol = 0.0

        anchor_pv += _typical_price(candle) * candle.volume
        anchor_vol += candle.volume
        avwap = anchor_pv / anchor_vol if anchor_time is not None and anchor_vol > 0 else None

        vwap = _rolling_vwap(candles, i, params.vwap_window)
        poc, vah, val, node_type = _volume_profile(candles, i, params.volume_profile)

        out.append(
            LocationState(
                time=candle.time,
                price=candle.close,
                poc=poc,
                vah=vah,
                val=val,
                node_type=node_type,
                vwap=vwap,
                avwap=avwap,
                avwap_anchor_time=anchor_time,
            )
        )

    return out
