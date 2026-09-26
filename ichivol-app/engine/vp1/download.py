"""Download Vision zips + verify CHECKSUM; maintain VP1 manifest."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx

from vp1 import (
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    SPOT_INTERVALS,
    SYMBOLS,
    WINDOW_END,
    WINDOW_START,
)
from vp1.urls import (
    checksum_url,
    day_range,
    funding_monthly_url,
    month_range,
    metrics_daily_url,
    spot_klines_monthly_url,
)

DEFAULT_ROOT = Path(__file__).resolve().parent / "data"
_SLEEP_S = 0.15


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_checksum_line(text: str, expected_name: str | None = None) -> str:
    """Binance CHECKSUM: `<sha256>  <filename>` (two spaces or space)."""
    line = text.strip().splitlines()[0].strip()
    parts = line.split()
    if len(parts) < 2:
        raise ValueError(f"invalid CHECKSUM: {text!r}")
    digest, name = parts[0].lower(), parts[1]
    if expected_name and name != expected_name:
        raise ValueError(f"CHECKSUM name mismatch: {name} != {expected_name}")
    if len(digest) != 64:
        raise ValueError(f"invalid sha256 in CHECKSUM: {digest}")
    return digest


def data_root(root: Path | None = None) -> Path:
    path = root or DEFAULT_ROOT
    path.mkdir(parents=True, exist_ok=True)
    (path / "raw").mkdir(exist_ok=True)
    (path / "series").mkdir(exist_ok=True)
    return path


def manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def load_manifest(root: Path) -> dict:
    path = manifest_path(root)
    if not path.exists():
        return {
            "protocol": PROTOCOL_ID,
            "protocol_version": PROTOCOL_VERSION,
            "window_utc": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
            "symbols": list(SYMBOLS),
            "files": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(root: Path, man: dict) -> None:
    tmp = manifest_path(root).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(manifest_path(root))


def _get(client: httpx.Client, url: str) -> bytes:
    for attempt in range(5):
        r = client.get(url, timeout=60, follow_redirects=True)
        if r.status_code in (418, 429):
            time.sleep(int(r.headers.get("Retry-After", "5")) + 1)
            continue
        if r.status_code == 404:
            raise FileNotFoundError(url)
        r.raise_for_status()
        time.sleep(_SLEEP_S)
        return r.content
    raise RuntimeError(f"rate limited: {url}")


def download_verified(
    client: httpx.Client,
    url: str,
    dest: Path,
    *,
    kind: str,
    meta: dict | None = None,
) -> dict:
    """Fetch zip + CHECKSUM; write dest only if digest matches. Returns file manifest entry."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    name = dest.name
    if dest.exists():
        local = sha256_bytes(dest.read_bytes())
        entry = {
            "url": url,
            "sha256": local,
            "bytes": dest.stat().st_size,
            "kind": kind,
            "fetched_at": None,
            "cached": True,
            **(meta or {}),
        }
        return entry

    checksum_body = _get(client, checksum_url(url)).decode("utf-8", errors="replace")
    expected = parse_checksum_line(checksum_body, expected_name=name)
    payload = _get(client, url)
    digest = sha256_bytes(payload)
    if digest != expected:
        raise ValueError(f"sha256 mismatch for {url}: got {digest}, want {expected}")
    dest.write_bytes(payload)
    return {
        "url": url,
        "sha256": digest,
        "binance_checksum": expected,
        "bytes": len(payload),
        "kind": kind,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cached": False,
        **(meta or {}),
    }


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def download_spot_klines(
    root: Path,
    *,
    symbols: Iterable[str] = SYMBOLS,
    intervals: Iterable[str] = SPOT_INTERVALS,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    client: httpx.Client | None = None,
) -> dict:
    own = client is None
    client = client or httpx.Client()
    man = load_manifest(root)
    try:
        for symbol in symbols:
            for interval in intervals:
                for year, month in month_range(start, end):
                    url = spot_klines_monthly_url(symbol, interval, year, month)
                    dest = (
                        root
                        / "raw"
                        / "spot"
                        / "klines"
                        / symbol
                        / interval
                        / f"{symbol}-{interval}-{year}-{month:02d}.zip"
                    )
                    key = rel(root, dest)
                    try:
                        entry = download_verified(
                            client,
                            url,
                            dest,
                            kind="spot_klines_monthly",
                            meta={"symbol": symbol, "interval": interval, "year": year, "month": month},
                        )
                        man["files"][key] = entry
                    except FileNotFoundError:
                        man["files"][key] = {
                            "url": url,
                            "missing": True,
                            "kind": "spot_klines_monthly",
                            "symbol": symbol,
                            "interval": interval,
                            "year": year,
                            "month": month,
                        }
        save_manifest(root, man)
        return man
    finally:
        if own:
            client.close()


def download_funding(
    root: Path,
    *,
    symbols: Iterable[str] = SYMBOLS,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    client: httpx.Client | None = None,
) -> dict:
    own = client is None
    client = client or httpx.Client()
    man = load_manifest(root)
    try:
        for symbol in symbols:
            for year, month in month_range(start, end):
                url = funding_monthly_url(symbol, year, month)
                dest = (
                    root
                    / "raw"
                    / "futures"
                    / "um"
                    / "fundingRate"
                    / symbol
                    / f"{symbol}-fundingRate-{year}-{month:02d}.zip"
                )
                key = rel(root, dest)
                try:
                    entry = download_verified(
                        client,
                        url,
                        dest,
                        kind="futures_funding_monthly",
                        meta={"symbol": symbol, "year": year, "month": month},
                    )
                    man["files"][key] = entry
                except FileNotFoundError:
                    man["files"][key] = {
                        "url": url,
                        "missing": True,
                        "kind": "futures_funding_monthly",
                        "symbol": symbol,
                        "year": year,
                        "month": month,
                    }
        save_manifest(root, man)
        return man
    finally:
        if own:
            client.close()


def download_metrics_oi(
    root: Path,
    *,
    symbols: Iterable[str] = SYMBOLS,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
    client: httpx.Client | None = None,
) -> dict:
    """Daily metrics zips (sum_open_interest). Many files — resume-friendly."""
    own = client is None
    client = client or httpx.Client()
    man = load_manifest(root)
    try:
        for symbol in symbols:
            for day in day_range(start, end):
                url = metrics_daily_url(symbol, day)
                dest = (
                    root
                    / "raw"
                    / "futures"
                    / "um"
                    / "metrics"
                    / symbol
                    / f"{symbol}-metrics-{day.isoformat()}.zip"
                )
                key = rel(root, dest)
                if key in man.get("files", {}) and not man["files"][key].get("missing"):
                    if dest.exists():
                        continue
                try:
                    entry = download_verified(
                        client,
                        url,
                        dest,
                        kind="futures_metrics_daily",
                        meta={"symbol": symbol, "day": day.isoformat()},
                    )
                    man["files"][key] = entry
                except FileNotFoundError:
                    man["files"][key] = {
                        "url": url,
                        "missing": True,
                        "kind": "futures_metrics_daily",
                        "symbol": symbol,
                        "day": day.isoformat(),
                    }
                if len(man["files"]) % 50 == 0:
                    save_manifest(root, man)
        save_manifest(root, man)
        return man
    finally:
        if own:
            client.close()
