"""T6 — Claude Auditor scaffolding (observation / post-outcome only).

Produces structured ``AuditReport`` objects for human (or Claude) review.
Never mutates strategy, paper gates, or live decision scores.
Hypotheses are suggestions only — status stays ``proposed``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from app.strategy_lab.ruleset_backtest import RulesetTradeDetail

AUDITOR_VERSION = "audit_report_v0"

_DISCLAIMER = (
    "AuditReport — post-outcome review only. Hypotheses are proposed for "
    "human Lab experiments; never auto-applied to production strategy."
)


@dataclass(frozen=True)
class AuditHypothesis:
    id: str
    statement: str
    suggested_experiment: str
    status: str = "proposed"  # never auto_applied / never live

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "suggested_experiment": self.suggested_experiment,
            "status": self.status,
        }


@dataclass(frozen=True)
class AuditReport:
    version: str
    symbol: str
    timeframe: str
    ruleset_id: str | None
    trade_index: int
    subject: dict
    outcome: dict
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    hypotheses: list[AuditHypothesis] = field(default_factory=list)
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ruleset_id": self.ruleset_id,
            "trade_index": self.trade_index,
            "subject": dict(self.subject),
            "outcome": dict(self.outcome),
            "what_worked": list(self.what_worked),
            "what_failed": list(self.what_failed),
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "disclaimer": self.disclaimer,
        }


def _leaf_keys(why: Sequence[dict], *, passed: bool) -> list[str]:
    out: list[str] = []
    for leaf in why:
        if not isinstance(leaf, dict):
            continue
        ok = leaf.get("passed")
        if ok is passed:
            key = leaf.get("key")
            if isinstance(key, str) and key:
                out.append(key)
    return out


def _hypotheses_for_trade(
    detail: RulesetTradeDetail,
    *,
    net_pct: float,
) -> list[AuditHypothesis]:
    hyps: list[AuditHypothesis] = []
    exit_reason = detail.exit_reason
    if exit_reason == "stop" and net_pct < 0:
        hyps.append(
            AuditHypothesis(
                id="h_stop_widen_or_filter",
                statement=(
                    "Trade exited via stop at a net loss — entry timing or stop "
                    "distance may be misaligned with regime."
                ),
                suggested_experiment=(
                    "Lab: ablation on entry conditions + regime_slices on this ruleset"
                ),
            )
        )
    if exit_reason == "max_hold":
        hyps.append(
            AuditHypothesis(
                id="h_max_hold_too_short",
                statement="Exit by max_hold — trend may need more room.",
                suggested_experiment=(
                    "Lab: walk_forward_opt on exit.max_hold_bars (IS only → OOS)"
                ),
            )
        )
    failed_entry = _leaf_keys(detail.why_entered, passed=False)
    if failed_entry:
        hyps.append(
            AuditHypothesis(
                id="h_entry_leaves_weak",
                statement=(
                    "Some entry leaves failed at signal time: "
                    + ", ".join(failed_entry[:8])
                ),
                suggested_experiment=(
                    "Lab: compare_family_weights / run_family_weights_study on symbol"
                ),
            )
        )
    if net_pct > 0 and exit_reason == "target":
        hyps.append(
            AuditHypothesis(
                id="h_winner_target_ok",
                statement="Target hit with net profit — preserve this exit geometry in A/B.",
                suggested_experiment=(
                    "Lab: leave-one-out ablation; keep target_atr if expectancy holds OOS"
                ),
            )
        )
    if not hyps:
        hyps.append(
            AuditHypothesis(
                id="h_baseline_review",
                statement="No strong heuristic flag — review WHY ENTERED/EXITED manually.",
                suggested_experiment="Lab: run_event_study + regime_slices for context",
            )
        )
    return hyps


def build_audit_report_from_trade(
    detail: RulesetTradeDetail,
    *,
    symbol: str,
    timeframe: str,
    ruleset_id: str | None,
    trade_index: int,
) -> AuditReport:
    """Deterministic post-outcome audit from one ruleset trade detail."""
    t = detail.trade
    net_pct = float(math.exp(t.net_log_return) - 1.0)
    gross_pct = float(math.exp(t.log_return) - 1.0)
    passed = _leaf_keys(detail.why_entered, passed=True)
    failed = _leaf_keys(detail.why_entered, passed=False)
    what_worked = list(passed)
    what_failed: list[str] = []
    if net_pct < 0:
        what_failed.append(f"net_loss:{net_pct:.4%}")
    if detail.exit_reason == "stop" and net_pct < 0:
        what_failed.append("stopped_out")
    if failed:
        what_failed.extend(f"entry_leaf_failed:{k}" for k in failed)
    if net_pct >= 0 and detail.exit_reason in ("target", "signal"):
        what_worked.append(f"exit_{detail.exit_reason}")

    return AuditReport(
        version=AUDITOR_VERSION,
        symbol=symbol,
        timeframe=timeframe,
        ruleset_id=ruleset_id,
        trade_index=trade_index,
        subject={
            "direction": t.direction.value,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "exit_reason": detail.exit_reason,
            "stop_price": detail.stop_price,
            "target_price": detail.target_price,
            "why_entered": list(detail.why_entered),
            "why_exited": list(detail.why_exited),
        },
        outcome={
            "net_return_pct": net_pct,
            "gross_return_pct": gross_pct,
            "cost_log": t.cost_log,
            "log_return_gross": t.log_return,
            "log_return_net": t.net_log_return,
        },
        what_worked=what_worked,
        what_failed=what_failed,
        hypotheses=_hypotheses_for_trade(detail, net_pct=net_pct),
    )
