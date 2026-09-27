"""Build frozen series JSON from Vision zips; frozen loader (no network)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from vp1 import PROTOCOL_ID, PROTOCOL_VERSION, WINDOW_END, WINDOW_START
from vp1.download import data_root, load_manifest, rel, save_manifest, sha256_bytes


# Vision spot klines switch from milliseconds to microseconds on 2025-01-01.
_US_THRESHOLD = 1_000_000_000_000_000  # 1e15


def normalize_vision_time_ms(ts: int) -> int:
    """Normalize Vision open/close time to milliseconds (µs → //1000 if ≥1e15)."""
    t = int(ts)
    if t >= _US_THRESHOLD:
        return t // 1000
    return t


INTERVAL_MS: dict[str, int] = {
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

# Max allowed missing bars as fraction of expected count before hard fail.
COMPLETENESS_GAP_FRAC = 0.02


def _window_ms() -> tuple[int, int]:
    start = datetime(WINDOW_START.year, WINDOW_START.month, WINDOW_START.day, tzinfo=timezone.utc)
    # inclusive end day → exclusive next midnight
    end_excl = datetime(WINDOW_END.year, WINDOW_END.month, WINDOW_END.day, tzinfo=timezone.utc)
    end_excl = end_excl.replace(hour=0) + __import__("datetime").timedelta(days=1)
    return int(start.timestamp() * 1000), int(end_excl.timestamp() * 1000)


def read_zip_csv_rows(zip_path: Path) -> list[list[str]]:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            raise ValueError(f"no csv in {zip_path}")
        raw = zf.read(names[0])
    text = raw.decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


def klines_from_spot_zip(zip_path: Path, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    """Vision spot kline CSV: no header; col0=open_time, col6=close_time (ms or µs)."""
    rows = read_zip_csv_rows(zip_path)
    out: list[dict[str, Any]] = []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for r in rows:
        if not r or r[0].startswith("open"):
            continue
        open_ms = normalize_vision_time_ms(int(r[0]))
        close_ms = normalize_vision_time_ms(int(r[6]))
        if open_ms < start_ms or open_ms >= end_ms:
            continue
        if close_ms >= now_ms:
            continue  # forming bar
        out.append(
            {
                "open_time": open_ms,
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                "close_time": close_ms,
                "taker_buy_base": float(r[9]) if len(r) > 9 and r[9] else None,
            }
        )
    return out


def find_bar_gaps(
    open_times_ms: list[int],
    interval: str,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> list[dict[str, Any]]:
    """List missing-bar gaps (open_time expected but absent)."""
    step = INTERVAL_MS[interval]
    if not open_times_ms:
        if start_ms is not None and end_ms is not None:
            return [{"from_ms": start_ms, "to_ms": end_ms, "missing": (end_ms - start_ms) // step}]
        return [{"from_ms": None, "to_ms": None, "missing": 0, "empty": True}]
    times = sorted(open_times_ms)
    gaps: list[dict[str, Any]] = []
    if start_ms is not None and times[0] > start_ms:
        missing = (times[0] - start_ms) // step
        if missing > 0:
            gaps.append({"from_ms": start_ms, "to_ms": times[0], "missing": missing})
    for a, b in zip(times, times[1:]):
        if b - a > step:
            missing = (b - a) // step - 1
            if missing > 0:
                gaps.append({"from_ms": a + step, "to_ms": b, "missing": missing})
    if end_ms is not None:
        # last expected open = end_ms - step (exclusive end)
        last_expected = end_ms - step
        if times[-1] < last_expected:
            missing = (last_expected - times[-1]) // step
            if missing > 0:
                gaps.append({"from_ms": times[-1] + step, "to_ms": end_ms, "missing": missing})
    return gaps


def assert_series_completeness(
    bars: list[dict[str, Any]],
    interval: str,
    *,
    start_ms: int,
    end_ms: int,
    max_gap_frac: float = COMPLETENESS_GAP_FRAC,
) -> dict[str, Any]:
    """Count expected vs obtained bars; raise if gap fraction exceeds threshold."""
    step = INTERVAL_MS[interval]
    expected = max(0, (end_ms - start_ms) // step)
    obtained = len(bars)
    opens = [int(b["open_time"]) for b in bars]
    gaps = find_bar_gaps(opens, interval, start_ms=start_ms, end_ms=end_ms)
    missing = sum(int(g["missing"]) for g in gaps)
    frac = (missing / expected) if expected else 1.0
    report = {
        "interval": interval,
        "expected": expected,
        "obtained": obtained,
        "missing": missing,
        "gap_frac": frac,
        "gaps": gaps[:50],  # cap list for errors
        "n_gap_segments": len(gaps),
    }
    if expected > 0 and frac > max_gap_frac:
        raise ValueError(
            f"VP1 completeness fail {interval}: obtained={obtained} expected={expected} "
            f"missing={missing} ({frac:.2%} > {max_gap_frac:.2%}); "
            f"gaps={gaps[:20]}"
        )
    return report


def build_spot_series(
    root: Path,
    symbol: str,
    interval: str,
    *,
    start: date = WINDOW_START,
    end: date = WINDOW_END,
) -> dict[str, Any]:
    start_ms, end_ms = _window_ms()
    # Override with explicit dates if needed — use constants for now
    raw_dir = root / "raw" / "spot" / "klines" / symbol / interval
    bars: list[dict[str, Any]] = []
    sources: list[str] = []
    if raw_dir.exists():
        for zip_path in sorted(raw_dir.glob(f"{symbol}-{interval}-*.zip")):
            bars.extend(klines_from_spot_zip(zip_path, start_ms, end_ms))
            sources.append(rel(root, zip_path))
    bars.sort(key=lambda b: b["open_time"])
    # dedupe by open_time
    dedup: dict[int, dict[str, Any]] = {}
    for b in bars:
        dedup[b["open_time"]] = b
    bars = [dedup[k] for k in sorted(dedup)]

    completeness = assert_series_completeness(
        bars, interval, start_ms=start_ms, end_ms=end_ms
    )

    body_obj = {
        "protocol": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "kind": "spot_klines",
        "symbol": symbol,
        "interval": interval,
        "window": [start.isoformat(), end.isoformat()],
        "n_bars": len(bars),
        "completeness": {
            "expected": completeness["expected"],
            "obtained": completeness["obtained"],
            "missing": completeness["missing"],
            "gap_frac": completeness["gap_frac"],
            "n_gap_segments": completeness["n_gap_segments"],
        },
        "bars": bars,
    }
    body = json.dumps(body_obj, separators=(",", ":"), sort_keys=True)
    digest = sha256_bytes(body.encode("utf-8"))
    out_name = f"{symbol}_spot_{interval}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.json"
    out_path = root / "series" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")

    man = load_manifest(root)
    man["files"][rel(root, out_path)] = {
        "sha256": digest,
        "kind": "series_spot_klines",
        "symbol": symbol,
        "interval": interval,
        "n_rows": len(bars),
        "expected_rows": completeness["expected"],
        "missing_rows": completeness["missing"],
        "first_open_ms": bars[0]["open_time"] if bars else None,
        "last_open_ms": bars[-1]["open_time"] if bars else None,
        "source_files": sources,
        "bytes": len(body.encode("utf-8")),
        "time_unit": "ms",
        "vision_us_normalized": True,
    }
    save_manifest(root, man)
    return man["files"][rel(root, out_path)]


def load_series(root: Path, relative_path: str, *, allow_network: bool = False) -> dict[str, Any]:
    """Frozen loader: verifies sha256 against manifest. Refuses network."""
    if allow_network:
        raise ValueError("VP1 frozen loader must not use network (allow_network forbidden)")
    root = data_root(root)
    man = load_manifest(root)
    entry = man.get("files", {}).get(relative_path)
    if entry is None:
        raise FileNotFoundError(f"not in manifest: {relative_path}")
    if entry.get("missing"):
        raise FileNotFoundError(f"manifest marks missing: {relative_path}")
    path = root / relative_path
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    expected = entry.get("sha256")
    if expected and digest != expected:
        raise ValueError(f"sha256 mismatch for {relative_path}: got {digest}, want {expected}")
    if relative_path.endswith(".json"):
        return json.loads(raw.decode("utf-8"))
    return {"path": relative_path, "sha256": digest, "bytes": len(raw)}


def verify_manifest(root: Path) -> list[str]:
    """Return list of error strings (empty = OK). Skips missing=True entries."""
    root = data_root(root)
    man = load_manifest(root)
    errors: list[str] = []
    for key, entry in man.get("files", {}).items():
        if entry.get("missing"):
            continue
        path = root / key
        if not path.exists():
            errors.append(f"missing file: {key}")
            continue
        digest = sha256_bytes(path.read_bytes())
        if entry.get("sha256") and digest != entry["sha256"]:
            errors.append(f"sha256 mismatch: {key}")
    return errors
