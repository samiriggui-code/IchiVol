"""Event Study — Phase 1 Strategy Lab.

For each historical *entry signal* (desired position becoming LONG/SHORT),
observe what price does afterwards — without capital, fees, or sizing.

Convention (aligned with app/backtest/engine.py anti-lookahead):
  - Signal at bar i uses only candles[0..i].
  - Entry reference = open of bar i+1 (first tradable price).
  - Horizon h = close of bar (entry_idx + h - 1) vs entry.
  - MFE/MAE scanned on highs/lows from entry_idx through that exit bar,
    signed by direction, ATR-normalized with ATR known at signal bar i.

This is NOT a backtester. It answers: "after this observation, what typically
happens next?" — the bridge before full ruleset backtests.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Sequence

from app.agents.types import Direction
from app.backtest import experiments
from app.indicators.atr import AtrState
from app.indicators.ichimoku import Candle

DEFAULT_HORIZONS = (1, 3, 5, 10)
DEFAULT_R_MULTIPLE = 1.0


@dataclass(frozen=True)
class EventObservation:
    """One historical signal occurrence and its forward path."""

    signal_index: int
    entry_index: int
    signal_time: int
    entry_time: int
    direction: Direction
    entry_price: float
    atr: float
    returns_atr: dict[int, float | None]
    """horizon -> signed ATR-normalized close return (None if not enough bars)."""
    mfe_atr: float | None
    """Max favorable excursion in ATR over the longest available horizon window."""
    mae_atr: float | None
    """Max adverse excursion in ATR (positive number = pain)."""
    hit_plus_r_before_minus_r: bool | None
    """True if +R ATR touched before -R ATR within the scan window; None if neither."""


@dataclass(frozen=True)
class HorizonStats:
    horizon: int
    n: int
    mean_atr: float | None
    median_atr: float | None
    mean_pct: float | None


@dataclass(frozen=True)
class EventStudyResult:
    symbol: str
    timeframe: str
    variant: str
    n_bars: int
    n_events: int
    horizons: tuple[int, ...]
    r_multiple: float
    horizon_stats: list[HorizonStats]
    mean_mfe_atr: float | None
    mean_mae_atr: float | None
    median_mfe_atr: float | None
    median_mae_atr: float | None
    pct_hit_plus_r_before_minus_r: float | None
    """Among events where +R or -R was touched; None if none resolved."""
    n_resolved_r: int
    events: list[EventObservation] = field(repr=False)


def extract_entry_signals(desired: Sequence[Direction]) -> list[tuple[int, Direction]]:
    """Bars where desired becomes LONG/SHORT from a different prior state.

    Index is the *signal* bar (causal close). Entry is open of the next bar.
    """
    out: list[tuple[int, Direction]] = []
    prev = Direction.NEUTRAL
    for i, d in enumerate(desired):
        if d in (Direction.LONG, Direction.SHORT) and d != prev:
            out.append((i, d))
        prev = d
    return out


def _signed_excursion(direction: Direction, entry: float, high: float, low: float) -> tuple[float, float]:
    """Return (favorable, adverse) price moves, both >= 0."""
    if direction == Direction.LONG:
        return max(0.0, high - entry), max(0.0, entry - low)
    if direction == Direction.SHORT:
        return max(0.0, entry - low), max(0.0, high - entry)
    return 0.0, 0.0


def _signed_close_return(direction: Direction, entry: float, close: float) -> float:
    if direction == Direction.LONG:
        return close - entry
    if direction == Direction.SHORT:
        return entry - close
    return 0.0


def observe_event(
    candles: Sequence[Candle],
    signal_index: int,
    direction: Direction,
    atr: float,
    horizons: Sequence[int],
    r_multiple: float = DEFAULT_R_MULTIPLE,
) -> EventObservation | None:
    """Build one EventObservation, or None if entry/ATR unavailable."""
    n = len(candles)
    entry_index = signal_index + 1
    if entry_index >= n or atr <= 0 or direction == Direction.NEUTRAL:
        return None

    entry_price = candles[entry_index].open
    max_h = max(horizons)
    returns_atr: dict[int, float | None] = {}
    mfe = 0.0
    mae = 0.0
    last_scanned = entry_index - 1

    for h in sorted(horizons):
        exit_index = entry_index + h - 1
        if exit_index >= n:
            returns_atr[h] = None
            continue
        for j in range(last_scanned + 1, exit_index + 1):
            fav, adv = _signed_excursion(
                direction, entry_price, candles[j].high, candles[j].low
            )
            mfe = max(mfe, fav)
            mae = max(mae, adv)
        last_scanned = exit_index
        signed = _signed_close_return(direction, entry_price, candles[exit_index].close)
        returns_atr[h] = signed / atr

    # If some horizons missing, still expose MFE/MAE over whatever we scanned;
    # if nothing scanned, leave None.
    if last_scanned < entry_index:
        mfe_atr = mae_atr = None
    else:
        mfe_atr = mfe / atr
        mae_atr = mae / atr

    hit = _hit_plus_r_before_minus_r(
        candles,
        entry_index=entry_index,
        entry_price=entry_price,
        direction=direction,
        atr=atr,
        r_multiple=r_multiple,
        max_bars=max_h,
    )

    return EventObservation(
        signal_index=signal_index,
        entry_index=entry_index,
        signal_time=candles[signal_index].time,
        entry_time=candles[entry_index].time,
        direction=direction,
        entry_price=entry_price,
        atr=atr,
        returns_atr=returns_atr,
        mfe_atr=mfe_atr,
        mae_atr=mae_atr,
        hit_plus_r_before_minus_r=hit,
    )


def _hit_plus_r_before_minus_r(
    candles: Sequence[Candle],
    *,
    entry_index: int,
    entry_price: float,
    direction: Direction,
    atr: float,
    r_multiple: float,
    max_bars: int,
) -> bool | None:
    """Walk bar-by-bar; within each bar check adverse then favorable (conservative).

    Conservative intra-bar order: assume stop (-R) can hit before target (+R)
    on the same candle unless we only have one-sided evidence. If both levels
    are inside the same bar's range, count as miss (adverse first).
    """
    plus = r_multiple * atr
    minus = r_multiple * atr
    end = min(len(candles), entry_index + max_bars)
    for j in range(entry_index, end):
        fav, adv = _signed_excursion(direction, entry_price, candles[j].high, candles[j].low)
        hit_plus = fav >= plus
        hit_minus = adv >= minus
        if hit_minus and hit_plus:
            return False
        if hit_minus:
            return False
        if hit_plus:
            return True
    return None


def _mean(xs: Sequence[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _median(xs: Sequence[float]) -> float | None:
    return statistics.median(xs) if xs else None


def aggregate_events(
    events: Sequence[EventObservation],
    horizons: Sequence[int],
    r_multiple: float,
    *,
    symbol: str,
    timeframe: str,
    variant: str,
    n_bars: int,
) -> EventStudyResult:
    horizon_stats: list[HorizonStats] = []
    for h in horizons:
        atr_vals: list[float] = []
        pct_vals: list[float] = []
        for ev in events:
            r = ev.returns_atr.get(h)
            if r is None:
                continue
            atr_vals.append(r)
            pct_vals.append(r * ev.atr / ev.entry_price if ev.entry_price else 0.0)
        horizon_stats.append(
            HorizonStats(
                horizon=h,
                n=len(atr_vals),
                mean_atr=_mean(atr_vals),
                median_atr=_median(atr_vals),
                mean_pct=_mean(pct_vals),
            )
        )

    mfe_vals = [e.mfe_atr for e in events if e.mfe_atr is not None]
    mae_vals = [e.mae_atr for e in events if e.mae_atr is not None]
    resolved = [e.hit_plus_r_before_minus_r for e in events if e.hit_plus_r_before_minus_r is not None]
    hits = sum(1 for x in resolved if x)

    return EventStudyResult(
        symbol=symbol,
        timeframe=timeframe,
        variant=variant,
        n_bars=n_bars,
        n_events=len(events),
        horizons=tuple(horizons),
        r_multiple=r_multiple,
        horizon_stats=horizon_stats,
        mean_mfe_atr=_mean(mfe_vals),
        mean_mae_atr=_mean(mae_vals),
        median_mfe_atr=_median(mfe_vals),
        median_mae_atr=_median(mae_vals),
        pct_hit_plus_r_before_minus_r=(hits / len(resolved) if resolved else None),
        n_resolved_r=len(resolved),
        events=list(events),
    )


def study_positions(
    candles: Sequence[Candle],
    desired: Sequence[Direction],
    atr_states: Sequence[AtrState],
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    r_multiple: float = DEFAULT_R_MULTIPLE,
    symbol: str = "",
    timeframe: str = "",
    variant: str = "",
) -> EventStudyResult:
    if len(candles) != len(desired) or len(candles) != len(atr_states):
        raise ValueError("candles, desired, and atr_states must be the same length")

    events: list[EventObservation] = []
    for signal_index, direction in extract_entry_signals(desired):
        atr_val = atr_states[signal_index].atr
        if atr_val is None or atr_val <= 0:
            continue
        obs = observe_event(
            candles,
            signal_index,
            direction,
            atr_val,
            horizons,
            r_multiple=r_multiple,
        )
        if obs is not None:
            events.append(obs)

    return aggregate_events(
        events,
        horizons,
        r_multiple,
        symbol=symbol,
        timeframe=timeframe,
        variant=variant,
        n_bars=len(candles),
    )


def run_event_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    variant: str = experiments.PIPELINE,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    r_multiple: float = DEFAULT_R_MULTIPLE,
    exchange: str = "binance",
) -> EventStudyResult:
    """Fetch OHLCV, build the named experiment position series, run event study."""
    prepared = experiments.prepare_variants(
        symbol, timeframe=timeframe, limit=limit, exchange=exchange
    )
    if variant not in prepared.positions:
        known = ", ".join(sorted(prepared.positions))
        raise ValueError(f"unknown variant {variant!r}; known: {known}")

    return study_positions(
        prepared.candles,
        prepared.positions[variant],
        prepared.atr_states,
        horizons=horizons,
        r_multiple=r_multiple,
        symbol=symbol,
        timeframe=timeframe,
        variant=variant,
    )


def event_study_dict(result: EventStudyResult, *, include_events: bool = False) -> dict:
    payload: dict = {
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "variant": result.variant,
        "n_bars": result.n_bars,
        "n_events": result.n_events,
        "horizons": list(result.horizons),
        "r_multiple": result.r_multiple,
        "horizon_stats": [
            {
                "horizon": h.horizon,
                "n": h.n,
                "mean_atr": h.mean_atr,
                "median_atr": h.median_atr,
                "mean_pct": h.mean_pct,
            }
            for h in result.horizon_stats
        ],
        "mean_mfe_atr": result.mean_mfe_atr,
        "mean_mae_atr": result.mean_mae_atr,
        "median_mfe_atr": result.median_mfe_atr,
        "median_mae_atr": result.median_mae_atr,
        "pct_hit_plus_r_before_minus_r": result.pct_hit_plus_r_before_minus_r,
        "n_resolved_r": result.n_resolved_r,
        "note": (
            "Event study only — no capital, fees, or position sizing. "
            "Entry = open of bar after signal; returns ATR-normalized."
        ),
    }
    if include_events:
        payload["events"] = [
            {
                "signal_index": e.signal_index,
                "entry_index": e.entry_index,
                "signal_time": e.signal_time,
                "entry_time": e.entry_time,
                "direction": e.direction.value,
                "entry_price": e.entry_price,
                "atr": e.atr,
                "returns_atr": {str(k): v for k, v in e.returns_atr.items()},
                "mfe_atr": e.mfe_atr,
                "mae_atr": e.mae_atr,
                "hit_plus_r_before_minus_r": e.hit_plus_r_before_minus_r,
            }
            for e in result.events
        ]
    return payload
