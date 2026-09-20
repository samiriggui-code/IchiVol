"""Ablation testing â€” Strategy Lab Phase 5.

Build cumulative (or leave-one-out) ruleset variants and run them on the
*same* OHLCV window so each added filter can be judged by whether it
actually improves expectancy / PF / drawdown â€” not by stacking indicators
for their own sake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.agents.types import Direction
from app.market_data.resolve import resolve_and_fetch
from app.strategy_lab.perf_db import persist_study_result
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.run_ruleset import (
    RulesetStudyResult,
    ruleset_study_dict,
    study_ruleset_on_candles,
)

# Default ladder matching the audit brief (LONG bias).
DEFAULT_ABLATION_LAYERS: tuple[tuple[str, dict[str, bool | int | float | str]], ...] = (
    (
        "A_ICHIMOKU",
        {
            "price_above_kumo": True,
            "tenkan_above_kijun": True,
            "tk_cross_age_max": 3,
        },
    ),
    ("B_RVOL", {"rvol_min": 1.5}),
    ("C_BOS", {"bos_bullish": True}),
    ("D_ATR", {"atr_expansion": True}),
    ("E_CMF", {"cmf_min": 0.0}),
)

# Kumo -> RVOL -> Kijun analytics ladder (research).
# Retest is a parallel hypothesis (catalog IV_EXP_E_*), not cumulative on BO bar.
KIJUN_ABLATION_LAYERS: tuple[tuple[str, dict[str, bool | int | float | str]], ...] = (
    ("A_KUMO_BO", {"kumo_breakout_bullish": True}),
    ("B_RVOL", {"rvol_min": 1.5}),
    ("C_KIJUN_SLOPE", {"kijun_slope": "RISING"}),
    ("D_KIJUN_DIST", {"price_kijun_distance_atr_max": 2.0}),
    ("E_KUMO_ORIENT", {"kumo_orientation": "BULLISH"}),
)

# T-EXP ladder (docs/ICHIVOL_V2_ROADMAP.md): Ichimoku -> RVOL -> structure ->
# PPO -> BEST Cloud. Cumulative steps = models A (A+B), B (+C), C (+D), D (+E).
# PPO/BEST Cloud parameters are fixed a priori (12/26/9 ; EMA 20/50).
PPO_ABLATION_LAYERS: tuple[tuple[str, dict[str, bool | int | float | str]], ...] = (
    (
        "A_ICHIMOKU",
        {
            "price_above_kumo": True,
            "tenkan_above_kijun": True,
            "tk_cross_age_max": 3,
        },
    ),
    ("B_RVOL", {"rvol_min": 1.5}),
    ("C_BOS", {"bos_bullish": True}),
    ("D_PPO", {"ppo_momentum": "STRONG_BULLISH"}),
    ("E_BEST_CLOUD", {"best_cloud_trend": "BULLISH"}),
)

ABLATION_LADDERS = {
    "default": DEFAULT_ABLATION_LAYERS,
    "kijun": KIJUN_ABLATION_LAYERS,
    "ppo": PPO_ABLATION_LAYERS,
}


@dataclass(frozen=True)
class AblationStep:
    label: str
    ruleset: Ruleset
    study: RulesetStudyResult
    experiment_id: str | None = None


@dataclass(frozen=True)
class AblationDelta:
    from_label: str
    to_label: str
    added_conditions: list[str]
    n_signals_delta: int
    n_trades_delta: int
    win_rate_delta: float | None
    profit_factor_delta: float | None
    expectancy_delta: float | None
    max_drawdown_delta: float | None
    sharpe_delta: float | None
    mean_mfe_atr_delta: float | None
    mean_mae_atr_delta: float | None
    improves_expectancy: bool | None
    improves_profit_factor: bool | None
    note: str


@dataclass(frozen=True)
class AblationResult:
    symbol: str
    timeframe: str
    mode: str
    n_bars: int
    steps: list[AblationStep]
    deltas: list[AblationDelta]


def build_cumulative_rulesets(
    layers: Sequence[tuple[str, Mapping[str, bool | int | float | str]]],
    *,
    base_id: str = "IV_ABLATION",
    direction: Direction = Direction.LONG,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    version: str = "1",
) -> list[Ruleset]:
    """A, A+B, A+B+Câ€¦ â€” each step adds one layer's conditions."""
    if not layers:
        raise ValueError("ablation layers must be non-empty")
    accumulated: dict[str, bool | int | float | str] = {}
    out: list[Ruleset] = []
    for label, conds in layers:
        accumulated.update(dict(conds))
        out.append(
            parse_ruleset(
                {
                    "id": f"{base_id}__{label}",
                    "version": version,
                    "direction": direction.value,
                    "description": f"Ablation cumulative step {label}",
                    "conditions": dict(accumulated),
                    "entry": "next_open",
                    "stop_atr": stop_atr,
                    "target_atr": target_atr,
                    "meta": {"ablation_label": label, "ablation_mode": "cumulative"},
                }
            )
        )
    return out


def build_leave_one_out_rulesets(
    full_conditions: Mapping[str, bool | int | float | str],
    *,
    base_id: str = "IV_ABLATION",
    direction: Direction = Direction.LONG,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    version: str = "1",
) -> list[Ruleset]:
    """FULL plus FULL without each key (one at a time)."""
    if len(full_conditions) < 2:
        raise ValueError("leave-one-out needs at least 2 conditions")
    keys = list(full_conditions.keys())
    out: list[Ruleset] = [
        parse_ruleset(
            {
                "id": f"{base_id}__FULL",
                "version": version,
                "direction": direction.value,
                "description": "Ablation full condition set",
                "conditions": dict(full_conditions),
                "entry": "next_open",
                "stop_atr": stop_atr,
                "target_atr": target_atr,
                "meta": {"ablation_label": "FULL", "ablation_mode": "leave_one_out"},
            }
        )
    ]
    for drop in keys:
        remaining = {k: v for k, v in full_conditions.items() if k != drop}
        out.append(
            parse_ruleset(
                {
                    "id": f"{base_id}__NO_{drop.upper()}",
                    "version": version,
                    "direction": direction.value,
                    "description": f"Ablation without {drop}",
                    "conditions": remaining,
                    "entry": "next_open",
                    "stop_atr": stop_atr,
                    "target_atr": target_atr,
                    "meta": {
                        "ablation_label": f"NO_{drop}",
                        "ablation_mode": "leave_one_out",
                        "dropped": drop,
                    },
                }
            )
        )
    return out


def build_leave_one_layer_out_rulesets(
    layers: Sequence[tuple[str, Mapping[str, bool | int | float | str]]],
    *,
    base_id: str = "IV_ABLATION",
    direction: Direction = Direction.LONG,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    version: str = "1",
) -> list[Ruleset]:
    """FULL (all layers) plus FULL without each *layer* (all its conditions).

    Unlike per-key leave-one-out this answers "does removing PPO / BEST Cloud
    / RVOL change anything?" even when a layer carries several conditions.
    Layers must not share condition keys (else a drop would be ambiguous).
    """
    if len(layers) < 2:
        raise ValueError("leave-one-layer-out needs at least 2 layers")
    seen: dict[str, str] = {}
    for label, conds in layers:
        for key in conds:
            if key in seen:
                raise ValueError(
                    f"condition {key!r} is in both layers {seen[key]!r} and {label!r}"
                )
            seen[key] = label

    def _mk(label: str, conds: dict, desc: str, extra: dict) -> Ruleset:
        return parse_ruleset(
            {
                "id": f"{base_id}__{label}",
                "version": version,
                "direction": direction.value,
                "description": desc,
                "conditions": conds,
                "entry": "next_open",
                "stop_atr": stop_atr,
                "target_atr": target_atr,
                "meta": {
                    "ablation_label": label,
                    "ablation_mode": "leave_one_layer_out",
                    **extra,
                },
            }
        )

    full: dict[str, bool | int | float | str] = {}
    for _, conds in layers:
        full.update(dict(conds))
    out = [_mk("FULL", full, "Ablation full layer set", {})]
    for drop_label, drop_conds in layers:
        remaining = {k: v for k, v in full.items() if k not in drop_conds}
        out.append(
            _mk(
                f"NO_{drop_label}",
                remaining,
                f"Ablation without layer {drop_label}",
                {"dropped": drop_label},
            )
        )
    return out


def _metric_pair(
    prev: RulesetStudyResult, curr: RulesetStudyResult
) -> AblationDelta:
    prev_label = str(prev.ruleset.meta.get("ablation_label") or prev.ruleset.id)
    curr_label = str(curr.ruleset.meta.get("ablation_label") or curr.ruleset.id)
    added = [k for k in curr.ruleset.conditions if k not in prev.ruleset.conditions]

    def _bt(study: RulesetStudyResult, attr: str) -> float | None:
        if study.backtest is None:
            return None
        return getattr(study.backtest.metrics, attr)

    def _delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return b - a

    wr_d = _delta(_bt(prev, "win_rate"), _bt(curr, "win_rate"))
    pf_d = _delta(_bt(prev, "profit_factor"), _bt(curr, "profit_factor"))
    exp_d = _delta(_bt(prev, "expectancy"), _bt(curr, "expectancy"))
    dd_d = _delta(_bt(prev, "max_drawdown"), _bt(curr, "max_drawdown"))
    sh_d = _delta(_bt(prev, "sharpe"), _bt(curr, "sharpe"))
    mfe_d = _delta(prev.event_study.mean_mfe_atr, curr.event_study.mean_mfe_atr)
    mae_d = _delta(prev.event_study.mean_mae_atr, curr.event_study.mean_mae_atr)

    n_trades_prev = prev.backtest.metrics.num_trades if prev.backtest else 0
    n_trades_curr = curr.backtest.metrics.num_trades if curr.backtest else 0

    improves_exp = None if exp_d is None else exp_d > 0
    improves_pf = None if pf_d is None else pf_d > 0

    note_parts: list[str] = []
    if improves_exp is True:
        note_parts.append("expectancyâ†‘")
    elif improves_exp is False:
        note_parts.append("expectancyâ†“")
    if improves_pf is True:
        note_parts.append("PFâ†‘")
    elif improves_pf is False:
        note_parts.append("PFâ†“")
    if curr.n_signals < prev.n_signals:
        note_parts.append(f"signals {prev.n_signals}â†’{curr.n_signals}")
    if dd_d is not None and dd_d < 0:
        note_parts.append("DDâ†“")
    elif dd_d is not None and dd_d > 0:
        note_parts.append("DDâ†‘")

    return AblationDelta(
        from_label=prev_label,
        to_label=curr_label,
        added_conditions=added,
        n_signals_delta=curr.n_signals - prev.n_signals,
        n_trades_delta=n_trades_curr - n_trades_prev,
        win_rate_delta=wr_d,
        profit_factor_delta=pf_d,
        expectancy_delta=exp_d,
        max_drawdown_delta=dd_d,
        sharpe_delta=sh_d,
        mean_mfe_atr_delta=mfe_d,
        mean_mae_atr_delta=mae_d,
        improves_expectancy=improves_exp,
        improves_profit_factor=improves_pf,
        note="; ".join(note_parts) if note_parts else "no clear lift",
    )


def parse_layers(raw: Sequence[Mapping[str, Any]] | None) -> list[tuple[str, dict[str, bool | int | float | str]]]:
    """Parse [{label, conditions}, ...] from API body; None â†’ default ladder."""
    if raw is None:
        return [(lab, dict(conds)) for lab, conds in DEFAULT_ABLATION_LAYERS]
    out: list[tuple[str, dict[str, bool | int | float | str]]] = []
    for i, item in enumerate(raw):
        label = str(item.get("label") or f"L{i}").strip()
        conds = item.get("conditions")
        if not isinstance(conds, Mapping) or not conds:
            raise ValueError(f"layer {label!r} needs non-empty conditions")
        # Validate via parse_ruleset on a throwaway cumulative later; soft-check keys here
        out.append((label, dict(conds)))  # type: ignore[arg-type]
    if not out:
        raise ValueError("layers must be non-empty")
    return out


def run_ablation_on_candles(
    candles: Sequence,
    *,
    symbol: str,
    timeframe: str,
    mode: str = "cumulative",
    layers: Sequence[tuple[str, Mapping[str, bool | int | float | str]]] | None = None,
    full_conditions: Mapping[str, bool | int | float | str] | None = None,
    direction: Direction = Direction.LONG,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    base_id: str = "IV_ABLATION",
    persist: bool = False,
    horizons: Sequence[int] = (1, 3, 5, 10),
) -> AblationResult:
    mode_l = mode.lower().strip()
    if mode_l == "cumulative":
        layer_list = list(layers) if layers is not None else [
            (lab, dict(c)) for lab, c in DEFAULT_ABLATION_LAYERS
        ]
        rulesets = build_cumulative_rulesets(
            layer_list,
            base_id=base_id,
            direction=direction,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )
    elif mode_l in ("leave_one_layer_out", "loll"):
        layer_list = list(layers) if layers is not None else [
            (lab, dict(c)) for lab, c in DEFAULT_ABLATION_LAYERS
        ]
        rulesets = build_leave_one_layer_out_rulesets(
            layer_list,
            base_id=base_id,
            direction=direction,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )
    elif mode_l in ("leave_one_out", "loo"):
        if full_conditions is None:
            # Default: merge default ladder into full set
            full: dict[str, bool | int | float | str] = {}
            for _, c in DEFAULT_ABLATION_LAYERS:
                full.update(c)
            full_conditions = full
        rulesets = build_leave_one_out_rulesets(
            full_conditions,
            base_id=base_id,
            direction=direction,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )
    else:
        raise ValueError(
            "mode must be 'cumulative', 'leave_one_out' or 'leave_one_layer_out'"
        )

    steps: list[AblationStep] = []
    for rs in rulesets:
        study = study_ruleset_on_candles(
            candles,
            rs,
            symbol=symbol,
            timeframe=timeframe,
            horizons=horizons,
            with_backtest=True,
        )
        exp_id = None
        if persist:
            saved = persist_study_result(
                study,
                parameters={
                    "ablation": True,
                    "ablation_mode": mode_l,
                    "ablation_label": rs.meta.get("ablation_label"),
                },
            )
            exp_id = saved.get("experiment_id")
        steps.append(
            AblationStep(
                label=str(rs.meta.get("ablation_label") or rs.id),
                ruleset=rs,
                study=study,
                experiment_id=exp_id,
            )
        )

    deltas: list[AblationDelta] = []
    if mode_l == "cumulative":
        for i in range(1, len(steps)):
            deltas.append(_metric_pair(steps[i - 1].study, steps[i].study))
    else:
        # Compare each leave-one-out against FULL (index 0)
        full_study = steps[0].study
        for step in steps[1:]:
            deltas.append(_metric_pair(step.study, full_study))

    return AblationResult(
        symbol=symbol,
        timeframe=timeframe,
        mode=mode_l,
        n_bars=len(candles),
        steps=steps,
        deltas=deltas,
    )


def run_ablation(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "cumulative",
    layers: Sequence[Mapping[str, Any]] | None = None,
    direction: str = "LONG",
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    base_id: str = "IV_ABLATION",
    persist: bool = False,
    exchange: str = "binance",
) -> AblationResult:
    _p, _s, candles = resolve_and_fetch(
        symbol, timeframe, limit, default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles for {symbol} {timeframe}")
    dir_enum = Direction(direction.upper())
    if dir_enum == Direction.NEUTRAL:
        raise ValueError("direction must be LONG or SHORT")
    parsed_layers = (
        parse_layers(layers)
        if mode.lower() in ("cumulative", "leave_one_layer_out")
        else None
    )
    return run_ablation_on_candles(
        candles,
        symbol=symbol.upper(),
        timeframe=timeframe,
        mode=mode,
        layers=parsed_layers,
        direction=dir_enum,
        stop_atr=stop_atr,
        target_atr=target_atr,
        base_id=base_id,
        persist=persist,
    )


def ablation_dict(result: AblationResult) -> dict:
    return {
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "mode": result.mode,
        "n_bars": result.n_bars,
        "steps": [
            {
                "label": s.label,
                "experiment_id": s.experiment_id,
                "ruleset": s.ruleset.to_dict(),
                "n_signals": s.study.n_signals,
                "n_matching_bars": s.study.n_matching_bars,
                "study": ruleset_study_dict(s.study, include_events=False),
            }
            for s in result.steps
        ],
        "deltas": [
            {
                "from_label": d.from_label,
                "to_label": d.to_label,
                "added_conditions": d.added_conditions,
                "n_signals_delta": d.n_signals_delta,
                "n_trades_delta": d.n_trades_delta,
                "win_rate_delta": d.win_rate_delta,
                "profit_factor_delta": d.profit_factor_delta,
                "expectancy_delta": d.expectancy_delta,
                "max_drawdown_delta": d.max_drawdown_delta,
                "sharpe_delta": d.sharpe_delta,
                "mean_mfe_atr_delta": d.mean_mfe_atr_delta,
                "mean_mae_atr_delta": d.mean_mae_atr_delta,
                "improves_expectancy": d.improves_expectancy,
                "improves_profit_factor": d.improves_profit_factor,
                "note": d.note,
            }
            for d in result.deltas
        ],
        "note": (
            "Ablation on one shared OHLCV window. "
            "A filter must improve expectancy and/or PF to justify keeping it."
        ),
    }



