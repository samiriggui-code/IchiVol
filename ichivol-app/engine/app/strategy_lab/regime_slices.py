"""Regime-sliced ruleset studies — Strategy Lab Phase 6.

Run one ruleset on a shared OHLCV window, then re-aggregate Event Study and
ATR backtest metrics for GLOBAL and each orthogonal regime tag present at
signal time (TRENDING / RANGING / HIGH_VOLATILITY / …).

Answers: "is this strategy bad, or bad *in this regime*?"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.agents.types import Direction
from app.backtest.engine import BacktestResult
from app.backtest.metrics import compute_metrics
from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.evaluator import extract_ruleset_signals
from app.strategy_lab.event_study import (
    DEFAULT_HORIZONS,
    EventObservation,
    aggregate_events,
    observe_event,
)
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.perf_db import persist_study_result
from app.strategy_lab.regime import RegimeTags, classify_regimes
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.ruleset_backtest import RulesetBacktestResult, simulate_ruleset_trades
from app.strategy_lab.run_ruleset import RulesetStudyResult, ruleset_study_dict


SLICE_ORDER = (
    "GLOBAL",
    "TRENDING",
    "RANGING",
    "HIGH_VOLATILITY",
    "NORMAL_VOLATILITY",
    "LOW_VOLATILITY",
    "BULL",
    "BEAR",
    "SIDEWAYS",
)


@dataclass(frozen=True)
class RegimeSliceResult:
    regime: str
    n_signals: int
    n_bars_in_regime: int
    study: RulesetStudyResult
    experiment_id: str | None = None


@dataclass(frozen=True)
class RegimeSliceReport:
    symbol: str
    timeframe: str
    ruleset: Ruleset
    n_bars: int
    slices: list[RegimeSliceResult]
    regime_bar_counts: dict[str, int]


def _filter_signals(
    signals: Sequence[tuple[int, Direction]],
    regimes: Sequence[RegimeTags],
    label: str,
) -> list[tuple[int, Direction]]:
    if label == "GLOBAL":
        return list(signals)
    out: list[tuple[int, Direction]] = []
    for idx, direction in signals:
        if label in regimes[idx].labels():
            out.append((idx, direction))
    return out


def _count_bars(regimes: Sequence[RegimeTags]) -> dict[str, int]:
    counts: dict[str, int] = {"GLOBAL": len(regimes)}
    for tags in regimes:
        for lab in tags.labels():
            counts[lab] = counts.get(lab, 0) + 1
    return counts


def _study_from_signals(
    features,
    ruleset: Ruleset,
    signals: Sequence[tuple[int, Direction]],
    *,
    symbol: str,
    timeframe: str,
    horizons: Sequence[int],
    commission_bps: float,
    slippage_bps: float,
    variant_suffix: str,
) -> RulesetStudyResult:
    r_multiple = float(ruleset.stop_atr)
    events: list[EventObservation] = []
    for signal_index, direction in signals:
        atr_val = features.atr[signal_index].atr
        if atr_val is None or atr_val <= 0:
            continue
        obs = observe_event(
            features.candles,
            signal_index,
            direction,
            atr_val,
            horizons,
            r_multiple=r_multiple,
        )
        if obs is not None:
            events.append(obs)

    study = aggregate_events(
        events,
        horizons,
        r_multiple,
        symbol=symbol,
        timeframe=timeframe,
        variant=f"{ruleset.id}@{variant_suffix}",
        n_bars=len(features.candles),
    )

    details, posn, bar_returns, skipped, _rejected = simulate_ruleset_trades(
        features.candles,
        features.atr,
        signals,
        stop_atr=float(ruleset.stop_atr),
        target_atr=float(ruleset.target_atr),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    backtest = BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(features.candles),
        bar_returns=bar_returns,
        posn=posn[:-1] if len(posn) > 1 else posn,
        trades=[d.trade for d in details],
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    bt = RulesetBacktestResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        backtest=backtest,
        metrics=compute_metrics(backtest),
        details=details,
        n_signals=len(signals),
        n_skipped_in_position=skipped,
    )
    matching = len(signals)  # rising-edge already; slice-specific
    return RulesetStudyResult(
        ruleset=ruleset,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(features.candles),
        n_matching_bars=matching,
        n_signals=len(signals),
        event_study=study,
        backtest=bt,
    )


def run_regime_slices_on_candles(
    candles: Sequence,
    ruleset: Ruleset,
    *,
    symbol: str = "",
    timeframe: str = "",
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    persist: bool = False,
    commission_bps: float = 5.0,
    slippage_bps: float = 3.0,
    min_signals: int = 1,
) -> RegimeSliceReport:
    features = build_feature_series(candles)
    regimes = classify_regimes(candles)
    signals = extract_ruleset_signals(features, ruleset, rising_edge=True)
    bar_counts = _count_bars(regimes)

    # Which slice labels appear on at least one signal (plus GLOBAL)
    labels_present: set[str] = {"GLOBAL"}
    for idx, _ in signals:
        labels_present.update(regimes[idx].labels())

    ordered = [lab for lab in SLICE_ORDER if lab in labels_present]
    for lab in sorted(labels_present):
        if lab not in ordered:
            ordered.append(lab)

    slices: list[RegimeSliceResult] = []
    for lab in ordered:
        filtered = _filter_signals(signals, regimes, lab)
        if lab != "GLOBAL" and len(filtered) < min_signals:
            continue
        study = _study_from_signals(
            features,
            ruleset,
            filtered,
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            variant_suffix=lab,
        )
        exp_id = None
        if persist:
            saved = persist_study_result(
                study,
                market_regime=lab,
                parameters={
                    "regime_slice": True,
                    "regime": lab,
                    "n_bars_in_regime": bar_counts.get(lab, 0),
                },
            )
            exp_id = saved.get("experiment_id")
        slices.append(
            RegimeSliceResult(
                regime=lab,
                n_signals=len(filtered),
                n_bars_in_regime=bar_counts.get(lab, 0),
                study=study,
                experiment_id=exp_id,
            )
        )

    return RegimeSliceReport(
        symbol=symbol,
        timeframe=timeframe,
        ruleset=ruleset,
        n_bars=len(candles),
        slices=slices,
        regime_bar_counts=bar_counts,
    )


def run_regime_slices(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str | None = None,
    ruleset: dict | Ruleset | None = None,
    persist: bool = False,
    exchange: str = "binance",
) -> RegimeSliceReport:
    if ruleset is not None:
        rs = ruleset if isinstance(ruleset, Ruleset) else parse_ruleset(ruleset)
    elif ruleset_id:
        rs = get_builtin_ruleset(ruleset_id)
    else:
        rs = get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001")

    _p, _s, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles for {symbol} {timeframe}")
    return run_regime_slices_on_candles(
        candles, rs, symbol=symbol.upper(), timeframe=timeframe, persist=persist
    )


def regime_slices_dict(report: RegimeSliceReport) -> dict:
    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "ruleset": report.ruleset.to_dict(),
        "n_bars": report.n_bars,
        "regime_bar_counts": report.regime_bar_counts,
        "slices": [
            {
                "regime": s.regime,
                "n_signals": s.n_signals,
                "n_bars_in_regime": s.n_bars_in_regime,
                "experiment_id": s.experiment_id,
                "study": ruleset_study_dict(s.study, include_events=False),
            }
            for s in report.slices
        ],
        "note": (
            "Regime at signal bar (causal ADX+ATR). "
            "GLOBAL = all signals; other rows = same ruleset filtered by tag. "
            "A weak GLOBAL PF with strong TRENDING PF means regime-conditional edge."
        ),
    }
