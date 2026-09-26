# VP3 — B0–B7 entry baselines

**Protocol:** `docs/VALIDATION-PROTOCOL.md` §2 + carte VP3 (questions A, B, H, J).  
**Harness:** VP2 (`engine/vp2/`) · simulateur S1 · coûts base/adverse.  
**Data:** frozen VP1 spot (+ HTF 4h/1d for B5+).

| ID | Entrée |
|----|--------|
| B0 | Buy & hold after warm-up · `exit_mode=hold` |
| B1 | TK cross bullish + close > displayed cloud (§2.1) |
| B2 | B1 + `rvol20 ≥ 1.5` |
| B5 | B2 + HTF closed ≠ short (§2.2) |
| B6 | B5 + ATR regime ∉ {dead, extreme} |
| B7 | `build_pipeline` → BUY (closed bar) |

B3/B4/B8 = later VP steps. Full WF verdicts (§5/§9) via `python -m vp3 wf` (local data).

```bash
python -m vp3 list
python -m vp3 run --strategy B1 --symbol BTCUSDT --interval 1h --cost base
python -m vp3 wf --strategy B1 --symbol BTCUSDT --interval 1h
```

## Metrics / folds

- `folds.py` — WF1–WF7 + purge gate (§5.1.2)
- `metrics.py` — bar Sharpe / Sortino (§8.1 all-bars downside) / CAGR / maxDD
- `bootstrap.py` — paired block Δ + trade mean IC (§9.2)
- `dsr.py` — PSR / DSR scaffold (§9.3, N = T10b)
- `wf.py` — per-fold runner on frozen VP1
