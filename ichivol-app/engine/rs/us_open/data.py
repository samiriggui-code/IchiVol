"""Téléchargement vérifié et chargement des klines 5 min (RS-05 §1)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from rs.us_open import DATA_END_EXCL_MS, DAY_END, DOWNLOAD_START, INTERVAL

VISION = "https://data.binance.vision/data/spot/monthly/klines"

# open_ms -> (open, high, low, close, volume)
Bars = dict[int, tuple[float, float, float, float, float]]


def months(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def download(symbol: str, root: Path) -> list[dict]:
    """Télécharge les zips mensuels manquants ; vérifie le sha256 contre le .CHECKSUM Binance."""
    out_dir = root / "raw" / symbol / INTERVAL
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for y, m in months(DOWNLOAD_START, DAY_END):
        name = f"{symbol}-{INTERVAL}-{y}-{m:02d}.zip"
        url = f"{VISION}/{symbol}/{INTERVAL}/{name}"
        expected = _get(url + ".CHECKSUM").decode().split()[0].strip().lower()
        path = out_dir / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            path.write_bytes(_get(url))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"checksum mismatch {name}: {digest} != {expected}")
        entries.append({"url": url, "file": name, "sha256": digest, "binance_checksum": expected})
    return entries


def write_manifest(root: Path, manifest: dict[str, list[dict]]) -> str:
    body = json.dumps(manifest, indent=1, sort_keys=True)
    (root / "manifest.json").write_text(body, encoding="utf-8")
    return hashlib.sha256(body.encode()).hexdigest()


def parse_zip(blob: bytes) -> Bars:
    bars: Bars = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            text = z.read(member).decode()
            for row in csv.reader(io.StringIO(text)):
                if not row or not row[0].strip().isdigit():
                    continue  # en-tête éventuel
                t = int(row[0])
                if t > 10**14:  # horodatage en µs (archives 2025+)
                    t //= 1000
                bars[t] = (float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
    return bars


def truncate(bars: Bars, end_excl_ms: int = DATA_END_EXCL_MS) -> Bars:
    out = {t: b for t, b in bars.items() if t < end_excl_ms}
    assert_no_reserved(out, end_excl_ms)
    return out


def assert_no_reserved(bars: Bars, end_excl_ms: int = DATA_END_EXCL_MS) -> None:
    bad = [t for t in bars if t >= end_excl_ms]
    if bad:
        raise AssertionError(f"{len(bad)} barre(s) >= 2025-01-01 chargées")


def load(symbol: str, root: Path) -> Bars:
    bars: Bars = {}
    for path in sorted((root / "raw" / symbol / INTERVAL).glob(f"{symbol}-{INTERVAL}-*.zip")):
        bars.update(parse_zip(path.read_bytes()))
    return truncate(bars)
