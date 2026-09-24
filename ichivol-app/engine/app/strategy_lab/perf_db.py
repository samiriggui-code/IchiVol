"""Strategy Lab Performance DB — Phase 4.

Persist ruleset study results (event study + ATR backtest) so experiments
can be listed, compared, and re-read without recomputing. Does not vote in
the live pipeline.

T10b — optional ``hypothesis_id`` lineage tag + display-only complexity.
Complexity never auto-rejects a study (prerequisite for T9g ablation).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import StrategyLabExperiment
from app.strategy_lab.event_study import event_study_dict
from app.strategy_lab.run_ruleset import RulesetStudyResult

ENGINE_VERSION = "strategy_lab_v1"
METRICS_BASIS_NET_V1 = "net_v1"

_COMPOSITION_KEYS = frozenset({"all", "any"})


def _exit_rule_label(rs) -> str:
    """Compact exit description for Perf DB (additive; ATR always present)."""
    parts = ["atr_stop_target"]
    if rs.exit.condition_group is not None:
        parts.append("signal")
    if rs.exit.max_hold_bars is not None:
        parts.append(f"max_hold={rs.exit.max_hold_bars}")
    return "+".join(parts)


def _dataset_version(symbol: str, timeframe: str, n_bars: int, start: int | None, end: int | None) -> str:
    return f"{symbol}:{timeframe}:bars={n_bars}:t={start or 0}-{end or 0}"


def _parameters_with_levier(bt, parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Stamp ``levier: true`` when Lab reinforce.max_exposure > 1."""
    out = dict(parameters or {})
    if bt is not None and getattr(bt, "levier", False):
        out["levier"] = True
    return out


def _count_condition_leaves(raw: Any) -> int:
    """Count leaf condition keys in flat or all/any composition."""
    if not isinstance(raw, Mapping) or not raw:
        return 0
    keys = {str(k) for k in raw.keys()}
    if keys & _COMPOSITION_KEYS:
        n = 0
        for group in ("all", "any"):
            block = raw.get(group)
            if isinstance(block, Mapping):
                n += len(block)
        return n
    return len(raw)


def ruleset_complexity(rules_json: Mapping[str, Any] | None) -> dict[str, Any]:
    """Display-only complexity score derived from persisted ``rules_json``.

    Never used to auto-reject experiments (T10b hard rule — T9g may warn later).
    """
    if not rules_json:
        return {
            "score": 0,
            "entry_leaves": 0,
            "exit_leaves": 0,
            "exit_extras": 0,
            "note": "display-only; no auto-reject",
        }
    entry_leaves = _count_condition_leaves(rules_json.get("conditions"))
    exit_block = rules_json.get("exit")
    exit_leaves = 0
    exit_extras = 0
    if isinstance(exit_block, Mapping):
        exit_leaves = _count_condition_leaves(exit_block.get("conditions"))
        if exit_block.get("max_hold_bars") is not None:
            exit_extras += 1
        trail = exit_block.get("trail")
        if isinstance(trail, Mapping) and trail:
            exit_extras += 1
        partial = exit_block.get("partial_tp")
        if isinstance(partial, list):
            exit_extras += len(partial)
        reinforce = exit_block.get("reinforce")
        if isinstance(reinforce, Mapping) and reinforce:
            exit_extras += 1
            exit_leaves += _count_condition_leaves(reinforce.get("conditions"))
    score = entry_leaves + exit_leaves + exit_extras
    return {
        "score": score,
        "entry_leaves": entry_leaves,
        "exit_leaves": exit_leaves,
        "exit_extras": exit_extras,
        "note": "display-only; no auto-reject",
    }


def _resolve_hypothesis_id(
    *,
    hypothesis_id: str | None,
    parameters: dict[str, Any] | None,
) -> str | None:
    if hypothesis_id is not None:
        hid = str(hypothesis_id).strip()
        return hid or None
    if parameters and parameters.get("hypothesis_id") is not None:
        hid = str(parameters["hypothesis_id"]).strip()
        return hid or None
    return None


def lineage_count_for(
    session: Session,
    row: StrategyLabExperiment,
) -> int:
    """How many Perf DB rows share this experiment's lineage key.

    Prefer ``hypothesis_id`` when set; else ``ruleset_id`` + symbol + timeframe.
    """
    if row.hypothesis_id:
        stmt = (
            select(func.count())
            .select_from(StrategyLabExperiment)
            .where(StrategyLabExperiment.hypothesis_id == row.hypothesis_id)
        )
    else:
        stmt = (
            select(func.count())
            .select_from(StrategyLabExperiment)
            .where(
                StrategyLabExperiment.ruleset_id == row.ruleset_id,
                StrategyLabExperiment.symbol == row.symbol,
                StrategyLabExperiment.timeframe == row.timeframe,
            )
        )
    return int(session.scalar(stmt) or 0)


def _lineage_counts_batch(
    session: Session,
    rows: Sequence[StrategyLabExperiment],
) -> dict[str, int]:
    """Map experiment id → lineage_count without N+1 when listing."""
    if not rows:
        return {}
    by_hyp: dict[str, list[str]] = {}
    by_ruleset: dict[tuple[str, str, str], list[str]] = {}
    for r in rows:
        if r.hypothesis_id:
            by_hyp.setdefault(r.hypothesis_id, []).append(r.id)
        else:
            key = (r.ruleset_id, r.symbol, r.timeframe)
            by_ruleset.setdefault(key, []).append(r.id)

    out: dict[str, int] = {}
    for hid, ids in by_hyp.items():
        n = session.scalar(
            select(func.count())
            .select_from(StrategyLabExperiment)
            .where(StrategyLabExperiment.hypothesis_id == hid)
        )
        count = int(n or 0)
        for eid in ids:
            out[eid] = count
    for (rid, sym, tf), ids in by_ruleset.items():
        n = session.scalar(
            select(func.count())
            .select_from(StrategyLabExperiment)
            .where(
                StrategyLabExperiment.ruleset_id == rid,
                StrategyLabExperiment.symbol == sym,
                StrategyLabExperiment.timeframe == tf,
            )
        )
        count = int(n or 0)
        for eid in ids:
            out[eid] = count
    return out


def save_experiment(
    session: Session,
    study: RulesetStudyResult,
    *,
    market_regime: str = "GLOBAL",
    parameters: dict[str, Any] | None = None,
    engine_version: str = ENGINE_VERSION,
    hypothesis_id: str | None = None,
) -> StrategyLabExperiment:
    """Insert one StrategyLabExperiment row from a completed RulesetStudyResult."""
    rs = study.ruleset
    es = study.event_study
    bt = study.backtest

    start = es.events[0].signal_time if es.events else None
    end = es.events[-1].signal_time if es.events else None
    # Prefer candle span from backtest if available
    if study.n_bars and es.events:
        start = es.events[0].signal_time
        end = es.events[-1].entry_time

    exit_reasons: dict = {}
    number_of_trades = 0
    win_rate = profit_factor = expectancy = max_dd = None
    sharpe = sortino = total_return = cagr = exposure = None
    if bt is not None:
        exit_reasons = {}
        for d in bt.details:
            exit_reasons[d.exit_reason] = exit_reasons.get(d.exit_reason, 0) + 1
        m = bt.metrics
        number_of_trades = m.num_trades
        win_rate = m.win_rate
        profit_factor = m.profit_factor if m.profit_factor != float("inf") else None
        expectancy = m.expectancy
        max_dd = m.max_drawdown
        sharpe = m.sharpe
        sortino = m.sortino
        total_return = m.total_return
        cagr = m.cagr
        exposure = m.exposure

    params = _parameters_with_levier(bt, parameters)
    hid = _resolve_hypothesis_id(hypothesis_id=hypothesis_id, parameters=params)

    row = StrategyLabExperiment(
        ruleset_id=rs.id,
        ruleset_version=rs.version,
        symbol=study.symbol,
        timeframe=study.timeframe,
        market_regime=market_regime,
        hypothesis_id=hid,
        date_range_start=start,
        date_range_end=end,
        rules_json=rs.to_dict(),
        entry_rule=rs.entry,
        exit_rule=_exit_rule_label(rs),
        stop_rule=f"{rs.stop_atr}*ATR",
        target_rule=f"{rs.target_atr}*ATR",
        n_bars=study.n_bars,
        n_signals=study.n_signals,
        n_matching_bars=study.n_matching_bars,
        number_of_trades=number_of_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown=max_dd,
        sharpe=sharpe,
        sortino=sortino,
        total_return=total_return,
        cagr=cagr,
        exposure=exposure,
        mean_mfe_atr=es.mean_mfe_atr,
        mean_mae_atr=es.mean_mae_atr,
        median_mfe_atr=es.median_mfe_atr,
        median_mae_atr=es.median_mae_atr,
        pct_hit_plus_r_before_minus_r=es.pct_hit_plus_r_before_minus_r,
        n_resolved_r=es.n_resolved_r,
        exit_reasons_json=exit_reasons,
        event_study_json=event_study_dict(es, include_events=False),
        parameters_json=params,
        dataset_version=_dataset_version(
            study.symbol, study.timeframe, study.n_bars, start, end
        ),
        engine_version=engine_version,
        metrics_basis=METRICS_BASIS_NET_V1 if bt is not None else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def experiment_dict(
    row: StrategyLabExperiment,
    *,
    lineage_count: int | None = None,
) -> dict:
    complexity = ruleset_complexity(row.rules_json)
    return {
        "experiment_id": row.id,
        "ruleset_id": row.ruleset_id,
        "ruleset_version": row.ruleset_version,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "market_regime": row.market_regime,
        "hypothesis_id": row.hypothesis_id,
        "lineage_count": lineage_count,
        "complexity": complexity,
        "date_range_start": row.date_range_start,
        "date_range_end": row.date_range_end,
        "rules_json": row.rules_json,
        "entry_rule": row.entry_rule,
        "exit_rule": row.exit_rule,
        "stop_rule": row.stop_rule,
        "target_rule": row.target_rule,
        "n_bars": row.n_bars,
        "n_signals": row.n_signals,
        "n_matching_bars": row.n_matching_bars,
        "number_of_trades": row.number_of_trades,
        "win_rate": row.win_rate,
        "profit_factor": row.profit_factor,
        "expectancy": row.expectancy,
        "max_drawdown": row.max_drawdown,
        "sharpe": row.sharpe,
        "sortino": row.sortino,
        "total_return": row.total_return,
        "cagr": row.cagr,
        "exposure": row.exposure,
        "mean_mfe_atr": row.mean_mfe_atr,
        "mean_mae_atr": row.mean_mae_atr,
        "median_mfe_atr": row.median_mfe_atr,
        "median_mae_atr": row.median_mae_atr,
        "pct_hit_plus_r_before_minus_r": row.pct_hit_plus_r_before_minus_r,
        "n_resolved_r": row.n_resolved_r,
        "exit_reasons": row.exit_reasons_json,
        "event_study": row.event_study_json,
        "parameters": row.parameters_json,
        "dataset_version": row.dataset_version,
        "engine_version": row.engine_version,
        "metrics_basis": row.metrics_basis,  # None = legacy gross; "net_v1" = net of fees
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def experiments_dicts(
    session: Session,
    rows: Sequence[StrategyLabExperiment],
) -> list[dict]:
    """Serialize rows with batched lineage_count (T10b)."""
    counts = _lineage_counts_batch(session, rows)
    return [
        experiment_dict(r, lineage_count=counts.get(r.id))
        for r in rows
    ]


def get_experiment(session: Session, experiment_id: str) -> StrategyLabExperiment | None:
    return session.get(StrategyLabExperiment, experiment_id)


def list_experiments(
    session: Session,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    ruleset_id: str | None = None,
    market_regime: str | None = None,
    engine_version: str | None = None,
    hypothesis_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StrategyLabExperiment]:
    stmt = select(StrategyLabExperiment).order_by(StrategyLabExperiment.created_at.desc())
    if symbol:
        stmt = stmt.where(StrategyLabExperiment.symbol == symbol.upper())
    if timeframe:
        stmt = stmt.where(StrategyLabExperiment.timeframe == timeframe)
    if ruleset_id:
        stmt = stmt.where(StrategyLabExperiment.ruleset_id == ruleset_id)
    if market_regime:
        stmt = stmt.where(StrategyLabExperiment.market_regime == market_regime)
    if engine_version:
        stmt = stmt.where(StrategyLabExperiment.engine_version == engine_version)
    if hypothesis_id:
        stmt = stmt.where(StrategyLabExperiment.hypothesis_id == hypothesis_id)
    stmt = stmt.offset(max(0, offset)).limit(min(limit, 200))
    return list(session.scalars(stmt))


def compare_rulesets(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    ruleset_ids: Sequence[str],
    market_regime: str = "GLOBAL",
) -> list[StrategyLabExperiment]:
    """Latest experiment per ruleset_id for symbol/timeframe/regime."""
    out: list[StrategyLabExperiment] = []
    for rid in ruleset_ids:
        rows = list_experiments(
            session,
            symbol=symbol,
            timeframe=timeframe,
            ruleset_id=rid,
            market_regime=market_regime,
            limit=1,
        )
        if rows:
            out.append(rows[0])
    return out


def persist_study_result(
    study: RulesetStudyResult,
    *,
    market_regime: str = "GLOBAL",
    parameters: dict[str, Any] | None = None,
    hypothesis_id: str | None = None,
) -> dict:
    """Open a session, save, return experiment_dict. Caller-facing helper."""
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        row = save_experiment(
            session,
            study,
            market_regime=market_regime,
            parameters=parameters,
            hypothesis_id=hypothesis_id,
        )
        return experiment_dict(row, lineage_count=lineage_count_for(session, row))
    finally:
        session.close()
