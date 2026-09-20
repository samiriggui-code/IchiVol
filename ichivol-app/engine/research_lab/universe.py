"""Universe definitions for experiments A/B/C.

A (reference) = the 20 crypto symbols the live paper sync scans (catalog).
B (extended)  = A + up to 20 more Binance spot USDT pairs chosen by a rule that
uses ONLY information available before the study starts (never returns):
  - TRADING spot USDT pair listed with >= 30 daily bars before the selection window ends
  - median daily quote volume over the selection window (2025-05-01..2025-05-31) >= MIN_QUOTE_VOL
  - not a stablecoin / wrapped / leveraged / commodity-token base asset
  - ranked by that median volume, top EXTRA taken
Limitation (documented in the report): pairs delisted since are absent from
exchangeInfo, so residual survivorship bias remains.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import httpx

from research_lab.data import BASE, CACHE, _get, fetch_klines, ms

A_UNIVERSE = (
    "BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT ADAUSDT DOGEUSDT AVAXUSDT LINKUSDT DOTUSDT "
    "LTCUSDT ATOMUSDT UNIUSDT NEARUSDT APTUSDT ARBUSDT OPUSDT SUIUSDT PEPEUSDT TONUSDT"
).split()

SEL_START, SEL_END = ms(2025, 5, 1), ms(2025, 6, 1)
MIN_QUOTE_VOL = 20_000_000.0
EXTRA = 20
_EXCLUDED_BASE = {
    "USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "AEUR", "USD1", "XUSD", "BFUSD", "USDE", "PAXG",
    "WBTC", "WBETH", "BETH", "EURI", "PYUSD", "RLUSD", "UST", "BUSD", "GBP", "TRY", "BRL",
}


def _is_excluded(base: str) -> bool:
    return base in _EXCLUDED_BASE or base.endswith(("UP", "DOWN", "BULL", "BEAR")) and len(base) > 4


def select_extended(client: httpx.Client | None = None) -> dict:
    out = CACHE / "universe_B.json"
    if out.exists():
        return json.loads(out.read_text())
    CACHE.mkdir(exist_ok=True)
    client = client or httpx.Client()
    info = _get(client, "/api/v3/exchangeInfo", {"permissions": "SPOT"})
    cands = [
        s for s in info["symbols"]
        if s["status"] == "TRADING" and s["quoteAsset"] == "USDT" and not _is_excluded(s["baseAsset"])
        and s["symbol"] not in A_UNIVERSE
    ]
    ranked = []
    for s in cands:
        rows = fetch_klines(s["symbol"], "1d", SEL_START, SEL_END, client)
        if len(rows) < 28:  # not listed (or too young) during the selection window
            continue
        med = statistics.median(float(r[7]) for r in rows)  # quote asset volume
        if med >= MIN_QUOTE_VOL:
            ranked.append((med, s["symbol"]))
    ranked.sort(reverse=True)
    chosen = [sym for _, sym in ranked[:EXTRA]]
    payload = {
        "rule": __doc__,
        "selection_window": [SEL_START, SEL_END],
        "min_quote_vol": MIN_QUOTE_VOL,
        "n_candidates_scanned": len(cands),
        "n_eligible": len(ranked),
        "extra": chosen,
        "median_quote_volume": {sym: med for med, sym in ranked[:EXTRA]},
    }
    out.write_text(json.dumps(payload, indent=1))
    return payload
