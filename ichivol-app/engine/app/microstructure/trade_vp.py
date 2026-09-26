"""Trade-tape Volume Profile — research candidate (Binance micro).

POC / VAH / VAL from aggressor trades vs OHLCV typical-price approx.
Uses the same binning primitive as ``indicators.location`` (T1 single path).
Does **not** replace location VP and never votes in the live pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.indicators.volume_profile_core import compute_volume_profile_bins
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


def _levels_from_pairs(
    pairs: Sequence[tuple[float, float]],
    *,
    lo: float,
    hi: float,
    params: TradeVpParams,
) -> VolumeProfileLevels:
    """``pairs`` = (price, volume) on a caller-fixed ``[lo, hi]`` grid."""
    n = len(pairs)
    if n < 2 or hi <= lo:
        return VolumeProfileLevels(None, None, None, 0.0, n)
    bins = compute_volume_profile_bins(
        pairs,
        lo=lo,
        hi=hi,
        num_bins=params.num_bins,
        value_area_pct=params.value_area_pct,
    )
    return VolumeProfileLevels(
        poc=bins.poc,
        vah=bins.vah,
        val=bins.val,
        total_volume=bins.total_volume,
        n_samples=n,
    )


def candle_price_range(candles: Sequence[Candle]) -> tuple[float, float] | None:
    """High/low extent of the candle window — natural common grid for compares."""
    if not candles:
        return None
    lo = min(c.low for c in candles)
    hi = max(c.high for c in candles)
    if hi <= lo:
        return None
    return lo, hi


def compute_trade_volume_profile(
    trades: Sequence[AggressorTrade],
    params: TradeVpParams = TradeVpParams(),
    *,
    price_lo: float | None = None,
    price_hi: float | None = None,
) -> VolumeProfileLevels:
    pairs = [(float(t.price), float(t.size)) for t in trades]
    if price_lo is None or price_hi is None:
        priced = [p for p, v in pairs if v > 0]
        if len(priced) < 2:
            return VolumeProfileLevels(None, None, None, 0.0, len(pairs))
        price_lo = min(priced)
        price_hi = max(priced)
    return _levels_from_pairs(pairs, lo=float(price_lo), hi=float(price_hi), params=params)


def compute_kline_volume_profile(
    candles: Sequence[Candle],
    params: TradeVpParams = TradeVpParams(),
    *,
    price_lo: float | None = None,
    price_hi: float | None = None,
) -> VolumeProfileLevels:
    """OHLCV approx — typical price × bar volume on the candle high/low grid.

    Same sample rule and grid convention as ``location._volume_profile``.
    """
    pairs = [
        ((c.high + c.low + c.close) / 3.0, float(c.volume)) for c in candles
    ]
    if price_lo is None or price_hi is None:
        span = candle_price_range(candles)
        if span is None:
            return VolumeProfileLevels(None, None, None, 0.0, len(pairs))
        price_lo, price_hi = span
    return _levels_from_pairs(pairs, lo=float(price_lo), hi=float(price_hi), params=params)


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
    price_lo: float | None = None
    price_hi: float | None = None
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
            "price_lo": self.price_lo,
            "price_hi": self.price_hi,
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
    """Compare trade-tape VP to kline VP on one shared candle high/low grid."""
    span = candle_price_range(candles)
    if span is None:
        empty = VolumeProfileLevels(None, None, None, 0.0, 0)
        return VpCompareReport(
            symbol=symbol,
            timeframe=timeframe,
            n_bars=len(candles),
            n_trades=len(trades),
            kline=empty,
            trade=empty,
            poc_abs_diff=None,
            vah_abs_diff=None,
            val_abs_diff=None,
            price_lo=None,
            price_hi=None,
        )
    lo, hi = span
    kline = compute_kline_volume_profile(candles, params, price_lo=lo, price_hi=hi)
    trade = compute_trade_volume_profile(trades, params, price_lo=lo, price_hi=hi)
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
        price_lo=lo,
        price_hi=hi,
    )
