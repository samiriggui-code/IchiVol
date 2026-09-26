"""VP1 unit tests — URL builders, CHECKSUM parse, frozen loader (no network)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from vp1.download import parse_checksum_line, sha256_bytes
from vp1.load import build_spot_series, load_series, verify_manifest
from vp1.urls import checksum_url, funding_monthly_url, month_range, spot_klines_monthly_url


def test_month_range_inclusive():
    from datetime import date

    assert month_range(date(2020, 9, 1), date(2020, 11, 15)) == [
        (2020, 9),
        (2020, 10),
        (2020, 11),
    ]


def test_spot_and_funding_urls():
    u = spot_klines_monthly_url("BTCUSDT", "1h", 2020, 9)
    assert u.endswith("/BTCUSDT-1h-2020-09.zip")
    assert "data.binance.vision/data/spot/monthly/klines" in u
    assert checksum_url(u).endswith(".zip.CHECKSUM")
    f = funding_monthly_url("ETHUSDT", 2021, 1)
    assert "futures/um/monthly/fundingRate/ETHUSDT" in f


def test_parse_checksum_line():
    digest = "a" * 64
    assert parse_checksum_line(f"{digest}  BTCUSDT-1h-2020-09.zip", "BTCUSDT-1h-2020-09.zip") == digest
    with pytest.raises(ValueError):
        parse_checksum_line(f"{digest}  WRONG.zip", "BTCUSDT-1h-2020-09.zip")


def test_frozen_loader_verifies_sha256(tmp_path: Path):
    root = tmp_path
    (root / "series").mkdir(parents=True)
    payload = {"protocol": "VP1", "bars": [{"open_time": 1}]}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    rel = "series/test.json"
    path = root / rel
    path.write_text(body, encoding="utf-8")
    digest = sha256_bytes(body.encode())
    man = {
        "protocol": "VP1",
        "files": {rel: {"sha256": digest, "kind": "series_spot_klines"}},
    }
    (root / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

    loaded = load_series(root, rel)
    assert loaded["protocol"] == "VP1"

    # Tamper
    path.write_text(body + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        load_series(root, rel)

    with pytest.raises(ValueError, match="network"):
        load_series(root, rel, allow_network=True)


def test_build_spot_series_from_synthetic_zip(tmp_path: Path):
    from datetime import datetime, timezone

    root = tmp_path
    raw = root / "raw" / "spot" / "klines" / "BTCUSDT" / "1h"
    raw.mkdir(parents=True)
    # One closed bar in window
    open_ms = int(datetime(2020, 9, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    close_ms = open_ms + 3_600_000 - 1
    csv = f"{open_ms},100,101,99,100.5,10,{close_ms},0,0,5,0,0\n"
    zpath = raw / "BTCUSDT-1h-2020-09.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("BTCUSDT-1h-2020-09.csv", csv)

    (root / "manifest.json").write_text(
        json.dumps({"protocol": "VP1", "files": {}}), encoding="utf-8"
    )
    entry = build_spot_series(root, "BTCUSDT", "1h")
    assert entry["n_rows"] == 1
    assert verify_manifest(root) == []
    rel = f"series/BTCUSDT_spot_1h_20200901_20260831.json"
    series = load_series(root, rel)
    assert series["n_bars"] == 1
    assert series["bars"][0]["close"] == 100.5
