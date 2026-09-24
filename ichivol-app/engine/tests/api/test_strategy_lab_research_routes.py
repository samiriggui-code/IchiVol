"""HTTP surface for Strategy Lab Research (T5b / T6 / T7 / Researcher)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.agents.types import Direction, StrategyAgentOutput
from app.decision.pipeline import build_pipeline
from app.main import app

client = TestClient(app)


def _ichi() -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=Direction.LONG,
        probability=0.7,
        confidence=1.0,
        expected_value=0.0,
        reasons=["tk_cross_bullish"],
        invalidation=[],
        metadata={"score": 50.0},
    )


def _rvol() -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="RVOL_AGENT",
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=0.8,
        expected_value=0.0,
        reasons=[],
        invalidation=[],
        metadata={"confirmed": True, "anomaly_level": "SIGNIFICANT", "rvol": 2.5},
    )


def test_family_weight_profiles_catalog():
    res = client.get("/api/engine/strategy-lab/family-weight-profiles")
    assert res.status_code == 200
    body = res.json()
    assert len(body["profiles"]) >= 1
    assert "observation" in body["disclaimer"].lower() or "lab" in body["disclaimer"].lower()
    row = body["profiles"][0]
    assert "id" in row and "weights" in row and "version" in row


def test_propose_experiment_plan_from_audit_dict():
    audit = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "ruleset_id": "IV_ICHIMOKU_ONLY_LONG_001",
        "hypotheses": [
            {
                "id": "h_stop_widen_or_filter",
                "statement": "Stop may be tight",
                "suggested_experiment": "regime",
                "status": "proposed",
            }
        ],
    }
    res = client.post(
        "/api/engine/strategy-lab/propose-experiment-plan",
        json={"audit_report": audit},
    )
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["status"] == "proposed"
    assert plan["symbol"] == "BTCUSDT"
    assert len(plan["steps"]) >= 1
    assert "never auto-runs" in plan["disclaimer"].lower()


def test_audit_report_rejects_missing_ruleset():
    res = client.post(
        "/api/engine/strategy-lab/audit-report",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100},
    )
    assert res.status_code == 422


def test_monte_carlo_rejects_missing_ruleset():
    res = client.post(
        "/api/engine/strategy-lab/monte-carlo",
        json={"symbol": "BTCUSDT", "limit": 100},
    )
    assert res.status_code == 422


def test_family_weights_compare_monkeypatched(monkeypatch):
    from app.api import strategy_lab_research as mod

    pipe = build_pipeline(_ichi(), _rvol())
    decision = MagicMock()
    decision.decision = "BUY"
    decision.confidence = 0.7
    row = MagicMock()
    row.symbol = "BTCUSDT"
    row.timeframe = "1h"
    row.pipeline = pipe
    row.decision = decision

    monkeypatch.setattr(mod, "scan_symbol", lambda *a, **k: row)

    res = client.get(
        "/api/engine/strategy-lab/family-weights/compare",
        params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "profiles" in body
    assert "observation" in body["disclaimer"].lower()


def test_feature_redundancy_study_monkeypatched(monkeypatch):
    from app.api import strategy_lab_research as mod
    from app.strategy_lab.redundancy import FeatureRedundancyReport

    fake = FeatureRedundancyReport(
        symbol="BTCUSDT",
        timeframe="1h",
        n_bars=100,
        direction="LONG",
        keys=["bos_bullish", "tk_cross_bullish"],
    )
    monkeypatch.setattr(
        mod,
        "resolve_and_fetch",
        lambda *a, **k: ("binance", "BTCUSDT", []),
    )
    monkeypatch.setattr(mod, "run_feature_redundancy_study", lambda *a, **k: fake)

    res = client.get(
        "/api/engine/strategy-lab/feature-redundancy/study",
        params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 100},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "no auto-reject" in body["disclaimer"].lower()
    assert body["n_bars"] == 100


def test_feature_redundancy_study_rejects_missing_symbol():
    res = client.get("/api/engine/strategy-lab/feature-redundancy/study")
    assert res.status_code == 422


def test_ablation_oos_study_monkeypatched(monkeypatch):
    from app.api import strategy_lab_research as mod
    from app.strategy_lab.ablation_oos import AblationOosReport
    from app.strategy_lab.deep_history import LabHistoryBundle

    fake = AblationOosReport(
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        ladder="default",
        n_bars=200,
        n_folds=2,
        train_bars=100,
        test_bars=40,
    )
    fake_bundle = LabHistoryBundle(
        dataset_id="live_test",
        candles=[],
        manifest={"dataset_id": "live_test"},
        quality={"ok": True, "n_candles": 200, "codes": [], "code_counts": {}, "n_issues": 0, "degraded": False},
        data_warning=None,
    )
    monkeypatch.setattr(mod, "resolve_lab_history", lambda *a, **k: fake_bundle)
    monkeypatch.setattr(mod, "run_ablation_oos_study_on_candles", lambda *a, **k: fake)

    res = client.post(
        "/api/engine/strategy-lab/ablation-oos/study",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200, "ladder": "default"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "no auto-reject" in body["disclaimer"].lower()


def test_ablation_oos_study_rejects_missing_symbol():
    res = client.post("/api/engine/strategy-lab/ablation-oos/study", json={})
    assert res.status_code == 422


def test_walk_forward_route_monkeypatched(monkeypatch):
    """Hermetic: must not call live providers (rév.53)."""
    from app.api import strategy_lab_wf as mod
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.walk_forward import WalkForwardReport

    rs = get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001")
    fake = WalkForwardReport(
        symbol="BTCUSDT",
        timeframe="1h",
        ruleset=rs,
        mode="rolling",
        n_bars=200,
        warmup_bars=52,
        train_bars=100,
        test_bars=40,
        step_bars=40,
        folds=[],
        oos_summary={"n_folds": 0, "total_oos_trades": 0},
        quality_report={"ok": True, "n_candles": 200, "codes": [], "code_counts": {}, "n_issues": 0, "degraded": False},
    )
    monkeypatch.setattr(mod, "run_walk_forward", lambda *a, **k: fake)

    res = client.post(
        "/api/engine/strategy-lab/walk-forward",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200},
    )
    assert res.status_code == 200, res.text
    assert res.json()["symbol"] == "BTCUSDT"
    assert res.json()["quality_report"] is not None


def test_regime_slices_route_monkeypatched(monkeypatch):
    """Hermetic: must not call live providers (rév.53)."""
    from app.api import strategy_lab as mod
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.regime_slices import RegimeSliceReport

    rs = get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001")
    fake = RegimeSliceReport(
        symbol="BTCUSDT",
        timeframe="1h",
        ruleset=rs,
        n_bars=200,
        slices=[],
        regime_bar_counts={"GLOBAL": 200},
        quality_report={"ok": True, "n_candles": 200, "codes": [], "code_counts": {}, "n_issues": 0, "degraded": False},
    )
    monkeypatch.setattr(mod, "run_regime_slices", lambda *a, **k: fake)

    res = client.post(
        "/api/engine/strategy-lab/regime-slices",
        json={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 200},
    )
    assert res.status_code == 200, res.text
    assert res.json()["symbol"] == "BTCUSDT"
    assert res.json()["quality_report"] is not None


def test_microstructure_cvd_compare_monkeypatched(monkeypatch):
    from app.api import strategy_lab_research as mod
    from app.indicators.ichimoku import Candle
    from app.microstructure.trade_cvd import CvdCompareReport
    from app.universe.types import AssetClass, Instrument

    candles = [
        Candle(
            time=1_700_000_000,
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=100.0,
            taker_buy_volume=60.0,
        ),
        Candle(
            time=1_700_003_600,
            open=1.5,
            high=2.5,
            low=1.0,
            close=2.0,
            volume=100.0,
            taker_buy_volume=40.0,
        ),
    ]
    fake = CvdCompareReport(
        symbol="BTCUSDT",
        timeframe="1h",
        n_bars=2,
        n_trades=4,
        bars_with_trades=2,
        bars_with_kline_cvd=2,
        bias_agreement_rate=1.0,
        delta_corr=0.99,
        sample=[],
    )
    monkeypatch.setattr(
        mod,
        "get_instrument",
        lambda _s: Instrument(
            id="BTCUSDT",
            asset_class=AssetClass.CRYPTO,
            label="BTC",
            provider="binance",
            provider_symbol="BTCUSDT",
            quote="USDT",
        ),
    )
    monkeypatch.setattr(
        mod,
        "resolve_and_fetch",
        lambda *a, **k: ("binance", "BTCUSDT", candles),
    )
    monkeypatch.setattr(mod, "fetch_binance_agg_trades", lambda *a, **k: [])
    monkeypatch.setattr(mod, "compare_kline_vs_trade_cvd", lambda *a, **k: fake)

    res = client.get(
        "/api/engine/strategy-lab/microstructure/cvd-compare",
        params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 2},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "research only" in body["disclaimer"].lower()
    assert body["bias_agreement_rate"] == 1.0


def test_microstructure_cvd_compare_rejects_non_binance(monkeypatch):
    from app.api import strategy_lab_research as mod
    from app.universe.types import AssetClass, Instrument

    monkeypatch.setattr(
        mod,
        "get_instrument",
        lambda _s: Instrument(
            id="EURUSD",
            asset_class=AssetClass.FOREX,
            label="EURUSD",
            provider="biquote",
            provider_symbol="EURUSD",
            quote="USD",
        ),
    )
    res = client.get(
        "/api/engine/strategy-lab/microstructure/cvd-compare",
        params={"symbol": "EURUSD", "limit": 2},
    )
    assert res.status_code == 422
    assert "binance" in res.json()["detail"].lower()


def test_microstructure_cvd_compare_rejects_missing_symbol():
    res = client.get("/api/engine/strategy-lab/microstructure/cvd-compare")
    assert res.status_code == 422
