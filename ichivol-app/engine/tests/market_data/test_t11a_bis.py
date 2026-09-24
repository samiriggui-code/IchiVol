"""T11a-bis leftovers — raw_fallback, candle volume columns, Lab hardenings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import Asset
from app.db.models import Candle as CandleRow
from app.db.session import SessionLocal
from app.indicators.ichimoku import Candle
from app.market_data.collector import fetch_stored_candles, upsert_candles
from app.market_data.volume_semantics import VolumeType
from app.strategy_lab import deep_history as dh


def test_resolve_exports_resolved_symbol():
    from app.market_data.resolve import ResolvedSymbol, resolve

    r = resolve("NOT_IN_CATALOG_XYZ")
    assert isinstance(r, ResolvedSymbol)
    assert r.resolution == "raw_fallback"
    assert r.provider.id == "binance"


@pytest.mark.skipif(
    SessionLocal is None, reason="no session factory"
)
def test_candle_volume_fields_round_trip_db():
    session = SessionLocal()
    try:
        sym = "T11ABISVOL"
        exch = "binance"
        # Clean prior
        asset = session.execute(
            select(Asset).where(Asset.symbol == sym, Asset.exchange == exch)
        ).scalar_one_or_none()
        if asset is not None:
            session.query(CandleRow).filter_by(asset_id=asset.id).delete()
            session.commit()

        c = Candle(
            time=1_700_000_000,
            open=1.0,
            high=2.0,
            low=0.5,
            close=1.5,
            volume=10.0,
            taker_buy_volume=4.0,
            volume_type=VolumeType.EXCHANGE_VOLUME,
        )
        n = upsert_candles(
            session, symbol=sym, exchange=exch, timeframe="1h", candles=[c]
        )
        assert n == 1
        loaded = fetch_stored_candles(
            session, symbol=sym, exchange=exch, timeframe="1h", limit=10
        )
        assert len(loaded) == 1
        assert loaded[0].taker_buy_volume == 4.0
        assert loaded[0].volume_type == VolumeType.EXCHANGE_VOLUME

        row = session.execute(
            select(CandleRow).join(Asset).where(Asset.symbol == sym)
        ).scalar_one()
        assert row.volume_type == "EXCHANGE_VOLUME"
        assert row.taker_buy_volume == 4.0
    finally:
        session.close()


def test_lab_datasets_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DATASETS_DIR", str(tmp_path / "labds"))
    root = dh._datasets_root()
    assert root == tmp_path / "labds"
    assert root.is_dir()


def test_manifest_write_lock(tmp_path):
    root = tmp_path / "ds"
    root.mkdir()
    dh._save_manifest(root, {"a": {"n": 1}})
    dh._save_manifest(root, {"a": {"n": 1}, "b": {"n": 2}})
    man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert set(man) == {"a", "b"}
    assert (root / "manifest.lock").exists()


def test_lab_drops_forming_candle(tmp_path):
    # last bar still forming relative to now
    now = 1_700_003_600
    bars = [
        Candle(time=1_700_000_000, open=1, high=1, low=1, close=1, volume=1),
        Candle(time=1_700_003_600, open=1, high=1, low=1, close=1, volume=1),  # forming for 1h
    ]
    bundle = dh.bundle_from_live_candles(
        bars, symbol="X", timeframe="1h", provider="binance", now=now
    )
    assert len(bundle.candles) == 1
    assert bundle.candles[0].time == 1_700_000_000
