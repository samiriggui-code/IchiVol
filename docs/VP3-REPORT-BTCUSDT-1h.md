# VP3 — rapports provisoires A / B / H (BTCUSDT 1h, coûts base)

**Tip code :** `main` post-#148 + compare CLI  
**Protocole :** `VP0-2026-09-26`  
**Données :** VP1 frozen spot local (`vp1/data/`, gitignored)  
**Bootstrap :** block apparié, n=500 (smoke ; production = 10 000)  
**DSR N trials :** 1 (T10b à renseigner)  
**Date run :** 2026-09-26

> Verdicts **provisoires** — pas de claim EDGE formel tant que n_boot=10 000, N T10b figé, et grille symbole×TF complète.

## Setup

| Champ | Valeur |
|-------|--------|
| Symbole × TF | BTCUSDT · 1h |
| Plis | WF1–WF7 (§5) + purge time-stop |
| Harness | VP2 / `sim.py` S1 |
| Strates | B0 hold · B1 TK+cloud · B2 +RVOL · B5 +HTF |

## Question A — B1 vs B0

| | B1 | B0 |
|--|----|----|
| N trades (agrégat WF) | 320 | 7 (1/pli) |
| Espérance / trade | **−19.77** | n/a (equity) |
| Plis positifs | 1/7 | 5/7 (CAGR>0) |
| Sharpe equity agg | −1.05 | **+0.78** |
| DSR | 0.025 | n/a |

- Δ mean barre (B1−B0) : **−7.0e−5** · IC 95 % exclut 0 (**contre** B1)
- **bi_beats_bj = false** — B1 ne bat pas B0

## Question B — B2 vs B1

| | B2 | B1 |
|--|----|----|
| N trades | 129 | 320 |
| Espérance | **+0.45** | −19.77 |
| Plis positifs | 3/7 | 1/7 |
| DSR | 0.52 | 0.025 |

- Δ mean barre (B2−B1) : **+2.1e−5** · IC exclut 0 (favorable B2)
- DSR(B2) **0.52 < 0.95** → **bi_beats_bj = false** (pas de claim EDGE)

## Question H — B5 vs B2

| | B5 | B2 |
|--|----|----|
| N trades | 99 | 129 |
| Espérance | **+10.20** | +0.45 |
| Plis positifs | 3/7 | 3/7 |
| DSR | 0.72 | 0.52 |

- Δ mean barre (B5−B2) : IC **inclut 0**
- **bi_beats_bj = false**

## Lecture courte

1. **B0** reste le benchmark equity à battre sur BTC 1h WF.
2. **B1** (TK+cloud seul) est **dominé** par B0 après coûts.
3. **B2** (RVOL) améliore B1 (Δ>0) mais DSR insuffisant.
4. **B5** (HTF) espérance reportée plus haute, Δ vs B2 non significatif à n_boot=500.

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3 compare --question A --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question B --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question H --symbol BTCUSDT --interval 1h --n-boot 10000
```

Question **J** (B7 vs meilleur B0–B6) : à lancer après gel N T10b + run B6/B7.
