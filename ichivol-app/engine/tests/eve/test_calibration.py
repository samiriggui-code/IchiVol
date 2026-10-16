from types import SimpleNamespace
from unittest.mock import MagicMock

from app.eve.calibration import (
    active_policy,
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
            outcome_json={
                "closed": {"realized_pnl": 10.0, "pnl_pct": 0.02},
                "followups": [{"proposed_action": "CLOSE"}],
            },
        ),
        SimpleNamespace(
            eve_action="LONG",
            coherence_json={"score": 0.7},
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
    assert "jev_score" in obs["not"]
