"""Indice de cohérence — documented, not interchangeable with JEV scores.

Components (weights sum to 1.0, policy-versioned):
- data_quality: fraction of FactSheet facts with status=ok
- contradiction_penalty: Challenger findings reduce score
- guardian_penalty: Guardian warnings/anomalies
- jev_alignment: optional NOUL from Shadow/review (if present)
- hypothesis_stability: agreement Analyst vs baseline mapping

Distinct from: JEV SCORE, LLM-declared confidence, empirical win-rate, PnL.
"""

from __future__ import annotations

from typing import Any

COHERENCE_POLICY_V1 = {
    "version": "eve.coherence.v1",
    "weights": {
        "data_quality": 0.35,
        "contradiction": 0.25,
        "guardian": 0.20,
        "jev_alignment": 0.10,
        "hypothesis_stability": 0.10,
    },
}


def compute_coherence(
    *,
    data_quality: float,
    contradiction_count: int,
    guardian_warning_count: int,
    jev_noul: float | None,
    analyst_agrees_baseline: bool | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pol = policy or COHERENCE_POLICY_V1
    w = dict(pol.get("weights") or COHERENCE_POLICY_V1["weights"])

    dq = max(0.0, min(1.0, float(data_quality)))
    contra = max(0.0, 1.0 - min(contradiction_count, 5) / 5.0)
    guard = max(0.0, 1.0 - min(guardian_warning_count, 5) / 5.0)
    jev = float(jev_noul) if isinstance(jev_noul, (int, float)) else None
    if jev is not None:
        jev = max(0.0, min(1.0, jev))
        jev_component = jev
        jev_weight = float(w.get("jev_alignment", 0.1))
    else:
        jev_component = 0.0
        jev_weight = 0.0
        # Redistribute unused JEV weight to data_quality.
        w["data_quality"] = float(w.get("data_quality", 0.35)) + float(
            COHERENCE_POLICY_V1["weights"]["jev_alignment"]
        )

    if analyst_agrees_baseline is None:
        hyp = 0.5
    else:
        hyp = 1.0 if analyst_agrees_baseline else 0.35

    score = (
        float(w.get("data_quality", 0.35)) * dq
        + float(w.get("contradiction", 0.25)) * contra
        + float(w.get("guardian", 0.20)) * guard
        + jev_weight * jev_component
        + float(w.get("hypothesis_stability", 0.10)) * hyp
    )
    score = round(max(0.0, min(1.0, score)), 4)

    return {
        "schema": "ichivol.eve.coherence.v1",
        "score": score,
        "policy_version": pol.get("version"),
        "components": {
            "data_quality": dq,
            "contradiction_resilience": contra,
            "guardian_clearance": guard,
            "jev_alignment": jev,
            "hypothesis_stability": hyp,
        },
        "weights_applied": {
            "data_quality": w.get("data_quality"),
            "contradiction": w.get("contradiction"),
            "guardian": w.get("guardian"),
            "jev_alignment": jev_weight,
            "hypothesis_stability": w.get("hypothesis_stability"),
        },
        "not": [
            "jev_score",
            "llm_confidence",
            "empirical_win_rate",
            "realized_pnl",
        ],
    }
