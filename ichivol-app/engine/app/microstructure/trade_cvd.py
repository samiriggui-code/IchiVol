"""Trade-tape Cumulative Volume Delta — research candidate (Binance micro).

Builds bar deltas from aggressor trades, then cumulative / rolling bias.
Does **not** replace ``indicators.cvd`` (kline taker approx) and never votes
in the live pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.indicators.cvd import CvdBias, CvdParams, CvdState, compute_cvd
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class AggressorTrade:
    """One trade with aggressor side (buyer_is_aggressor=True → buy volume)."""

    time_ms: int
    price: float
    size: float
    buyer_is_aggressor: bool


def trade_delta(trade: AggressorTrade) -> float:
    """+size if buyer aggressor, −size if seller aggressor."""
    return float(trade.size) if trade.buyer_is_aggressor else -float(trade.size)


def bucket_trade_deltas_to_bars(
    trades: Sequence[AggressorTrade],
    bar_opens: Sequence[int],
    *,
    tf_seconds: int,
) -> list[float | None]:
    """Sum signed trade size into each bar ``[open, open+tf)``.

    ``bar_opens`` are unix **seconds** (Candle.time). Trades use ms.
    Bars with no trades → ``None`` (unknown), not 0.
    """
    if not bar_opens:
        return []
    n = len(bar_opens)
    sums = [0.0] * n
    seen = [False] * n
    # Pointer scan — bars sorted ascending.
    j = 0
    for tr in sorted(trades, key=lambda t: t.time_ms):
        t_sec = tr.time_ms / 1000.0
        while j + 1 < n and bar_opens[j + 1] <= t_sec:
            j += 1
        if j >= n:
            break
        open_t = bar_opens[j]
        if open_t <= t_sec < open_t + tf_seconds:
            sums[j] += trade_delta(tr)
            seen[j] = True
        elif t_sec < open_t:
            continue
    return [sums[i] if seen[i] else None for i in range(n)]


def compute_trade_cvd_from_deltas(
    times: Sequence[int],
    deltas: Sequence[float | None],
    params: CvdParams = CvdParams(),
) -> list[CvdState]:
    """Same bias semantics as kline CVD, fed by trade-bucket deltas."""
    if len(times) != len(deltas):
        raise ValueError("times/deltas length mismatch")
    out: list[CvdState] = []
    stored: list[float | None] = []
    cumulative = 0.0
    have = False
    for i, t in enumerate(times):
        d = deltas[i]
        if d is None:
            stored.append(None)
            out.append(
                CvdState(
                    time=t,
                    delta=None,
                    cumulative=None,
                    rolling_delta=None,
                    bias=CvdBias.UNKNOWN,
                )
            )
            continue
        stored.append(d)
        cumulative += d
        have = True
        start = max(0, i - params.window + 1)
        window = [x for x in stored[start : i + 1] if x is not None]
        rolling = sum(window) if window else None
        # Volume proxy = sum |delta| in window (trade-based).
        window_vol = sum(abs(x) for x in window) if window else 0.0
        if rolling is None or window_vol <= 0:
            bias = CvdBias.UNKNOWN
        else:
            ratio = rolling / window_vol
            if ratio > params.bias_threshold:
                bias = CvdBias.BULLISH
            elif ratio < -params.bias_threshold:
                bias = CvdBias.BEARISH
            else:
                bias = CvdBias.NEUTRAL
        out.append(
            CvdState(
                time=t,
                delta=d,
                cumulative=cumulative if have else None,
                rolling_delta=rolling,
                bias=bias,
            )
        )
    return out


def compute_trade_cvd(
    candles: Sequence[Candle],
    trades: Sequence[AggressorTrade],
    *,
    tf_seconds: int,
    params: CvdParams = CvdParams(),
) -> list[CvdState]:
    opens = [c.time for c in candles]
    deltas = bucket_trade_deltas_to_bars(trades, opens, tf_seconds=tf_seconds)
    return compute_trade_cvd_from_deltas(opens, deltas, params)


@dataclass(frozen=True)
class CvdCompareReport:
    symbol: str
    timeframe: str
    n_bars: int
    n_trades: int
    bars_with_trades: int
    bars_with_kline_cvd: int
    bias_agreement_rate: float | None
    delta_corr: float | None
    sample: list[dict]
    disclaimer: str = (
        "Trade CVD vs kline CVD compare — research only; does not alter "
        "decision, confidence, fills, or gates."
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "n_trades": self.n_trades,
            "bars_with_trades": self.bars_with_trades,
            "bars_with_kline_cvd": self.bars_with_kline_cvd,
            "bias_agreement_rate": self.bias_agreement_rate,
            "delta_corr": self.delta_corr,
            "sample": list(self.sample),
            "disclaimer": self.disclaimer,
        }


def compare_kline_vs_trade_cvd(
    candles: Sequence[Candle],
    trades: Sequence[AggressorTrade],
    *,
    symbol: str,
    timeframe: str,
    tf_seconds: int,
    params: CvdParams = CvdParams(),
    sample_limit: int = 20,
) -> CvdCompareReport:
    """Side-by-side bias/delta agreement — Lab measurement only."""
    import statistics

    kline = compute_cvd(candles, params)
    trade = compute_trade_cvd(candles, trades, tf_seconds=tf_seconds, params=params)
    agree = 0
    compared = 0
    pairs_k: list[float] = []
    pairs_t: list[float] = []
    sample: list[dict] = []
    bars_trades = 0
    bars_kline = 0
    for ks, ts in zip(kline, trade):
        if ts.delta is not None:
            bars_trades += 1
        if ks.delta is not None:
            bars_kline += 1
        if (
            ks.bias not in (CvdBias.UNKNOWN,)
            and ts.bias not in (CvdBias.UNKNOWN,)
            and ks.delta is not None
            and ts.delta is not None
        ):
            compared += 1
            if ks.bias == ts.bias:
                agree += 1
            pairs_k.append(float(ks.delta))
            pairs_t.append(float(ts.delta))
            if len(sample) < sample_limit:
                sample.append(
                    {
                        "time": ks.time,
                        "kline_delta": ks.delta,
                        "trade_delta": ts.delta,
                        "kline_bias": ks.bias.value,
                        "trade_bias": ts.bias.value,
                    }
                )
    corr = None
    if len(pairs_k) >= 2 and len(set(pairs_k)) > 1 and len(set(pairs_t)) > 1:
        try:
            corr = float(statistics.correlation(pairs_k, pairs_t))
        except statistics.StatisticsError:
            corr = None
    return CvdCompareReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        n_trades=len(trades),
        bars_with_trades=bars_trades,
        bars_with_kline_cvd=bars_kline,
        bias_agreement_rate=(agree / compared) if compared else None,
        delta_corr=corr,
        sample=sample,
    )
