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

B3/B4/B8 = later VP steps. Full WF verdicts (§5/§9) = follow-up once entry masks are green.

```bash
python -m vp3 list
python -m vp3 run --strategy B1 --symbol BTCUSDT --interval 1h --cost base
```
