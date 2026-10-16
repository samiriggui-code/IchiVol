from types import SimpleNamespace
from unittest.mock import MagicMock

from app.eve.calibration import (
    active_policy,
    brier_score,
    expected_calibration_error,
    observe_from_dossiers,
    propose_adjustment,
)


def test_policy_is_not_finetune() -> None:
    p = active_policy()
    assert p["not"] == "llm_finetune"
    assert "coherence" in p
    assert p["routing"]["use_jev_shadow"] is True


def test_propose_adjustment_high_abstain() -> None:
    p = active_policy()
    prop = propose_adjustment(policy=p, observed={"abstain_rate": 0.9, "mean_coherence": 0.6, "n": 10})
    assert prop["applied"] is False
    assert prop["not"] == "llm_retraining"
    assert any(c.get("path") == "thresholds.min_data_quality_to_act" for c in prop["changes"])


def test_propose_adjustment_low_win_rate() -> None:
    p = active_policy()
    prop = propose_adjustment(
        policy=p,
        observed={"win_rate": 0.2, "closed_n": 10, "abstain_rate": 0.1, "mean_coherence": 0.6, "n": 10},
    )
    assert any(c.get("reason") == "low_win_rate_raise_quality_floor" for c in prop["changes"])
    assert prop["applied"] is False


def test_observe_from_dossiers_aggregates() -> None:
    rows = [
        SimpleNamespace(
            eve_action="ABSTAIN",
            coherence_json={"score": 0.5},
            decision_time_json={},
            outcome_json={
                "closed": {"realized_pnl": 10.0, "pnl_pct": 0.02},
                "followups": [{"proposed_action": "CLOSE"}],
            },
        ),
        SimpleNamespace(
            eve_action="LONG",
            coherence_json={"score": 0.7},
            decision_time_json={"degradation": {"mean_confidence": 0.8}},
            outcome_json={
                "closed": {"realized_pnl": -5.0, "pnl_pct": -0.01},
                "followups": [{"proposed_action": "HOLD"}],
            },
        ),
    ]
    session = MagicMock()
    session.scalars.return_value = rows
    obs = observe_from_dossiers(session, limit=10)
    assert obs["n"] == 2
    assert obs["abstain_rate"] == 0.5
    assert obs["closed_n"] == 2
    assert obs["win_rate"] == 0.5
    assert obs["followup_close_rate"] == 0.5
    assert obs["calibration_pairs_n"] == 1
    assert obs["brier"] == brier_score([(0.8, 0.0)])
    assert obs["ece"] is not None
    assert obs["ece"]["applied"] is False
    assert "jev_score" in obs["not"]
    assert "auto_platt" in obs["not"]


def test_brier_and_ece_perfect_and_bad() -> None:
    perfect = [(0.9, 1.0), (0.1, 0.0)]
    assert brier_score(perfect) is not None
    assert brier_score(perfect) < 0.05
    ece = expected_calibration_error(perfect, n_bins=5)
    assert ece is not None
    assert ece["applied"] is False
    assert ece["ece"] >= 0.0
