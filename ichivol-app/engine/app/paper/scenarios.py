"""Scenario calculator for paper buy sheet + open positions (T0-CALC).

Scenarios are computed from historical data — not forecasts. Target/stop EUR
amounts MUST come from ``preview_manual_buy`` outcomes (never recomputed here
with a divergent formula). Crash uses the worst adverse move actually observed
on closed candles; duration / expectancy come from a cached PIPELINE backtest
(``net_v2``).
"""

from __future__ import annotations

import logging
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Sequence

from app.backtest.engine import BacktestResult, Trade, run_backtest
from app.backtest.experiments import PIPELINE, prepare_variants
from app.backtest.metrics import compute_metrics
from app.indicators.ichimoku import Candle
from app.market_data.resolve import resolve_and_fetch
from app.market_data.timeframes import TF_SECONDS
from app.paper.broker import _commission_bps, _friction
from app.paper.financing import financing_bps_for
from app.paper.risk import apply_exit_friction
from app.paper.strategy_profiles import BASELINE_PROFILE

logger = logging.getLogger(__name__)

DISCLAIMER = "Scénarios calculés sur l'historique — pas une prévision."
EXPECTANCY_MIN_N = 30
_HISTORY_LIMIT = 1000
_BT_CACHE_TTL_S = 6 * 3600.0

# (symbol, timeframe) -> (monotonic_ts, payload)
_PIPELINE_BT_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def _iso(ts: int | float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()


def closed_candles(candles: Sequence[Candle], timeframe: str, *, now: float | None = None) -> list[Candle]:
    """Drop the still-forming bar so crash/backtest history is causal (last close only)."""
    if not candles:
        return []
    now = time.time() if now is None else float(now)
    tf_s = float(TF_SECONDS.get(timeframe, 3600))
    last = candles[-1]
    # Bar open at ``time`` closes at ``time + tf_s``. If that is still in the future, drop it.
    if float(last.time) + tf_s > now + 1e-6:
        return list(candles[:-1])
    return list(candles)


def worst_adverse_long(
    candles: Sequence[Candle],
) -> dict[str, Any] | None:
    """Worst LONG adverse move: min(low/prev_close−1, open/prev_close−1) with its date."""
    if len(candles) < 2:
        return None
    worst_move = 0.0
    worst_time: int | None = None
    worst_kind: str | None = None
    worst_value: float | None = None  # low or open that produced the move
    for i in range(1, len(candles)):
        prev_close = float(candles[i - 1].close)
        if prev_close <= 0:
            continue
        c = candles[i]
        low_move = float(c.low) / prev_close - 1.0
        gap_move = float(c.open) / prev_close - 1.0
        candidates = (
            (low_move, "low", float(c.low)),
            (gap_move, "gap_open", float(c.open)),
        )
        for move, kind, value in candidates:
            if move < worst_move:
                worst_move = move
                worst_time = int(c.time)
                worst_kind = kind
                worst_value = value
    if worst_time is None:
        return None
    return {
        "move": worst_move,
        "time": worst_time,
        "date": _iso(worst_time),
        "kind": worst_kind,
        "value": worst_value,
    }


def _net_exit_pnl(
    *,
    qty: float,
    entry_fill: float,
    exit_mid: float,
    direction: str,
    profile: dict[str, Any],
    symbol: str,
    entry_fee: float,
) -> tuple[float, float, float]:
    """Net PnL at an exit mid-price (exit friction + commission), same path as preview close."""
    spread_bps, slip_bps = _friction(profile, symbol)
    exit_fill = apply_exit_friction(
        exit_mid, direction=direction, spread_bps=spread_bps, slippage_bps=slip_bps
    )
    comm_bps = _commission_bps(profile, symbol)
    exit_fee = qty * exit_fill * comm_bps / 10_000.0
    if direction == "LONG":
        net = qty * (exit_fill - entry_fill) - entry_fee - exit_fee
    else:
        net = qty * (entry_fill - exit_fill) - entry_fee - exit_fee
    return float(net), float(exit_fill), float(exit_fee)


def _row(label: str, net_eur: float, invested: float, equity: float, **extra: Any) -> dict[str, Any]:
    return {
        "label": label,
        "net_eur": net_eur,
        "pct_of_invested": (net_eur / invested) if invested else None,
        "pct_of_equity": (net_eur / equity) if equity else None,
        **extra,
    }


def _median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _hold_stats(trades: Sequence[Trade], timeframe: str) -> dict[str, Any]:
    tf_s = float(TF_SECONDS.get(timeframe, 3600))

    def _durations(subset: Sequence[Trade]) -> tuple[list[float], list[float]]:
        bars: list[float] = []
        hours: list[float] = []
        for t in subset:
            secs = max(0.0, float(t.exit_time) - float(t.entry_time))
            hours.append(secs / 3600.0)
            bars.append(secs / tf_s if tf_s > 0 else 0.0)
        return bars, hours

    winners = [t for t in trades if t.net_log_return > 0]
    losers = [t for t in trades if t.net_log_return <= 0]
    all_bars, all_hours = _durations(trades)
    w_bars, w_hours = _durations(winners)
    l_bars, l_hours = _durations(losers)

    def pack(bars: list[float], hours: list[float]) -> dict[str, float | None]:
        med_h = _median_or_none(hours)
        return {
            "median_bars": _median_or_none(bars),
            "median_hours": med_h,
            "median_days": (med_h / 24.0) if med_h is not None else None,
            "n": len(bars),
        }

    return {
        "all": pack(all_bars, all_hours),
        "winners": pack(w_bars, w_hours),
        "losers": pack(l_bars, l_hours),
    }


def _financing_for_hours(
    profile: dict[str, Any],
    symbol: str,
    *,
    notional: float,
    hours: float | None,
    direction: str = "LONG",
) -> float:
    if hours is None or hours <= 0 or notional <= 0:
        return 0.0
    bps = financing_bps_for(profile, symbol, direction=direction)
    days = hours / 24.0
    return float(notional * (bps / 10_000.0) * days)


def _run_pipeline_backtest(symbol: str, timeframe: str, *, limit: int = _HISTORY_LIMIT) -> dict[str, Any]:
    prepared = prepare_variants(symbol, timeframe=timeframe, limit=limit)
    candles = closed_candles(prepared.candles, timeframe)
    if len(candles) < 2:
        raise ValueError(f"not enough closed candles for {symbol} {timeframe}")
    # Re-align desired positions to closed length (drop last forming desired too).
    desired = prepared.positions[PIPELINE]
    if len(desired) > len(candles):
        desired = desired[: len(candles)]
    elif len(desired) < len(candles):
        candles = candles[: len(desired)]
    bt = run_backtest(candles, desired, symbol=symbol, timeframe=timeframe)
    metrics = compute_metrics(bt)
    return {
        "backtest": bt,
        "metrics": metrics,
        "candles": candles,
        "n_bars": len(candles),
        "from_ts": int(candles[0].time) if candles else None,
        "to_ts": int(candles[-1].time) if candles else None,
    }


def cached_pipeline_backtest(
    symbol: str,
    timeframe: str,
    *,
    limit: int = _HISTORY_LIMIT,
    force: bool = False,
) -> dict[str, Any]:
    """PIPELINE backtest cached 6 h per (symbol, timeframe)."""
    key = (symbol.upper(), timeframe)
    now = time.monotonic()
    if not force:
        hit = _PIPELINE_BT_CACHE.get(key)
        if hit is not None and now - hit[0] < _BT_CACHE_TTL_S:
            return hit[1]
    payload = _run_pipeline_backtest(symbol, timeframe, limit=limit)
    _PIPELINE_BT_CACHE[key] = (now, payload)
    return payload


def clear_scenario_caches() -> None:
    _PIPELINE_BT_CACHE.clear()


def fetch_closed_history(
    symbol: str,
    timeframe: str,
    *,
    limit: int = _HISTORY_LIMIT,
    candles: Sequence[Candle] | None = None,
) -> list[Candle]:
    if candles is not None:
        return closed_candles(candles, timeframe)
    _prov, _sym, raw = resolve_and_fetch(symbol, timeframe, limit=limit)
    return closed_candles(raw, timeframe)


def build_scenarios(
    symbol: str,
    timeframe: str,
    entry_price: float,
    qty: float,
    stop_price: float,
    target_price: float,
    profile: dict[str, Any] | None = None,
    *,
    net_gain_if_target: float,
    net_loss_if_stop: float,
    invested: float,
    equity: float,
    entry_fee: float = 0.0,
    direction: str = "LONG",
    candles: Sequence[Candle] | None = None,
    pipeline_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build buy-sheet scenarios. Target/stop EUR must be the preview outcomes."""
    prof = dict(profile) if profile is not None else dict(BASELINE_PROFILE)
    hist = fetch_closed_history(symbol, timeframe, candles=candles)

    # --- crash ---
    ref = worst_adverse_long(hist) if direction == "LONG" else None
    if ref is None:
        crash_mid = float(stop_price)
        ref_payload = None
    else:
        crash_raw = float(entry_price) * (1.0 + float(ref["move"]))
        crash_mid = min(float(stop_price), crash_raw) if direction == "LONG" else float(stop_price)
        ref_payload = {
            "move": ref["move"],
            "date": ref["date"],
            "kind": ref["kind"],
            "value": ref["value"],
            "candle_time": ref["time"],
        }
    crash_net, crash_fill, _crash_fee = _net_exit_pnl(
        qty=qty,
        entry_fill=entry_price,
        exit_mid=crash_mid,
        direction=direction,
        profile=prof,
        symbol=symbol,
        entry_fee=entry_fee,
    )
    # Invariant: crash loss is at least as severe as stop (net_eur more negative or equal).
    if crash_net > net_loss_if_stop + 1e-9:
        crash_net = float(net_loss_if_stop)
        crash_mid = float(stop_price)

    target_row = _row("Objectif", float(net_gain_if_target), invested, equity, exit_price=float(target_price))
    stop_row = _row("Stop", float(net_loss_if_stop), invested, equity, exit_price=float(stop_price))
    crash_row = _row(
        "Crash",
        float(crash_net),
        invested,
        equity,
        exit_price=float(crash_mid),
        exit_fill=float(crash_fill),
        reference=ref_payload,
    )

    # --- duration + expectancy from PIPELINE backtest ---
    bt_err: str | None = None
    try:
        payload = pipeline_payload if pipeline_payload is not None else cached_pipeline_backtest(symbol, timeframe)
    except Exception as exc:  # noqa: BLE001 — scenarios stay usable without BT
        logger.warning("scenarios: pipeline backtest failed for %s %s: %s", symbol, timeframe, exc)
        payload = None
        bt_err = str(exc)

    holding: dict[str, Any]
    expectancy: dict[str, Any]
    window: dict[str, Any]
    financing_eur = 0.0
    if payload is None:
        holding = {"all": None, "winners": None, "losers": None, "error": bt_err}
        expectancy = {
            "available": False,
            "n": 0,
            "message": "échantillon insuffisant (0 trades)" if not bt_err else f"backtest indisponible: {bt_err}",
            "expectancy_per_trade": None,
            "expectancy_eur": None,
            "win_rate_net": None,
        }
        window = {"from": None, "to": None, "n_bars": 0, "metrics_basis": "net_v2"}
    else:
        bt: BacktestResult = payload["backtest"]
        metrics = payload["metrics"]
        trades = bt.trades
        holding = _hold_stats(trades, timeframe)
        med_hours = (holding["all"] or {}).get("median_hours")
        financing_eur = _financing_for_hours(
            prof, symbol, notional=invested, hours=med_hours, direction=direction
        )
        n = len(trades)
        if n >= EXPECTANCY_MIN_N and metrics.expectancy is not None:
            # expectancy is a simple return (fraction) per trade — scale by invested notional
            exp_eur = float(metrics.expectancy) * float(invested)
            expectancy = {
                "available": True,
                "n": n,
                "message": None,
                "expectancy_per_trade": float(metrics.expectancy),
                "expectancy_eur": exp_eur,
                "win_rate_net": metrics.win_rate,
            }
        else:
            expectancy = {
                "available": False,
                "n": n,
                "message": f"échantillon insuffisant ({n} trades)",
                "expectancy_per_trade": None,
                "expectancy_eur": None,
                "win_rate_net": metrics.win_rate,
            }
        window = {
            "from": _iso(payload.get("from_ts")),
            "to": _iso(payload.get("to_ts")),
            "n_bars": int(payload.get("n_bars") or 0),
            "metrics_basis": "net_v2",
        }

    return {
        "disclaimer": DISCLAIMER,
        "target": target_row,
        "stop": stop_row,
        "crash": crash_row,
        "holding": {
            **holding,
            "financing_eur_median": financing_eur,
            "financing_bps_per_day": financing_bps_for(prof, symbol, direction=direction),
        },
        "expectancy": expectancy,
        "backtest_window": window,
        "history_bars": len(hist),
        "history_to": _iso(hist[-1].time) if hist else None,
    }


def build_open_position_scenarios(
    position: Any,
    *,
    mark_price: float,
    profile: dict[str, Any] | None = None,
    equity: float,
    financing_paid: float = 0.0,
    candles: Sequence[Candle] | None = None,
    pipeline_payload: dict[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Scenarios for an OPEN lot, from current mark and from entry."""
    from app.paper.liquidation import preview_close_cash_delta

    prof = dict(profile) if profile is not None else dict(BASELINE_PROFILE)
    symbol = position.symbol
    timeframe = position.timeframe
    direction = position.direction or "LONG"
    qty = float(position.qty or 0.0)
    entry = float(position.entry_price)
    entry_fee = float(position.entry_fee or 0.0)
    invested = float(position.notional or (qty * entry))
    stop = float(position.stop_price) if position.stop_price is not None else entry * 0.98
    target = float(position.take_profit_price) if position.take_profit_price is not None else entry * 1.04

    # From entry — same fee path as a full round-trip
    net_target, _, _ = _net_exit_pnl(
        qty=qty, entry_fill=entry, exit_mid=target, direction=direction,
        profile=prof, symbol=symbol, entry_fee=entry_fee,
    )
    net_stop, _, _ = _net_exit_pnl(
        qty=qty, entry_fill=entry, exit_mid=stop, direction=direction,
        profile=prof, symbol=symbol, entry_fee=entry_fee,
    )
    base = build_scenarios(
        symbol,
        timeframe,
        entry,
        qty,
        stop,
        target,
        prof,
        net_gain_if_target=net_target,
        net_loss_if_stop=net_stop,
        invested=invested,
        equity=equity,
        entry_fee=entry_fee,
        direction=direction,
        candles=candles,
        pipeline_payload=pipeline_payload,
    )

    # Close-now at mark (liquidation path)
    close_now = preview_close_cash_delta(position, mark_price=float(mark_price), profile=prof)
    mark_realized = float(close_now["realized"])

    # From mark: delta vs closing now
    def _from_mark(exit_mid: float) -> dict[str, Any]:
        sim = preview_close_cash_delta(position, mark_price=float(exit_mid), profile=prof)
        net_from_entry = float(sim["realized"])
        net_from_mark = net_from_entry - mark_realized
        return {
            "exit_price": float(sim["exit_fill"]),
            "net_eur_from_entry": net_from_entry,
            "net_eur_from_mark": net_from_mark,
            "pct_of_invested": (net_from_entry / invested) if invested else None,
            "pct_of_equity": (net_from_entry / equity) if equity else None,
            "cash_delta": float(sim["cash_delta"]),
        }

    hist = fetch_closed_history(symbol, timeframe, candles=candles)
    ref = worst_adverse_long(hist) if direction == "LONG" else None
    if ref is None:
        crash_mid = min(stop, float(mark_price)) if direction == "LONG" else stop
    else:
        crash_raw = float(mark_price) * (1.0 + float(ref["move"]))
        crash_mid = min(float(stop), crash_raw) if direction == "LONG" else float(stop)

    from_mark = {
        "close_now": {
            "exit_price": float(close_now["exit_fill"]),
            "net_eur_from_entry": mark_realized,
            "net_eur_from_mark": 0.0,
            "cash_delta": float(close_now["cash_delta"]),
            "exit_fee": float(close_now["exit_fee"]),
        },
        "target": _from_mark(target),
        "stop": _from_mark(stop),
        "crash": {
            **_from_mark(crash_mid),
            "reference": (
                {
                    "move": ref["move"],
                    "date": ref["date"],
                    "kind": ref["kind"],
                    "value": ref["value"],
                    "candle_time": ref["time"],
                }
                if ref
                else None
            ),
        },
    }

    now_ts = time.time() if now is None else float(now)
    entry_ts = position.entry_time
    if hasattr(entry_ts, "timestamp"):
        entry_epoch = float(entry_ts.replace(tzinfo=timezone.utc).timestamp()) if entry_ts.tzinfo is None else float(entry_ts.timestamp())
    else:
        entry_epoch = float(entry_ts)
    elapsed_h = max(0.0, (now_ts - entry_epoch) / 3600.0)
    med_h = ((base.get("holding") or {}).get("all") or {}).get("median_hours")
    remaining_h = max(0.0, float(med_h) - elapsed_h) if med_h is not None else None
    fin_to_median = _financing_for_hours(
        prof, symbol, notional=invested, hours=remaining_h, direction=direction
    )

    return {
        **base,
        "mark": {"price": float(mark_price)},
        "from_entry": {
            "target": base["target"],
            "stop": base["stop"],
            "crash": base["crash"],
        },
        "from_mark": from_mark,
        "elapsed": {
            "hours": elapsed_h,
            "days": elapsed_h / 24.0,
            "median_hours": med_h,
            "vs_median_ratio": (elapsed_h / med_h) if med_h and med_h > 0 else None,
        },
        "financing": {
            "paid_eur": float(financing_paid),
            "estimated_remaining_to_median_eur": fin_to_median,
            "estimated_total_to_median_eur": float(financing_paid) + fin_to_median,
            "bps_per_day": financing_bps_for(prof, symbol, direction=direction),
        },
        "liquidation_close_now": from_mark["close_now"],
    }
