"""Eve cycle A→G — observation to potential verdict.

Phases H–I (Risk Kernel / paper open) live in ``eve.paper_submit`` and are
gated by ``EVE_PAPER_AUTONOMY`` (default off). This module never opens lots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.eve.actions import normalize_action
from app.eve.calibration import active_policy
from app.eve.coherence import compute_coherence
from app.eve.context import build_engine_context
from app.eve.dossier import persist_dossier
from app.eve.modes import (
    run_analyst,
    run_challenger,
    run_guardian,
    run_shadow_mode,
    synthesize_action,
)
from app.eve.paper_submit import autonomy_enabled, submit_paper_from_dossier


def evaluate_opportunity(
    symbol: str,
    timeframe: str = "1h",
    *,
    session: Session | None = None,
    persist: bool = True,
    use_jev: bool | None = None,
    policy_override: dict[str, Any] | None = None,
    paper_dry_run: bool = True,
) -> dict[str, Any]:
    """Run Eve Intelligence evaluation. Never places orders.

    When ``persist`` and ``paper_dry_run``, runs Risk Kernel dry-run via
    ``paper_submit`` (autonomy still gates any real open — default off).
    """
    policy = active_policy(policy_override)
    routing = policy.get("routing") or {}
    context = build_engine_context(symbol, timeframe)

    dq = float(context.get("data_quality") or 0)
    skip_floor = float(routing.get("skip_jev_if_data_quality_below") or 0)
    jev_on = True if use_jev is None else bool(use_jev)
    if dq < skip_floor:
        jev_on = False

    analyst = run_analyst(
        context,
        use_jev=jev_on and bool(routing.get("use_jev_analyst", True)),
        primitives=routing.get("analyst_primitives"),
    )
    challenger = run_challenger(
        context,
        use_jev=jev_on and bool(routing.get("use_jev_challenger", True)),
        primitives=routing.get("challenger_primitives"),
    )
    guardian = run_guardian(
        context,
        use_jev=jev_on and bool(routing.get("use_jev_guardian", True)),
        primitives=routing.get("guardian_primitives"),
    )
    shadow = run_shadow_mode(
        context,
        use_jev=jev_on and bool(routing.get("use_jev_shadow", True)),
        primitives=routing.get("shadow_primitives"),
    )

    baseline_action = normalize_action((context.get("baseline") or {}).get("decision"))
    synthesis = synthesize_action(
        analyst=analyst,
        challenger=challenger,
        guardian=guardian,
        shadow=shadow,
        baseline_action=baseline_action,
    )

    # Policy thresholds may force abstain.
    thresholds = policy.get("thresholds") or {}
    contradictions = challenger.get("contradictions") or []
    if dq < float(thresholds.get("min_data_quality_to_act") or 0):
        synthesis["action"] = "ABSTAIN"
        synthesis["rationale"] = "Policy: data_quality below min_data_quality_to_act"
    max_c = int(thresholds.get("max_contradictions_before_abstain") or 99)
    if len(contradictions) >= max_c:
        synthesis["action"] = "ABSTAIN"
        synthesis["rationale"] = "Policy: too many Challenger contradictions"

    analyst_agrees = None
    primary = (analyst.get("hypotheses") or {}).get("primary_action")
    if baseline_action and primary:
        analyst_agrees = normalize_action(str(primary)) == baseline_action

    coherence = compute_coherence(
        data_quality=dq,
        contradiction_count=len(contradictions),
        guardian_warning_count=len(guardian.get("warnings") or []),
        jev_noul=synthesis.get("shadow_noul"),
        analyst_agrees_baseline=analyst_agrees,
        policy=policy.get("coherence"),
    )

    now = datetime.now(timezone.utc).isoformat()
    verdict = {
        "action": synthesis["action"],
        "status": "potential",
        "scenario_retained": synthesis["action"],
        "scenarios_rejected": synthesis.get("rejected_scenarios") or [],
        "reasoning": synthesis.get("rationale"),
        "coherence_score": coherence.get("score"),
        "baseline_decision": (context.get("baseline") or {}).get("decision"),
        "disagrees_with_baseline": synthesis.get("disagrees_with_baseline"),
        "risk_authorization": "not_submitted",
        "order_submitted": False,
        "executed": False,
        "modes": {
            "analyst": {"scenarios": analyst.get("scenarios")},
            "challenger": {"contradiction_count": len(contradictions)},
            "guardian": {"warning_count": len(guardian.get("warnings") or [])},
            "shadow": {"provider": (shadow.get("result") or {}).get("provider")},
        },
        "note": (
            "Potential decision — Risk Kernel not invoked here; "
            "use POST /eve/dossiers/{id}/paper-submit (autonomy default off)"
        ),
    }

    decision_time = {
        "captured_at": now,
        "context_as_of": context.get("as_of"),
        "known_at": context.get("known_at"),
        "includes_future_outcome": False,
    }

    modes_pack = {
        "analyst": analyst,
        "challenger": challenger,
        "guardian": guardian,
        "shadow": shadow,
        "synthesis": synthesis,
    }
    jev_pack = {
        "analyst": analyst.get("jev"),
        "challenger": challenger.get("jev"),
        "guardian": guardian.get("jev"),
        "shadow": (shadow.get("result") or {}).get("jev"),
    }

    result: dict[str, Any] = {
        "schema": "ichivol.eve.evaluation.v1",
        "symbol": context.get("symbol"),
        "timeframe": context.get("timeframe"),
        "status": "potential",
        "execution_status": "not_executed",
        "context": context,
        "modes": modes_pack,
        "jev": jev_pack,
        "coherence": coherence,
        "policy": {
            "version": policy.get("version"),
            "routing": routing,
            "thresholds": thresholds,
        },
        "decision_time": decision_time,
        "verdict": verdict,
        "baseline_decision": (context.get("baseline") or {}).get("decision"),
        "eve_action": synthesis["action"],
        "dossier_id": None,
        "verdict_id": None,
    }

    if persist and session is not None:
        dossier = persist_dossier(
            session,
            payload={
                "symbol": result["symbol"],
                "timeframe": result["timeframe"],
                "status": "open",
                "context": context,
                "modes": modes_pack,
                "jev": jev_pack,
                "coherence": coherence,
                "policy": result["policy"],
                "decision_time": decision_time,
                "baseline_decision": result["baseline_decision"],
                "eve_action": result["eve_action"],
                "verdict": verdict,
            },
        )
        session.flush()
        result["dossier_id"] = dossier.id
        result["verdict_id"] = dossier.verdict_id

        # V2 Phase H dry-run: record Risk Kernel stance without opening.
        if paper_dry_run:
            try:
                paper = submit_paper_from_dossier(
                    session,
                    dossier.id,
                    execute=False,  # always dry-run from evaluate path
                    allow_screener=True,
                )
                result["paper_submit"] = paper
                result["execution_status"] = dossier.execution_status
                verdict["risk_authorization"] = paper.get("risk_authorization")
                verdict["paper_submit_status"] = paper.get("status")
                verdict["note"] = (
                    "Potential + Risk Kernel dry-run; "
                    f"autonomy={'on' if autonomy_enabled() else 'off'}"
                )
            except Exception as exc:  # noqa: BLE001 — evaluation must not fail on RK dry-run
                result["paper_submit"] = {
                    "ok": False,
                    "error": type(exc).__name__,
                    "status": "dry_run_error",
                }

        session.commit()

    return result
