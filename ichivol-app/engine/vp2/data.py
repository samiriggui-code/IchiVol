"""Build sim.py inputs from frozen VP1 spot series (+ ATR stop distance)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.agents.types import Direction
from app.indicators.atr import compute_atr
from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from vp1.download import data_root, load_manifest
from vp1.load import load_series

from vp2 import BAR_SECONDS

DecisionFn = Callable[[int, Candle, float | None], str]
"""(bar_index, candle, atr_stop_distance) -> BUY | WATCH | ..."""


def series_rel_path(symbol: str, interval: str, window_start: str = "20200901", window_end: str = "20260831") -> str:
    return f"series/{symbol}_spot_{interval}_{window_start}_{window_end}.json"


def load_vp1_spot(
    root: Path | None,
    symbol: str,
    interval: str,
) -> tuple[dict[str, Any], str]:
    """Load frozen series + return (payload, sha256 from manifest)."""
    root = data_root(root)
    rel = series_rel_path(symbol, interval)
    man = load_manifest(root)
    entry = man.get("files", {}).get(rel)
    if entry is None:
        raise FileNotFoundError(f"VP1 series not in manifest: {rel}")
    payload = load_series(root, rel)
    digest = entry.get("sha256") or ""
    return payload, digest


def bars_to_candles(bars: list[dict[str, Any]]) -> list[Candle]:
    out: list[Candle] = []
    for b in bars:
        out.append(
            Candle(
                time=int(b["open_time"] // 1000),
                open=float(b["open"]),
                high=float(b["high"]),
                low=float(b["low"]),
                close=float(b["close"]),
                volume=float(b["volume"]),
                taker_buy_volume=float(b["taker_buy_base"]) if b.get("taker_buy_base") is not None else None,
            )
        )
    return out


def build_sim_feed(
    candles: list[Candle],
    *,
    decide: DecisionFn | None = None,
) -> dict[int, tuple[Candle, BarSignal]]:
    """Map open_time_s -> (candle, BarSignal) with ATR(14)×1.5 stop_distance (§6).

    Default decide = always WATCH (no entries). Callers inject BUY for harness tests / VP3.
    """
    if decide is None:
        def decide(_i: int, _c: Candle, _sd: float | None) -> str:
            return "WATCH"

    atr = compute_atr(candles)
    feed: dict[int, tuple[Candle, BarSignal]] = {}
    for i, c in enumerate(candles):
        sd = atr[i].suggested_stop_distance
        stop = float(sd) if isinstance(sd, (int, float)) and sd > 0 else None
        decision = decide(i, c, stop)
        direction = (
            Direction.LONG if decision == "BUY" else Direction.SHORT if decision == "SELL" else Direction.NEUTRAL
        )
        feed[c.time] = (
            c,
            BarSignal(
                time=c.time,
                decision=decision,
                direction=direction,
                stop_distance=stop,
                rvol=None,
                failed=(),
                fail_codes=(),
                primary="signal" if decision in ("BUY", "SELL") else "vp2_flat",
                mtf_aligned=None,
            ),
        )
    return feed


def window_seconds(start_iso: str, end_iso_inclusive: str, interval: str) -> tuple[int, int]:
    """[start, end) unix seconds for sim window from calendar ISO dates (UTC)."""
    from datetime import date, datetime, timedelta, timezone

    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso_inclusive)
    start_s = int(datetime(s.year, s.month, s.day, tzinfo=timezone.utc).timestamp())
    end_excl = datetime(e.year, e.month, e.day, tzinfo=timezone.utc) + timedelta(days=1)
    # last bar open must be < end_excl; for closed bars of `interval`, end is midnight after last day
    _ = BAR_SECONDS[interval]  # validate
    return start_s, int(end_excl.timestamp())
