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
| D7 | B6/B7 1ʳᵉ run VP-J1 | **Joués** étape 2 — +12 → N=36 | N=36 gelé | VP-J1 FINAL |
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

- Lab = **autre harnais**, **pré-gel VP0** → **ne compte pas** dans N T10b (**N reste 24** jusqu’à VP-J1).
- Pour **BTCUSDT, ETHUSDT, SOLUSDT** (présents dans A et B) : fenêtres **validation 2025 S2** et **holdout 2026** sont marquées **« déjà vus »** (contamination d’information, pas d’incrément N). Doc seulement — aucun retuning.

---

## VP-J1 — extension ledger (étape 2 **jouée**)

**Base main :** `2a585f8` (#154 VP-NT1 mergé)  
**N gelé (VP-J1) :** **36** = 24 + 12  
**Run :** `python -m vp3.j1_run` · n_boot=10 000 · rapport [`VP3-REPORT-FINAL.md`](./VP3-REPORT-FINAL.md) · artefact [`vp3-artifacts/j1_results.json`](./vp3-artifacts/j1_results.json)

### 12 hypothèses B6/B7 (+1 chacune au 1ʳᵉ run — **jouées**)

Params :

| B* | Définition | Params figés pour le run |
|----|------------|--------------------------|
| **B6** | B5 + régime ATR ≠ dead/extreme + gate ADX | seuils ci-dessous (LiveScreenerSettings / AtrParams / AdxParams) |
| **B7** | pipeline live Option B → BUY | `strategy_version` + blob SHA + `WARMUP_BARS` |

| # | hypothesis_id | B* | symbole | TF | coûts | statut | compte |
|---|----------------|----|---------|----|-------|--------|--------|
| 25 | `B6-BTCUSDT-1h-base` | B6 | BTCUSDT | 1h | base | **joué** (VP-J1) | **+1** |
| 26 | `B6-BTCUSDT-4h-base` | B6 | BTCUSDT | 4h | base | **joué** | **+1** |
| 27 | `B6-ETHUSDT-1h-base` | B6 | ETHUSDT | 1h | base | **joué** | **+1** |
| 28 | `B6-ETHUSDT-4h-base` | B6 | ETHUSDT | 4h | base | **joué** | **+1** |
| 29 | `B6-SOLUSDT-1h-base` | B6 | SOLUSDT | 1h | base | **joué** | **+1** |
| 30 | `B6-SOLUSDT-4h-base` | B6 | SOLUSDT | 4h | base | **joué** | **+1** |
| 31 | `B7-BTCUSDT-1h-base` | B7 | BTCUSDT | 1h | base | **joué** | **+1** |
| 32 | `B7-BTCUSDT-4h-base` | B7 | BTCUSDT | 4h | base | **joué** | **+1** |
| 33 | `B7-ETHUSDT-1h-base` | B7 | ETHUSDT | 1h | base | **joué** | **+1** |
| 34 | `B7-ETHUSDT-4h-base` | B7 | ETHUSDT | 4h | base | **joué** | **+1** |
| 35 | `B7-SOLUSDT-1h-base` | B7 | SOLUSDT | 1h | base | **joué** | **+1** |
| 36 | `B7-SOLUSDT-4h-base` | B7 | SOLUSDT | 4h | base | **joué** | **+1** |

```
N_proposé = 24 (gelé NT1) + 12 (B6/B7 × 3 × 2) = 36
Adverse sur les mêmes hyps = pas +1
```

**N T10b gelé = 36** (VALIDÉ Claude + utilisateur, 2026-09-27) — 24 (NT1) + 12 (B6/B7 × 3 × 2). Adverse non compté.

### Gel B6 — seuils ATR (LiveScreenerSettings)

Lu dans `LiveScreenerSettings.production_defaults()` / passé **explicitement** à `compute_atr` :

| Champ | Valeur | Fichier | Blob @ `main` `2a585f8` |
|-------|--------|---------|-------------------------|
| `atr_dead_percentile` | **0.15** | `app/strategy_lab/adn_ichivol.py` `DEFAULT_LIVE_ATR_DEAD` | ADN `4c9b608e9b6e…` |
| `atr_extreme_percentile` | **0.90** | `DEFAULT_LIVE_ATR_EXTREME` | idem |
| `atr_stop_multiplier` | **1.5** | `DEFAULT_LIVE_ATR_STOP_MULT` | (hint stop ; pas le filtre B6) |
| `period` / `regime_lookback` | 14 / 100 | `app/indicators/atr.py` `AtrParams` | atr `e019b7774ba6…` |

### Gel B6 — params ADX (même source que le pipeline)

`LIVE_ADX_PARAMS = AdxParams()` — identique aux défauts utilisés par `compute_adx` / `pipeline._regime_stage` :

| Champ | Valeur | Fichier | Blob |
|-------|--------|---------|------|
| `period` | **14** | `app/indicators/adx.py` `AdxParams` | `b7e6f7a50d3f4e511bd5e37fba04b763af736d2e` |
| `weak_threshold` (ABSENT) | **20.0** | idem | idem |
| `trending_threshold` (TRENDING) | **25.0** | idem | idem |
| `strong_threshold` (STRONG) | **40.0** | idem | idem |
| Gate B6 | passe si `adx is None` OR `UNKNOWN` OR ∈ {TRENDING, STRONG} ; bloque ABSENT/DEVELOPING | `vp3.entries.live_regime_ok` (= logique `pipeline._regime_stage`) | — |

### Gel B7 — pipeline live Option B

| Champ | Valeur figée | Source @ `main` `2a585f8` |
|-------|--------------|---------------------------|
| `strategy_version` | **`ichivol_pipeline_v1`** | `app/decision/pipeline.py` `STRATEGY_VERSION` |
| Blob SHA `pipeline.py` | `9403d9f4d48ee4e054f722e6581d5f8e0883b2db` | `git rev-parse …/pipeline.py` |
| Entrée B7 | `build_pipeline(...)` → `BUY` · **`i >= WARMUP_BARS` (78)** | `vp3/entries.py` |
| Sortie B7 | `common_rules` (§6) | `vp3/rules.py` |

---

## Définition de J (VALIDÉE avant run)

**Question J :** B7 vs **Bj**, où Bj = « meilleur de B0–B6 » **par case symbole×TF**.

1. Parmi `{B0, B1, B2, B5, B6}` : **max DSR_i** (N=36, profil base).
2. Égalité → plus simple : `B0 < B1 < B2 < B5 < B6`.
3. Même Bj en adverse.
4. B7 hors pool Bj.

---

## Audit `vp3/entries.py` B6 / B7 vs §2

| Point | Statut |
|-------|--------|
| B6 ATR via `LiveScreenerSettings.production_defaults().atr_params()` | **CORRIGÉ avant 1ʳᵉ run** |
| B6 gate ADX (= pipeline) | **CORRIGÉ avant 1ʳᵉ run** |
| B7 `WARMUP_BARS` | **CORRIGÉ avant 1ʳᵉ run** |
| B7 sortie §6 | OK (inchangé) |
| B7 HTF `_align_mtf_directions` | INFO VP3-R6 (inchangé) |

Commit corrections : `9a7a019` sur `cursor/vp-j1-a2fe`

---

## VP-P — lignes diagnostiques (amendement `VP0-2026-09-27b`)

Pré-enregistrées le 2026-09-27 (Claude local, branche `claude/vp-p-paper-fidele`) **avant** tout run P.
Diagnostic descriptif : **aucun claim, aucun DSR**. Comptées au lineage pour la traçabilité.

| # | hypothesis_id | Définition | Univers | TF | coûts | compte |
|---|----------------|-----------|---------|----|-------|--------|
| P1 | `P1-U20-1h-paper` | paper fidèle (`ICHIVOL_BASELINE_V1` @ `99ffc66`) : B7 + sorties paper + tailles paper + capital commun 5 000 | 20 cryptos `A_UNIVERSE` | 1h | paper (7,5 bps + friction/symbole) | **+1** (diag.) |
| P2 | `P2-U3-1h-paper` | idem | BTC / ETH / SOL | 1h | idem | **+1** (diag.) |

Adverse (R2), reset par pli (R3) et seeds d'ordre (R1-s) = même hypothèse → **pas +1**.

| P3 | `P3-U20-1h-event` | étude d'événement : début de série BUY contre 20 témoins même symbole / même mois, h = 24/48/96/168 (amendement `VP0-2026-09-28`) | 20 cryptos | 1h | paper + adverse | **+1** (diag.) |

C2 / C3 (contrôles de fidélité) et la correction ε (Q.1) : **pas +1**.
Lineage : 36 (gelé VP-J1) + 12 (VP-S1, si validé) + 2 (VP-P) = **50** ; sans VP-S1 = 38.

---

## Hors scope

- B3 / B4 / B8 · autre retuning · val 2025 / holdout · features CI / T-CYCLE · merge sans OK Claude  


---

## Chantier RS (stratégie alternative) — centralisé par le pilote RS (Claude local)

| Lineage | Hypothèse | Amendement | Statut | Compte |
|---------|-----------|------------|--------|--------|
| `RS-D1-U3-4h` | Cassure Donchian 55 / sortie de tendance (stop 3 ATR suiveur, canal 20), BTC / ETH / SOL 4h, capital commun paper | `VP0-2026-09-28b` | **joué 2026-09-28** (`1a4eba5`) — CANDIDAT (D1–D7, dev) → **VALIDÉ 2025** (V1–V5, `VP0-2026-09-28d`, +5,0 %, maxDD −4,3 %) · holdout 2026 fermé · [rapport](./RS-D1-REPORT.md) | **+1** |

Règles de tenue :
- les lignes RS ne sont ajoutées **que** par le pilote RS ;
- VP-S1 (+12, #157) et P1 / P2 / P3 (#159) restent tenues par leurs chantiers ;
- le total N se lit après merge de chaque PR.

---

## VP-S1 étape 1 — BM / BN (+12) → N proposé = 48

**Amendement :** `VP0-2026-09-27` Questions M/N (Bouclier) · figé avant run  
**Branche :** `cursor/vp-s1-a2fe`  
**Statut hyps :** **proposées** (code + tests) — **pas encore jouées** (aucun run étape 1)

| B* | Définition | Params figés |
|----|------------|--------------|
| **BM** | Paper réel | Entrées = B7 ; `exit_mode=direction` ; stop 1.5 ATR + TP 2R ; **pas** de time-stop ; `full_cash` |
| **BN** | Bouclier régime | Exposé si HTF close §2.2 ≠ short ; `exit_mode=exposure` ; pas stop/TP/time-stop ; coûts à chaque bascule ; `full_cash` |

| # | hypothesis_id | B* | symbole | TF | coûts | statut | compte |
|---|----------------|----|---------|----|-------|--------|--------|
| 37 | `BM-BTCUSDT-1h-base` | BM | BTCUSDT | 1h | base | proposé (VP-S1) | **+1** |
| 38 | `BM-BTCUSDT-4h-base` | BM | BTCUSDT | 4h | base | proposé | **+1** |
| 39 | `BM-ETHUSDT-1h-base` | BM | ETHUSDT | 1h | base | proposé | **+1** |
| 40 | `BM-ETHUSDT-4h-base` | BM | ETHUSDT | 4h | base | proposé | **+1** |
| 41 | `BM-SOLUSDT-1h-base` | BM | SOLUSDT | 1h | base | proposé | **+1** |
| 42 | `BM-SOLUSDT-4h-base` | BM | SOLUSDT | 4h | base | proposé | **+1** |
| 43 | `BN-BTCUSDT-1h-base` | BN | BTCUSDT | 1h | base | proposé | **+1** |
| 44 | `BN-BTCUSDT-4h-base` | BN | BTCUSDT | 4h | base | proposé | **+1** |
| 45 | `BN-ETHUSDT-1h-base` | BN | ETHUSDT | 1h | base | proposé | **+1** |
| 46 | `BN-ETHUSDT-4h-base` | BN | ETHUSDT | 4h | base | proposé | **+1** |
| 47 | `BN-SOLUSDT-1h-base` | BN | SOLUSDT | 1h | base | proposé | **+1** |
| 48 | `BN-SOLUSDT-4h-base` | BN | SOLUSDT | 4h | base | proposé | **+1** |

```
N_proposé = 36 (gelé J1) + 12 (BM/BN × 3 × 2) = 48
Adverse sur les mêmes hyps = pas +1
```

**N T10b proposé = 48** — à valider Claude avant étape 2 (run). DSR reporté avec N=48, non bloquant pour M/N.

### Hors scope VP-S1

Validation 2025 · holdout 2026 · variantes de paramètres · paper live.  

