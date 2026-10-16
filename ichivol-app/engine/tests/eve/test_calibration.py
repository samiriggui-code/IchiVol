from app.eve.calibration import active_policy, propose_adjustment


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
