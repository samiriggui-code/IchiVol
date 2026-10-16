"""V1-G — policy calibration (thresholds / weights), NOT LLM weight training.

Observations can be derived from dossiers / Phase J outcomes. Proposals are
versioned suggestions only — never auto-applied, never LLM fine-tuning.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EveDossier
from app.eve.coherence import COHERENCE_POLICY_V1
from app.eve.primitive_study import routing_from_study, run_primitive_routing_study

# Study-backed defaults (recomputed at import for determinism of fixtures).
_STUDY = run_primitive_routing_study()
_STUDY_ROUTING = routing_from_study(_STUDY)

DEFAULT_POLICY: dict[str, Any] = {
    "version": "eve.policy.v1.1",
    "created_at": "2026-10-16T00:00:00+00:00",
    "kind": "calibration_policy",
    "not": "llm_finetune",
    "routing": {
        **_STUDY_ROUTING,
        # Keep feature flags aligned with non-empty primitive lists.
        "use_jev_analyst": bool(_STUDY_ROUTING.get("analyst_primitives")),
        "use_jev_challenger": bool(_STUDY_ROUTING.get("challenger_primitives")),
        "use_jev_guardian": bool(_STUDY_ROUTING.get("guardian_primitives")),
        "use_jev_shadow": bool(_STUDY_ROUTING.get("shadow_primitives")),
    },
    "primitive_study": {
        "version": _STUDY.get("thresholds", {}).get("version"),
        "recommended_routing": _STUDY.get("recommended_routing"),
        "cells": [
            {
                "mode": c["mode"],
                "primitive": c["primitive"],
                "verdict": c["verdict"],
                "reason": c["reason"],
                "metrics": c["metrics"],
            }
            for c in _STUDY.get("cells", [])
        ],
    },
    "thresholds": {
        "min_data_quality_to_act": 0.35,
        "max_contradictions_before_abstain": 4,
        "guardian_critical_forces_abstain": True,
    },
    "coherence": deepcopy(COHERENCE_POLICY_V1),
}


def active_policy(override: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = deepcopy(DEFAULT_POLICY)
    if override:
        for key, value in override.items():
            if key in ("routing", "thresholds", "coherence", "primitive_study") and isinstance(
                value, dict
            ):
                pol[key] = {**pol.get(key, {}), **value}
            else:
                pol[key] = value
    pol["loaded_at"] = datetime.now(timezone.utc).isoformat()
    return pol


def observe_from_dossiers(session: Session, *, limit: int = 100) -> dict[str, Any]:
    """Aggregate measurable stats from dossiers + closed outcomes (Phase J).

    Distinct from LLM confidence / JEV SCORE. Used only as input to
    ``propose_adjustment`` — never auto-mutates policy.
    """
    stmt = (
        select(EveDossier)
        .order_by(EveDossier.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    rows = list(session.scalars(stmt))
    n = len(rows)
    if n == 0:
        return {
            "schema": "ichivol.eve.calibration_observe.v1",
            "n": 0,
            "abstain_rate": None,
            "mean_coherence": None,
            "closed_n": 0,
            "win_rate": None,
            "mean_realized_pnl": None,
            "mean_pnl_pct": None,
            "followup_close_rate": None,
            "note": "no_dossiers",
        }

    abstain = 0
    coherence_vals: list[float] = []
    closed_pnls: list[float] = []
    closed_pcts: list[float] = []
    followup_close = 0
    followup_n = 0

    for d in rows:
        action = (d.eve_action or "").upper()
        if action in ("ABSTAIN", "HOLD", "WATCH", "NO_TRADE", ""):
            # Count pure ABSTAIN for abstain_rate; HOLD is not abstain.
            if action == "ABSTAIN" or action == "":
                abstain += 1
        coh = d.coherence_json if isinstance(d.coherence_json, dict) else {}
        score = coh.get("score")
        if isinstance(score, (int, float)):
            coherence_vals.append(float(score))
        oc = d.outcome_json if isinstance(d.outcome_json, dict) else {}
        closed = oc.get("closed") if isinstance(oc.get("closed"), dict) else None
        if closed:
            rp = closed.get("realized_pnl")
            if isinstance(rp, (int, float)):
                closed_pnls.append(float(rp))
            pp = closed.get("pnl_pct")
            if isinstance(pp, (int, float)):
                closed_pcts.append(float(pp))
        for fu in oc.get("followups") or []:
            if not isinstance(fu, dict):
                continue
            followup_n += 1
            if str(fu.get("proposed_action") or "").upper() == "CLOSE":
                followup_close += 1

    closed_n = len(closed_pnls)
    wins = sum(1 for p in closed_pnls if p > 0)
    return {
        "schema": "ichivol.eve.calibration_observe.v1",
        "n": n,
        "abstain_rate": round(abstain / n, 4) if n else None,
        "mean_coherence": round(sum(coherence_vals) / len(coherence_vals), 4)
        if coherence_vals
        else None,
        "closed_n": closed_n,
        "win_rate": round(wins / closed_n, 4) if closed_n else None,
        "mean_realized_pnl": round(sum(closed_pnls) / closed_n, 6) if closed_n else None,
        "mean_pnl_pct": round(sum(closed_pcts) / len(closed_pcts), 6) if closed_pcts else None,
        "followup_close_rate": round(followup_close / followup_n, 4) if followup_n else None,
        "followup_n": followup_n,
        "not": ["jev_score", "llm_confidence", "finetune_labels"],
    }


def propose_adjustment(
    *,
    policy: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    """Document a proposed calibration change from historical observations.

    Does not mutate live policy automatically — versioned suggestion only.
    """
    suggestion = {
        "schema": "ichivol.eve.calibration_proposal.v1",
        "base_version": policy.get("version"),
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "observed": observed,
        "changes": [],
        "status": "proposal",
        "applied": False,
        "not": "llm_retraining",
    }
    abstain_rate = observed.get("abstain_rate")
    if isinstance(abstain_rate, (int, float)) and abstain_rate > 0.8:
        suggestion["changes"].append(
            {
                "path": "thresholds.min_data_quality_to_act",
                "from": policy.get("thresholds", {}).get("min_data_quality_to_act"),
                "to": 0.30,
                "reason": "high_abstain_rate",
            }
        )
    mean_coherence = observed.get("mean_coherence")
    if isinstance(mean_coherence, (int, float)) and mean_coherence < 0.4:
        suggestion["changes"].append(
            {
                "path": "coherence.weights.data_quality",
                "reason": "low_mean_coherence_review_weights",
                "note": "Manual review required before applying",
            }
        )
    win_rate = observed.get("win_rate")
    closed_n = observed.get("closed_n") or 0
    if (
        isinstance(win_rate, (int, float))
        and isinstance(closed_n, int)
        and closed_n >= 5
        and win_rate < 0.35
    ):
        suggestion["changes"].append(
            {
                "path": "thresholds.min_data_quality_to_act",
                "from": policy.get("thresholds", {}).get("min_data_quality_to_act"),
                "to": 0.45,
                "reason": "low_win_rate_raise_quality_floor",
                "note": "Paper outcomes net of fees — review before apply",
            }
        )
    followup_close_rate = observed.get("followup_close_rate")
    if isinstance(followup_close_rate, (int, float)) and followup_close_rate > 0.7:
        suggestion["changes"].append(
            {
                "path": "thresholds.max_contradictions_before_abstain",
                "from": policy.get("thresholds", {}).get("max_contradictions_before_abstain"),
                "to": 3,
                "reason": "high_followup_close_rate_tighten_entry",
                "note": "Many Phase J CLOSE proposals — consider stricter entry",
            }
        )
    return suggestion


def calibration_report(session: Session, *, limit: int = 100) -> dict[str, Any]:
    """Observe dossiers → propose adjustments (never auto-applied)."""
    policy = active_policy()
    observed = observe_from_dossiers(session, limit=limit)
    proposal = propose_adjustment(policy=policy, observed=observed)
    return {
        "schema": "ichivol.eve.calibration_report.v1",
        "policy_version": policy.get("version"),
        "observed": observed,
        "proposal": proposal,
        "applied": False,
        "not": "llm_finetune",
    }
