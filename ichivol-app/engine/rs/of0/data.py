"""Klines 1 s : téléchargement vérifié, lecture en flux par heure (RS-07 §1)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterator

from rs.of0 import DATA_END_EXCL_MS, DOWNLOAD_END, DOWNLOAD_START, HOUR_MS, SYMBOL

VISION = "https://data.binance.vision/data/spot/monthly/klines"
INTERVAL = "1s"

# (open_ms, open, high, low, close, volume, taker_buy)
Second = tuple[int, float, float, float, float, float, float]


def months() -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = DOWNLOAD_START.year, DOWNLOAD_START.month
    while (y, m) <= (DOWNLOAD_END.year, DOWNLOAD_END.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def zip_name(y: int, m: int) -> str:
    return f"{SYMBOL}-{INTERVAL}-{y}-{m:02d}.zip"


def raw_dir(root: Path) -> Path:
    return root / "raw" / SYMBOL / INTERVAL


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=600) as r:
        return r.read()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_month(root: Path, y: int, m: int) -> dict:
    name = zip_name(y, m)
    url = f"{VISION}/{SYMBOL}/{INTERVAL}/{name}"
    expected = _get(url + ".CHECKSUM").decode().split()[0].strip().lower()
    path = raw_dir(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or _sha256(path) != expected:
        tmp = path.with_suffix(".part")
        tmp.write_bytes(_get(url))
        tmp.replace(path)
    digest = _sha256(path)
    if digest != expected:
        raise ValueError(f"checksum mismatch {name}: {digest} != {expected}")
    return {"url": url, "file": name, "sha256": digest, "binance_checksum": expected}


def write_manifest(root: Path, entries: list[dict]) -> str:
    body = json.dumps({SYMBOL: sorted(entries, key=lambda e: e["file"])}, indent=1, sort_keys=True)
    (root / "manifest.json").write_text(body, encoding="utf-8")
    return hashlib.sha256(body.encode()).hexdigest()


def iter_seconds(zip_path: Path) -> Iterator[Second]:
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            with z.open(member) as fh:
                for row in csv.reader(io.TextIOWrapper(fh, encoding="ascii")):
                    if not row or not row[0].isdigit():
                        continue
                    t = int(row[0])
                    if t > 10**14:  # µs (archives 2025+)
                        t //= 1000
                    if t >= DATA_END_EXCL_MS:
                        raise AssertionError("barre >= 2025-01-01 lue")
                    yield (t, float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]), float(row[9]))


def iter_hours(seconds: Iterator[Second]) -> Iterator[tuple[int, list[Second]]]:
    """Regroupe des secondes triées par heure UTC `[h, h+1h)`."""
    cur: int | None = None
    buf: list[Second] = []
    for s in seconds:
        h = s[0] - s[0] % HOUR_MS
        if h != cur:
            if buf:
                yield cur, buf  # type: ignore[misc]
            cur, buf = h, []
        buf.append(s)
    if buf:
        yield cur, buf  # type: ignore[misc]


def load_vp1_1h(path: Path) -> dict[int, tuple[float, float]]:
    """(volume, taker_buy) des klines 1h VP1, **tronquées < 2025** à la lecture (C1)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, tuple[float, float]] = {}
    for b in payload["bars"]:
        t = int(b["open_time"])
        if t >= DATA_END_EXCL_MS:
            continue
        out[t] = (float(b["volume"]), float(b["taker_buy_base"]))
    return out
