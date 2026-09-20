"""Public Binance klines (data-api.binance.vision, free, no key) with a local cache.

Provenance is recorded per file (source URL, fetch time, sha256, bar count) in
``research_lab/cache/manifest.json`` so a run can name the exact data version.
Only fully closed bars are ever stored.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "https://data-api.binance.vision"
CACHE = Path(__file__).parent / "cache"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
_MIN_SLEEP_S = 0.12  # ~8 req/s, far below the 6000 weight/min public limit (klines = weight 2)


def _get(client: httpx.Client, path: str, params: dict) -> list | dict:
    for attempt in range(5):
        r = client.get(BASE + path, params=params, timeout=30)
        if r.status_code in (418, 429):
            time.sleep(int(r.headers.get("Retry-After", "5")) + 1)
            continue
        r.raise_for_status()
        time.sleep(_MIN_SLEEP_S)
        return r.json()
    raise RuntimeError(f"rate limited: {path} {params}")


def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int, client: httpx.Client | None = None) -> list[list]:
    """Closed bars with open time in [start_ms, end_ms). Paginates by 1000."""
    own = client is None
    client = client or httpx.Client()
    out: list[list] = []
    step = INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000)
    cur = start_ms
    try:
        while cur < end_ms:
            rows = _get(client, "/api/v3/klines", {"symbol": symbol, "interval": interval, "startTime": cur, "limit": 1000})
            if not rows:
                break
            for r in rows:
                if r[0] >= end_ms:
                    break
                if r[6] < now_ms:  # close time already passed -> bar is closed
                    out.append(r)
            last_open = rows[-1][0]
            if last_open + step <= cur:
                break
            cur = last_open + step
            if len(rows) < 1000:
                break
    finally:
        if own:
            client.close()
    return out


def load_or_fetch(symbol: str, interval: str, start_ms: int, end_ms: int, client: httpx.Client | None = None) -> list[list]:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{symbol}_{interval}_{start_ms}_{end_ms}.json"
    if path.exists():
        return json.loads(path.read_text())
    rows = fetch_klines(symbol, interval, start_ms, end_ms, client)
    body = json.dumps(rows)
    path.write_text(body)
    man_path = CACHE / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    man[path.name] = {
        "source": f"{BASE}/api/v3/klines",
        "symbol": symbol,
        "interval": interval,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "n_bars": len(rows),
        "first_open": rows[0][0] if rows else None,
        "last_open": rows[-1][0] if rows else None,
        "sha256": hashlib.sha256(body.encode()).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    man_path.write_text(json.dumps(man, indent=1))
    return rows


def ms(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)
