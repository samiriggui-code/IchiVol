"""T12c — academic / naive reference baselines (Lab observation only).

Same candles + same fees for every baseline. Buy & hold uses the engine
``run_backtest`` path; Donchian / structure use the Lab ruleset ATR backtest
with identical ``commission_bps`` / ``slippage_bps``.

**DÉCISION CURSOR — à relire par Claude** : « structure seule » =
rising-edge ``bos_bullish`` (ablation ladder ``C_BOS``), pas
``IV_ICHIMOKU_ONLY_*`` (Ichimoku structure, déjà cataloguée).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.agents.types import Direction
from app.backtest.engine import BacktestResult, run_backtest
from app.backtest.metrics import Metrics, compute_metrics
from app.indicators.ichimoku import Candle
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.run_ruleset import RulesetStudyResult, study_ruleset_on_candles

# Lab canonical fees (same as study_ruleset_on_candles / walk_forward defaults).
DEFAULT_COMMISSION_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 3.0

REF_BUY_HOLD_ID = "IV_REF_BUY_HOLD_LONG_001"
REF_DONCHIAN_ID = "IV_REF_DONCHIAN_BO_LONG_001"
REF_STRUCTURE_BOS_ID = "IV_REF_STRUCTURE_BOS_LONG_001"

_DONCHIAN_RAW: dict[str, Any] = {
    "id": REF_DONCHIAN_ID,
    "version": "1",
    "direction": "LONG",
    "description": "T12c reference — Donchian breakout UP alone (ATR 1R/2R)",
    "conditions": {"donchian_breakout": "UP"},
    "entry": "next_open",
    "stop_atr": 1.0,
    "target_atr": 2.0,
    "meta": {"reference": True, "t12c": True},
}

_STRUCTURE_BOS_RAW: dict[str, Any] = {
    "id": REF_STRUCTURE_BOS_ID,
    "version": "1",
    "direction": "LONG",
    "description": "T12c reference — BOS bullish alone (ATR 1R/2R)",
    "conditions": {"bos_bullish": True},
    "entry": "next_open",
    "stop_atr": 1.0,
    "target_atr": 2.0,
    "meta": {"reference": True, "t12c": True},
}


def donchian_reference_ruleset() -> Ruleset:
    return parse_ruleset(_DONCHIAN_RAW)


def structure_bos_reference_ruleset() -> Ruleset:
    return parse_ruleset(_STRUCTURE_BOS_RAW)


def _metrics_dict(m: Metrics) -> dict[str, Any]:
    return {
        "n_bars": m.n_bars,
        "total_return": m.total_return,
        "cagr": m.cagr,
        "sharpe": m.sharpe,
        "sortino": m.sortino,
        "max_drawdown": m.max_drawdown,
        "num_trades": m.num_trades,
        "win_rate": m.win_rate,
        "profit_factor": m.profit_factor if m.profit_factor != float("inf") else None,
        "expectancy": m.expectancy,
        "exposure": m.exposure,
        "win_rate_gross": m.win_rate_gross,
        "profit_factor_gross": (
            m.profit_factor_gross if m.profit_factor_gross != float("inf") else None
        ),
        "expectancy_gross": m.expectancy_gross,
        "metrics_basis": "net_v1",
    }


def _buy_hold_backtest(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    commission_bps: float,
    slippage_bps: float,
) -> BacktestResult:
    desired = [Direction.LONG] * len(candles)
    return run_backtest(
        candles,
        desired,
        symbol=symbol,
        timeframe=timeframe,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )


@dataclass(frozen=True)
class ReferenceBaselineRow:
    id: str
    kind: str  # buy_hold | donchian_breakout | structure_bos
    engine: str  # run_backtest | ruleset_atr
    n_bars: int
    commission_bps: float
    slippage_bps: float
    metrics: dict[str, Any]
    n_signals: int | None = None
    n_matching_bars: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "engine": self.engine,
            "n_bars": self.n_bars,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "metrics": self.metrics,
            "n_signals": self.n_signals,
            "n_matching_bars": self.n_matching_bars,
        }


@dataclass(frozen=True)
class ReferenceBaselinesReport:
    symbol: str
    timeframe: str
    n_bars: int
    commission_bps: float
    slippage_bps: float
    baselines: tuple[ReferenceBaselineRow, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "baselines": [b.to_dict() for b in self.baselines],
            "notes": list(self.notes),
        }


def _row_from_study(
    study: RulesetStudyResult,
    *,
    kind: str,
    commission_bps: float,
    slippage_bps: float,
) -> ReferenceBaselineRow:
    if study.backtest is None:
        raise ValueError(f"ruleset study {study.ruleset.id} missing backtest")
    return ReferenceBaselineRow(
        id=study.ruleset.id,
        kind=kind,
        engine="ruleset_atr",
        n_bars=study.n_bars,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        metrics=_metrics_dict(study.backtest.metrics),
        n_signals=study.n_signals,
        n_matching_bars=study.n_matching_bars,
    )


def run_reference_baselines_on_candles(
    candles: Sequence[Candle],
    *,
    symbol: str = "",
    timeframe: str = "",
    commission_bps: float = DEFAULT_COMMISSION_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
) -> ReferenceBaselinesReport:
    """Run buy&hold + Donchian-alone + structure-BOS on the same series/fees."""
    if len(candles) < 2:
        raise ValueError("need at least 2 candles for reference baselines")

    bh = _buy_hold_backtest(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    bh_metrics = compute_metrics(bh)
    buy_hold = ReferenceBaselineRow(
        id=REF_BUY_HOLD_ID,
        kind="buy_hold",
        engine="run_backtest",
        n_bars=bh.n_bars,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        metrics=_metrics_dict(bh_metrics),
        n_signals=None,
        n_matching_bars=None,
    )

    donchian_raw = {
        **_DONCHIAN_RAW,
        "stop_atr": float(stop_atr),
        "target_atr": float(target_atr),
    }
    structure_raw = {
        **_STRUCTURE_BOS_RAW,
        "stop_atr": float(stop_atr),
        "target_atr": float(target_atr),
    }

    donchian_study = study_ruleset_on_candles(
        candles,
        parse_ruleset(donchian_raw),
        symbol=symbol,
        timeframe=timeframe,
        with_backtest=True,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    structure_study = study_ruleset_on_candles(
        candles,
        parse_ruleset(structure_raw),
        symbol=symbol,
        timeframe=timeframe,
        with_backtest=True,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )

    notes = (
        "Fees identical across baselines (Lab defaults 5+3 bps unless overridden).",
        "Buy&hold = always LONG via run_backtest (net_v2 engine fees).",
        "Donchian / structure = ruleset ATR SL/TP (stop_atr/target_atr).",
        "DÉCISION CURSOR — structure seule = bos_bullish (C_BOS), pas Ichimoku-only.",
    )

    return ReferenceBaselinesReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        baselines=(
            buy_hold,
            _row_from_study(
                donchian_study,
                kind="donchian_breakout",
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            ),
            _row_from_study(
                structure_study,
                kind="structure_bos",
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
            ),
        ),
        notes=notes,
    )


def catalog_reference_ruleset_ids() -> tuple[str, ...]:
    """Ids expected in the builtin catalog (Donchian + structure; not buy&hold)."""
    return (REF_DONCHIAN_ID, REF_STRUCTURE_BOS_ID)


def load_catalog_reference_rulesets() -> list[Ruleset]:
    return [get_builtin_ruleset(rid) for rid in catalog_reference_ruleset_ids()]
