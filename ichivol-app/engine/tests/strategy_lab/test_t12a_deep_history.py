"""T12a — versioned deep history + validate_candles at construction."""

from __future__ import annotations

import json
from pathlib import Path

from app.market_data.quality import QualityReport
from app.strategy_lab.ablation_oos import run_ablation_oos_study_on_candles
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.deep_history import (
    TWELVE_DATA_MAX_BARS,
    build_or_load_binance_history,
    build_or_load_from_candles,
    bundle_from_live_candles,
    load_dataset,
    quality_report_to_manifest,
    resolve_lab_history,
)
from app.strategy_lab.regime_slices import regime_slices_dict, run_regime_slices_on_candles
from app.strategy_lab.walk_forward import run_walk_forward_on_candles, walk_forward_dict
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_twelve_data_max_bars_cap():
    assert TWELVE_DATA_MAX_BARS == 5_000


def test_quality_report_to_manifest_includes_code_counts():
    from app.market_data.quality import QualityIssue

    report = QualityReport(
        issues=[
            QualityIssue("gap", 1, "missing"),
            QualityIssue("gap", 3, "missing"),
            QualityIssue("duplicate", 2, "dup"),
        ],
        n_candles=10,
    )
    d = quality_report_to_manifest(report)
    assert d["ok"] is False
    assert d["degraded"] is True
    assert d["code_counts"]["gap"] == 2
    assert d["code_counts"]["duplicate"] == 1
    assert "gap" in d["codes"]


def test_build_or_load_persists_sha256_and_quality(tmp_path: Path):
    candles = _make_candles(80, seed=3)
    bundle = build_or_load_from_candles(
        candles,
        dataset_id="test_btc_1h",
        provider="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        root=tmp_path,
        now=int(candles[-1].time) + 7200,
    )
    assert bundle.dataset_id == "test_btc_1h"
    assert "sha256" in bundle.manifest
    assert bundle.quality["n_candles"] == 80
    assert "code_counts" in bundle.quality
    assert (tmp_path / "test_btc_1h.json").exists()
    man = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert man["test_btc_1h"]["sha256"] == bundle.manifest["sha256"]
    assert man["test_btc_1h"]["quality"]["code_counts"] == bundle.quality["code_counts"]

    loaded = load_dataset("test_btc_1h", root=tmp_path)
    assert loaded.manifest["sha256"] == bundle.manifest["sha256"]
    assert len(loaded.candles) == 80


def test_degraded_dataset_usable_with_warning(tmp_path: Path):
    candles = _make_candles(40, seed=1)
    # Force a multi-bar gap between bar 10 and 11.
    from app.indicators.ichimoku import Candle

    fixed = list(candles)
    gap_bar = fixed[11]
    fixed[11] = Candle(
        time=fixed[10].time + 8 * 3600,
        open=gap_bar.open,
        high=gap_bar.high,
        low=gap_bar.low,
        close=gap_bar.close,
        volume=gap_bar.volume,
        taker_buy_volume=gap_bar.taker_buy_volume,
        volume_type=gap_bar.volume_type,
    )
    # Drop bars that would now be out of order relative to the jumped timestamp.
    kept = fixed[:12]
    for c in fixed[12:]:
        if c.time > kept[-1].time:
            kept.append(c)
    bundle = build_or_load_from_candles(
        kept,
        dataset_id="degraded_gap",
        provider="binance",
        symbol="ETHUSDT",
        timeframe="1h",
        root=tmp_path,
        now=int(kept[-1].time) + 7200,
    )
    assert bundle.manifest.get("degraded") is True
    assert bundle.data_warning is not None
    assert "usable" in bundle.data_warning.lower()
    again = load_dataset("degraded_gap", root=tmp_path)
    assert again.data_warning is not None
    assert len(again.candles) == len(kept)


def test_studies_return_quality_report():
    candles = _make_candles(280, seed=7)
    meta = bundle_from_live_candles(
        candles, symbol="BTCUSDT", timeframe="1h", dataset_id="live_test"
    )
    rs = get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001")

    wf = run_walk_forward_on_candles(
        candles,
        rs,
        symbol="BTCUSDT",
        timeframe="1h",
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        dataset_id=meta.dataset_id,
        quality_report=meta.quality,
        data_warning=meta.data_warning,
    )
    wf_body = walk_forward_dict(wf)
    assert wf_body["quality_report"] is not None
    assert "code_counts" in wf_body["quality_report"]
    assert wf_body["dataset_id"] == "live_test"

    rg = run_regime_slices_on_candles(
        candles,
        rs,
        symbol="BTCUSDT",
        timeframe="1h",
        dataset_id=meta.dataset_id,
        quality_report=meta.quality,
        data_warning=meta.data_warning,
    )
    rg_body = regime_slices_dict(rg)
    assert rg_body["quality_report"]["n_candles"] == 280

    abl = run_ablation_oos_study_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        compare_mode="additive",
        layers=(
            ("A_KUMO", {"price_above_kumo": True}),
            ("B_RVOL", {"rvol_min": 1.0}),
        ),
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=1,
        dataset_id=meta.dataset_id,
        quality_report=meta.quality,
        data_warning=meta.data_warning,
    )
    abl_body = abl.to_dict()
    assert abl_body["quality_report"]["ok"] in (True, False)
    assert abl_body["dataset_id"] == "live_test"


def test_day_aligned_cache_single_download(monkeypatch, tmp_path: Path):
    """Two calls same UTC day → one fetch, one file (rév.53)."""
    import app.strategy_lab.deep_history as dh

    candles = _make_candles(48, seed=2)
    fetches = {"n": 0}

    def _fake_fetch(symbol, interval, start_ms, end_ms, *, client=None):
        fetches["n"] += 1
        return list(candles)

    monkeypatch.setattr(dh, "_binance_fetch_range", _fake_fetch)
    # Mid-day UTC then later same day — aligned end identical.
    day0 = 1_704_067_200_000  # 2023-12-01 00:00:00 UTC
    noon = day0 + 12 * 3_600_000
    evening = day0 + 20 * 3_600_000

    b1 = build_or_load_binance_history(
        "BTCUSDT",
        "1h",
        years=2.0,
        end_ms=noon,
        root=tmp_path,
        now=noon // 1000,
    )
    b2 = build_or_load_binance_history(
        "BTCUSDT",
        "1h",
        years=2.0,
        end_ms=evening,
        root=tmp_path,
        now=evening // 1000,
    )
    assert fetches["n"] == 1
    assert b1.dataset_id == b2.dataset_id
    series = list(tmp_path.glob("binance_*.json"))
    assert len(series) == 1


def test_load_dataset_rejects_tampered_sha256(tmp_path: Path):
    candles = _make_candles(40, seed=4)
    bundle = build_or_load_from_candles(
        candles,
        dataset_id="tamper_me",
        provider="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        root=tmp_path,
        now=int(candles[-1].time) + 7200,
    )
    path = tmp_path / "tamper_me.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows[0]["close"] = float(rows[0]["close"]) + 1.0
    path.write_text(json.dumps(rows, separators=(",", ":"), sort_keys=True) + "\n")
    try:
        load_dataset("tamper_me", root=tmp_path)
        raise AssertionError("expected sha256 mismatch")
    except ValueError as exc:
        assert "sha256" in str(exc).lower()
    # Untouched reload still works via a fresh write
    build_or_load_from_candles(
        candles,
        dataset_id="ok_me",
        provider="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        root=tmp_path,
        now=int(candles[-1].time) + 7200,
    )
    assert load_dataset("ok_me", root=tmp_path).dataset_id == "ok_me"
    assert bundle.manifest["sha256"]


def test_short_history_warning_biquote_100_bars(monkeypatch, tmp_path: Path):
    """deep_history on biquote (~100 bars) → coverage warning (rév.53)."""
    candles = _make_candles(100, seed=6)

    class _Prov:
        id = "biquote"

    monkeypatch.setattr(
        "app.market_data.resolve.resolve",
        lambda symbol, default_provider="binance": (_Prov(), "EURUSD"),
    )
    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        lambda *a, **k: (_Prov(), "EURUSD", list(candles)),
    )
    bundle = resolve_lab_history(
        "EURUSD",
        "1h",
        deep_history=True,
        years=2.0,
        limit=5000,
        exchange="biquote",
        root=tmp_path,
        now=int(candles[-1].time) + 7200,
    )
    assert len(bundle.candles) == 100
    assert bundle.history_span_seconds is not None
    assert bundle.history_span_seconds < 2 * 365 * 86400
    assert bundle.history_warning is not None
    assert "demandés" in bundle.history_warning
    assert "historique obtenu" in bundle.history_warning
