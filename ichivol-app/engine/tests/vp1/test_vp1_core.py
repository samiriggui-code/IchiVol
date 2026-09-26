"""VP1 unit tests — URL builders, CHECKSUM parse, frozen loader (no network)."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from vp1.download import parse_checksum_line, sha256_bytes
from vp1.load import load_series, verify_manifest
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
    # Dense 1h bars for Sept 2020 only would fail completeness on full window —
    # build with a tiny root window via monkeypatch? Instead write enough continuous
    # bars is heavy. Use klines_from_spot_zip + normalize unit tests for µs;
    # here keep one bar and expect completeness fail → catch by building only
    # after patching COMPLETENESS? Simpler: call normalize + klines directly.

    open_ms = int(datetime(2020, 9, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    close_ms = open_ms + 3_600_000 - 1
    csv = f"{open_ms},100,101,99,100.5,10,{close_ms},0,0,5,0,0\n"
    zpath = raw / "BTCUSDT-1h-2020-09.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("BTCUSDT-1h-2020-09.csv", csv)

    from vp1.load import klines_from_spot_zip

    bars = klines_from_spot_zip(zpath, open_ms, open_ms + 3_600_000)
    assert len(bars) == 1
    assert bars[0]["close"] == 100.5


def test_normalize_vision_microseconds():
    from vp1.load import normalize_vision_time_ms

    # 2025-01-01 00:00 UTC in µs (Vision spot post-2025)
    us = 1_735_689_600_000_000
    assert us >= 1_000_000_000_000_000
    assert normalize_vision_time_ms(us) == us // 1000
    ms = 1_600_000_000_000
    assert normalize_vision_time_ms(ms) == ms


def test_klines_accept_microsecond_rows(tmp_path: Path):
    from datetime import datetime, timezone

    from vp1.load import klines_from_spot_zip

    raw = tmp_path
    # 2025-01-01 bar in µs
    open_us = int(datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)
    close_us = open_us + 3_600_000_000 - 1_000
    assert open_us >= 1e15
    csv = f"{open_us},100,101,99,100.5,10,{close_us},0,0,5,0,0\n"
    zpath = raw / "BTCUSDT-1h-2025-01.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("x.csv", csv)
    start_ms = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = start_ms + 3_600_000
    bars = klines_from_spot_zip(zpath, start_ms, end_ms)
    assert len(bars) == 1
    assert bars[0]["open_time"] == start_ms
    assert bars[0]["close_time"] == close_us // 1000


def test_completeness_fails_on_large_gap():
    from vp1.load import assert_series_completeness

    # Two bars with a huge hole
    t0 = 1_600_000_000_000
    bars = [
        {"open_time": t0},
        {"open_time": t0 + 100 * 3_600_000},
    ]
    with pytest.raises(ValueError, match="completeness"):
        assert_series_completeness(
            bars, "1h", start_ms=t0, end_ms=t0 + 200 * 3_600_000, max_gap_frac=0.02
        )
