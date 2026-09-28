"""VP-P data: Binance Vision spot klines (1h + 4h) for the paper universe, 2020-09-01 → 2024-12-31 only.

Same discipline as VP1 (vp1.download / vp1.load): every zip is checked against Binance's CHECKSUM, the built
series carry a sha256 in ``vpp/data/manifest.json`` and the loader refuses a file whose digest changed.
Months before a symbol's listing are 404 on Vision: recorded as ``missing`` (the symbol simply starts later).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.indicators.ichimoku import Candle
from vp1.download import download_verified, rel
from vp1.load import INTERVAL_MS, find_bar_gaps, klines_from_spot_zip
from vp1.urls import month_range, spot_klines_monthly_url

from vpp import DATA_END, DATA_START, INTERVALS, PROTOCOL_ID, PROTOCOL_VERSION, U20

DEFAULT_ROOT = Path(__file__).resolve().parent / "data"


def _window_ms() -> tuple[int, int]:
    start = datetime(DATA_START.year, DATA_START.month, DATA_START.day, tzinfo=timezone.utc)
    end_excl = datetime(DATA_END.year, DATA_END.month, DATA_END.day, tzinfo=timezone.utc) + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end_excl.timestamp() * 1000)


def data_root(root: Path | None = None) -> Path:
    path = root or DEFAULT_ROOT
    (path / "raw").mkdir(parents=True, exist_ok=True)
    (path / "series").mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def load_manifest(root: Path) -> dict:
    path = _manifest_path(root)
    if not path.exists():
        return {
            "protocol": PROTOCOL_ID,
            "protocol_version": PROTOCOL_VERSION,
            "window_utc": [DATA_START.isoformat(), DATA_END.isoformat()],
            "files": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(root: Path, man: dict) -> None:
    tmp = _manifest_path(root).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(_manifest_path(root))


def download(
    root: Path | None = None,
    *,
    symbols: Iterable[str] = U20,
    intervals: Iterable[str] = INTERVALS,
    client: httpx.Client | None = None,
) -> dict:
    """Fetch monthly spot zips (verified) for the data window. Resume-friendly (existing zips are reused)."""
    root = data_root(root)
    own = client is None
    client = client or httpx.Client()
    man = load_manifest(root)
    try:
        for symbol in symbols:
            for interval in intervals:
                for year, month in month_range(DATA_START, DATA_END):
                    url = spot_klines_monthly_url(symbol, interval, year, month)
                    dest = root / "raw" / symbol / interval / f"{symbol}-{interval}-{year}-{month:02d}.zip"
                    key = rel(root, dest)
                    if man["files"].get(key, {}).get("missing"):
                        continue
                    meta = {"symbol": symbol, "interval": interval, "year": year, "month": month}
                    try:
                        man["files"][key] = download_verified(client, url, dest, kind="spot_klines_monthly", meta=meta)
                    except FileNotFoundError:
                        man["files"][key] = {"url": url, "missing": True, "kind": "spot_klines_monthly", **meta}
            save_manifest(root, man)
        return man
    finally:
        if own:
            client.close()


def series_rel(symbol: str, interval: str) -> str:
    return f"series/{symbol}_spot_{interval}_{DATA_START:%Y%m%d}_{DATA_END:%Y%m%d}.json"


def build(root: Path | None = None, *, symbols: Iterable[str] = U20, intervals: Iterable[str] = INTERVALS) -> dict:
    """Build one frozen JSON series per symbol × interval and record its sha256 + gap report."""
    root = data_root(root)
    start_ms, end_ms = _window_ms()
    man = load_manifest(root)
    for symbol in symbols:
        for interval in intervals:
            raw_dir = root / "raw" / symbol / interval
            bars: dict[int, dict[str, Any]] = {}
            sources: list[str] = []
            for zip_path in sorted(raw_dir.glob(f"{symbol}-{interval}-*.zip")):
                for b in klines_from_spot_zip(zip_path, start_ms, end_ms):
                    bars[b["open_time"]] = b
                sources.append(rel(root, zip_path))
            ordered = [bars[k] for k in sorted(bars)]
            if not ordered:
                raise ValueError(f"no bars for {symbol} {interval}")
            # completeness is judged from the first listed bar (a later listing is not a gap)
            gaps = find_bar_gaps([b["open_time"] for b in ordered], interval,
                                 start_ms=ordered[0]["open_time"], end_ms=end_ms)
            missing = sum(int(g["missing"]) for g in gaps)
            body = json.dumps(
                {"protocol": PROTOCOL_ID, "protocol_version": PROTOCOL_VERSION, "symbol": symbol,
                 "interval": interval, "n_bars": len(ordered), "bars": ordered},
                separators=(",", ":"), sort_keys=True,
            )
            out = root / series_rel(symbol, interval)
            out.write_text(body, encoding="utf-8")
            man["files"][series_rel(symbol, interval)] = {
                "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "kind": "series_spot_klines",
                "symbol": symbol,
                "interval": interval,
                "n_rows": len(ordered),
                "first_open_ms": ordered[0]["open_time"],
                "last_open_ms": ordered[-1]["open_time"],
                "missing_rows_since_listing": missing,
                "gap_frac_since_listing": missing / max(1, (end_ms - ordered[0]["open_time"]) // INTERVAL_MS[interval]),
                "n_gap_segments": len(gaps),
                "source_files": len(sources),
            }
    save_manifest(root, man)
    return man


def load_candles(symbol: str, interval: str, root: Path | None = None) -> tuple[list[Candle], str]:
    """Frozen loader: verifies the manifest sha256, never touches the network."""
    root = data_root(root)
    key = series_rel(symbol, interval)
    entry = load_manifest(root)["files"].get(key)
    if entry is None:
        raise FileNotFoundError(f"not in VP-P manifest: {key}")
    raw = (root / key).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["sha256"]:
        raise ValueError(f"sha256 mismatch for {key}: got {digest}, want {entry['sha256']}")
    payload = json.loads(raw.decode("utf-8"))
    _, end_ms = _window_ms()
    candles = [
        Candle(
            time=int(b["open_time"] // 1000), open=float(b["open"]), high=float(b["high"]), low=float(b["low"]),
            close=float(b["close"]), volume=float(b["volume"]),
            taker_buy_volume=float(b["taker_buy_base"]) if b.get("taker_buy_base") is not None else None,
        )
        for b in payload["bars"]
        if b["open_time"] < end_ms  # defensive: nothing after 2024-12-31 can enter a run
    ]
    return candles, digest
