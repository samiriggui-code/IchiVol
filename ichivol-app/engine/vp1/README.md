# VP1 — data.binance.vision + frozen loader

**Protocol:** `docs/VALIDATION-PROTOCOL.md` §4 + carte VP1.  
**Univers:** BTCUSDT, ETHUSDT, SOLUSDT · TF spot `1h`/`4h`/`1d` · fenêtre 2020-09-01 → 2026-08-31 UTC.

## Layout

```
vp1/data/          # gitignored payloads
  raw/...          # Vision zips (+ verified via .CHECKSUM)
  series/...       # frozen JSON series
  manifest.json    # sha256 per file (commit when stable)
```

## Commands (from `ichivol-app/engine`)

```bash
python -m vp1 download-spot
python -m vp1 download-funding
python -m vp1 download-oi [--symbol BTCUSDT]   # daily metrics — many files
python -m vp1 build-spot
python -m vp1 verify
```

## Notes

- Source host: `https://data.binance.vision` (not `data-api` REST).
- OI = Vision **daily** `futures/um/daily/metrics` (`sum_open_interest`). Monthly metrics tree is empty.
- ETH/SOL metrics may start after 2020-09-01 → document skip for B4/E/G if incomplete (protocol §4).
- Frozen loader `load.load_series` verifies sha256 and **refuses** network.
- Full OI download is large; resume-friendly (skips existing manifest entries).
