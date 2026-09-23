"""T7 — Monte Carlo / risk of ruin tests."""

from __future__ import annotations

from app.risk.monte_carlo import run_monte_carlo


def test_insufficient_trades():
    rep = run_monte_carlo([0.01] * 5, min_trades=20)
    assert rep.sufficient is False
    assert rep.risk_of_ruin is None
    assert "research only" in rep.disclaimer.lower()


def test_deterministic_seed():
    rets = [0.02, -0.01, 0.015, -0.005] * 8  # 32 trades
    a = run_monte_carlo(rets, n_paths=200, seed=7)
    b = run_monte_carlo(rets, n_paths=200, seed=7)
    assert a.to_dict() == b.to_dict()
    assert a.sufficient is True
    assert a.risk_of_ruin is not None
    assert 0.0 <= a.risk_of_ruin <= 1.0
    assert a.p50_final_equity is not None


def test_all_losses_high_ruin():
    rets = [-0.05] * 25
    rep = run_monte_carlo(rets, n_paths=300, seed=1, ruin_floor=0.5)
    assert rep.sufficient is True
    assert rep.risk_of_ruin is not None and rep.risk_of_ruin > 0.9
    assert rep.mean_final_equity is not None and rep.mean_final_equity < 1.0


def test_all_wins_low_ruin():
    rets = [0.02] * 25
    rep = run_monte_carlo(rets, n_paths=300, seed=1, ruin_floor=0.5)
    assert rep.risk_of_ruin == 0.0
    assert rep.mean_final_equity is not None and rep.mean_final_equity > 1.0
