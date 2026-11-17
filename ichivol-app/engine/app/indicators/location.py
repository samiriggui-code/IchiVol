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
from app.indicators.volume_profile_core import compute_volume_profile_bins


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

    # Shared binning primitive — grid = candle high/low extent (not typical-price span).
    bins = compute_volume_profile_bins(
        [(_typical_price(c), float(c.volume)) for c in window],
        lo=lo,
        hi=hi,
        num_bins=params.num_bins,
        value_area_pct=params.value_area_pct,
    )
    if bins.poc is None or bins.total_volume <= 0:
        return None, None, None, NodeType.UNKNOWN

    current_bin = bins.bin_index(_typical_price(candles[end]))
    avg_bin_volume = bins.total_volume / bins.num_bins
    current_bin_volume = bins.volumes[current_bin]
    if current_bin_volume >= params.hvn_ratio * avg_bin_volume:
        node_type = NodeType.HVN
    elif current_bin_volume <= params.lvn_ratio * avg_bin_volume:
        node_type = NodeType.LVN
    else:
        node_type = NodeType.NEUTRAL

    return bins.poc, bins.vah, bins.val, node_type


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
