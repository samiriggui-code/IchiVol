# T11b — Twelve Data vs biquote (forex / métaux)

Généré : `2026-09-24T14:52:26.325923+00:00`  
Mode : `dry-run (synthétique)`  
TF : `1h` · limit `300`  
Crédits Twelve Data (session) : **5**

## Méthode

- Symboles catalogue FX/métaux ; biquote via `provider_symbol` catalogue.
- Twelve Data via forme slash (`EUR/USD`, …) — **hors catalogue live**.
- Aucun changement `catalog.py` / watchlist (T11b partiel).
- Crédits = acquisitions `_try_acquire_credit_slot` (fenêtre moteur).

## Résultats

| Symbole | BQ bars | TD bars | Overlap % | Δ close | TD credits | BQ ms | TD ms | Err |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| EURUSD | 120 | 120 | 100.0 | 0.0 | 1 | 0.1 | 0.1 |  |
| GBPUSD | 120 | 120 | 100.0 | 0.0 | 1 | 0.1 | 0.1 |  |
| USDJPY | 120 | 120 | 100.0 | 0.0 | 1 | 0.1 | 0.1 |  |
| XAUUSD | 120 | 120 | 100.0 | 0.0 | 1 | 0.1 | 0.1 |  |
| XAGUSD | 120 | 120 | 100.0 | 0.0 | 1 | 0.1 | 0.1 |  |

## Recommandation

Keep live FX/metals on biquote (Phase 1c). Twelve Data remains equities-only in catalog; use TD only if overlap/quality justifies the credit cost (T11c decision — human). Dry-run rows are synthetic.

## JSON

```json
{
  "generated_at": "2026-09-24T14:52:26.325923+00:00",
  "dry_run": true,
  "timeframe": "1h",
  "limit": 300,
  "symbols": [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "XAUUSD",
    "XAGUSD"
  ],
  "twelve_data_credits_total": 5,
  "comparisons": [
    {
      "symbol": "EURUSD",
      "biquote": {
        "symbol": "EURUSD",
        "provider": "biquote",
        "provider_symbol": "EURUSD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 0,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "twelve_data": {
        "symbol": "EURUSD",
        "provider": "twelve_data",
        "provider_symbol": "EUR/USD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 1,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "time_overlap": {
        "a_bars": 120,
        "b_bars": 120,
        "intersection": 120,
        "only_a": 0,
        "only_b": 0,
        "overlap_pct_of_min": 100.0
      },
      "close_delta_last": 0.0
    },
    {
      "symbol": "GBPUSD",
      "biquote": {
        "symbol": "GBPUSD",
        "provider": "biquote",
        "provider_symbol": "GBPUSD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 0,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "twelve_data": {
        "symbol": "GBPUSD",
        "provider": "twelve_data",
        "provider_symbol": "GBP/USD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 1,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "time_overlap": {
        "a_bars": 120,
        "b_bars": 120,
        "intersection": 120,
        "only_a": 0,
        "only_b": 0,
        "overlap_pct_of_min": 100.0
      },
      "close_delta_last": 0.0
    },
    {
      "symbol": "USDJPY",
      "biquote": {
        "symbol": "USDJPY",
        "provider": "biquote",
        "provider_symbol": "USDJPY",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 0,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "twelve_data": {
        "symbol": "USDJPY",
        "provider": "twelve_data",
        "provider_symbol": "USD/JPY",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 1,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "time_overlap": {
        "a_bars": 120,
        "b_bars": 120,
        "intersection": 120,
        "only_a": 0,
        "only_b": 0,
        "overlap_pct_of_min": 100.0
      },
      "close_delta_last": 0.0
    },
    {
      "symbol": "XAUUSD",
      "biquote": {
        "symbol": "XAUUSD",
        "provider": "biquote",
        "provider_symbol": "XAUUSD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 0,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "twelve_data": {
        "symbol": "XAUUSD",
        "provider": "twelve_data",
        "provider_symbol": "XAU/USD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 1,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "time_overlap": {
        "a_bars": 120,
        "b_bars": 120,
        "intersection": 120,
        "only_a": 0,
        "only_b": 0,
        "overlap_pct_of_min": 100.0
      },
      "close_delta_last": 0.0
    },
    {
      "symbol": "XAGUSD",
      "biquote": {
        "symbol": "XAGUSD",
        "provider": "biquote",
        "provider_symbol": "XAGUSD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 0,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "twelve_data": {
        "symbol": "XAGUSD",
        "provider": "twelve_data",
        "provider_symbol": "XAG/USD",
        "timeframe": "1h",
        "n_bars": 120,
        "wall_ms": 0.1,
        "credits": 1,
        "volume_type": "NONE",
        "first_time": 1700000000,
        "last_time": 1700428400,
        "last_close": 2.24,
        "error": null
      },
      "time_overlap": {
        "a_bars": 120,
        "b_bars": 120,
        "intersection": 120,
        "only_a": 0,
        "only_b": 0,
        "overlap_pct_of_min": 100.0
      },
      "close_delta_last": 0.0
    }
  ],
  "recommendation": "Keep live FX/metals on biquote (Phase 1c). Twelve Data remains equities-only in catalog; use TD only if overlap/quality justifies the credit cost (T11c decision \u2014 human). Dry-run rows are synthetic."
}
```
