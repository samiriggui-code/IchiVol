"""T9g-fix — hardened ablation OOS recommendations (review_candidate)."""

from __future__ import annotations

from app.agents.types import Direction
from app.strategy_lab.ablation_oos import (
    decide_recommendation,
    run_ablation_oos_study_on_candles,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles

_TINY_LAYERS = (
    ("A_KUMO", {"price_above_kumo": True}),
    ("B_RVOL", {"rvol_min": 1.0}),
)


def test_decide_review_candidate_requires_all_gates():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=0.1,
        is_expectancy_delta=0.02,
        total_oos_trades=40,
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.01, 0.02, 0.005],
        adverse_oos_expectancy_delta=0.004,
    )
    assert rec == "review_candidate"
    assert "promote" not in rec
    assert reasons


def test_decide_reject_mixed_folds_no_majority():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,  # aggregate positive
        oos_profit_factor_delta=0.1,
        is_expectancy_delta=0.02,
        total_oos_trades=40,
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.02, -0.01, -0.005],  # 1/3 only
        adverse_oos_expectancy_delta=0.01,
    )
    assert rec == "reject"
    assert any("majority" in r.lower() for r in reasons)


def test_decide_reject_adverse_cost_negative():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=0.1,
        is_expectancy_delta=0.02,
        total_oos_trades=40,
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.01, 0.02, 0.005],
        adverse_oos_expectancy_delta=-0.01,
    )
    assert rec == "reject"
    assert any("adverse" in r.lower() for r in reasons)


def test_decide_inconclusive_too_few_trades():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=0.0,
        is_expectancy_delta=0.0,
        total_oos_trades=5,
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.01, 0.02, 0.005],
        adverse_oos_expectancy_delta=0.01,
    )
    assert rec == "inconclusive"
    assert "min_oos_trades" in reasons[0]


def test_decide_inconclusive_when_variant_has_few_trades():
    """rév.50 — use min(base, variant): base=40, variant=5 → inconclusive."""
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.02,
        oos_profit_factor_delta=0.1,
        is_expectancy_delta=0.01,
        total_oos_trades=min(40, 5),
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.01, 0.02, 0.005],
        adverse_oos_expectancy_delta=0.01,
    )
    assert rec == "inconclusive"
    assert "min_oos_trades" in reasons[0]


def test_study_inconclusive_when_variant_has_few_trades_mocked_wf(monkeypatch):
    """#71 réserve — study-level min(trades): base=40 OOS, variant=5 → inconclusive.

    Must fail if someone replaces ``min(trades_base, trades_var)`` with ``max``.
    """
    from types import SimpleNamespace

    call_n = {"i": 0}

    def _fake_run_wf(candles, ruleset, **kwargs):
        # Per pair: base, var, base_adv, var_adv
        idx = call_n["i"] % 4
        call_n["i"] += 1
        if idx in (0, 2):  # baseline (+ adverse baseline)
            trades = 40
            mean_exp = 0.01
            mean_pf = 1.2
        else:  # variant (+ adverse variant) — few trades
            trades = 5
            mean_exp = 0.02
            mean_pf = 1.3
        oos = {
            "n_folds": 3,
            "total_oos_trades": trades,
            "mean_oos_expectancy": mean_exp,
            "mean_oos_profit_factor": mean_pf,
        }
        # Three folds with positive expectancy deltas when compared
        folds = []
        for _ in range(3):
            folds.append(
                SimpleNamespace(
                    train=SimpleNamespace(
                        backtest=SimpleNamespace(
                            metrics=SimpleNamespace(expectancy=0.015, profit_factor=1.25)
                        )
                    ),
                    test=SimpleNamespace(
                        backtest=SimpleNamespace(
                            metrics=SimpleNamespace(expectancy=mean_exp, profit_factor=mean_pf)
                        )
                    ),
                )
            )
        return SimpleNamespace(oos_summary=oos, folds=folds)

    monkeypatch.setattr("app.strategy_lab.ablation_oos._run_wf", _fake_run_wf)
    candles = _make_candles(200, seed=9)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        layers=_TINY_LAYERS,
        direction=Direction.LONG,
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=30,
    )
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.oos_total_trades_baseline == 40
    assert c.oos_total_trades_variant == 5
    assert c.recommendation == "inconclusive"
    assert any("min_oos_trades" in r for r in c.reasons)


def test_decide_reject_pf_degraded():
    rec, reasons = decide_recommendation(
        oos_expectancy_delta=0.01,
        oos_profit_factor_delta=-0.2,
        is_expectancy_delta=0.02,
        total_oos_trades=40,
        n_folds=3,
        min_oos_trades=30,
        fold_oos_expectancy_deltas=[0.01, 0.02, 0.005],
        adverse_oos_expectancy_delta=0.01,
    )
    assert rec == "reject"
    assert any("PF" in r or "pf" in r.lower() for r in reasons)


def test_report_displays_lineage_and_history_warning(monkeypatch):
    monkeypatch.setattr(
        "app.strategy_lab.ablation_oos._lineage_trial_count",
        lambda _hid: 20,
    )
    candles = _make_candles(280, seed=11)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        layers=_TINY_LAYERS,
        direction=Direction.LONG,
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=1,
        hypothesis_id="h_test_lineage",
    )
    body = report.to_dict()
    assert body["hypothesis_id"] == "h_test_lineage"
    assert body["lineage_trial_count"] == 20
    assert body["n_bars"] == 280
    assert body["history_warning"] is not None
    assert "indicatif" in body["history_warning"].lower()
    assert body["min_oos_trades"] == 1
    c = body["candidates"][0]
    assert c["recommendation"] in ("review_candidate", "reject", "inconclusive")
    assert c["recommendation"] != "promote"
    assert "fold_oos_expectancy_deltas" in c
    assert "adverse_oos_expectancy_delta" in c
    assert "review_candidate is not a promotion" in body["disclaimer"].lower() or (
        "not a promotion" in body["disclaimer"].lower()
    )


def test_ablation_oos_additive_on_synthetic():
    candles = _make_candles(280, seed=11)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        layers=_TINY_LAYERS,
        direction=Direction.LONG,
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=1,
    )
    assert report.n_bars == 280
    assert report.compare_mode == "additive"
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.label == "B_RVOL"
    assert c.recommendation in ("review_candidate", "reject", "inconclusive")
    assert "no auto-reject" in report.disclaimer.lower()


def test_ablation_oos_leave_one_layer():
    candles = _make_candles(260, seed=5)
    report = run_ablation_oos_study_on_candles(
        candles,
        symbol="ETHUSDT",
        timeframe="1h",
        compare_mode="leave_one_layer_out",
        layers=_TINY_LAYERS,
        train_bars=70,
        test_bars=25,
        step_bars=25,
        warmup_bars=52,
        min_oos_trades=1,
    )
    assert report.compare_mode == "leave_one_layer_out"
    assert len(report.candidates) == 2
    labels = {c.label for c in report.candidates}
    assert labels == {"A_KUMO", "B_RVOL"}
