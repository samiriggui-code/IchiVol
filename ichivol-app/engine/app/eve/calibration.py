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
from app.eve.settings_schema import policy_threshold_overrides

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
        # Fallback ladder (buberlo / jarrodwatts) — never auto-tunes itself.
        "min_jev_confidence": 0.45,
        "low_confidence_blocks_paper_execute": True,
        "late_forces_hold": True,
        "entry_gate_min_confidence": 0.55,
        "entry_gate_blocks_paper_execute": True,
    },
    "coherence": deepcopy(COHERENCE_POLICY_V1),
}


def active_policy(override: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = deepcopy(DEFAULT_POLICY)
    # Operator knobs (Settings schema) feed thresholds — never auto-tune.
    knobs = policy_threshold_overrides()
    pol["thresholds"] = {**pol.get("thresholds", {}), **knobs}
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


def _predicted_confidence(decision_time: dict[str, Any] | None) -> float | None:
    """Point forecast in [0,1] from decision_time (immutable) for Brier/ECE."""
    dt = decision_time if isinstance(decision_time, dict) else {}
    deg = dt.get("degradation") if isinstance(dt.get("degradation"), dict) else {}
    mean_c = deg.get("mean_confidence")
    if isinstance(mean_c, (int, float)) and 0.0 <= float(mean_c) <= 1.0:
        return float(mean_c)
    gate = dt.get("entry_gate") if isinstance(dt.get("entry_gate"), dict) else {}
    gate_c = gate.get("confidence")
    if isinstance(gate_c, (int, float)) and 0.0 <= float(gate_c) <= 1.0:
        return float(gate_c)
    # Fall back to max CHOICE confidence in persisted JEV probs.
    best: float | None = None
    probs = dt.get("jev_probabilities")
    if isinstance(probs, dict):
        for mode_pack in probs.values():
            if not isinstance(mode_pack, dict):
                continue
            answers = mode_pack.get("answers")
            if not isinstance(answers, dict):
                continue
            for ans in answers.values():
                if not isinstance(ans, dict):
                    continue
                conf = ans.get("confidence")
                if isinstance(conf, (int, float)) and 0.0 <= float(conf) <= 1.0:
                    best = float(conf) if best is None else max(best, float(conf))
    return best


def brier_score(pairs: list[tuple[float, float]]) -> float | None:
    """Mean squared error of probability vs binary outcome. Observe-only."""
    if not pairs:
        return None
    return round(sum((p - y) ** 2 for p, y in pairs) / len(pairs), 6)


def expected_calibration_error(
    pairs: list[tuple[float, float]],
    *,
    n_bins: int = 10,
) -> dict[str, Any] | None:
    """Equal-width ECE in [0,1]. Observe-only — never auto-applies Platt."""
    if not pairs or n_bins < 2:
        return None
    bins: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, y in pairs:
        idx = min(n_bins - 1, max(0, int(p * n_bins)))
        bins[idx].append((p, y))
    ece = 0.0
    reliability: list[dict[str, Any]] = []
    n = len(pairs)
    for i, bucket in enumerate(bins):
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(y for _, y in bucket) / len(bucket)
        weight = len(bucket) / n
        ece += weight * abs(acc - conf)
        reliability.append(
            {
                "bin": i,
                "n": len(bucket),
                "mean_confidence": round(conf, 4),
                "empirical_rate": round(acc, 4),
                "gap": round(abs(acc - conf), 4),
            }
        )
    return {
        "ece": round(ece, 6),
        "n_bins": n_bins,
        "n": n,
        "reliability": reliability,
        "applied": False,
        "not": "auto_platt",
    }


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
            "brier": None,
            "ece": None,
            "note": "no_dossiers",
        }

    abstain = 0
    coherence_vals: list[float] = []
    closed_pnls: list[float] = []
    closed_pcts: list[float] = []
    followup_close = 0
    followup_n = 0
    calib_pairs: list[tuple[float, float]] = []

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
            # Directional dossiers only — Brier on win/loss vs decision_time conf.
            if action in ("LONG", "SHORT") and isinstance(rp, (int, float)):
                pred = _predicted_confidence(
                    d.decision_time_json if isinstance(d.decision_time_json, dict) else None
                )
                if pred is not None:
                    calib_pairs.append((pred, 1.0 if float(rp) > 0 else 0.0))
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
        "brier": brier_score(calib_pairs),
        "ece": expected_calibration_error(calib_pairs),
        "calibration_pairs_n": len(calib_pairs),
        "not": ["jev_score", "llm_confidence", "finetune_labels", "auto_platt"],
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
