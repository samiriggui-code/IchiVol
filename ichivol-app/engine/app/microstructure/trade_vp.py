"""Trade-tape Volume Profile — research candidate (Binance micro).

POC / VAH / VAL from aggressor trades vs OHLCV typical-price approx.
Does **not** replace ``indicators.location`` VP and never votes in the
live pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.microstructure.trade_cvd import AggressorTrade


@dataclass(frozen=True)
class TradeVpParams:
    num_bins: int = 24
    value_area_pct: float = 0.70


@dataclass(frozen=True)
class VolumeProfileLevels:
    poc: float | None
    vah: float | None
    val: float | None
    total_volume: float
    n_samples: int

    def to_dict(self) -> dict:
        return {
            "poc": self.poc,
            "vah": self.vah,
            "val": self.val,
            "total_volume": self.total_volume,
            "n_samples": self.n_samples,
        }


def _profile_from_pairs(
    pairs: Sequence[tuple[float, float]],
    params: TradeVpParams,
) -> VolumeProfileLevels:
    """``pairs`` = (price, volume) samples."""
    if len(pairs) < 2:
        return VolumeProfileLevels(None, None, None, 0.0, len(pairs))
    prices = [p for p, v in pairs if v > 0]
    if len(prices) < 2:
        return VolumeProfileLevels(None, None, None, 0.0, len(pairs))
    lo = min(prices)
    hi = max(prices)
    if hi <= lo:
        return VolumeProfileLevels(None, None, None, 0.0, len(pairs))
    num_bins = max(1, params.num_bins)
    bin_width = (hi - lo) / num_bins
    volumes = [0.0] * num_bins

    def bin_index(price: float) -> int:
        idx = int((price - lo) / bin_width)
        return min(max(idx, 0), num_bins - 1)

    for price, vol in pairs:
        if vol <= 0:
            continue
        volumes[bin_index(price)] += vol

    total = sum(volumes)
    if total <= 0:
        return VolumeProfileLevels(None, None, None, 0.0, len(pairs))

    poc_idx = max(range(num_bins), key=lambda b: volumes[b])
    poc = lo + (poc_idx + 0.5) * bin_width
    lo_idx, hi_idx = poc_idx, poc_idx
    covered = volumes[poc_idx]
    target = params.value_area_pct * total
    while covered < target and (lo_idx > 0 or hi_idx < num_bins - 1):
        left = volumes[lo_idx - 1] if lo_idx > 0 else -1.0
        right = volumes[hi_idx + 1] if hi_idx < num_bins - 1 else -1.0
        if right >= left:
            hi_idx += 1
            covered += volumes[hi_idx]
        else:
            lo_idx -= 1
            covered += volumes[lo_idx]
    return VolumeProfileLevels(
        poc=poc,
        vah=lo + (hi_idx + 1) * bin_width,
        val=lo + lo_idx * bin_width,
        total_volume=total,
        n_samples=len(pairs),
    )


def compute_trade_volume_profile(
    trades: Sequence[AggressorTrade],
    params: TradeVpParams = TradeVpParams(),
) -> VolumeProfileLevels:
    pairs = [(t.price, float(t.size)) for t in trades]
    return _profile_from_pairs(pairs, params)


def compute_kline_volume_profile(
    candles: Sequence[Candle],
    params: TradeVpParams = TradeVpParams(),
) -> VolumeProfileLevels:
    """OHLCV approx — typical price × bar volume (same idea as location VP)."""
    pairs = [
        ((c.high + c.low + c.close) / 3.0, float(c.volume)) for c in candles
    ]
    return _profile_from_pairs(pairs, params)


@dataclass(frozen=True)
class VpCompareReport:
    symbol: str
    timeframe: str
    n_bars: int
    n_trades: int
    kline: VolumeProfileLevels
    trade: VolumeProfileLevels
    poc_abs_diff: float | None
    vah_abs_diff: float | None
    val_abs_diff: float | None
    disclaimer: str = (
        "Trade VP vs kline VP compare — research only; does not alter "
        "decision, confidence, fills, or gates."
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "n_trades": self.n_trades,
            "kline": self.kline.to_dict(),
            "trade": self.trade.to_dict(),
            "poc_abs_diff": self.poc_abs_diff,
            "vah_abs_diff": self.vah_abs_diff,
            "val_abs_diff": self.val_abs_diff,
            "disclaimer": self.disclaimer,
        }


def _abs_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs(float(a) - float(b))


def compare_kline_vs_trade_vp(
    candles: Sequence[Candle],
    trades: Sequence[AggressorTrade],
    *,
    symbol: str,
    timeframe: str,
    params: TradeVpParams = TradeVpParams(),
) -> VpCompareReport:
    kline = compute_kline_volume_profile(candles, params)
    trade = compute_trade_volume_profile(trades, params)
    return VpCompareReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        n_trades=len(trades),
        kline=kline,
        trade=trade,
        poc_abs_diff=_abs_diff(kline.poc, trade.poc),
        vah_abs_diff=_abs_diff(kline.vah, trade.vah),
        val_abs_diff=_abs_diff(kline.val, trade.val),
    )
