"""Shared Volume Profile binning primitive (POC / VAH / VAL).

Single calculation path for ``indicators.location`` and Lab trade-VP compare.
Callers choose the price/volume samples and the ``[lo, hi]`` grid; this module
only bins and expands the value area — no HVN/LVN, no pipeline votes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class VolumeProfileBins:
    """Histogram + levels on a fixed ``[lo, hi]`` grid."""

    poc: float | None
    vah: float | None
    val: float | None
    volumes: tuple[float, ...]
    lo: float
    hi: float
    bin_width: float
    total_volume: float
    num_bins: int

    def bin_index(self, price: float) -> int:
        if self.bin_width <= 0 or self.num_bins < 1:
            return 0
        idx = int((price - self.lo) / self.bin_width)
        return min(max(idx, 0), self.num_bins - 1)


def empty_volume_profile_bins(
    *, lo: float = 0.0, hi: float = 0.0, num_bins: int = 0
) -> VolumeProfileBins:
    n = max(0, num_bins)
    return VolumeProfileBins(
        poc=None,
        vah=None,
        val=None,
        volumes=tuple(0.0 for _ in range(n)),
        lo=lo,
        hi=hi,
        bin_width=0.0,
        total_volume=0.0,
        num_bins=n,
    )


def compute_volume_profile_bins(
    pairs: Sequence[tuple[float, float]],
    *,
    lo: float,
    hi: float,
    num_bins: int,
    value_area_pct: float,
) -> VolumeProfileBins:
    """Bin ``(price, volume)`` samples onto ``[lo, hi]`` and compute POC/VAH/VAL.

    Same algorithm historically inlined in ``location._volume_profile``:
    POC at bin midpoints, value area expands from POC toward the heavier
    adjacent bin until ``value_area_pct`` of total volume is covered.
    """
    num_bins = max(1, int(num_bins))
    if hi <= lo:
        return empty_volume_profile_bins(lo=lo, hi=hi, num_bins=num_bins)

    bin_width = (hi - lo) / num_bins
    volumes = [0.0] * num_bins

    def bin_index(price: float) -> int:
        idx = int((price - lo) / bin_width)
        return min(max(idx, 0), num_bins - 1)

    for price, vol in pairs:
        if vol <= 0:
            continue
        volumes[bin_index(price)] += float(vol)

    total_volume = sum(volumes)
    if total_volume <= 0:
        return VolumeProfileBins(
            poc=None,
            vah=None,
            val=None,
            volumes=tuple(volumes),
            lo=lo,
            hi=hi,
            bin_width=bin_width,
            total_volume=0.0,
            num_bins=num_bins,
        )

    poc_idx = max(range(num_bins), key=lambda b: volumes[b])
    poc_price = lo + (poc_idx + 0.5) * bin_width

    lo_idx, hi_idx = poc_idx, poc_idx
    covered = volumes[poc_idx]
    target = value_area_pct * total_volume
    while covered < target and (lo_idx > 0 or hi_idx < num_bins - 1):
        left_vol = volumes[lo_idx - 1] if lo_idx > 0 else -1.0
        right_vol = volumes[hi_idx + 1] if hi_idx < num_bins - 1 else -1.0
        if right_vol >= left_vol:
            hi_idx += 1
            covered += volumes[hi_idx]
        else:
            lo_idx -= 1
            covered += volumes[lo_idx]

    return VolumeProfileBins(
        poc=poc_price,
        vah=lo + (hi_idx + 1) * bin_width,
        val=lo + lo_idx * bin_width,
        volumes=tuple(volumes),
        lo=lo,
        hi=hi,
        bin_width=bin_width,
        total_volume=total_volume,
        num_bins=num_bins,
    )
