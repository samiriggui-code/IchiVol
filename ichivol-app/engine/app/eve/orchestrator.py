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
from app.eve.degradation import (
    apply_degradation,
    assess_degradation,
    extract_probabilities,
)
from app.eve.dossier import persist_dossier
from app.eve.entry_gate import run_entry_gate
from app.eve.heuristic import heuristic_badge
from app.eve.signal_rules import apply_signal_rules
from app.eve.modes import (
    run_analyst,
    run_challenger,
    run_guardian,
    run_shadow_mode,
    synthesize_action,
)
from app.eve.paper_submit import autonomy_enabled, submit_paper_from_dossier
from app.jev.adapter import health as jev_health


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

    # Build provisional jev pack for degradation (full pack assembled below).
    jev_pack_preview = {
        "analyst": analyst.get("jev"),
        "challenger": challenger.get("jev"),
        "guardian": guardian.get("jev"),
        # Prefer adapter envelope (ok/error/late); panel payload is secondary.
        "shadow": shadow.get("jev") or (shadow.get("result") or {}).get("jev"),
    }
    degradation = assess_degradation(
        jev_pack_preview,
        jev_requested=jev_on,
        min_confidence=float(thresholds.get("min_jev_confidence") or 0.45),
    )
    synthesis = apply_degradation(synthesis, degradation)
    badge = heuristic_badge(degradation)

    # QuantDinger-style pre-trade gate (fail-closed). Advisory vs Risk Kernel.
    gate_min_conf = float(thresholds.get("entry_gate_min_confidence") or 0.55)
    entry_gate = run_entry_gate(
        context,
        eve_action=str(synthesis.get("action") or ""),
        use_jev=jev_on,
        min_confidence=gate_min_conf,
    )
    if (
        synthesis.get("action") in ("LONG", "SHORT")
        and entry_gate.get("decision") == "reject"
        and not entry_gate.get("allowed", False)
    ):
        rejected = list(synthesis.get("rejected_scenarios") or [])
        rejected.append(f"entry_gate:{entry_gate.get('reason')}")
        synthesis["rejected_scenarios"] = rejected
        synthesis["action"] = "ABSTAIN"
        synthesis["rationale"] = (
            f"Entry gate reject ({entry_gate.get('reason')}) → ABSTAIN"
        )
    synthesis["entry_gate"] = {
        "decision": entry_gate.get("decision"),
        "allowed": entry_gate.get("allowed"),
        "reason": entry_gate.get("reason"),
        "confidence": entry_gate.get("confidence"),
    }

    # Gamma-style AND gates in code (portable signals when present).
    signal_rules = apply_signal_rules(
        str(synthesis.get("action") or ""),
        jev_pack_preview,
    )
    if (
        synthesis.get("action") in ("LONG", "SHORT")
        and signal_rules.get("decision") == "reject"
        and not signal_rules.get("allowed", False)
    ):
        rejected = list(synthesis.get("rejected_scenarios") or [])
        rejected.append(f"signal_rules:{signal_rules.get('reason')}")
        synthesis["rejected_scenarios"] = rejected
        synthesis["action"] = "ABSTAIN"
        synthesis["rationale"] = (
            f"Signal rules reject ({signal_rules.get('reason')}) → ABSTAIN"
        )
    synthesis["signal_rules"] = {
        "decision": signal_rules.get("decision"),
        "allowed": signal_rules.get("allowed"),
        "reason": signal_rules.get("reason"),
        "rule": signal_rules.get("rule"),
    }

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
        "shadow": shadow.get("jev") or (shadow.get("result") or {}).get("jev"),
    }

    # Fingerprint / model pin — best-effort, never blocks evaluation.
    provider_health: dict[str, Any] | None = None
    if jev_on:
        try:
            provider_health = jev_health(timeout_s=1.5)
        except Exception:  # noqa: BLE001
            provider_health = None

    event_radar = context.get("event_radar") if isinstance(context.get("event_radar"), dict) else None

    decision_time = {
        "captured_at": now,
        "context_as_of": context.get("as_of"),
        "known_at": context.get("known_at"),
        "includes_future_outcome": False,
        "degradation": degradation,
        "heuristic": badge,
        "entry_gate": {
            "decision": entry_gate.get("decision"),
            "allowed": entry_gate.get("allowed"),
            "reason": entry_gate.get("reason"),
            "confidence": entry_gate.get("confidence"),
            "checks": entry_gate.get("checks") or [],
        },
        "signal_rules": {
            "decision": signal_rules.get("decision"),
            "allowed": signal_rules.get("allowed"),
            "reason": signal_rules.get("reason"),
            "rule": signal_rules.get("rule"),
        },
        "event_radar": {
            "enabled": bool((event_radar or {}).get("enabled")),
            "direction": (event_radar or {}).get("direction"),
            "impact": (event_radar or {}).get("impact"),
            "relevance": (event_radar or {}).get("relevance"),
            "freshness": (event_radar or {}).get("freshness"),
            "confidence": (event_radar or {}).get("confidence"),
            "provider": (event_radar or {}).get("provider"),
            "event_count": (event_radar or {}).get("event_count"),
            "reference_only": True,
        }
        if event_radar
        else None,
        "jev_probabilities": extract_probabilities(jev_pack),
        "jev_fingerprint": (provider_health or {}).get("fingerprint"),
        "jev_provider": (provider_health or {}).get("provider"),
        "model_mismatch": any(
            bool((env or {}).get("model_mismatch"))
            for env in jev_pack.values()
            if isinstance(env, dict)
        ),
    }

    verdict["degradation"] = degradation
    verdict["heuristic"] = badge
    verdict["entry_gate"] = synthesis.get("entry_gate")
    if degradation.get("level") != "healthy":
        verdict["note"] = (
            f"Potential ({degradation.get('level')}) — "
            f"source={badge.get('label')}; Risk Kernel dry-run still gated"
        )

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
        "degradation": degradation,
        "heuristic": badge,
        "entry_gate": entry_gate,
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

        # Paper path: essai à blanc Risk Kernel sur tous les livres, jamais d'exécution ici.
        # En autonomie, seul eve.autopilot exécute, sur les livres dont la méthode moteur a proposé le trade.
        if paper_dry_run:
            try:
                auto = autonomy_enabled()
                paper = submit_paper_from_dossier(
                    session,
                    dossier.id,
                    portfolio_code=None,  # tous les livres virtuels
                    execute=False,
                    allow_screener=True,
                )
                result["paper_submit"] = paper
                result["execution_status"] = dossier.execution_status
                verdict["risk_authorization"] = paper.get("risk_authorization")
                verdict["paper_submit_status"] = paper.get("status")
                n_books = len(paper.get("portfolio_codes") or paper.get("portfolios") or [])
                verdict["note"] = (
                    "Potential + Risk Kernel"
                    + " dry-run"
                    + f"; autonomy={'on' if auto else 'off'}"
                    + f"; livres={n_books or 1}"
                )
            except Exception as exc:  # noqa: BLE001 — evaluation must not fail on RK path
                result["paper_submit"] = {
                    "ok": False,
                    "error": type(exc).__name__,
                    "status": "paper_submit_error",
                }

        session.commit()

    return result
