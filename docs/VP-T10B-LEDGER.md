# VP — Ledger T10b (compte d’hypothèses)

**Job :** VP-NT1 étape 1 · branche `cursor/vp-nt1-a2fe`  
**Protocole :** `VP0-2026-09-26` §10 · clarification VP2-R1 §12  
**Périmètre :** hypothèses **jouées sur données VP1** depuis le gel VP0  
**Date ledger :** 2026-09-27  
**Profil adverse :** aucun run à ce jour (et **≠ +1** s’il est rejoué plus tard)

> **STOP étape 1** — N proposé ci-dessous ; **pas de rerun** tant que Claude + utilisateur n’ont pas validé N.

---

## Règles de comptage (rappel §10 + brief VP-NT1)

| Règle | Effet sur N |
|-------|-------------|
| Nouvelle strate / params / **symbole×TF** / définition **B\*** | **+1** |
| Même hypothèse rejouée après correctif bug (**VP-FIX1**) ou clarification (**VP2-R1**) | **pas +1** (noter `rejeu`) |
| Profil **adverse** sur la même hyp | **pas +1** |
| Doute | **compter (+1)** + colonne / section **doute** |

Unité d’hypothèse = `(B*, params figés, symbole, TF, profil coûts=base)`.  
Une question A/B/H **réutilise** les mêmes B* : pas de double comptage quand Bi apparaît comme Bj.

---

## Inventaire — lignes comptées (+1)

Params figés communs (code `vp3`) :

| B* | Définition (résumé) | Params |
|----|---------------------|--------|
| **B0** | Buy & Hold | entrée = long dès 1ʳᵉ barre éligible ; `exit_mode=hold` ; `full_cash` ; force_flat fin de fenêtre |
| **B1** | Ichimoku événement | `tenkan=9`, `kijun=26`, `senkou_b=52`, `displacement=26` ; sortie commune §6 |
| **B2** | B1 + RVOL | B1 + `rvol_window=20`, `rvol_min=1.5` ; sortie §6 |
| **B5** | B2 + MTF | B2 + HTF fermée ≠ short (1h→4h, 4h→1d) ; sortie §6 |

| # | hypothesis_id | B* | params (clé) | symbole | TF | coûts | date 1ʳᵉ jouée | commit 1ʳᵉ formal | rapport source | rejeu | doute | compte |
|---|----------------|----|--------------|---------|----|-------|----------------|-------------------|----------------|-------|-------|--------|
| 1 | `B0-BTCUSDT-1h-base` | B0 | hold / full_cash | BTCUSDT | 1h | base | 2026-09-26 | `7d0f5f4` (#150) | `VP3-REPORT-BTCUSDT-1h.md` v1 | v2 VP-FIX1 (`3223ec3`) ; v3 VP2-R1 / GRID (`b1cd43d`) | — | **+1** |
| 2 | `B1-BTCUSDT-1h-base` | B1 | Ichi 9/26/52/26 | BTCUSDT | 1h | base | 2026-09-26 | `7d0f5f4` (#150) | idem v1 | idem | — | **+1** |
| 3 | `B2-BTCUSDT-1h-base` | B2 | + rvol20≥1.5 | BTCUSDT | 1h | base | 2026-09-26 | `7d0f5f4` (#150) | idem v1 | idem | — | **+1** |
| 4 | `B5-BTCUSDT-1h-base` | B5 | + HTF≠short | BTCUSDT | 1h | base | 2026-09-26 | `7d0f5f4` (#150) | idem v1 | idem | — | **+1** |
| 5 | `B0-BTCUSDT-4h-base` | B0 | hold / full_cash | BTCUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | `VP3-REPORT-GRID.md` | — | — | **+1** |
| 6 | `B1-BTCUSDT-4h-base` | B1 | Ichi 9/26/52/26 | BTCUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 7 | `B2-BTCUSDT-4h-base` | B2 | + rvol20≥1.5 | BTCUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 8 | `B5-BTCUSDT-4h-base` | B5 | + HTF≠short | BTCUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 9 | `B0-ETHUSDT-1h-base` | B0 | hold / full_cash | ETHUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 10 | `B1-ETHUSDT-1h-base` | B1 | Ichi 9/26/52/26 | ETHUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 11 | `B2-ETHUSDT-1h-base` | B2 | + rvol20≥1.5 | ETHUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 12 | `B5-ETHUSDT-1h-base` | B5 | + HTF≠short | ETHUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 13 | `B0-ETHUSDT-4h-base` | B0 | hold / full_cash | ETHUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 14 | `B1-ETHUSDT-4h-base` | B1 | Ichi 9/26/52/26 | ETHUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 15 | `B2-ETHUSDT-4h-base` | B2 | + rvol20≥1.5 | ETHUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 16 | `B5-ETHUSDT-4h-base` | B5 | + HTF≠short | ETHUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 17 | `B0-SOLUSDT-1h-base` | B0 | hold / full_cash | SOLUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 18 | `B1-SOLUSDT-1h-base` | B1 | Ichi 9/26/52/26 | SOLUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 19 | `B2-SOLUSDT-1h-base` | B2 | + rvol20≥1.5 | SOLUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 20 | `B5-SOLUSDT-1h-base` | B5 | + HTF≠short | SOLUSDT | 1h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 21 | `B0-SOLUSDT-4h-base` | B0 | hold / full_cash | SOLUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 22 | `B1-SOLUSDT-4h-base` | B1 | Ichi 9/26/52/26 | SOLUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 23 | `B2-SOLUSDT-4h-base` | B2 | + rvol20≥1.5 | SOLUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |
| 24 | `B5-SOLUSDT-4h-base` | B5 | + HTF≠short | SOLUSDT | 4h | base | 2026-09-27 | `b1cd43d` (#153) | GRID | — | — | **+1** |

**Sous-total compté : 24**

---

## Non joué sur VP1 (0 ligne)

| B* / Q | Statut |
|--------|--------|
| **B3** | Pas dans `vp3.STRATEGIES` ; VP5 ; aucun rapport / artifact `/tmp` |
| **B4** | Idem |
| **B6** | Code présent (`entries.py`) ; **aucun** compare/rapport/CLI documenté sur VP1 |
| **B7** / Q **J** | Explicitement hors scope VP3 formal / FIX1 / GRID1 ; jamais exécuté sur VP1 |
| Profil **adverse** | Jamais joué |

---

## Rejeux documentés (pas +1)

| Hypothèses | Run | Motif |
|------------|-----|-------|
| B0–B5 BTCUSDT 1h | #149 smoke n_boot=500 (`e352c3c`) puis #150 n_boot=10 000 | Même hyp ; bootstrap seulement |
| B0–B5 BTCUSDT 1h | **v2** post VP-FIX1 (`3223ec3` / rapport `393044f`) | Correctif bug (données µs, DSR, WF, stop@raw) |
| B0–B5 BTCUSDT 1h | **v3** dans GRID1 (`b1cd43d`) | Clarification VP2-R1 time-stop (§12) — pas nouvelle règle |

---

## Calcul N proposé

```
N_T10b = |{ B* ∈ {B0,B1,B2,B5} } × { BTC,ETH,SOL } × { 1h,4h } × coûts=base |
       = 4 × 3 × 2
       = 24

Première formalisation BTC 1h : 4
Nouvelles cellules GRID1 :       20
Rejeux / adverse / B3–B7 :       +0
────────────────────────────────
N proposé :                      24
```

**N T10b gelé = 24** (VALIDÉ Claude + utilisateur, 2026-09-27) — B0 compté, rejeux non comptés, adverse non compté.

---

## Cas douteux (arbitrages)

| ID | Question | Arbitrage | Impact si inverse | doute |
|----|----------|-----------|-------------------|-------|
| D1 | **B0** compte-t-il ? | **Oui** — B0 est une définition B* jouée (baseline Q A) | N=18 | — |
| D2 | Smoke #149 (n_boot=500) = +1 distinct de #150 ? | **Non** — même hyp | 0 | — |
| D3 | v2 VP-FIX1 / v3 VP2-R1 = nouvelles hyps ? | **Non** — bugfix / clarification §12 | N+=4 → 28 | — |
| D4 | Compter **questions** (18) au lieu de B* ? | **Non** — §10 = B*×symbole×TF | N=18 | — |
| D5 | Tests unitaires `tests/vp3` | **Non** — pas données VP1 | 0 | — |
| D6 | Runs Lab pré-VP (`research_lab/runs/2026-09-20`) | **N inchangé** (autre harnais, pré-gel) — voir section Contamination | si on comptait chaque variante Lab → N≫24 | **oui** |
| D7 | B6 codé mais jamais lancé = +1 « latent » ? | **Non** — seuls essais **joués** | 0 | — |
| D8 | TF **1d** (HTF B5) = hyp signal ? | **Non** | 0 | — |

---

## Contamination pré-gel (Lab 2026-09-20)

Sources : `ichivol-app/engine/research_lab/runs/2026-09-20/` (manifest + trades_*.csv) et `research_lab/results_main.json` (40 lignes agrégées).

### Symboles

| Variante | n_symbols | Liste | BTC / ETH / SOL |
|----------|----------:|-------|-----------------|
| **A** (`A_reference`) | **20** | ADAUSDT, APTUSDT, ARBUSDT, ATOMUSDT, AVAXUSDT, BNBUSDT, **BTCUSDT**, DOGEUSDT, DOTUSDT, **ETHUSDT**, LINKUSDT, LTCUSDT, NEARUSDT, OPUSDT, PEPEUSDT, **SOLUSDT**, SUIUSDT, TONUSDT, UNIUSDT, XRPUSDT | **oui les trois** |
| **B** (`B_extended_universe`) | **40** | AAVEUSDT, ADAUSDT, APTUSDT, ARBUSDT, ATOMUSDT, AVAXUSDT, BNBUSDT, BONKUSDT, **BTCUSDT**, CRVUSDT, DOGEUSDT, DOTUSDT, ENAUSDT, ETHFIUSDT, **ETHUSDT**, FETUSDT, HBARUSDT, INITUSDT, KAITOUSDT, LINKUSDT, LTCUSDT, NEARUSDT, NEIROUSDT, OPUSDT, PENGUUSDT, PEPEUSDT, PNUTUSDT, SHIBUSDT, **SOLUSDT**, SUIUSDT, SUSDT, TAOUSDT, TONUSDT, TRUMPUSDT, TRXUSDT, UNIUSDT, VIRTUALUSDT, WIFUSDT, WLDUSDT, XRPUSDT | **oui les trois** |
| C / E | 20 | même univers que A (trades_C / trades_E) | **oui** |

### Fenêtres (manifest)

| Fenêtre | UTC | Chevauchement protocole VP |
|---------|-----|----------------------------|
| **DEV** | 2025-06-01 → 2026-01-01 | chevauche **validation 2025 S2** |
| **VAL** | 2026-01-01 → 2026-09-20 (~16:00) | = **holdout 2026** (partiel jusqu’au run Lab) |

### Variantes jouées

- `A_reference`, `B_extended_universe`, `C_breakout_persistence_k3`, `E_exit_direction_flip`
- Suivi : `results_review.json` (run_review) · `results_costsweep.json` (run_extra)

Harnais Lab ≠ VP2/VP3 : pipeline live (long+short, multi-positions, `exit_mode=decision|direction`), **pas** B0–B5 §6.

### Params B2 / B5 vs date Lab (git log -S / blame)

| Artefact | Introduit | vs 2026-09-20 |
|----------|-----------|---------------|
| `app/indicators/rvol.py` defaults `primary_window=20`, `significant_threshold=1.5` | ship `3719c1f` **2026-09-16** | **AVANT** Lab |
| `vp3` `RVOL_WINDOW=20`, `RVOL_MIN=1.5` (B2/B5 formels) | #148 `d3abe6f` **2026-09-26** | **APRÈS** Lab |
| `vp3` `HTF_MAP` + règle B5 « HTF ≠ short » | #148 `d3abe6f` **2026-09-26** | **APRÈS** Lab |
| Lab `research_lab/signals.py` HTF align (pipeline live) | présent au tip Lab `60c9428` (manifest 2026-09-20) | **au jour** du Lab (autre contrat que B5 VP) |

Conclusion params : les **nombres** 20 / 1.5 existaient déjà dans l’indicateur app avant le Lab ; la **définition VP B2/B5** (et le filtre HTF B5) est formalisée **après** le 2026-09-20.

### Conclusion (D6) — N inchangé

- Lab = **autre harnais**, **pré-gel VP0** → **ne compte pas** dans N T10b (**N reste 24**).
- Pour **BTCUSDT, ETHUSDT, SOLUSDT** (présents dans A et B) : fenêtres **validation 2025 S2** et **holdout 2026** sont marquées **« déjà vus »** (contamination d’information, pas d’incrément N). Doc seulement — aucun retuning.

---

## Hors scope ledger (étape 2 = autre job)

- Rerun grille `n_trials=24` + adverse (VP-NT1 étape 2)  
- Q J / B7 · changement params · features CI / T-CYCLE  
