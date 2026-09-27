# VP3 — grille A / B / H (VP-GRID1)

**Job :** VP-GRID1 · branche `cursor/vp-grid1-a2fe`  
**Protocole :** `VP0-2026-09-26` + clarification VP2-R1 (§12, 2026-09-26)  
**Coûts :** base · **n_boot :** 10 000 · **DSR N trials :** 1 (non figé)  
**Time-stop :** entrée = barre 1 → sortie `entry+(n−1)·bar`  
**Date run :** 2026-09-27

> Pas de claim **EDGE**. **Hors scope :** Q J (B7), figer N T10b, profil adverse.

## Séries VP1 (sha256 + complétude)

| Symbole | TF | n_bars | expected | missing | gap_frac | sha256 |
|---|---|---:|---:|---:|---:|---|
| BTCUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `3fe8b4708b69…` |
| BTCUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `cd8bef9a07f7…` |
| BTCUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `1d04e6bbee29…` |
| ETHUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `a1e6ee7841ff…` |
| ETHUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `67f46cf63f0b…` |
| ETHUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `527f6d464dec…` |
| SOLUSDT | 1h | 52565 | 52584 | 19 | 0.0361% | `7a798cb75dea…` |
| SOLUSDT | 4h | 13146 | 13146 | 0 | 0.0000% | `0c75aed211b7…` |
| SOLUSDT | 1d | 2191 | 2191 | 0 | 0.0000% | `84c36bf47565…` |

Full digests :

```
BTCUSDT 1h 3fe8b4708b6953c0331b23d0facb2b9b773574ab9bc66a197e9c639d28da0d88
BTCUSDT 4h cd8bef9a07f70904dcfc414224411e2ceaeb37b05205c743e1fe87c0bae40782
BTCUSDT 1d 1d04e6bbee290adedc5778823302a4cf4b4de36af7bab3fdd9ede1a7da8ef819
ETHUSDT 1h a1e6ee7841ff48538a256455bfe6e07a1a8d844da9ea51c77c319e1082d77083
ETHUSDT 4h 67f46cf63f0b3bf2d5d640e0967ad613130349a0d7dd04d588889f8761fda756
ETHUSDT 1d 527f6d464dec9ea30ced0b515249dcb128ae62e3e4f5e2072342f23bf9759623
SOLUSDT 1h 7a798cb75dea3f33c2a1a259f9ec1c2d0dc3a3d4989a82cc2e5d6be07b9539f7
SOLUSDT 4h 0c75aed211b7cfcd851bc2f00d09dc803e1001779683f79a5c0119eea4e623df
SOLUSDT 1d 84c36bf4756517d57bf381757753fa1a111f6f7459399cf64bb0ae368a8c7096
```

### Note — 19 barres 1h manquantes (Vision)

Les **mêmes 10 plages** (19 barres) manquent sur **BTCUSDT, ETHUSDT et SOLUSDT** 1h (timestamps identiques) :

| from (UTC) | to (UTC) | missing |
|---|---|---:|
| 2020-11-30 06:00 | 2020-11-30 07:00 | 1 |
| 2020-12-21 15:00 | 2020-12-21 18:00 | 3 |
| 2020-12-25 02:00 | 2020-12-25 03:00 | 1 |
| 2021-02-11 04:00 | 2021-02-11 05:00 | 1 |
| 2021-03-06 02:00 | 2021-03-06 03:00 | 1 |
| 2021-04-20 02:00 | 2021-04-20 04:00 | 2 |
| 2021-04-25 05:00 | 2021-04-25 08:00 | 3 |
| 2021-08-13 02:00 | 2021-08-13 06:00 | 4 |
| 2021-09-29 07:00 | 2021-09-29 09:00 | 2 |
| 2023-03-24 13:00 | 2023-03-24 14:00 | 1 |

**Time-stop vs trous :** le décompte S1 est en **temps réel** `(t − entry_time) // bar_seconds` (VP2-R1). Un trade qui traverse un trou atteint donc le seuil time-stop avec **moins de 48 barres réellement présentes** dans la série. Documenté seulement — **pas de changement de règle** dans cette PR.

---

## BTCUSDT · 1h

*(v3 — remplace la v2 post-VP-FIX1 ; time-stop VP2-R1)*

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 317 | -20.48 | 0.02347 | 2/7 | 7 | Sharpe=0.7766 | 0.927 | True | -7.04e-05 |
| B | B2 vs B1 | **false** | 129 | -4.167 | 0.412 | 3/7 | 317 | -20.48 | 0.02347 | True | 1.99e-05 |
| H | B5 vs B2 | **false** | 99 | 5.799 | 0.636 | 3/7 | 129 | -4.167 | 0.412 | False | 3.61e-06 |

## BTCUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 71 | 24.21 | 0.7007 | 3/7 | 7 | Sharpe=0.8198 | 0.9375 | False | -1.85e-04 |
| B | B2 vs B1 | **false** | 22 | 63.9 | 0.8525 | 0/7 | 71 | 24.21 | 0.7007 | False | -8.13e-08 |
| H | B5 vs B2 | **false** | 14 | 114.4 | 0.9503 | 0/7 | 22 | 63.9 | 0.8525 | False | 3.21e-06 |

## ETHUSDT · 1h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 296 | -24.14 | 0.0222 | 1/7 | 7 | Sharpe=0.496 | 0.8234 | False | -6.30e-05 |
| B | B2 vs B1 | **false** | 119 | -3.679 | 0.4209 | 3/7 | 296 | -24.14 | 0.0222 | True | 2.25e-05 |
| H | B5 vs B2 | **false** | 91 | -1.514 | 0.4841 | 2/7 | 119 | -3.679 | 0.4209 | False | 1.16e-06 |

## ETHUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 76 | -37.04 | 0.2428 | 2/7 | 7 | Sharpe=0.5093 | 0.8296 | False | -1.90e-04 |
| B | B2 vs B1 | **false** | 21 | -128.7 | 0.08093 | 1/7 | 76 | -37.04 | 0.2428 | False | -2.63e-06 |
| H | B5 vs B2 | **false** | 17 | -149.8 | 0.08906 | 1/7 | 21 | -128.7 | 0.08093 | False | 2.53e-06 |

## SOLUSDT · 1h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 265 | 34.96 | 0.9382 | 4/7 | 7 | Sharpe=0.927 | 0.9589 | False | -8.58e-05 |
| B | B2 vs B1 | **false** | 98 | 51.94 | 0.9405 | 4/7 | 265 | 34.96 | 0.9382 | False | -1.28e-05 |
| H | B5 vs B2 | **false** | 80 | 44.99 | 0.8946 | 5/7 | 98 | 51.94 | 0.9405 | False | -4.80e-06 |

## SOLUSDT · 4h

| Q | Pair | bi_beats | N_i | exp_i | DSR_i | pos_i | N_j | exp_j / Sharpe_j | DSR_j | Δmean IC excl.0 | Δmean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| A | B1 vs B0 | **false** | 68 | 88.13 | 0.8725 | 4/7 | 7 | Sharpe=0.9424 | 0.9616 | False | -3.72e-04 |
| B | B2 vs B1 | **false** | 26 | 221.3 | 0.955 | 2/7 | 68 | 88.13 | 0.8725 | False | -9.18e-06 |
| H | B5 vs B2 | **false** | 17 | 115.2 | 0.7723 | 0/7 | 26 | 221.3 | 0.955 | False | -4.84e-05 |

## Synthèse

| Symbole×TF | A (B1≻B0) | B (B2≻B1) | H (B5≻B2) |
|---|---|---|---|
| BTCUSDT 1h | false (Δ<0) | false (Δ>0 DSR=0.41) | false (IC∋0) |
| BTCUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| ETHUSDT 1h | false (IC∋0) | false (Δ>0 DSR=0.42) | false (IC∋0) |
| ETHUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| SOLUSDT 1h | false (IC∋0) | false (IC∋0) | false (IC∋0) |
| SOLUSDT 4h | false (IC∋0) | false (IC∋0) | false (IC∋0) |

### Lecture courte

- Aucun `bi_beats_bj=true` sur la grille (confirmé).
- B0 reste difficile à battre en equity sur plusieurs couples.
- **Cas DSR_i ≥ 0.95** (liste exhaustive sur la grille) :
  - BTCUSDT 4h · H (B5) · DSR_i = **0.9503**
  - SOLUSDT 4h · B (B2) · DSR_i = **0.955**
- DSR calculés avec **N trials = 1** → **surévalués** ; **non interprétables** avant gel N T10b.
- **4h :** N trades **14–26** → **puissance faible**, aucune conclusion.
- Claim EDGE toujours bloqué (N T10b non figé, adverse non joué, Q J hors scope).

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3.grid_run /tmp/vp3_grid_results.jsonl 10000
```

