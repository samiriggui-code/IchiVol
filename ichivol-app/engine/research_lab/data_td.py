"""Twelve Data free-tier history (user's own key from .env, read-only, rate-limited to the 8 credits/min quota).
Research use only; results are NOT to be redistributed (provider terms)."""
import json, os, time
from pathlib import Path
import httpx
from research_lab.data import CACHE

def _key():
    for line in open(Path(__file__).resolve().parent.parent / ".env", encoding="utf-8"):
        if line.startswith("TWELVE_DATA_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("no key")

def fetch(symbol: str, interval: str, n: int = 5000):
    path = CACHE / f"TD_{symbol.replace('/', '')}_{interval}_{n}.json"
    if path.exists():
        return json.loads(path.read_text())
    r = httpx.get("https://api.twelvedata.com/time_series", params={"symbol": symbol, "interval": interval, "outputsize": n, "timezone": "UTC", "order": "ASC", "apikey": _key()}, timeout=60).json()
    if r.get("status") == "error" or "values" not in r:
        raise RuntimeError(f"{symbol} {interval}: {r.get('message', r)}"[:200])
    path.write_text(json.dumps(r["values"]))
    time.sleep(8)  # 8 credits / minute
    return r["values"]
