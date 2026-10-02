from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.location import (
    LocationParams,
    NodeType,
    VolumeProfileParams,
    compute_location,
)
from app.indicators.structure import BosEvent, StructureBias, StructureState


def _flat_structure(n: int, bos_at: dict[int, BosEvent] | None = None) -> list[StructureState]:
    bos_at = bos_at or {}
    return [
        StructureState(
            time=i,
            last_swing_high=None,
            last_swing_low=None,
            bias=StructureBias.UNKNOWN,
            bos=bos_at.get(i, BosEvent.NONE),
        )
        for i in range(n)
    ]


def _candle(time: int, price: float, volume: float = 1.0) -> Candle:
    return Candle(time=time, open=price, high=price + 1, low=price - 1, close=price, volume=volume)


def test_poc_lands_in_the_price_band_with_the_most_volume():
    # Heavy volume clustered around price 100; light volume scattered
    # elsewhere -- POC should land in the heavy cluster.
    candles = [_candle(i, 100.0, volume=50.0) for i in range(20)]
    candles += [_candle(20 + i, 150.0, volume=1.0) for i in range(20)]
    structure = _flat_structure(len(candles))

    states = compute_location(candles, structure, LocationParams(volume_profile=VolumeProfileParams(lookback=40)))
    last = states[-1]

    assert last.poc is not None
    assert 95.0 <= last.poc <= 105.0
    assert last.vah is not None and last.val is not None
    assert last.val <= last.poc <= last.vah
    # Golden lock: shared binning extract must not change location VP numbers.
    assert last.poc == 100.08333333333333
    assert last.vah == 101.16666666666667
    assert last.val == 99.0


def test_current_bar_in_the_dominant_cluster_is_a_high_volume_node():
    candles = [_candle(i, 100.0, volume=50.0) for i in range(20)]
    structure = _flat_structure(len(candles))
    states = compute_location(candles, structure, LocationParams(volume_profile=VolumeProfileParams(lookback=20, num_bins=10)))
    assert states[-1].node_type == NodeType.HVN


def test_current_bar_in_a_thin_untraded_region_is_a_low_volume_node():
    # Most volume at 100; current (last) bar sits alone at a distant price
    # with tiny volume -- clearly the least-traded bin.
    candles = [_candle(i, 100.0, volume=50.0) for i in range(20)]
    candles.append(_candle(20, 200.0, volume=0.01))
    structure = _flat_structure(len(candles))
    states = compute_location(candles, structure, LocationParams(volume_profile=VolumeProfileParams(lookback=21, num_bins=20)))
    assert states[-1].node_type == NodeType.LVN


def test_rolling_vwap_of_uniform_volume_equals_average_typical_price():
    candles = [_candle(i, 100.0 + i, volume=10.0) for i in range(10)]
    structure = _flat_structure(len(candles))
    states = compute_location(candles, structure, LocationParams(vwap_window=10))
    # Uniform volume -> VWAP is the plain average of typical prices, which
    # for these flat candles (high=price+1, low=price-1) equals `price`.
    expected = sum(c.close for c in candles) / len(candles)
    assert states[-1].vwap is not None
    assert abs(states[-1].vwap - expected) < 1e-9


def test_anchored_vwap_is_none_before_any_confirmed_break_of_structure():
    candles = [_candle(i, 100.0, volume=10.0) for i in range(10)]
    structure = _flat_structure(len(candles))  # all BosEvent.NONE
    states = compute_location(candles, structure)
    assert all(s.avwap is None for s in states)
    assert all(s.avwap_anchor_time is None for s in states)


def test_anchored_vwap_resets_and_accumulates_causally_from_the_break():
    candles = [_candle(i, 100.0, volume=10.0) for i in range(10)]
    structure = _flat_structure(len(candles), bos_at={5: BosEvent.BULLISH})
    states = compute_location(candles, structure)

    assert states[4].avwap is None
    assert states[4].avwap_anchor_time is None
    for i in range(5, 10):
        assert states[i].avwap_anchor_time == 5
        # Uniform price/volume after the anchor -> AVWAP stays at the flat price.
        assert states[i].avwap is not None
        assert abs(states[i].avwap - 100.0) < 1e-9


def test_rejects_mismatched_lengths():
    import pytest

    candles = [_candle(0, 100.0)]
    with pytest.raises(ValueError):
        compute_location(candles, [])
