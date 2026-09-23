"""Researcher scaffolding — turn AuditReport hypotheses into Lab experiment plans.

Never auto-runs backtests, never writes Perf DB, never changes live strategy.
Status is always ``proposed``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.auditor import AuditHypothesis, AuditReport

RESEARCHER_VERSION = "researcher_plan_v0"

_DISCLAIMER = (
    "Researcher experiment plan — proposed for human review only. "
    "Never auto-runs Lab studies or mutates production strategy."
)


@dataclass(frozen=True)
class ProposedExperimentStep:
    tool: str
    args: dict[str, Any]
    purpose: str

    def to_dict(self) -> dict:
        return {"tool": self.tool, "args": dict(self.args), "purpose": self.purpose}


@dataclass(frozen=True)
class ProposedExperimentPlan:
    version: str
    status: str
    source_hypothesis_ids: list[str]
    symbol: str
    timeframe: str
    ruleset_id: str | None
    steps: list[ProposedExperimentStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "status": self.status,
            "source_hypothesis_ids": list(self.source_hypothesis_ids),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ruleset_id": self.ruleset_id,
            "steps": [s.to_dict() for s in self.steps],
            "notes": list(self.notes),
            "disclaimer": self.disclaimer,
        }


def _json_stable(obj: Mapping[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _steps_for_hypothesis(
    hyp: AuditHypothesis,
    *,
    symbol: str,
    timeframe: str,
    ruleset_id: str | None,
) -> list[ProposedExperimentStep]:
    rid = ruleset_id or "IV_ICHIMOKU_ONLY_LONG_001"
    base_args = {"symbol": symbol, "timeframe": timeframe, "ruleset_id": rid}
    hid = hyp.id
    steps: list[ProposedExperimentStep] = []

    if hid == "h_stop_widen_or_filter":
        steps.append(
            ProposedExperimentStep(
                tool="run_regime_slices",
                args=dict(base_args),
                purpose="Check whether stop-outs concentrate in one regime",
            )
        )
        steps.append(
            ProposedExperimentStep(
                tool="run_ablation",
                args={**base_args, "mode": "leave_one_out"},
                purpose="Ablate entry leaves that may cause weak entries into stops",
            )
        )
    elif hid == "h_max_hold_too_short":
        steps.append(
            ProposedExperimentStep(
                tool="run_walk_forward_opt",
                args={
                    **base_args,
                    "grid": {"max_hold_bars": [24, 48, 72, 96]},
                    "objective": "expectancy",
                },
                purpose="IS grid on max_hold then measure OOS (anti-overfit)",
            )
        )
    elif hid == "h_entry_leaves_weak":
        steps.append(
            ProposedExperimentStep(
                tool="compare_family_weights",
                args={"symbol": symbol, "timeframe": timeframe},
                purpose="See if family-weight profiles disagree at entry",
            )
        )
        steps.append(
            ProposedExperimentStep(
                tool="propose_ruleset_edit",
                args={
                    "base_ruleset_id": rid,
                    "patch": {
                        "op": "set_leaf",
                        "group": "all",
                        "key": "rvol_min",
                        "value": 2.0,
                    },
                },
                purpose="Propose tighter participation leaf for Lab review",
            )
        )
    elif hid == "h_winner_target_ok":
        steps.append(
            ProposedExperimentStep(
                tool="run_event_study",
                args={"symbol": symbol, "timeframe": timeframe, "variant": "PIPELINE"},
                purpose="Confirm target-hit winners still look healthy out-of-sample window",
            )
        )
    else:
        steps.append(
            ProposedExperimentStep(
                tool="run_ruleset_event_study",
                args=dict(base_args),
                purpose=f"Baseline Lab study for hypothesis {hid}",
            )
        )
        steps.append(
            ProposedExperimentStep(
                tool="run_monte_carlo",
                args={**base_args, "min_trades": 20},
                purpose="Risk-of-ruin context before promoting any change",
            )
        )
    return steps


def propose_experiment_plan(
    report: AuditReport | Mapping[str, Any],
    *,
    hypothesis_ids: Sequence[str] | None = None,
) -> ProposedExperimentPlan:
    """Build a proposed Lab plan from an AuditReport (object or dict)."""
    if isinstance(report, AuditReport):
        symbol = report.symbol
        timeframe = report.timeframe
        ruleset_id = report.ruleset_id
        hyps = list(report.hypotheses)
    else:
        symbol = str(report.get("symbol", ""))
        timeframe = str(report.get("timeframe", "1h"))
        ruleset_id = report.get("ruleset_id")
        if ruleset_id is not None:
            ruleset_id = str(ruleset_id)
        raw_hyps = report.get("hypotheses") or []
        hyps = [
            AuditHypothesis(
                id=str(h.get("id", "h_unknown")),
                statement=str(h.get("statement", "")),
                suggested_experiment=str(h.get("suggested_experiment", "")),
                status=str(h.get("status", "proposed")),
            )
            for h in raw_hyps
            if isinstance(h, Mapping)
        ]

    if hypothesis_ids:
        want = set(hypothesis_ids)
        hyps = [h for h in hyps if h.id in want]
    if not hyps:
        raise ValueError("no hypotheses to plan from")

    steps: list[ProposedExperimentStep] = []
    notes: list[str] = []
    seen_tools: set[tuple[str, str]] = set()
    for h in hyps:
        notes.append(f"{h.id}: {h.statement}")
        for step in _steps_for_hypothesis(
            h, symbol=symbol, timeframe=timeframe, ruleset_id=ruleset_id
        ):
            key = (step.tool, _json_stable(step.args))
            if key in seen_tools:
                continue
            seen_tools.add(key)
            steps.append(step)

    return ProposedExperimentPlan(
        version=RESEARCHER_VERSION,
        status="proposed",
        source_hypothesis_ids=[h.id for h in hyps],
        symbol=symbol,
        timeframe=timeframe,
        ruleset_id=ruleset_id,
        steps=steps,
        notes=notes,
    )
