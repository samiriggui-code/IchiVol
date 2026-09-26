# VP3 — rapports A / B / H (BTCUSDT 1h, coûts base)

**Tip code :** `main` @ `e352c3c` (+ ce PR)  
**Protocole :** `VP0-2026-09-26`  
**Données :** VP1 frozen spot local (`vp1/data/`, gitignored)  
**Bootstrap :** block apparié, **n = 10 000**, seed 7  
**DSR N trials :** 1 (T10b à figurer avant claim EDGE)  
**Date run :** 2026-09-26

> Pas de claim **EDGE** formel : N T10b = 1 provisoire ; grille symbole×TF incomplète ; Q J (B7) non jouée.

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
| Espérance / trade | **−19.77** (IC exclut 0, négatif) | n/a (equity) |
| Plis positifs | 1/7 | **5/7** (CAGR>0) |
| Sharpe equity agg | −1.05 | **+0.78** |
| DSR | 0.025 | 0.927 |
| maxDD pire pli | −26.3 % | −62.9 % (B0 exempté §9) |

- Δ mean barre (B1−B0) : **−6.97e−5** · IC 95 % `[−1.34e−4, −5.96e−6]` exclut 0 (**contre** B1)
- Δ Sharpe : IC exclut 0 (**contre** B1)
- **bi_beats_bj = false** — B1 ne bat pas B0

## Question B — B2 vs B1

| | B2 | B1 |
|--|----|----|
| N trades | 129 | 320 |
| Espérance | **+0.45** | −19.77 |
| Plis positifs | 3/7 | 1/7 |
| DSR | 0.524 | 0.025 |

- Δ mean barre (B2−B1) : **+2.13e−5** · IC `[+5.94e−6, +3.67e−5]` exclut 0 (favorable B2)
- DSR(B2) **0.524 < 0.95** → **bi_beats_bj = false** (pas de claim)

## Question H — B5 vs B2

| | B5 | B2 |
|--|----|----|
| N trades | 99 | 129 |
| Espérance | **+10.20** | +0.45 |
| Plis positifs | 3/7 | 3/7 |
| DSR | 0.720 | 0.524 |

- Δ mean barre (B5−B2) : **+3.05e−6** · IC `[−2.78e−6, +9.27e−6]` **inclut 0**
- **bi_beats_bj = false**

## Lecture

1. **B0** reste le benchmark equity sur BTC 1h WF (Sharpe>0, 5/7 plis).
2. **B1** est **dominé** par B0 après coûts (Δ et Sharpe contre B1).
3. **B2** améliore B1 (Δ mean > 0, IC exclut 0) mais **DSR insuffisant**.
4. **B5** espérance reportée plus haute ; Δ vs B2 **non significatif**.

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3 compare --question A --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question B --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question H --symbol BTCUSDT --interval 1h --n-boot 10000
```

Suite : ETH/SOL · 4h · Q **J** (B7) · N T10b figé · adverse stress.
