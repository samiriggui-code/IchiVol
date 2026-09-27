# Handoff Cursor â†” Claude â€” IchiVol V3

## 2026-09-27 nuit â€” Claude local : VP-P Â« paper fidÃ¨le Â» livrÃ© (PR draft) Â· PRIORITÃ‰ recadrÃ©e par Samir

**Branche :** `claude/vp-p-paper-fidele` (worktree sÃ©parÃ© `IchiVol-vpp`) Â· **PR draft [#159](https://github.com/samiriggui-code/IchiVol/pull/159)** Â· **aucun merge sans revue**.

### Recadrage Samir (2026-09-27) â€” opposable
1. **PrioritÃ© = simuler fidÃ¨lement le paper rÃ©el** (tailles, capital commun, sorties, coÃ»ts) et diagnostiquer entrÃ©es / sorties / filtres. Pas de rÃ©duction du problÃ¨me au Â« manque de trades Â».
2. **BN (bouclier) reste une expÃ©rience sÃ©parÃ©e** (PR #157, rapport et verdict propres). Â« Bouclier validÃ© Â» â‰  rentabilitÃ© du paper.
3. **BM Ã  100 % du cash = variante Ã  allocation normalisÃ©e**, elle ne reprÃ©sente pas le paper (prÃ©cision Ã©crite dans l'amendement P.0, aucune rÃ¨gle M/N changÃ©e).
4. Validation 2025 et holdout 2026 **intacts** ; aucun nouvel indicateur / rÃ©glage sans problÃ¨me observÃ© + test prÃ©-enregistrÃ© distinct.

### LivrÃ©
| Commit | Contenu |
|--------|---------|
| `e745f73` | Amendement `VP0-2026-09-27b` (Question P, **prÃ©-enregistrÃ© avant run**) Â· audit [`VP-P-PAPER-REEL.md`](./VP-P-PAPER-REEL.md) (code + base prod en lecture seule) Â· ledger +2 lignes diag. |
| `da8dab5` | `research_lab/sim.py` options opt-in (`cost_by_symbol`, `levels_anchor`, `gate_equity`, `min_fill_fraction`, MFE/MAE) â€” **dÃ©fauts inchangÃ©s**, tests research_lab/vp1/vp2/vp3/paper verts Â· paquet `vpp/` Â· `tests/vpp` |
| suivant | Runs R1â€“R4, C1, contexte â†’ [`VP-P-REPORT.md`](./VP-P-REPORT.md) + `vpp-artifacts/` |

### RÃ©sultat court (dev 2021-07 â†’ 2024-12, 20 cryptos, capital commun 5 000 â‚¬)
- **5 000 â†’ 1 876 â‚¬ (âˆ’62,5 %), DD âˆ’64 %, 2 867 trades, 7/7 plis nÃ©gatifs** (continu et rÃ©initialisÃ©), seeds 0â€“4 identiques, adverse âˆ’80,6 %.
- Brut dÃ©jÃ  nÃ©gatif (âˆ’0,04 R/trade) ; coÃ»ts â‰ˆ 0,13 R/trade. Rendement aprÃ¨s BUY â‰ˆ dÃ©rive normale de l'actif (1â€“24 h) â†’ **problÃ¨me principal = information du signal d'entrÃ©e**.
- Plafond 10 %/position **toujours** atteint â†’ exposition moyenne 7,9 % : seconde limite (taille), indÃ©pendante.
- MTF 4h **ne bloque jamais** un BUY (WATCH seulement) â€” Ã©cart vs descriptions.
- Prod : les scans UI 15m/4h/1d **ouvrent des positions paper automatiques** (8/39 la 1Ê³áµ‰ semaine).

### Prochaine Ã©tape proposÃ©e (NON lancÃ©e, Ã  prÃ©-enregistrer si Samir valide)
**P3 = Ã©tude d'Ã©vÃ©nement** BUY vs barres alÃ©atoires mÃªme actif / mÃªme mois, h = 24/48/96/168, IC bootstrap blocs, dev seulement. Si rien ne passe â†’ on arrÃªte d'optimiser l'entrÃ©e B7. Sinon **un** test de sortie Ã  l'horizon trouvÃ©.

### âš ï¸ Incident dÃ©pÃ´t local (2026-09-27 ~22h)
Un autre agent travaille dans `C:\laragon\www\IchiVol` : changements de branche, `git stash`, `git reset --hard`. Mes premiÃ¨res modifications ont Ã©tÃ© mises dans **`stash@{0}` (Â« wip-off-156-branch Â»)** â€” tout a Ã©tÃ© restaurÃ© dans le worktree, **ce stash n'a pas Ã©tÃ© supprimÃ©** (il contient aussi des `.tmp-*.err` de l'autre agent). Les modifications de `sim.py` avaient Ã©tÃ© effacÃ©es par un `reset --hard` et ont Ã©tÃ© refaites. **RÃ¨gle proposÃ©e :** un worktree par agent.

---

## 2026-09-27 nuit â€” VERDICT Claude #156 UI-VP-BADGE : Ã€ CORRIGER (petit) Â· âš ï¸ build front cassÃ© sur main

### âš ï¸ DÃ©couverte : `npm run build` du front Ã©choue sur `main` depuis #152

`tsc -b` Ã©choue sur `src/lib/chartIntelligencePacks.test.ts` (types `node:test` / `node:assert` absents, fixtures typÃ©es de travers). Ce fichier de test est inclus dans `tsconfig.app.json`, donc **un rebuild `web` sur le VPS Ã©chouerait**. Erreur de Claude : j'avais validÃ© #152 avec `tsc --noEmit -p .`, qui ne vÃ©rifie **rien** (le `tsconfig.json` racine a `files: []`). **Ã€ partir de maintenant, la vÃ©rif front = `npx tsc -b`.**
Le `exclude` des `*.test.ts` ajoutÃ© dans #156 **corrige** ce problÃ¨me : les tests tournent via `tsx --test`, ils n'ont rien Ã  faire dans le build de l'app. â†’ **Garder cet exclude.** VÃ©rifiÃ© : `tsc -b` passe sur la branche #156 ; tests 6/6.

### #156 â€” revue

| Point | Verdict |
|-------|---------|
| Texte centralisÃ© `vpValidationCopy.ts` + `isActionableBuySell` | âœ… |
| Affichage seulement (aucun moteur / paper / gates) | âœ… |
| Lien vers le rapport (dÃ©pÃ´t **public**) | âœ… |
| **B1 â€” captures** | âŒ ce sont des **maquettes isolÃ©es**, pas l'app. Et `mobile.png` est **identique octet pour octet** Ã  `light.png` (mÃªme md5). Refaire 3 vraies captures **dans l'app** : matrice OpportunitÃ©s, fiche dÃ©cision, fiche Position ; clair, sombre et mobile 390 px. |
| **B2 â€” doublon dans la fiche** | âš ï¸ dans la fiche dÃ©cision, le badge apparaÃ®t **2 fois** (ligne verdict `DecisionsPage` + `DecisionPipelinePanel`). **Un seul badge par vue** : garder celui de la ligne verdict. |
| Mineur | CSS importÃ© globalement dans `main.tsx` plutÃ´t que dans le composant, et `createElement` au lieu de JSX : acceptable, Ã  ne pas gÃ©nÃ©raliser. |

**Suite :** Cursor corrige B1 + B2 sur #156 â†’ STOP â†’ merge aprÃ¨s OK Claude. **PrioritÃ©** : ce merge rÃ©pare aussi le build front de `main`.

---

## 2026-09-27 nuit â€” Claude : amendement Bouclier (M/N) figÃ© Â· job VP-S1 en file

**DÃ©cision Samir :** l'objectif est de gagner **sans risquer ses Ã©conomies**. On teste donc IchiVol comme **bouclier** (moins de chute), plus comme Â« battre le buy & hold Â». **Jamais d'argent rÃ©el imposÃ©** : backtest â†’ 8 semaines de broker virtuel â†’ dÃ©cision de Samir.

**Protocole :** amendement datÃ© `VP0-2026-09-27` dans [`VALIDATION-PROTOCOL.md`](./VALIDATION-PROTOCOL.md) (section Â« Questions M / N Â»), **figÃ© avant tout run** :
- **BM** = paper rÃ©el (entrÃ©es B7 ; sorties live : stop 1.5 ATR + TP 2R + sortie quand la direction n'est plus LONG ; pas de time-stop ; 100 % cash).
- **BN** = bouclier rÃ©gime (investi tant que la direction HTF close â‰  short, cash sinon).
- **N T10b = 48.** CritÃ¨res S1â€“S5 : chute â‰¤ Â½ de B0 Â· CAGR > 0 et â‰¥ Â½ de B0 Â· Calmar > B0 Â· IC Î” maxDD appariÃ© exclut 0 Â· tient en adverse. DSR reportÃ©, non bloquant.

### File Cursor (ordre)

1. **UI-VP-BADGE** (en cours) â†’ PR draft â†’ STOP.
2. **VP-S1** (aprÃ¨s revue du badge) :
   - **Ã‰tape 1** : code BM (`exit_mode="direction"` + stop/TP, sans time-stop, via Rules dÃ©diÃ©es dans `vp3/rules.py`) et BN (masque d'exposition HTF â‰  short, exÃ©cution close â†’ open t+1, sans stop). Tests unitaires (sortie direction, bascule BN, pas de lookahead HTF, coÃ»ts Ã  chaque bascule). Ledger T10b +12 â†’ N = 48. MÃ©triques S1â€“S5 + bootstrap Î” maxDD appariÃ©. **Aucun run.** PR draft â†’ STOP.
   - **Ã‰tape 2** (aprÃ¨s OK Claude) : run base + adverse, n_boot 10 000 â†’ `docs/VP-S1-REPORT.md` (un tableau S1â€“S5 par symbole Ã— TF, avec verdict) + artefact JSON. STOP.
   - **Interdit :** validation 2025, holdout 2026, toute variante de paramÃ¨tre, toucher au paper live.

---

## 2026-09-27 soir â€” Claude : VP3 CLÃ”TURÃ‰ Â· dÃ©cisions Samir Â· programme VP en PAUSE

**Tip :** `main` @ `99ae3e4`. VÃ©rifiÃ© aprÃ¨s merge #155 : les bornes lo/hi rÃ©elles des IC sont affichÃ©es âœ… ; les notes Â§9 (ICâˆ‹0 âˆ§ Nâ‰¥40 â†’ PAS D'EDGE) et B6 ATR UNKNOWN sont prÃ©sentes âœ….

### JournÃ©e 2026-09-27 (cloud + local)

| PR | Contenu | Revue |
|----|---------|-------|
| #151 | VP-FIX1 (Vision Âµs, DSR, bootstrap stationnaire, WF) | Claude local âœ… |
| #152 | Infobulles packs CI + fix `rafRef` StrictMode (calques invisibles) | Claude local âœ… + test navigateur |
| #153 | VP-GRID1 + VP2-R1 time-stop 48 barres | Claude cloud âœ… |
| #154 | VP-NT1 N=24, DSR barre, base + adverse | Claude cloud âœ… |
| #155 | VP-J1 N=36, B6/B7, Q J â€” **rapport FINAL** | Claude local âœ… |

### Lecture du rÃ©sultat (0 EDGE / 48)

- Sur les plis WF 2021â€“2024, aprÃ¨s coÃ»ts, **aucune rÃ¨gle d'entrÃ©e B1â†’B7 ne bat B0 (buy & hold)** de faÃ§on significative. Ajouter des filtres n'aide pas : **B7 (pipeline live) fait moins bien que des versions plus simples.**
- **Limites :**
  1. La sortie testÃ©e est la **sortie commune Â§6** (stop 1,5 ATR, objectif 2R, time-stop 48 barres), pas la sortie du paper live (changement de direction). La stratÃ©gie paper exacte n'a pas Ã©tÃ© testÃ©e telle quelle.
  2. 2020â€“2024 est une pÃ©riode trÃ¨s haussiÃ¨re pour la crypto.
  3. Â§9 juge le **rendement**, pas la protection contre les baisses (B0 : maxDD jusqu'Ã  âˆ’63 % sur un pli).

### DÃ©cisions Samir (2026-09-27) â€” opposables

1. **Programme VP en PAUSE.** On n'ouvre **ni la validation 2025 ni le holdout 2026** (le holdout ne sert qu'une fois ; pas de gaspillage sur des stratÃ©gies sans edge). Pas de VP4 Ã  VP9, pas de B3/B4/B8.
2. **Paper trading inchangÃ©** : il continue (forward test de la vraie stratÃ©gie avec ses vraies sorties).
3. **Prochaine Ã©tape : sÃ©ance de rÃ©flexion stratÃ©gie (Claude + Samir), sans code.** Piste principale : **timing de sortie / mise Ã  l'abri** plutÃ´t que choix des entrÃ©es (rester investi par dÃ©faut, sortir en rÃ©gime baissier ; objectif = presque le rendement de B0 avec une chute nettement plus faible). Chaque idÃ©e retenue = nouvelle hypothÃ¨se T10b (N passe de 36 Ã  37â€¦), sans toucher au holdout.
4. **Pas d'argent rÃ©el** sur les signaux IchiVol : la condition Â« preuve d'edge Â» du passage broker live n'est **pas** remplie.

### TÃ¢che Cursor : UI-VP-BADGE â€” **APPROUVÃ‰E par Samir (2026-09-27), Ã  lancer**

**UI-VP-BADGE** : sur les verdicts ACHAT/VENTE (DÃ©cisions, fiches, OpportunitÃ©s), badge discret Â« Signal non validÃ© â€” VP3 : pas d'edge mesurÃ© (0/48) Â» avec un lien vers `VP3-REPORT-FINAL.md`, dans l'esprit du `NON_VALIDE` d'AW1. Affichage seulement : aucun changement moteur, paper ou gates.

### âš ï¸ Rappel dÃ©ploiement

**#142** (CSS mobile, draft, **non mergÃ©**) tourne en prod sur le VPS (`RELEASE=9ab99fb`). DÃ©ployer `main` sans #142 **supprime ces correctifs mobiles en prod**. Avant tout dÃ©ploiement : reviewer puis merger #142, ou le rebaser.

### Cursor

**Job actif : UI-VP-BADGE** (branche `cursor/ui-vp-badge-a2fe`, PR draft, STOP). Rien d'autre tant que la sÃ©ance stratÃ©gie n'a pas abouti.

---

## 2026-09-27 â€” #155 VP-J1 MERGED

**Squash-merge :** [`e2af12b`](https://github.com/samiriggui-code/IchiVol/commit/e2af12b) Â· PR [#155](https://github.com/samiriggui-code/IchiVol/pull/155)  
**N T10b gelÃ© :** **36** Â· Claude VALIDÃ‰ (vp1/vp2/vp3 verts) Â· corrections doc prÃ©-merge incluses.

### LivrÃ©

| Item | Contenu |
|------|---------|
| Fixes prÃ©-run | B6 live ATR+ADX gate Â· B7 `WARMUP_BARS` Â· tests `test_vp3_b6_b7.py` |
| Run | `python -m vp3.j1_run` base+adverse Â· n_boot=10â€¯000 Â· N=36 Â· Q A/B/H/J |
| Artefact | [`docs/vp3-artifacts/j1_results.json`](./vp3-artifacts/j1_results.json) |
| Rapport | [`docs/VP3-REPORT-FINAL.md`](./VP3-REPORT-FINAL.md) â€” IC lo/hi rÃ©els + notes Â§9 / B6 ATR |
| Ledger | 12 hyps B6/B7 marquÃ©es **jouÃ©es** Â· N=36 |

### RÃ©sultat court

- **0** `bi_beats_bj` Â· **0 EDGE / 48** (24 base + 24 adverse)
- verdict_final : mix **PAS D'EDGE** / **NON CONCLUANT** (voir FINAL)
- Ïƒ(SR_ann) base â‰ˆ 0.631 Â· SR*_ann â‰ˆ 0.935 ; adverse Ïƒ â‰ˆ 0.858 Â· SR*_ann â‰ˆ 1.270
- Bj : BTC 1h=**B6**, BTC 4h=**B5**, ETH/SOL 1h+4h=**B0**
- Doc : IC Î” / IC trades Bi = bornes lo/hi depuis JSON ; Â§9 ICâˆ‹0 âˆ§ Nâ‰¥40 â†’ PAS D'EDGE ; INFO B6 ATR UNKNOWN (lab) vs PENDING (live), barres prÃ©-WF1 seulement

### STOP

Pas de nouveau job VP (B3/B4/B8, val 2025, holdout) **sans dÃ©cision de Samir**.

### Hors scope (respectÃ©)

B3/B4/B8 Â· retuning Â· val 2025 / holdout Â· features CI/T-CYCLE.

---

## 2026-09-27 â€” VP-J1 Ã©tape 1 â€” N=36 proposÃ©, STOP

**Branche :** `cursor/vp-j1-a2fe` @ `6e56058`  
**Base main :** `2a585f8` (#154 VP-NT1 **VALIDÃ‰** + squash-mergÃ©)  
**PR draft :** [#155](https://github.com/samiriggui-code/IchiVol/pull/155) â€” **aucun run** / **aucun merge** avant validation.

### LivrÃ© (Ã©tape 1 seulement)

| Item | Contenu |
|------|---------|
| Ledger | +12 hyps B6/B7 Ã— BTC/ETH/SOL Ã— 1h/4h â†’ **N proposÃ© = 36** |
| Gel B6 | ATR dead=**0.15** Â· extreme=**0.90** Â· `LiveScreenerSettings` / `AtrParams` @ main |
| Gel B7 | `strategy_version=ichivol_pipeline_v1` Â· blob `pipeline.py` `9403d9f4â€¦` |
| DÃ©f. **J** | Bj = max DSR_i parmi B0â€“B6 (base, N=36) ; Ã©galitÃ© â†’ plus simple B0&lt;â€¦&lt;B6 ; mÃªme Bj en adverse |
| Audit Â§2 | B6 : **pas de filtre ADX** (Ã©cart) ; B7 warm-up sans `WARMUP_BARS` (Ã©cart mineur) ; sorties Â§6 OK â€” **aucune correction** (corrigÃ© ensuite `9a7a019` avant Ã©tape 2) |
| HANDOFF-LOCAL | tip main **`2a585f8`** |

### STOP

Attendre validation Claude + utilisateur de **N=36**, de la **dÃ©finition de J**, et du **point c** (Ã©carts).  
**Ã‰tape 2 non commencÃ©e.** *(supersÃ©dÃ© â€” Ã©tape 2 DONE ci-dessus)*

### Hors scope

B3/B4/B8 Â· changement params/rÃ¨gles Â· val 2025 / holdout Â· features CI/T-CYCLE.

---

## 2026-09-27 â€” VP-NT1 Ã©tape 2 DONE

**Branche :** `cursor/vp-nt1-a2fe` Â· **PR draft :** [#154](https://github.com/samiriggui-code/IchiVol/pull/154)  
**N T10b gelÃ© :** **24** Â· tip code fixes `da6b5bb` (DSR barre + Â§9) Â· run complet + rapport ci-dessous.

### LivrÃ©

| Item | Contenu |
|------|---------|
| Run | `python -m vp3.nt1_run` base+adverse Â· n_boot=10â€¯000 Â· N=24 |
| Artefact | [`docs/vp3-artifacts/nt1_results.json`](./vp3-artifacts/nt1_results.json) |
| Rapport | [`docs/VP3-REPORT-GRID.md`](./VP3-REPORT-GRID.md) **v2** (v1 en Historique) |
| Ledger | contamination prÃ©-gel validÃ©e @ `e588557` (N inchangÃ©) |
| Tests | `tests/vp3` 31/31 (validÃ©s Claude) |

### RÃ©sultat court

- **0** `bi_beats_bj` Â· **0** EDGE (base et adverse)
- verdict_final : mix **PAS D'EDGE** / **NON CONCLUANT** (voir synthÃ¨se v2)
- Ïƒ(SR_ann) base â‰ˆ 0.645 Â· SR*_ann â‰ˆ 0.897 ; adverse Ïƒ â‰ˆ 0.898 Â· SR*_ann â‰ˆ 1.249

### STOP

PR #154 reste **draft**. Pas de merge. Pas dâ€™Ã©tape suivante autonome.

### Hors scope (respectÃ©)

Q J (B7) Â· B3/B4/B6 Â· changement params/rÃ¨gles Â· features CI/T-CYCLE Â· dÃ©cision sur val 2025 / holdout.

---

## 2026-09-27 â€” VP-NT1 Ã©tape 1 â€” ledger prÃªt, STOP

**Branche :** `cursor/vp-nt1-a2fe` @ `cb2f390`  
**Base main :** `b1cd43d` (#153 VP-GRID1 squash-mergÃ©, VALIDÃ‰ Claude)  
**PR draft :** [#154](https://github.com/samiriggui-code/IchiVol/pull/154) â€” **aucun merge** / **aucun rerun** avant validation de N.

### LivrÃ© (Ã©tape 1 seulement)

| Item | Contenu |
|------|---------|
| Ledger | [`docs/VP-T10B-LEDGER.md`](./VP-T10B-LEDGER.md) â€” 24 hyps B0/B1/B2/B5 Ã— BTC/ETH/SOL Ã— 1h/4h Ã— base |
| Non jouÃ© | B3, B4, B6, B7 / Q J = **0** run VP1 documentÃ© ; adverse = 0 |
| Rejeux notÃ©s | BTC 1h : #149 smoke â†’ #150 â†’ v2 VP-FIX1 â†’ v3 VP2-R1 (**pas +1**) |
| **N proposÃ©** | **`24`** = 4 Ã— 3 Ã— 2 |
| Cas douteux | D1â€“D8 dans le ledger (B0 comptÃ© ; rejeux non comptÃ©s ; pas de count par question) |
| HANDOFF-LOCAL | tip main sync **`b1cd43d`** |

### Calcul court

```
4 (BTC 1h B0/B1/B2/B5, 1Ê³áµ‰ #150) + 20 (GRID1 nouvelles cellules) = 24
```

### STOP

Attendre validation de **N** par Claude + utilisateur.  
**Ã‰tape 2 non commencÃ©e** (rerun grille base + adverse + verdicts Â§9).

### Hors scope (respectÃ©)

Q J (B7) Â· changement params/rÃ¨gles Â· features CI / T-CYCLE Â· tuning validation 2025 / holdout.

---

## 2026-09-27 â€” VP-GRID1 rÃ©serves Claude traitÃ©es

**Branche :** `cursor/vp-grid1-a2fe` Â· **PR draft :** [#153](https://github.com/samiriggui-code/IchiVol/pull/153)  
**Commit fixes :** `2d34ffb`  
**STOP :** pas de merge sans OK final Claude. **VP-NT1 non commencÃ©.**

### RÃ©serves corrigÃ©es

| # | Fix |
|---|-----|
| 1 | `VP3-REPORT-GRID.md` Lecture courte : DSR_i â‰¥ 0.95 exhaustif (BTC 4h H = 0.9503, SOL 4h B = 0.955) + ligne N trials=1 surÃ©valuÃ©s + ligne 4h N=14â€“26 puissance faible |
| 2 | Note 19 barres 1h manquantes : 10 plages identiques BTC/ETH/SOL + time-stop temps rÃ©el â†’ moins de 48 barres rÃ©elles si trou (doc only) |
| 3 | `vp3/grid_run.py` : `out_path.write_text("")` au dÃ©marrage |
| 4 | `test_vp2_harness.py` : 2 lignes vides avant `test_full_cash_sizes_near_initial` |
| 5 | Postgres : `test_routes` (daily_halt + no_atr) + `test_manual_buy` â€” **passent** sur `main@848f194` **et** sur la branche â†’ **pas de rÃ©gression** |

### Postgres â€” sortie collÃ©e

Commande (identique main / branche) :

```bash
cd ichivol-app/engine
.venv/bin/pytest -q \
  tests/api/test_routes.py::test_open_paper_route_uses_disposable_even_if_baseline_halted \
  tests/api/test_routes.py::test_open_paper_position_reports_no_atr_stop_honestly \
  tests/paper/test_manual_buy.py \
  --tb=line
```

**main @ `848f194` :**

```
.....                                                                    [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /workspace/ichivol-app/engine/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /workspace/ichivol-app/engine/.venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

**branche `cursor/vp-grid1-a2fe` :**

```
.....                                                                    [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /workspace/ichivol-app/engine/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /workspace/ichivol-app/engine/.venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

Verdict tests : **5/5 pass** des deux cÃ´tÃ©s â†’ pas de rÃ©gression GRID1.

### Hors scope (toujours)

Q J (B7) Â· gel N T10b Â· profil adverse Â· features CI / T-CYCLE. Job suivant **VP-NT1** seulement aprÃ¨s merge #153.

---

## 2026-09-27 â€” Cursor VP-GRID1 DONE Â· PR draft Â· STOP

**Branche :** `cursor/vp-grid1-a2fe` @ `4381ea2`  
**PR draft :** [#153](https://github.com/samiriggui-code/IchiVol/pull/153) â€” **aucun merge** sans verdict Claude.

### LivrÃ©

| ID | Contenu |
|----|---------|
| **VP2-R1** | `sim.py` : `(tâˆ’entry)//bar >= nâˆ’1` ; tests `exit_time == entry+(nâˆ’1)Â·bar` (+ cas n=48) ; note datÃ©e VALIDATION-PROTOCOL Â§12 |
| **VP1** | Rebuild ETH/SOL (+ BTC) 1h/4h/1d via `build-spot` + `assert_series_completeness` ; sha256 dans le rapport |
| **Grille** | A/B/H Ã— BTC/ETH/SOL Ã— 1h/4h Â· base Â· n_boot=10â€¯000 â†’ [`VP3-REPORT-GRID.md`](./VP3-REPORT-GRID.md) |
| **BTC 1h v3** | Remplace v2 : pointeur en tÃªte de [`VP3-REPORT-BTCUSDT-1h.md`](./VP3-REPORT-BTCUSDT-1h.md) |
| Helper | `python -m vp3.grid_run` |
| Handoff local | `HANDOFF-LOCAL-CLAUDE.md` sync `848f194` Â· #151/#152 Â· VP2-R1 tranchÃ© Â· job GRID1 |

### RÃ©sultat grille (synthÃ¨se)

**18/18** `bi_beats_bj=false`. Aucun claim EDGE. DÃ©tail + sha256 sÃ©ries dans le rapport GRID.

### Tests

- `tests/vp2` time-stop + `tests/vp1/vp3` : verts (locaux).  
- `pytest tests` Postgres : 3 Ã©checs **prÃ©existants / flaky DB** (`test_open_flow` equity drift, `test_routes` daily_halt vs no_atr, `test_manual_buy`) â€” reproduits hors branche sur `main` pour `test_open_flow` ; **hors scope VP-GRID1**.

### Hors scope (respectÃ©)

Q J (B7) Â· figer N T10b Â· profil adverse Â· features CI / T-CYCLE.

### STOP

Revue Claude sur cette PR. Pas de merge autonome.

---

## 2026-09-26 ~22h45 â€” DÃ‰CISIONS Claude (dÃ©lÃ©gation explicite de Samir : Â« dÃ©merde-toi Â»)

### #152 infobulles â€” **VALIDÃ‰ + test visuel fait par Claude** â†’ merge

- **Vraie cause de la disparition des calques** (bug **dÃ©jÃ  prÃ©sent sur main**, visible en dev) : en React StrictMode, le dÃ©montage annulait le `requestAnimationFrame` sans remettre `rafRef.current = null`. Ensuite `bump()` sortait toujours tout de suite, la projection n'Ã©tait jamais calculÃ©e, et l'overlay restait vide alors que les compteurs Ã©taient justes (mesurÃ© : `rafRef` bloquÃ© Ã  2, 11 appels de `bump` sans effet). CorrigÃ© : `rafRef.current = null` au nettoyage. Les nouvelles tentatives ajoutÃ©es par Cursor quand la taille vaut 0 (1áµ‰Ê³ affichage en dialog) sont conservÃ©es.
- Test navigateur (local, fiche BTCUSDT 1h, agent-browser) : pour chaque pack, calques dessinÃ©s **et** infobulle correcte. Overlay de **832 px** = zone de tracÃ© (hÃ´te 885 âˆ’ Ã©chelle 52), donc aucun dÃ©bordement.

| Pack | Ã‰lÃ©ments SVG dessinÃ©s | Calques de l'infobulle |
|------|-----------------------|------------------------|
| Calme | 66 | Market Structure, Ichimoku |
| Structure | 102 | + Support / Resistance |
| Setup | 98 | Market Structure, Fibonacci, FVG, Ichimoku |
| LiquiditÃ© | 102 | + S/R, Liquidity |
| Tout | 133 | les 8 calques |

`tsc` propre Â· tests packs 2/2.

### #151 VP-FIX1 â€” **merge**

### VP2-R1 time-stop â€” **dÃ©cision : 48 barres, la barre d'entrÃ©e compte comme barre 1**

Sortie au close de `entry_bar + 47` (1h) / `+ 23` (4h). C'est une **clarification de lecture** de Â§6 (Â« 48 barres Â»), pas une nouvelle rÃ¨gle : note datÃ©e Ã  ajouter dans VALIDATION-PROTOCOL Â§12. Le rapport BTC 1h est Ã  rejouer (v3) avec ce dÃ©compte.

### Prochain job Cursor : VP-GRID1 (voir message en bas de ce bloc)

1. VP2-R1 : `sim.py` time-stop `>= time_stop_bars - 1` (ou Ã©quivalent) + test `exit_time == entry + (n-1)Â·bar` + note Â§12 dans VALIDATION-PROTOCOL.
2. VP1 : reconstruire les sÃ©ries ETH et SOL (1h/4h/1d) avec contrÃ´le de complÃ©tude ; sha256 dans le rapport.
3. Rejouer A/B/H sur la grille **BTC/ETH/SOL Ã— 1h/4h**, coÃ»ts **base**, n_boot 10 000 â†’ `docs/VP3-REPORT-GRID.md` (un tableau par symboleÃ—TF + synthÃ¨se). Remplacer BTC 1h v2 par v3.
4. **Q J (B7) : pas encore.** **N T10b : pas encore** (on figera N aprÃ¨s avoir vu la grille, sur le compte rÃ©el d'hypothÃ¨ses jouÃ©es). **Adverse : pas encore.**
5. PR draft â†’ entrÃ©e handoff â†’ STOP.

---

## 2026-09-26 ~21h30 â€” #152 CI-T1/T2/INFO corrigÃ©s Â· push draft Â· STOP

**Branche :** `cursor/ci-pack-tooltips-a2fe`  
**PR draft :** https://github.com/samiriggui-code/IchiVol/pull/152  
**Tests :** `npx tsx --test src/lib/chartIntelligencePacks.test.ts` â†’ 2/2 pass

| ID | Fix |
|----|-----|
| **CI-T1** | `plotWidthPx(scale \|\| hostâˆ’rightScale)` ; overlay `.ci-chart-overlay` reprend `style={{ width }}` (plus `inset:0` pleine largeur) |
| **CI-T2** | `EXPECTED_BY_PACK` figÃ© (calm1 / structure2 / setup3 / liquidity3 / full5) + test repli largeur |
| **INFO** | `barSeconds` du timeframe courant (`res.replay.bar_seconds`) â†’ `IntelligenceChart` (plus `bar \|\| 3600` seul) |

**#151** â€” VALIDÃ‰ ; mÃ©nage local fait (`.gitignore` UTF-16 supprimÃ© ; `_ab_h_fix1.json` â†’ `ichivol-app/engine/vp1/data/runs/`). **Merge uniquement sur OK Samir.**

**STOP** â€” Samir : test visuel packs (hover + pas de dÃ©bordement Ã©chelle prix).

---

## 2026-09-26 ~21h â€” VERDICTS Claude #151 + #152

### #151 VP-FIX1 â€” **VALIDÃ‰** (merge possible dÃ¨s OK Samir)

- Code dÃ©jÃ  prÃ©-revu Ã  20h20 âœ…. Rapport v2 cohÃ©rent : les verdicts A/B/H ne changent pas (`false` partout). B2 a une espÃ©rance **nÃ©gative** (âˆ’4.31) aprÃ¨s correctifs ; B5 passe de +10.20 Ã  +5.39 ; 320â†’317 trades expliquÃ©s par la note sur la derniÃ¨re barre de pli. SÃ©ries 1h/4h/**1d** complÃ¨tes, avec sha256.
- MÃ©nage local (hors PR) : `engine/vp3/.gitignore` est en **UTF-16** (Git ne le lit pas correctement) et `vp3/_ab_h_fix1.json` traÃ®ne non suivi. RÃ©Ã©crire le `.gitignore` en UTF-8 ou le supprimer ; ranger les sorties de run dans `vp1/data/` (gitignored) ou `docs/`.
- Toujours en attente de Samir : **VP2-R1** (time-stop 48 vs 49 barres). Ã€ trancher **avant** la grille, sinon il faudra tout rejouer.

### #152 infobulles packs â€” **Ã€ CORRIGER**

| ID | Constat | Correction |
|----|---------|------------|
| **CI-T1** | `IntelligenceChart` : `width = max(scale.width(), host.clientWidth)`. `host.clientWidth` **inclut l'Ã©chelle de prix de droite** (visible, `rightPriceScale`). Donc dans le cas normal, l'overlay devient plus large que la zone de tracÃ© et les rayons / zones / extensions Fib **dÃ©bordent sur les Ã©tiquettes de prix**. En plus, `style={{width}}` a Ã©tÃ© retirÃ© de l'overlay (`inset:0`). | N'utiliser le repli hÃ´te **que si** `scale.width()` vaut 0, et retrancher la largeur de l'Ã©chelle : `scale.width() \|\| (host.clientWidth âˆ’ chart.priceScale('right').width())`. Remettre la largeur explicite de l'overlay. |
| **CI-T2** | `chartIntelligencePacks.test.ts` est **tautologique** : `expected` est calculÃ© avec la mÃªme fonction que le rÃ©sultat, donc le test passe toujours. | Figer les nombres attendus en dur par pack (ex. `calm: 1, structure: 2, setup: 3, liquidity: 3, full: 5`, Ã  dÃ©river de `LAYER_PACKS` Ã  la main). Ajouter un test du repli de largeur (`scale.width()=0` â†’ hÃ´te âˆ’ Ã©chelle ; `scale.width()>0` â†’ inchangÃ©). |
| **CI-T3** | Pas de preuve visuelle (Â« session auth Â»). | Samir valide Ã  la main en local (voir ci-dessous) ; sinon, captures via un compte de dev. |
| INFO | `bar \|\| 3600` : repli codÃ© en dur sur 1h. | Utiliser la durÃ©e de barre du timeframe courant. |

Le reste est OK : l'infobulle est une couche additive dans `BriefingControls`, sans toucher `DrawingLayer` / `*Drawing.tsx` ; le bouton paper de la matrice est bien exclu.

**Test manuel pour Samir (aprÃ¨s CI-T1) :** DÃ©cisions â†’ fiche BTCUSDT 1h â†’ passer la souris sur chaque pack (Calme / Structure / Setup / LiquiditÃ© / Complet). L'infobulle s'affiche, les calques FVG / Fib / structure sont toujours dessinÃ©s aprÃ¨s chaque clic, et rien ne recouvre l'Ã©chelle de prix Ã  droite.

---

## 2026-09-26 21h00 â€” Cursor CI pack tooltips Â· PR draft #152 Â· STOP

**Branche :** `cursor/ci-pack-tooltips-a2fe` @ `80216ce`  
**PR draft :** https://github.com/samiriggui-code/IchiVol/pull/152  
**Exception gel CI** limitÃ©e aux infobulles packs (OK Samir).

### Contenu
- `BriefingControls` : tip riche (calques du pack) â€” `.ci-pack-tip`, hors SVG
- `buildObjectTooltip` additif (`chartIntelligence.ts`)
- `IntelligenceChart` : fallback width/height host (anti calques vides) â€” **DrawingLayer / \*Drawing.tsx inchangÃ©s**
- Test `chartIntelligencePacks.test.ts` + `docs/CI-PACK-TOOLTIPS-PROOF.md`
- **Exclu** : bouton paper matrice (`DecisionsPage`)

### Preuve
Unit test comptes/pack stables. Captures hover pack BTCUSDT 1h = Ã  coller en review manuelle.

**STOP** â€” revue Claude avant merge.

---

## 2026-09-26 20h45 â€” Cursor VP-FIX1 DONE Â· PR draft Â· STOP

**Branche :** `cursor/vp-fix1-a2fe` Â· tip `80ffc37` (+ docs report/handoff)  
**PR :** draft [#151](https://github.com/samiriggui-code/IchiVol/pull/151) â€” **aucun merge** sans verdict Claude.

### LivrÃ©

| ID | Fichiers clÃ©s | Tests |
|----|---------------|-------|
| VP1-R1 | `vp1/load.py` â€” `normalize_vision_time_ms`, `assert_series_completeness` | `tests/vp1/test_vp1_core.py` (Âµs fixture + gaps) |
| VP3-R1 | `vp3/dsr.py` â€” Ïƒ empirique `trial_srs`, skew/kurt sample | `test_dsr_n1_equals_psr`, `test_dsr_decreases_with_n_trials_not_crushed` |
| VP3-R2 | `vp3/bootstrap.py` â€” Politisâ€“Romano | `test_stationary_block_mean_length_near_target` |
| VP3-R3 | `vp3/wf.py` â€” sim `fin+horizon`, gate `[gate,fin)`, force_flat B0/VAL/HOLD | (prÃ©-revue Claude âœ…) |
| VP3-R4 | `compare.py` / CLI dÃ©faut **10â€¯000** | â€” |
| VP3-R5 | assert timestamps appariÃ©s | `test_paired_block_timestamp_mismatch_raises` |
| VP2-R2 | `research_lab/sim.py` stop/TP @ raw open | `test_stop_tp_anchored_on_raw_open_not_fill` |
| AG0-R1 | `claudeTools.ts` `await readAnthropicStream` | `timeout â€¦ mode stream` 17/17 |
| ENV-R1/R2 | `deep_history.py` flock portable Â· kill-switch portfolio dÃ©diÃ© | commit sÃ©parÃ© `80ffc37` |
| VP2-R1 | **non touchÃ©** | â€” |

### Rebuild + run v2

- SÃ©ries BTC : 1h `3fe8b47â€¦` (52â€¯565) Â· 4h `cd8bef9â€¦` (13â€¯146) Â· **1d** `1d04e6bâ€¦` (**2â€¯191**, 0 trou)  
- A/B/H n_boot=10â€¯000 : toutes **`bi_beats_bj=false`** â€” dÃ©tail [`VP3-REPORT-BTCUSDT-1h.md`](./VP3-REPORT-BTCUSDT-1h.md) **v2** (tableau avant/aprÃ¨s + note derniÃ¨re barre de pli)  
- UI Chart Intelligence **stashÃ©e** (`stash@{0}: ci-pack-tooltips WIP`) â€” **hors** cette PR ; suite branche `cursor/ci-pack-tooltips-a2fe`

### STOP

Revue Claude sur cette PR. Pas de grille ETH/SOL/4h, pas Q J, pas figer N T10b, pas features CI/T-CYCLE dans ce push.

---

## 2026-09-26 20h20 â€” PrÃ©-revue Claude VP-FIX1 (local, pas encore de PR)

Branche locale `cursor/vp-fix1-a2fe` : `85fbba9` (VP-FIX1) + `80ffc37` (ENV-R1/R2). **Pas poussÃ©e, pas de PR, pas d'entrÃ©e Cursor.** Le run A/B/H v2 tourne (python lancÃ© Ã  19:44).

| ID | Statut |
|----|--------|
| VP1-R1 Âµs | âœ… corrigÃ© + contrÃ´le de complÃ©tude. VÃ©rifiÃ© sur les donnÃ©es reconstruites : BTC 1h **52 565 / 52 584** (19 trous), 4h **13 146 / 13 146**, derniÃ¨re barre 2026-08-31 23:00 UTC |
| VP3-R1 DSR | âœ… Ïƒ empirique + skew/kurt d'Ã©chantillon ; `n_trials>1` sans `trial_srs` lÃ¨ve une erreur (bien) |
| VP3-R2 stationnaire | âœ… Politisâ€“Romano |
| VP3-R3 force_flat | âœ… sim jusqu'Ã  fin de pli + horizon, equity coupÃ©e au pli, force_flat seulement B0 / VAL / HOLD |
| VP3-R4 / R5 / VP2-R2 / AG0-R1 / ENV-R1 / ENV-R2 | âœ… |
| VP2-R1 time-stop | non touchÃ© âœ… (en attente dÃ©cision Samir) |

Tests : vp1/vp2/vp3 + kill-switch + deep_history + t11a_bis **verts** Â· `claudeTools.test.ts` **17/17**.

**Points restants avant PR :**
1. **INFO Ã  documenter** : un signal sur la derniÃ¨re barre d'un pli est rempli au 1áµ‰Ê³ open du pli suivant ; il n'est donc comptÃ© dans **aucun** pli (1 barre par pli). C'est acceptable, mais Ã  Ã©crire dans le rapport v2.
2. SÃ©rie **1d** non reconstruite (nÃ©cessaire pour B5/B6 en 4h). Pas bloquant pour BTC 1h ; obligatoire avant la grille.
3. **UI Chart Intelligence dans l'arbre de travail (demande de Samir : infobulles sur les packs)** : exception au gel CI **limitÃ©e aux infobulles**, validÃ©e par Samir. **RÃ©gression signalÃ©e par Samir** : une fois les infobulles ajoutÃ©es, les calques FVG / Fibonacci / structure **disparaissent** au changement de pack. Ã€ 20h25, Cursor avait dÃ©jÃ  remis `DrawingLayer` / `IntelligenceChart` / `*Drawing.tsx` Ã  l'Ã©tat HEAD. La lib `buildObjectTooltip` est purement additive et `tsc` est propre. RÃ¨gles pour refaire :
   - branche dÃ©diÃ©e `cursor/ci-pack-tooltips-a2fe`, **sÃ©parÃ©e de VP-FIX1** ;
   - l'infobulle est une **couche en plus**, sans toucher au rendu ni au filtrage des calques (pas de changement de `pointer-events`, de z-index ni de clip sur le SVG des dessins) ;
   - critÃ¨re de non-rÃ©gression : sur BTCUSDT 1h, pour **chaque pack**, le nombre d'objets dessinÃ©s est le mÃªme avant et aprÃ¨s (test ou capture par pack dans la PR) ;
   - le bouton Â« ouvrir paper depuis la matrice Â» (`DecisionsPage.tsx`) n'est **pas** couvert par l'exception : il sort de cette PR, ou Samir le demande explicitement et il a une revue dÃ©diÃ©e (flux paper).
4. Ã€ la fin du run : rapport v2 (avant/aprÃ¨s + sha256 des nouvelles sÃ©ries), entrÃ©e handoff, **push + PR draft** â†’ STOP.

## 2026-09-26 nuit â€” REVIEW Claude a posteriori #140â†’#150 Â· VP-FIX1 ouvert

**Revue rÃ©alisÃ©e par Claude en local** sur `main` @ `65419b9` : vrai diff + tests (serveur 67/67 âœ… Â· moteur : voir fin de bloc).
Ces 9 PR avaient Ã©tÃ© mergÃ©es sans revue Claude (Â« file gel Claude pause Â»). Verdicts ci-dessous = **opposables**.

### Verdicts par PR

| PR | Sujet | Verdict |
|----|-------|---------|
| #140 | VP0 VALIDATION-PROTOCOL + AW0 | **VALIDÃ‰** (reste GEL DOC) |
| #143 | AW1 Â« Pourquoi ? Â» `explain_chart_object` | **VALIDÃ‰** â€” dÃ©terministe, observe-only, aucun niveau inventÃ©, `NON_VALIDE` affichÃ© |
| #144 | AG0 hygiÃ¨ne agent | **VALIDÃ‰** + 1 mineur (AG0-R1) |
| #145 | Filtre `entry_source` outcomes | **VALIDÃ‰** |
| #146 | VP1 Vision + manifest | **Ã€ CORRIGER â€” CRITIQUE** (VP1-R1) |
| #147 | VP2 harness Â§6 | **Ã€ CORRIGER** (VP2-R1 Ã  trancher, VP2-R2) |
| #148/#149 | VP3 B0â€“B7 + compare | **Ã€ CORRIGER** (VP3-R1â†’R5) |
| #150 | Rapport BTC 1h | **PROVISOIRE** â€” lecture qualitative plausible, chiffres Ã  rejouer aprÃ¨s VP-FIX1 |

VÃ©rifiÃ© OK (pas de lookahead) : nuage **affichÃ©** = `span[iâˆ’26]` ; HTF B5 = derniÃ¨re bougie HTF **close** Ã  `t+Î”` ; RVOL/ATR causaux ; `levels_only` n'a aucune sortie pipeline ; gap stop/TP â†’ fill Ã  l'open ; stop avant TP ; attribution trade â†’ pli d'entrÃ©e ; outcomes AG0 = open 1Ê³áµ‰ barre close aprÃ¨s signal.

### Corrections demandÃ©es (VP-FIX1)

| ID | SÃ©vÃ©ritÃ© | Constat | Correction attendue |
|----|----------|---------|---------------------|
| **VP1-R1** | **CRITIQUE** | Binance Vision **spot** passe en **microsecondes** au 2025-01-01 (vÃ©rifiÃ© : `BTCUSDT-1d-2025-01.zip` col0 = `1735689600000000`). `klines_from_spot_zip` compare Ã  des ms â†’ **toutes les barres 2025â€“2026 sont silencieusement jetÃ©es**. Preuve : 1d = **1583** barres = 2020-09-01â†’2024-12-31 exactement (fenÃªtre complÃ¨te â‰ˆ 2191). **Validation 2025 et holdout 2026 seraient vides.** WF1â€“WF7 non affectÃ©s. | Normaliser `open_time`/`close_time` (â‰¥ 1e15 â†’ Âµs â†’ `//1000`). Test fixture Âµs. **ContrÃ´le de complÃ©tude** : compter barres attendues vs obtenues par intervalle sur la fenÃªtre et **Ã©chouer** si trou > seuil (lister les trous). Rebuild sÃ©ries + manifest (nouveaux sha256), noter les anciens sha dans le rapport. VÃ©rifier aussi funding/OI (unitÃ©s). |
| **VP3-R1** | **HAUTE** (bloque Â« figer N T10b Â») | `expected_max_sr(sr_std=1.0)` : Ã©chelle fausse â€” SR est **par barre** (~1e-2), Ïƒ=1 â‡’ dÃ¨s N>1, SR* â‰ˆ 0.3+ et DSR â†’ 0 quoi qu'il arrive. `skew=0 / kurt=3` codÃ©s en dur. | Ïƒ(SR) = Ã©cart-type **empirique** des SR (mÃªme Ã©chelle par barre) des N essais T10b ; skew/kurt **d'Ã©chantillon** des returns de Bi dans PSR. Tests : N=1 â‡’ DSR = PSR(0) ; N croissant â‡’ DSR dÃ©croissant mais pas Ã©crasÃ© sur un cas synthÃ©tique. |
| **VP3-R2** | MOYENNE | Â§9.2 exige un block bootstrap **stationnaire** (longueurs gÃ©omÃ©triques, moyenne 24 / 6). ImplÃ©mentÃ© : blocs **fixes** circulaires. | Politisâ€“Romano stationnaire (p = 1/bloc_moyen), indices appariÃ©s. Test sur longueur moyenne des blocs. |
| **VP3-R3** | MOYENNE | `force_flat_at_end=True` dans chaque pli WF â‡’ trades ouverts dans les 48 derniÃ¨res barres **coupÃ©s en fin de pli** (`window_end`). Viole Â§5.1.7 (peut finir aprÃ¨s le pli) et Â§5.1.8 (sortie forcÃ©e seulement fin validation / holdout). | Sim jusqu'Ã  `fin pli + horizon time-stop` ; entrÃ©es gatÃ©es Ã  `[gate, fin pli)` ; trades attribuÃ©s au pli d'entrÃ©e ; `force_flat` seulement VAL2025 / HOLD2026. MÃªme fenÃªtre de returns pour Bi et Bj (appariement). |
| **VP3-R4** | BASSE | `compare_pair` et CLI `--n-boot` par dÃ©faut = **2000** (Â§9.2 : 10 000). | DÃ©faut 10 000. |
| **VP3-R5** | BASSE | Appariement par troncature `min(len)` sans vÃ©rifier les timestamps. | `assert` timestamps identiques barre Ã  barre (lever une erreur sinon). |
| **VP2-R1** | **Ã€ TRANCHER (utilisateur)** | Time-stop : sortie au close de `entry_bar + 48` â‡’ **49 barres** en position (test `exit_time == T0+H+n*H` le fige). Â§6 dit Â« 48 barres Â». | Proposition Claude : barre d'entrÃ©e = barre 1 â‡’ sortie au close de `entry + 47` (48 barres exposÃ©es). Si l'utilisateur valide : note de **clarification** datÃ©e dans VALIDATION-PROTOCOL Â§12 (lecture, pas nouvelle rÃ¨gle), test mis Ã  jour. |
| **VP2-R2** | BASSE | Stop/TP ancrÃ©s sur `fill` (open Ã— (1+spread+slip)) au lieu de `entry = open(t+1)` (Â§6). | Niveaux depuis l'open **brut** ; coÃ»ts restent sur le fill. |
| **VP3-R6** | INFO | B7 aligne HTF sur `candle.time` (open) â‡’ une bougie HTF plus tard que B5 (`time+Î”`). Causal, conservateur. | Documenter dans le rapport J (paritÃ© live) ; pas de changement. |
| **AG0-R1** | BASSE | Streaming : `return readAnthropicStream(...)` sans `await` dans le `try` â‡’ `clearTimeout` avant la lecture du corps ; le timeout ne couvre pas le stream. | `return await readAnthropicStream(...)` + test timeout en mode stream. |

### Suite (ordre strict)

1. **Cursor â€” VP-FIX1** : une branche `cursor/vp-fix1-*`, PR **draft**, VP1-R1 + VP3-R1â†’R5 + VP2-R2 + AG0-R1 (VP2-R1 seulement si OK utilisateur). Rebuild VP1, puis **rejouer BTCUSDT 1h A/B/H** (n_boot 10 000) â†’ `VP3-REPORT-BTCUSDT-1h.md` **v2** avec tableau avant/aprÃ¨s. EntrÃ©e handoff â†’ **STOP**.
2. **Claude** : revue VP-FIX1 (diff + tests + contrÃ´le complÃ©tude VP1).
3. Seulement aprÃ¨s : grille ETH/SOL Ã— 1h/4h Â· Q **J** (B7) Â· N T10b figÃ© (avec DSR corrigÃ©) Â· adverse.

**Aucun merge sans verdict Claude Ã©crit ici.**

### Tests locaux (Windows, Postgres, venv py3.14)

- Serveur : **67/67** âœ…
- Moteur, suites revues (vp1/vp2/vp3, AW1 explain, AG0 closed-only, evidence, entry_source) : **toutes vertes** âœ…
- Moteur, suite complÃ¨te : **8 Ã©checs sans rapport avec #140â†’#150** :
  - 6 Ã— `fcntl` absent sous Windows (`strategy_lab/deep_history.py:116`, `test_t11a_bis`) â†’ **ENV-R1** : ajouter un repli portable (`msvcrt` ou `filelock`) ou un skip Windows explicite.
  - `test_p1_study_budget_limit500_under_20s` : 22,5 s pour un budget de 20 s sur ce PC (performance machine) â†’ budget Ã  paramÃ©trer, ou marquer `slow`.
  - `test_trip_daily_loss_latches_and_needs_unlock` : `tripped=False`. Le test utilise le portefeuille baseline de la base locale, donc il dÃ©pend de l'Ã©tat de la DB ; fichier inchangÃ© depuis #81. â†’ **ENV-R2** : isoler le test dans un portefeuille dÃ©diÃ©.

---

## 2026-09-26 soir â€” SYNC LOCAL Â· tip `7d0f5f4` Â· journal journÃ©e

**PC local** fast-forward `3038eed` â†’ `main` @ **`7d0f5f4`** (= GitHub).  
Ce bloc = rÃ©sumÃ© unique de **toute la journÃ©e** pour reprise Claude / Cursor.

### Tip HEAD

`7d0f5f4` â€” docs(vp3): formalize A/B/H BTCUSDT 1h report at n_boot=10000 (#150)

### Journal (ordre chronologique approximatif)

| Bloc | Tips / PRs | Statut |
|------|------------|--------|
| Landing V3 | `c2cf1cf` | MERGED |
| Market TV plein Ã©cran + mobile + calques | `396a917` â€¦ `8ddeec2` | MERGED |
| Chart Intelligence prototype â†’ API â†’ DÃ©cisions | #124â†’#134 | **GEL** (bugs only) |
| T-CI-BRIEF packs/camÃ©ra | #133 `df013fb` | MERGED Â· sous GEL CI |
| T-CYCLE B1â€“B4 + P1â€“P6 | #123 `9e2b02f` | **GEL** |
| GOLDEN-RVOL py3.12 | #139 `c46eda1` | MERGED |
| Handoff GEL CI+T-CYCLE + VP0 | #136 `6634438` | MERGED |
| **VP0** VALIDATION-PROTOCOL + AW0 | #140 `34991b4` | **GEL DOC** |
| AW1 Â« Pourquoi ? Â» | #143 `7723e53` | MERGED |
| AG0 hygiÃ¨ne agent + filtre evidence | #144+#145 | MERGED |
| **VP1** Vision freeze | #146 `89e950a` | MERGED |
| **VP2** harness Â§6/Â§1ter | #147 `91c2795` | MERGED |
| **VP3** B0â€“B7 + compare A/B/H | #148â€“#150 â†’ `7d0f5f4` | MERGED Â· **pas de claim EDGE** |

### VP3 A/B/H â€” BTCUSDT 1h Â· n_boot=10â€¯000 Â· [`VP3-REPORT-BTCUSDT-1h.md`](./VP3-REPORT-BTCUSDT-1h.md)

| Q | Pair | bi_beats_bj |
|---|------|-------------|
| A | B1 vs B0 | **false** (B1 dominÃ©) |
| B | B2 vs B1 | **false** (Î” ok Â· DSR 0.52) |
| H | B5 vs B2 | **false** (IC inclut 0) |

### GEL actifs (ne pas rouvrir sans OK Claude)

- Chart Intelligence (features) Â· T-CYCLE (features) Â· VP0 doc  
- Pas de regen goldens Â· pas de claim EDGE (N T10b=1 provisoire)

### Suite file (Claude review puis OK utilisateur)

1. Revue Claude rapport VP3 A/B/H  
2. ETH/SOL Â· 4h Â· Q **J** (B7) Â· N T10b figÃ© Â· adverse stress  
3. Bugs/hotfixes CI ou T-CYCLE OK hors gel feature

### Docs Ã  lire

- [`VALIDATION-PROTOCOL.md`](./VALIDATION-PROTOCOL.md) Â· [`AW0-CONSOLIDATION.md`](./AW0-CONSOLIDATION.md)  
- [`VP3-REPORT-BTCUSDT-1h.md`](./VP3-REPORT-BTCUSDT-1h.md) Â· [`HANDOFF-LOCAL-CLAUDE.md`](../HANDOFF-LOCAL-CLAUDE.md)

---

## 2026-09-26 â€” VP1â†’VP3 MERGÃ‰S Â· compare A/B/H provisoire

### Merges (OK utilisateur Â· file gel Claude pause)

| PR | Tip | Contenu |
|----|-----|---------|
| #140 VP0 | `34991b4` | **GEL** VALIDATION-PROTOCOL + AW0 |
| #143 AW1 | `7723e53` | Pourquoi? / explain_chart_object |
| #144 AG0 | `c3d9a3c` | HygiÃ¨ne agent |
| #145 filtre | `7741c92` | outcomes exclut prÃ©-AG0 sans entry_source |
| **#146 VP1** | `89e950a` | Vision + manifest + loader |
| **#147 VP2** | `91c2795` | Harness Â§6 / Â§1ter |
| **#148 VP3** | `d3abe6f` | B0â€“B7 + WF + mÃ©triques + DSR |
| **#149** | `e352c3c` | compare A/B/H CLI + B0 WF fix + BTC 1h |
| **#150** | `7d0f5f4` | rapport formalisÃ© n_boot=10â€¯000 |

### VP3 compare â€” [`VP3-REPORT-BTCUSDT-1h.md`](./VP3-REPORT-BTCUSDT-1h.md) Â· tip `7d0f5f4`

BTCUSDT 1h Â· base Â· **n_boot=10â€¯000** :

| Q | Pair | bi_beats_bj | Note |
|---|------|-------------|------|
| A | B1 vs B0 | **false** | B1 dominÃ© (Î”&lt;0, IC exclut 0) |
| B | B2 vs B1 | **false** | Î”&gt;0 IC ok Â· DSR 0.52 |
| H | B5 vs B2 | **false** | IC Î” inclut 0 Â· DSR 0.72 |

Claude review au retour. Suite : ETH/SOL Â· 4h Â· Q J (B7) Â· N T10b.
---

## 2026-09-26 â€” VP2 harness Â· VP1 funding OK Â· file gel (Claude pause)

### Merges (OK utilisateur)

| PR | Tip | Contenu |
|----|-----|---------|
| #140 VP0 | `34991b4` | **GEL** VALIDATION-PROTOCOL + AW0 |
| #143 AW1 | `7723e53` | Pourquoi? / explain_chart_object |
| #144 AG0 | `c3d9a3c` | HygiÃ¨ne agent |
| #145 filtre | `7741c92` | outcomes exclut prÃ©-AG0 sans entry_source |

### VP1 â€” MERGED [#146](https://github.com/samiriggui-code/IchiVol/pull/146) â†’ `main` @ `89e950a`

- Package `engine/vp1/` : Vision download + CHECKSUM + manifest + frozen loader.
- **Spot** : 648 monthly zips Â· series 1h **37973** / 4h **9498** / 1d **1583** / symbole.
- **Funding** : 216 monthly zips OK (BTC/ETH/SOL).
- OI daily metrics = optionnel / gros volume (B4+) â€” resume-friendly.
- `vp1/data/` gitignored.

### VP2 â€” MERGED [#147](https://github.com/samiriggui-code/IchiVol/pull/147) â†’ `main` @ `91c2795`

- `research_lab/sim.py` : `exit_mode=levels_only`, `time_stop_bars`, `full_cash`, `force_flat_at_end`.
- Package `engine/vp2/` : Rules Â§6/Â§1ter, loader VP1â†’feed, run metadata (seed, sha256, protocol, cost base|adverse).
- Tests `tests/vp2/`.

### VP3 â€” MERGED [#148](https://github.com/samiriggui-code/IchiVol/pull/148) â†’ `main` @ `d3abe6f`

- `engine/vp3/` : entrÃ©es B0â€“B7 Â· WF Â· Â§8.1 Â· bootstrap Â· DSR Â· `vp3 wf|compare`.

---

## 2026-09-26 â€” MERGED #134+#133 Â· GEL Chart Intelligence Â· T-CYCLE P6 Â· tip `9e2b02f`

### Merges

| PR | Tip squash | Contenu |
|----|------------|---------|
| **#134** | `50ea9c4` | CI-R1â†’R9 (walk-forward, slim replay, lineage_key, LRU 32) |
| **#133** | `df013fb` | Briefing pÃ©riode/packs/camÃ©ra + entryTime hors sÃ©rie â†’ swing |

### VPS smoke replay (#134) â€” BTCUSDT 1h lookback=48 limit=300

| MÃ©trique | Valeur |
|----------|--------|
| Taille | **1,023 Mo** |
| 1Ê³áµ‰ appel | **7,33 s** Â· `cached=false` Â· 48 frames Â· walk_forward |
| 2áµ‰ appel | **`cached=true`** Â· 1,2 s (hit + transfert) |
| Frame keys | `as_of`, `objects`, `market_state` |
| Lineage | union frames **397** `lineage_key` / 937 ids |
| RELEASE | `df013fb main` (web rebuild post-#133) Â· backup `pre-ci-r7-r9-20260926-115211.tgz` |

### GEL Chart Intelligence

**Aucune nouvelle fonctionnalitÃ©** Chart Intelligence jusquâ€™Ã  VP0+ (protocole validation). Bugs / hotfixes OK.

### T-CYCLE P6 â€” MERGÃ‰ #123 @ `9e2b02f` Â· GEL

- `validate_cycle_synthetic` â†’ `_validate_cycle_synthetic_cached` + `@lru_cache(maxsize=32)`
- Test : 2áµ‰ appel &lt; 1 s
- Squash-merge #123 Â· VPS engine `RELEASE=9e2b02f` Â· **GEL T-CYCLE** (bugs only jusquâ€™Ã  VP)

### Ticket GOLDEN-RVOL â€” rapport bisect (ne pas rÃ©gÃ©nÃ©rer)

**Issue :** voir [#135](https://github.com/samiriggui-code/IchiVol/issues/135).  
**Update 2026-09-26 soir :** cause = py3.11 vs 3.12 `sum()` â€” voir Â§ Review Claude + PR #139. Bisect agent (tip vert) reste valide ; pas de regen.

### VP0

Voir [`VALIDATION-PROTOCOL.md`](./VALIDATION-PROTOCOL.md). Ancien fichier = annexe technique seulement.

## 2026-09-26 â€” MERGED #134 CI-R1â†’R9 Â· VPS smoke replay Â· tip `50ea9c4`

**Claude APPROUVÃ‰ Â· squash-merge #134** â†’ `main` @ `50ea9c4`.

### VPS smoke (post-rebuild engine+web)

| MÃ©trique | Valeur |
|----------|--------|
| Endpoint | `GET /chart-intelligence/BTCUSDT/replay?timeframe=1h&limit=300&lookback_bars=48` |
| Taille | **1,023 Mo** (1â€¯072â€¯573 bytes) â€” budget &lt; 1,5 Mo |
| 1Ê³áµ‰ appel | **7,33 s** Â· `cached=false` Â· `replay_mode=walk_forward` Â· 48 frames Â· 300 candles Â· 40 objets |
| 2áµ‰ appel | **`cached=true`** Â· 1,2 s (transfert payload ; hit cache moteur) |
| Frame keys | `as_of`, `objects`, `market_state` (sÃ©ries une fois Ã  la racine) |
| Lineage | root 40 ids / 36 `lineage_key` ; union frames 937 ids / **397 lineage_keys** |
| RELEASE | `50ea9c4 main` Â· backup `/opt/ichivol-backup/pre-ci-r7-r9-20260926-115211.tgz` |
| FQDN | https://ichivol.global-it-ss.com |

### Suite ordre Claude

1. ~~Squash-merge #134 + VPS smoke~~ **FAIT**
2. Squash-merge #133 (repli entryTime) + rebuild web
3. **GEL Chart Intelligence** (aucune nouvelle fonctionnalitÃ©)
4. T-CYCLE P6 (`lru_cache` `validate_cycle_synthetic`) puis merge + VPS + gel
5. Ticket **GOLDEN-RVOL** (bisect, rapport HANDOFF â€” pas de rÃ©gÃ©nÃ©ration Ã  lâ€™aveugle)
6. **VP0** protocole validation (doc only)

---

## 2026-09-26 â€” #133 briefing Â· repli entryTime hors sÃ©rie â†’ swing

**Suite OK Claude** (merge aprÃ¨s #134) : si `entryTime` &lt; premiÃ¨re bougie chargÃ©e, pÃ©riode / camÃ©ra = **`swing`**.

| Fichier | Changement |
|---------|------------|
| `chartIntelligenceBriefing.ts` | `defaultBriefing` + `cameraForPeriod` acceptent `seriesFirstTime` |
| `ChartIntelligencePanel.tsx` | corrige la pÃ©riode quand les bougies arrivent |

---

## 2026-09-26 â€” Chart Intelligence Briefing (pÃ©riode + packs + camÃ©ra) â€” PR #133 Â· branche `cursor/chart-intel-briefing-a2fe`

- **PR** : [#133](https://github.com/samiriggui-code/IchiVol/pull/133)
- **Revue** : APPROUVÃ‰ ; `context=position` â†’ **Depuis entrÃ©e** (entry âˆ’ 8 barres) ; repli swing si entry hors sÃ©rie
- Placement : fiches DÃ©cisions (`prep`) / Position (`position`) â€” **pas** MarchÃ©

### Fichiers briefing

| Fichier | RÃ´le |
|---------|------|
| `src/lib/chartIntelligenceBriefing.ts` | pÃ©riode / packs / `ChartCamera` / `defaultBriefing` |
| `src/components/chart-intelligence/BriefingControls.tsx` | UI segmented |
| `IntelligenceChart.tsx` | prop `camera` |
| `ChartIntelligencePanel.tsx` | wire + `entryTime` |

---

## 2026-09-26 â€” REVIEW Claude CI-R7â†’R9 Â· Chart Intelligence â€” MERGÃ‰ #134 @ `50ea9c4`

| ID | Correction |
|----|------------|
| **CI-R7** | Frames slim ; sÃ©ries une fois ; **mesurÃ© local 0,94 Mo / VPS 1,02 Mo** (48Ã—300) |
| **CI-R8** | `origin.lineage_key` ; known_at/status_history par lineage |
| **CI-R9** | Cache replay LRU **32** + purge Ã  lâ€™Ã©criture |

### Fichiers R7â€“R9

| Fichier | RÃ´le |
|---------|------|
| `app/chart_intelligence/service.py` | frames slim, lineage, LRU 32 |
| `app/chart_objects/from_{fvg,structure,breaks,fibonacci}.py` | `lineage_key` |
| `src/lib/useChartIntelligence.ts` | tronque sÃ©ries par `as_of` |
| `tests/api/test_chart_intelligence_route.py` | R7 taille, R8 FVG, R9 LRU |

---

## 2026-09-26 â€” REVIEW Claude CI-R1â†’R6 Â· Chart Intelligence â€” MERGÃ‰ dans #134

| ID | Correction |
|----|------------|
| **CI-R1** | replay walk-forward ; known_at ; status_history |
| **CI-R2** | closed_candles mid-bar |
| **CI-R3** | analysis = pipeline Option B |
| **CI-R4** | RVOL via `LiveScreenerSettings` |
| **CI-R5** | kumo projetÃ© `time - 25Ã—bar â‰¤ T` |
| **CI-R6** | docstring anti-lookahead clarifiÃ©e |

**GEL Chart Intelligence** aprÃ¨s merge #133.


---

## 2026-09-26 â€” Chart Intelligence placement â€” PR #130 Â· tip `14ed73e`

- **MarchÃ©** = `PriceChart` live uniquement (CI retirÃ©)
- **OpportunitÃ©s** = clic valeur â†’ fiche + Chart Intelligence (`context=prep`, palette signaux)
- **Portefeuille** = clic position â†’ fiche + Chart Intelligence (`context=position`)
- **VPS** : `RELEASE=14ed73e` Â· rebuild `web` Â· public **200**

---

## 2026-09-26 â€” Chart Intelligence API LIVE â€” PR #128 Â· tip `1f56aff`

- **PR** : [#128](https://github.com/samiriggui-code/IchiVol/pull/128) â†’ `main` @ `1f56aff`
- **API** : `GET /api/engine/chart-intelligence/{symbol}` (OHLCV + Ichimoku + ChartObjects + market_state + analysis + `as_of`)
- **Front** : `source="api"` (MarchÃ© + `/app/chart-intelligence`) â€” plus de mock en prod
- **VPS** : `RELEASE=1f56aff` Â· rebuild `engine`+`web` Â· endpoint **200** `mock=false` BTCUSDT
- Smoke VPS : `n_obj=32` candles=80 sur BTCUSDT 1h

---

## 2026-09-26 â€” Chart Intelligence BRANCHÃ‰ + VPS â€” PR #126 Â· tip `e52dcba`

- **PR** : [#126](https://github.com/samiriggui-code/IchiVol/pull/126) squash â†’ `main` @ `e52dcba`
- **Wiring** : `ChartIntelligencePanel` sous PriceChart (`MarketPage`) + route `/app/chart-intelligence` (mock SOLUSDT)
- **Fix build** : `OverviewPage` `drawdownRatio` (tsc 0) â€” requis pour rebuild `web`
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=e52dcba main` Â· rebuild `web` Â· public/api **200**
- **Backup** : `/opt/ichivol-backup/pre-chart-intel-wire-*.tgz`
- Mock Python uniquement ; API `chart-intelligence` pas encore cÃ´tÃ© engine

---

## 2026-09-26 â€” Chart Intelligence prototype MERGÃ‰ â€” PR #124 Â· tip `e0c84ba`

- **PR** : [#124](https://github.com/samiriggui-code/IchiVol/pull/124) squash-merge â†’ `main` @ `e0c84ba`
- **SHA** : `e0c84ba44259d269b4e38d3ac3ade700fe7dcd79`
- **Scope** : prototype React/TS isolÃ© sous `ichivol-app/src/components/chart-intelligence/` + `lib/chartIntelligence*` (mock Python, replay `as_of`)
- **Contrat** : `ChartObject` uniquement â€” **pas** de type `DrawingObject` (voir `INTEGRATION.md`)
- **Non fait (volontaire)** : aucun branchement pages / `Root.tsx` ; pas de route ; pas de dÃ©pendance ajoutÃ©e
- **VÃ©rifs** : `tsc` (seule erreur prÃ©existante `OverviewPage.tsx:389`) Â· `oxlint chart-intelligence` = 0
- **Revue Claude** : reportÃ©e (restriction jusquâ€™Ã  ~12:30) â€” Ã  relire quand dispo ; pas de suite UI sans lecture `INTEGRATION.md`

---

## 2026-09-26 â€” REVIEW Claude Â· T-CYCLE Cycle/Spectral Engine V0â†’V0.1 â€” tip `84e54e0`

**Pour Claude :** relecture complÃ¨te du chantier T-CYCLE avant toute suite (OOS / ablation / UI).  
**Branche :** `main` @ `84e54e0` Â· **VPS engine** dÃ©ployÃ© `RELEASE=main 84e54e0` Â· `/api/engine/health` 200 Â· `/cycle/BTCUSDT` 200.

### Diff Ã  lire (ordonnÃ©e)

```
17d7283..84e54e0
```

| Commit | Contenu |
|--------|---------|
| `17d7283` | `docs/CYCLE_ENGINE_AUDIT.md` |
| `d388c77` | CDC + METHODS + HANDOFF (chantier ouvert) |
| `e20b173` | `app/cycle/` FFT+Hilbert+ACF + tests lookahead |
| `9ace200` | `GET /cycle/{symbol}` + goldens OpenAPI/route_order |
| `66816fc` | study walk-forward + null models + agent tools + benchmark |
| `84e54e0` | perf API last-window (~9Ã—) + doc benchmark |

**Doc maÃ®tre :** [`docs/CYCLE_ENGINE_AUDIT.md`](./CYCLE_ENGINE_AUDIT.md)  
**CDC :** checkbox `T-CYCLE` ouverte (V0 livrÃ©, promotion gate **fermÃ©e**)  
**METHODS :** ligne Cycle/Spectral V3/test Â· rÃ¨gle Â« ne vote jamais LONG/SHORT Â»

### Ce qui est livrÃ© (observe-only)

- `CycleState` : pÃ©riode, phase, force, stabilitÃ©, rÃ©gime `TREND|CYCLE|TRANSITION|NOISE`, `methods_agreement` â€” **aucun** champ BUY/SELL/LONG/SHORT/proba de gain
- MÃ©thodes V0 : FFT periodogram Â· Hilbert/Ehlers-style Â· ACF peaks Â· consensus (stdlib only, **pas** numpy/talib/PyEMD)
- Causal : fenÃªtres â‰¤ T ; tests truncation `tests/cycle/test_cycle_lookahead.py`
- HTTP : `GET /api/engine/cycle/{symbol}` Â· `GET /api/engine/cycle/{symbol}/study`
- Agent : `get_cycle_state` Â· `run_cycle_study` (`read_only=True`)
- Lab : `app/cycle/study.py` â€” walk-forward + nulls (persist / hist avg / random) ; `verdict.promote_to_decision` **toujours false**
- Perf API : ~620 ms/symbole synthÃ©tique (avant ~5â€“7 s) ; screener 40â€“100 **hors scope**
- VPS : image `ichivol-engine` rebuildÃ©e sur ce tip

### Ce qui Nâ€™est PAS fait (volontaire)

- `decision/pipeline.py` / paper / confidence / combiner â€” **intacts**
- EMD/EEMD/CEEMDAN Â· deps TA-Lib/Wickra
- CycleStack MTF Â· ExpectedMoveRange Â· zones projetÃ©es UI
- Ablation Aâ€“G multi-symboles OOS rÃ©els
- Teaser Contexte / Desk cycle

### Questions pour Claude (review)

1. Le schÃ©ma `CycleState` + rÃ©gimes est-il cohÃ©rent avec la philosophie IchimokuÃ—RVOL (dimension TEMPS, pas un 10e vote) ?
2. La sÃ©paration API fast-path vs `compute_cycle_series` (Lab) est-elle acceptable cÃ´tÃ© causalitÃ© / stabilitÃ© ?
3. Les null models du study sont-ils suffisants pour un premier verdict, ou faut-il imposer dâ€™autres baselines avant OOS ?
4. HypothÃ¨se produit Â« filtre de rÃ©gime > prÃ©dicteur de prix Â» â€” valider ou corriger avant ablation.
5. Y a-t-il redondance dangereuse avec ATR/ADX/Donchian si on promeut trop tÃ´t un rÃ©gime CYCLE/NOISE ?
6. Perf ~620 ms : OK pour appel Ã  la demande ; faut-il un budget CPU Ã©crit avant tout teaserUI ?

### Suite proposÃ©e (aprÃ¨s OK Claude)

1. OOS multi-symboles (vrais OHLCV) via `/study`  
2. Ablation Aâ€“G  
3. DÃ©cision filtre vs prÃ©dicteur  
4. Seulement alors : Ã©ventuel teaser Contexte â€” **jamais** gate sans preuve  

### Contexte session parallÃ¨le (hors T-CYCLE, dÃ©jÃ  sur main)

- `dcafd6a` â€” page Contexte rebranchÃ©e (F&G, dominance, calendar, news, rÃ©gimes RSI/ATR, corr) â€” dÃ©ployÃ© web plus tÃ´t  
- Ne pas confondre avec Cycle Engine (autre surface)

Canal unique entre Cursor (implÃ©mentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff `17d7283..84e54e0`.

**Convention** : Ã  chaque PR / revue, ajouter une nouvelle entrÃ©e **en haut** ; ne jamais effacer les anciennes.

---

## 2026-09-26 â€” T-CYCLE V0.1 perf API (last-window)

- Benchmark synthÃ©tique : ~5â€“7 s/symbole car `compute_cycle_state` rejouait toute la sÃ©rie
- Fix : API/agent = derniÃ¨res `stability_lookback` fenÃªtres seulement ; Lab `compute_cycle_series` inchangÃ©
- Screener multi-symboles **toujours hors scope** tant que budget CPU non prouvÃ©

## 2026-09-26 â€” T-CYCLE V0 livrÃ© (observe-only) â€” tip Ã  jour sur `main`

- **Audit** : [`docs/CYCLE_ENGINE_AUDIT.md`](./CYCLE_ENGINE_AUDIT.md)
- **LivrÃ©** :
  - `app/cycle/` â€” FFT + Hilbert + ACF â†’ `CycleState` (stdlib, causal)
  - `GET /api/engine/cycle/{symbol}` + `GET /api/engine/cycle/{symbol}/study`
  - Agent tools `get_cycle_state` + `run_cycle_study`
  - Walk-forward + null models (`app/cycle/study.py`) ; `verdict.promote_to_decision` **toujours false**
  - Benchmark helper `app/cycle/benchmark.py` (`python -m app.cycle.benchmark`)
  - Tests lookahead / values / API / study
- **Pas livrÃ© (volontaire)** : pipeline gates, paper, UI Desk, EMD, CycleStack MTF, ExpectedMoveRange
- **Suite** : multi-symbol OOS, ablation Aâ€“G, benchmark 40/100 live candles, dÃ©cision filtre vs prÃ©dicteur
- CDC checkbox **T-CYCLE** reste ouverte jusquâ€™Ã  preuve OOS

## 2026-09-25 â€” T-CYCLE Cycle/Spectral Engine â€” chantier ouvert

- **Audit** : [`docs/CYCLE_ENGINE_AUDIT.md`](./CYCLE_ENGINE_AUDIT.md) Â· inscrit CDC V3 + METHODS
- **Objectif** : dimension TEMPS (pÃ©riode, phase, stabilitÃ©, rÃ©gime) â€” **pas** un 10e vote BUY/SELL
- **V0** : FFT + Hilbert + ACF â†’ `CycleState` ; API lecture seule ; tests lookahead ; **stdlib only**
- **Interdit V0** : `decision/pipeline.py`, paper, confidence, EMD live, UI Desk zones projetÃ©es
- **Promotion** : uniquement aprÃ¨s walk-forward + ablation + null models OOS
- Commits ordonnÃ©s (1 doc Ã  la fois) â€” pas de dump maquette

---

## 2026-09-25 â€” Agents 2b + Desk bulles MERGÃ‰S + VPS â€” tip `0fe45f2`

- Squash #117 Agents page â†” Eve + #118 Desk trajectoire bulles â†’ `main` @ `0fe45f2`
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=0fe45f2 main` Â· rebuild `web`/`server` Â· health **200**
- Live bundle contient `desk-eq-tip` + `Surveiller avec Eve`
- PrÃ©fÃ©rence Samir : **dÃ©ployer VPS Ã  chaque ajout/modif** (ne pas laisser en draft seul)

---

## 2026-09-25 â€” Chantier 2b Agents page â†” Eve runtime (draft)

- Branche `cursor/agents-page-a2fe` depuis `origin/main` @ Eve #111 mergÃ©
- **API** `GET /api/agents` : 6 role cards (`observer`â€¦`session`) + `runtime` (worker/drain) + `authorityChain` + rÃ©sumÃ© `eve` rÃ©trocompat
- **Statuts** dÃ©rivÃ©s (pas inventÃ©s) : engine health, kill-switch, positions paper, tÃ¢ches Eve, sessions FX, clÃ© LLM (env + settings user)
- **Front** `AgentsPage` : badges ACTIF/EN VEILLE/EN PAUSE/ERREUR ; notice runtime rÃ©elle ; chaÃ®ne dâ€™autoritÃ© si log ; mission Â« Surveiller avec Eve Â» via `POST /api/agents/missions`
- **FicheAgent** : FicheHost absent â†’ stub `?fiche=agent:id` + dialog maquette
- **OpÃ©rations / AgentLog** : follow-up (pas dâ€™injection ActivityPage â€” compare)
- Tests `agentRoles.test.ts` PASS ; `compare-maquette.mjs` **agents 1440/390 = 0** (script non modifiÃ©) ; desk Ã©carts `.up`/notice data-dÃ©pendants dÃ©jÃ  prÃ©sents sur main

### Suite
E2 evaluate_watch Â· FicheAgent quand fiches mergÃ©es Â· cancel mission endpoint Â· AgentLog â†’ journal ops

---

## 2026-09-25 â€” merge main â†’ Eve #111 (prÃªt merge)

- IntÃ¨gre main (thÃ¨me + copilot context #116) dans `cursor/eve-runtime-a2fe`
- E0+E1 AgentTask / schedule_recheck / API agents â€” **Ã  merger puis page Agents 2b**

---

## 2026-09-25 â€” Copilot : Â« Pourquoi BTC attend Â» charge le moteur (draft)

- Branche `cursor/copilot-context-a2fe`
- **Cause** : question â†’ mode `research` + prompt Â« si pas de LIVE_DATA â†’ thÃ©orie Â» + OpenRouter sans prefetch dÃ©cision â†’ RAG + hallucination `!status`
- **Fix** : planner `attendre/WAIT` â†’ `explain_decision` ; research+symbole prefetch DECISION+LIVE ; prompt research nâ€™impose plus la thÃ©orie si donnÃ©es prÃ©sentes
- Tests planner OK ; `npm test` server PASS

---

## 2026-09-25 â€” Fix thÃ¨me farci #2 â€” fuite CSS virgule (light = light)

- Bug : dans `maquette-theme.css`, sÃ©lecteurs aprÃ¨s `,` perdaient le prÃ©fixe `html.dark` â†’ `.segmented` restait sombre en mode clair (bandeau Tous/PASSE/â€¦)
- Fix : rÃ©Ã©criture sans fuite ; light â†’ shell/card/segmented/th tous clairs ; dark â†’ tous sombres
- Smoke local PASS ; VPS Ã  dÃ©ployer

---

## 2026-09-25 â€” Fix thÃ¨me farci dark/light (draft â†’ merge autonome)

- Branche `cursor/theme-fix-a2fe` depuis `main` @ `225549d`
- **Cause** : shell (`camap-tokens` html.dark) sombre + pages maquette figent `--bg/--card/--ink` en clair â†’ cartes crÃ¨me sur fond noir
- **Fix** : `theme/maquette-theme.css` resync vars + surfaces sous `html.dark` pour les 11 `*-page` ; dÃ©faut thÃ¨me = **light** (ignore prefers-color-scheme iOS) ; `theme-color` meta dynamique
- Smoke `scripts/smoke-theme-switch.mjs` : dark + light â†’ shell/card mÃªme famille (**PASS**)
- compare-maquette : 10 pages 0 ; desk Ã©carts `.up`/notice data-dÃ©pendants (hors thÃ¨me, script non modifiÃ©)
- **VPS** : dÃ©ployer aprÃ¨s merge â€” corrige le tÃ©lÃ©phone Samir (OpÃ©rations)

### Suite
Chantiers fiches (#110) + Eve (#111) continuent en parallÃ¨le.

---

## 2026-09-25 â€” UI-port (#109) â€” correctifs bugs avant merge

- Branche `cursor/ui-port-pages-a2fe` (mÃªme PR #109 draft)
- **Portefeuille** : plus de `positions.slice(0, 3)` (reste maquette dÃ©mo). Affiche **toutes** les positions ouvertes ; badge `1 POSITION` / `N POSITIONS` / `â€”`
- **OpportunitÃ©s** : bouton primaire **Enregistrer la dÃ©cision** â†’ `confirmUserDecision` + notice OK/erreur visible, indÃ©pendant de lâ€™ouverture paper. Paper reste en `suggestion` (Â« Ouvrir une position paper â†’ Â»)
- Branche distante doublon `cursor/ui-port-desk-4731` : absente sur origin (dÃ©jÃ  supprimÃ©e) ; branche locale purgÃ©e
- `compare-maquette.mjs` : **11Ã—0** 1440 + 390 â€” script non modifiÃ©
- **Pas de merge** â€” attendre OK Samir tÃ©lÃ©phone + relecture Claude

### Suite plan (aprÃ¨s merge #109)

1. Chantier 1 phase A â€” fiches (`cursor/ui-fiches-a2fe`) : INVENTAIRE.md â†’ FicheDecision â†’ points dâ€™entrÃ©e
2. Chantier 2 E0 â€” Eve runtime (`cursor/eve-runtime-a2fe`) : AgentTask + claim + worker minute (server/engine/prisma only)

---

## 2026-09-25 â€” UI-port 10 pages (#109) â€” draft, 11Ã—0 Ã©cart

- Branche `cursor/ui-port-pages-a2fe` depuis #108 + patches Claude 2/3 + `puppeteer-core@23`
- **11 pages = 0 Ã©cart** 1440 + 390 (`docs/ui-port/compare/RAPPORT.md`) â€” critÃ¨re unique `compare-maquette.mjs` (script non modifiÃ©)
- Ordre commits : desk â†’ opportunites â†’ portefeuille â†’ journal â†’ operations â†’ lab â†’ contexte â†’ copilot â†’ agents â†’ parametres
- Par page : DOM/CSS littÃ©ral maquette ; engine ou Â« â€” Â» ; `docs/ui-port/<page>-RETIRES.md` ; ancienne UI retirÃ©e
- Captures pleine page : `docs/ui-port/captures/<page>-{1440,390}.png` (tabbar/Plus masquÃ©s)
- Smoke 11 pages PASS : `docs/ui-port/smoke-11-pages.json` (bruit `llm-test` 422 ignorÃ© ; action copilot FAIL attendu sans clÃ© LLM)
- `find-unused-css` : classes mortes index.css nettoyÃ©es ; restent surtout `is-*` dâ€™Ã©tat (comme baseline MarchÃ©)
- **Draft PR #109 â€” pas de merge** avant relecture Claude + OK Samir tÃ©lÃ©phone
- **VPS prÃ©prod** : https://ichivol.global-it-ss.com â€” `RELEASE=025f1ac cursor/ui-port-pages-a2fe` Â· `web` rebuild Â· public 200
- Backup : `/opt/ichivol-backup/pre-uiport-pages-20260925-134158.tgz` (+ `env-pre-uiport-pages-*` si prÃ©sent)

### Suite

1. Relire Claude (RAPPORT + captures + RETIRES)
2. Samir teste tÃ©lÃ©phone sur VPS
3. Merge seulement aprÃ¨s double OK

---

## 2026-09-25 â€” Outil de contrÃ´le maquette â†” app (Claude)

- `ichivol-app/scripts/compare-maquette.mjs` : pour les 11 pages, en 1440 et 390, relÃ¨ve chaque classe CSS du contenu de la maquette et vÃ©rifie dans l'app prÃ©sence, taille/graisse/famille de police, hauteur (Â±4 px). Rapport `docs/ui-port/compare/RAPPORT.md` + dÃ©tail JSON par page. Code de sortie 1 s'il reste un Ã©cart.
- Classes d'Ã©tat/donnÃ©es (up, down, active, greenâ€¦) et graphiques SVG de dÃ©mo : non exigÃ©es, comparÃ©es si prÃ©sentes.
- ValidÃ© par Claude : MarchÃ© (#108 + patchs) = **0 Ã©cart** en 1440 et 390 ; Desk non portÃ© = 50 Ã©carts.
- DÃ©pendance : `npm i -D puppeteer-core@23` dans `ichivol-app/` (pas dans ce commit, pour ne pas figer le lockfile ici).
- RÃ¨gle : aucune page n'est Â« conforme Â» tant que ce script ne renvoie pas 0 Ã©cart pour elle.

---

## 2026-09-25 â€” UI-port MarchÃ© (#108) â€” correctif Claude nÂ°2 (portes + bouton)

- Base : `pr/108` @ `8203b04`
- **5 portes** : balisage identique Ã  la maquette (`stat()` â†’ `<span>` + `<b><span class="tag">`), suppression du `height: 44px` forcÃ©. Hauteur mesurÃ©e = **41 px** (maquette 41 px ; l'ancien correctif donnait 44 px)
- **Bouton Â« PrÃ©parer le trade â†’ Â»** : `inline-block`, largeur contenu Ã  toutes les tailles (maquette 153 px en 1440, 1100 et 390) ; l'ancien correctif le laissait pleine largeur entre 801 et 1150 px (836 px)
- Mesures faites sur la maquette ET l'app en Chromium headless, 1440 / 1100 / 390
- Build OK Â· oxlint 79

---

## 2026-09-25 â€” UI-port MarchÃ© (#108) â€” retouches CSS + smoke + VPS prÃ©prod

- Branche `cursor/ui-port-marche-a2fe` â€” **draft**, **pas de merge** avant OK Samir tÃ©lÃ©phone
- CSS only (`MarketPage.css`) :
  - mobile â‰¤800 : `button.primary` `width: auto` (maquette â‰ˆ 154 px Ã  390)
  - `.statline` : padding 13px 0, font 12px, hauteur verrouillÃ©e 44 px (5 portes = 220 px comme maquette)
- Smoke 11 pages : `docs/ui-port/smoke-11-pages.json` (bruit `llm-test` 422 ignorÃ©)
- **VPS prÃ©prod** : https://ichivol.global-it-ss.com â€” `RELEASE=37311b9 cursor/ui-port-marche-a2fe` Â· `web` rebuild Â· health 200 Â· backup `/opt/ichivol-backup/pre-marche-css-*`
  - **main non mergÃ©e** ; rollback = `git checkout main @ 604a8b0` + rebuild web

### Suite
OK Samir tÃ©lÃ©phone â†’ merge #108 â†’ Desk (mÃªme mÃ©thode).

---

## 2026-09-25 â€” UI-port MarchÃ© (#108) â€” corrections appliquÃ©es par Claude

- Base : `pr/108` @ `e7aaa9d` (rebasÃ©e sur main `604a8b0`)
- **Supports / rÃ©sistances** : la page charge les objets STRUCTURE du moteur (`getChartObjects(..., ['engine'])`) et n'affiche que la rÃ©sistance et le support les plus proches du dernier cours (`nearestSrObjects`), en pointillÃ©s, libellÃ©s Â« RÃ‰SISTANCE Â· â€¦ Â» / Â« SUPPORT Â· â€¦ Â»
- **Watchlist desktop** : mÃªme hauteur que la carte graphique, dÃ©filement interne (â‰¥ 801 px)
- **Typographie** : tailles alignÃ©es sur les valeurs CALCULÃ‰ES de la maquette (Chromium headless, 1440 et 390) â€” chart-summary 12 px, segmented 12, card-head small 12, checkrow 14, synthÃ¨se et step p 14, tag 10, eyebrow 11, bouton primaire 14, sous-titre 12 (y compris mobile)
- **Axe des prix** : fr-FR (`90 000`, `2 718,5`, `0,5862`)
- **Code mort** : supprimÃ©s `countObjectsByLayer`, `isIchimokuOn`, `change24hFromCandles`, `OBJECT_LAYER_META` (â†’ `OBJECT_LAYER_KEYS`), exports `ICHIMOKU_LAYER_KEYS`/`LAYERS_PREFS_VERSION` rendus privÃ©s ; supprimÃ©s `scripts/find-unused-css.mjs` (doublon racine) et `ichivol-app/scripts/recapture-390.mjs`
- **Capture 390** : la feuille Plus n'est PAS un bug (fermÃ©e par dÃ©faut) ; c'Ã©tait la capture pleine page qui figeait les Ã©lÃ©ments fixes au milieu â†’ `capture-ui-port-marche.mjs` masque tabbar + feuille Plus pendant la capture
- Build OK Â· oxlint 79 (main 83), 0 avertissement ajoutÃ© (`docs/ui-port/oxlint-compare.txt`)

### Reste Ã  faire (Cursor)
Relancer `capture-ui-port-marche.mjs` sur donnÃ©es rÃ©elles (1440 + 390 pleine page + superpositions), smoke 11 pages, puis validation Samir sur tÃ©lÃ©phone. Pas de merge avant.

---

## 2026-09-25 â€” UI-port MarchÃ© #108 (draft Â· corrections Claude)

- Branche : `cursor/ui-port-marche-a2fe` â€” **draft**, **ne pas merger** avant Samir + Claude
- Base : `main` @ `604a8b0` (#106 mergÃ©e) â€” rebase ; orphelins terminal #106 **supprimÃ©s** (`marche-RETIRES.md`)
- Corrections : prefs layout mortes Â· h1 Newsreader 38/32 Â· 24h watchlist (Binance ticker) Â· S/R cochÃ© Â· synthÃ¨se FR Â· mobile TF sous titre + checkrow empilÃ© Â· captures full-page
- Preuves : `docs/ui-port/marche/` Â· `docs/ui-p5/PARITE-MOBILE.md`
- **Pas** de runtime agents Â· engine/server intouchÃ©s

### Suite
Validation Samir + relecture Claude. Puis Desk.

---

## 2026-09-25 â€” UI-clean #106 MERGÃ‰E + VPS â€” tip `604a8b0`

- PR : https://github.com/samiriggui-code/IchiVol/pull/106 â€” **MERGÃ‰E** (squash) aprÃ¨s validation Claude
- Tip `ece8cb4` (fix useMarketController) â†’ merge commit `604a8b0`
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=604a8b0` Â· health 200 Â· backup `/opt/ichivol-backup/pre-uiclean-*`
- Smoke CI : pytest + frontend build â€” PASS

### Suite
#108 MarchÃ© (port littÃ©ral) â€” draft.

---
## 2026-09-25 â€” UI-P4 MERGÃ‰E (#103) + VPS

- PR : https://github.com/samiriggui-code/IchiVol/pull/103 â€” squash merge aprÃ¨s smoke PASS
- Branche : `cursor/ui-p4-remaining-a2fe`
- Pages : MarchÃ© Â· Strategy Lab Â· Contexte Â· Copilot Â· Agents Â· ParamÃ¨tres Â· pill PAPER
- Smoke desktop+mobile 390 + 11 pages + Plus â€” **PASS** Â· captures [`docs/ui-p4/`](./ui-p4/)
- Base : `main` @ `fbfe3f2` (fix opps #105) puis tip post-merge

### Suite
Nettoyage front (`ui-clean`) en **PR draft** â€” ne pas merger avant Claude. **Pas** de runtime agents.

---

## 2026-09-25 â€” Fix fiche OpportunitÃ©s mobile MERGÃ‰E (#105) + VPS â€” tip `fbfe3f2`

- PR : https://github.com/samiriggui-code/IchiVol/pull/105 â€” **MERGÃ‰E** (squash)
- Cause : `.is-sheet-open` masquait market-head / table mais **pas** `.opp-ribbon` / Pourquoi / pulse / filtres P2 â†’ Fermer hors Ã©cran
- Fix : wrapper `.decisions-chrome` masquÃ© en mobile ; fiche `position:fixed` + en-tÃªte sticky **â† Retour** ; `?symbol=` push/back ; re-tap onglet OpportunitÃ©s nettoie la query
- Smoke 390 : 3 symboles Â· scroll Â· 3 chemins de fermeture â€” **PASS** Â· [`docs/fix-opps-sheet/`](./fix-opps-sheet/)
- **VPS** : `RELEASE=fbfe3f2` Â· health 200 Â· bundle `â† Retour` Â· `decisions-chrome`

### Suite
UI-P4 smoke + merge.

---

## 2026-09-25 â€” Audit Agent Runtime VALIDÃ‰ (Claude) â€” merge docs

- PR : https://github.com/samiriggui-code/IchiVol/pull/102 â€” squash merge (docs only)
- Amendements Claude dans `docs/AGENT-RUNTIME-AUDIT.md` Â§ Â« DÃ©cisions validÃ©es Â» :
  Option D hybride Â· idempotence Â· fraÃ®cheur data_quality Â· next_closed_candle+60s Â· paper confirm humaine par dÃ©faut Â· mono-agent
- **Ordre gelÃ©** : P4 draft â†’ puis runtime P0â†’P2 en draft/phase. **Pas** de runtime agents maintenant.

### Suite
Terminer UI-P4 (#103) draft pour relecture Claude ; runtime agents ensuite.

---

## 2026-09-25 â€” UI-P3 MERGÃ‰E (#101) + VPS â€” tip `dfe14da`

- PR : https://github.com/samiriggui-code/IchiVol/pull/101 â€” **MERGÃ‰E** (squash) Â· tip `main` = `dfe14da`
- Branche : `cursor/ui-p3-journal-ops-a2fe`
- **Exception server minimale** : `PATCH /api/decisions/:id` accepte `note` (trim, max 500, videâ†’null) Â· ownership user â†’ 404 sinon Â· update in-place (archivÃ©e sans doublon)
- Client : `patchUserDecisionNote` Â· Journal nâ€™utilise plus `confirmUserDecision` pour la note
- OpÃ©rations : liens accent Â· pas de self-link Â« OpÃ©rations â†’ Â» Â· Â« Aucun run Â» si jamais de backtest
- Tests : `patchNote.test.ts` 8/8 Â· lint/build Â· smoke desktop+mobile 390 â€” **PASS** Â· captures [`docs/ui-p3/`](./ui-p3/)
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=dfe14da` ; health 200 ; bundle `Aucun run` Â· `Depuis le plus haut` Â· `Journal dâ€™audit` Â· `QualitÃ© des donnÃ©es`
- Backup : `/opt/ichivol-backup/pre-uip3-20260925-085136.tgz`

### Suite
UI-P4 + audit agents en **PR draft** â€” **ne pas merger** avant relecture Claude.

---

## 2026-09-25 â€” UI-P2 corrections + merge

- PR : https://github.com/samiriggui-code/IchiVol/pull/100 â€” squash merge aprÃ¨s corrections Â· tip main `1b620d3`
- Branche : `cursor/ui-p2-portfolio-opps-a2fe`
- Corrections : Drawdown Â« Depuis le plus haut Â» Â· montants page via `fmtEur` fr-FR (â‚¬)
- Captures : [`docs/ui-p2/`](./ui-p2/) Â· smoke PASS

### Suite
UI-P3 rebase sur main â†’ corrections note PATCH + ops polish â†’ merge + VPS.

---

## 2026-09-25 â€” UI-P2 Portefeuille + OpportunitÃ©s â€” PR draft #100

- PR : https://github.com/samiriggui-code/IchiVol/pull/100 â€” **draft** (attendre Claude avant merge)
- Branche : `cursor/ui-p2-portfolio-opps-a2fe` Â· tip `4fb867f`
- **PÃ©rimÃ¨tre front only** â€” `engine/` Â· `server/` intouchÃ©s ; style Desk P1 (muted, fr-FR, liens).
- **Portefeuille** : 4 KPI (Capital / Exposition / Disponible / Drawdown front) Â· Risk Kernel (PASSE/BLOQUÃ‰ via risk-lock) + barres limites engine Â· anneaux Allocation / Concentration (composants partagÃ©s Desk) Â· onglets + Labs paper conservÃ©s.
- **OpportunitÃ©s** : toolbar recherche + filtres Portes rÃ©elles (BUY/SELL/WATCH/NO_TRADE) Â· ruban Â« De lâ€™observation Ã  la dÃ©cision Â» (agrÃ©gats screener) Â· carte Â« Pourquoi {symbole} ? Â» si candidat Â· matrice / pulse / onglets classe inchangÃ©s.
- Captures : [`docs/ui-p2/`](./ui-p2/)
- Tests : lint/build Â· `scripts/smoke-ui-p2.mjs` desktop+mobile 390 â€” **PASS**

### Suite
**Attendre relecture Claude avant merge.** Puis dÃ©ploiement VPS.

---

## 2026-09-25 â€” UI-P1b MERGÃ‰E (#98) + VPS â€” tip `2538c74`

- PR : https://github.com/samiriggui-code/IchiVol/pull/98 â€” **MERGÃ‰E** (squash)
- **VÃ©rifiÃ©** : `origin/main` tip = `2538c74`
- Desk finition : sessions contraste + fr-FR 24h Â· NumberFormat Â· muted maquette Â· Capitalisation crypto 24h Â· liens accent
- **P&L jour prod** (prÃ©-merge) : `day_change â‰ˆ âˆ’10,28 â‚¬` / equity â‰ˆ 5â€¯007 â‚¬ â€” cohÃ©rent ; engine intact
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=2538c74` ; health 200 ; bundle `Capitalisation crypto 24h` Â· `session-status`
- Backup : `/opt/ichivol-backup/pre-uip1b-20260925-080011.tgz`

### Suite
UI-P2 â€” Portefeuille + OpportunitÃ©s conformes maquette.

---

## 2026-09-25 â€” UI-P1b Desk finition â€” PR draft #98

- PR : https://github.com/samiriggui-code/IchiVol/pull/98 â€” **draft** (attendre Claude avant merge)
- Branche : `cursor/ui-p1b-desk-finish-a2fe` Â· tip `177bd12`
- **PÃ©rimÃ¨tre front only** â€” contraste sessions, formats fr-FR, liens accent, lecture marchÃ©.
- Sessions : statut colorÃ© comme marqueurs (vert / ambre / gris) ; sÃ©lecteur non Â« disabled Â» ; heures `fr-FR` 24 h.
- Nombres Desk via `Intl.NumberFormat('fr-FR')` ; muted maquette `#7d8288` (clair) / `#a8b0bc` (sombre).
- Lecture : Â« Capitalisation crypto 24h Â» (plus de libellÃ© VolatilitÃ© sans mesure rÃ©elle).
- **P&L du jour (prod VPS, compte rÃ©el)** : `day_change = -10,28 â‚¬` pour equity â‰ˆ 5â€¯007 â‚¬ ; ref 24 h â‰ˆ 5â€¯017 â‚¬ â†’ **cohÃ©rent** (Ã©cart equity ~24 h). Engine non modifiÃ©.
- Captures : [`docs/ui-p1/01-desk-desktop.png`](./ui-p1/01-desk-desktop.png) Â· [`docs/ui-p1/02-desk-mobile-390.png`](./ui-p1/02-desk-mobile-390.png)
- Tests : lint/build Â· smoke Desk desktop+mobile 390 + checks p1b â€” **PASS**

### Suite
**Attendre relecture Claude avant merge.** Puis dÃ©ploiement VPS.

---

## 2026-09-25 â€” VPS dÃ©ployÃ© UI-P1 â€” tip `718b2ba`

- **FQDN** : https://ichivol.global-it-ss.com â€” rebuild `web`/`server`/`engine` depuis `main` @ `718b2ba`
- Backup : `/opt/ichivol-backup/pre-uip1-20260925-074227.tgz` ; `RELEASE` = `718b2ba main`
- VÃ©rifiÃ© : `/api/health` ok ; bundle Desk contient `Asia/Tokyo` Â· `Europe/London` Â· `America/New_York` Â· `Sessions de marchÃ©`

### Suite
Portage pages suivantes selon [`UI-MAQUETTE-GAP.md`](./UI-MAQUETTE-GAP.md).

---

## 2026-09-25 â€” UI-P1 Desk maquette MERGÃ‰E (#96) â€” tip `718b2ba`

- PR : https://github.com/samiriggui-code/IchiVol/pull/96 â€” **MERGÃ‰E** (squash)
- **VÃ©rifiÃ©** : `origin/main` tip = `718b2ba`
- Desk conforme maquette (option A) : KPI paper Â· sessions **IANA** Tokyo/Londres/NY (horaires locaux, week-end par place, DST auto) Â· marchÃ©s + variation Binance Â· CoinGecko/F&G Â· equity Â· Ã  surveiller Â· fraÃ®cheur Â· positions Â· budget risque Â· tape Â· contrÃ´le 1H Â· `/api/engine/health` Â· anneaux.
- Relocalisation : pulse â†’ OpportunitÃ©s ; pipeline/circuit/preuves â†’ OpÃ©rations ; labs â†’ Portefeuille.
- Captures : [`docs/ui-p1/01-desk-desktop.png`](./ui-p1/01-desk-desktop.png) Â· [`docs/ui-p1/02-desk-mobile-390.png`](./ui-p1/02-desk-mobile-390.png)
- Tests : lint/build Â· `check-market-sessions.mjs` (DST) Â· smoke Desk desktop+mobile â€” PASS

### Suite
DÃ©ploiement VPS `main` @ `718b2ba` â†’ portage pages suivantes selon `UI-MAQUETTE-GAP.md`.

---

## 2026-09-25 â€” VPS dÃ©ployÃ© UI-11p â€” tip `35ddce0`

- **FQDN** : https://ichivol.global-it-ss.com â€” stack rebuild (`web`/`server`/`engine`) depuis `main` @ `35ddce0`
- Backup hÃ´te : `/opt/ichivol-backup/pre-ui11p-*.tgz` ; `RELEASE` = `35ddce0 main`
- Bundle prod : routes `/app/desk`, `/app/opportunites`, â€¦ + `dash-mobile-tabbar` (Desk Â· OpportunitÃ©s Â· Portefeuille Â· Copilot Â· Plus)
- **Compte smoke** `ui11p-smoke@â€¦` : **absent** en prod (`users` â†’ 0 row) ; seul admin `samiriggui@gmail.com`
- **Copilot LLM prod** : PASS â€” `POST /api/agent/chat` mode `research` â†’ `provider=openrouter` / `anthropic/claude-sonnet-4.5` (clÃ© prÃ©sente, rÃ©ponse OK). Compte de test Ã©phÃ©mÃ¨re crÃ©Ã© puis **supprimÃ©**.
- AccÃ¨s agent : clÃ© SSH `cursor-cloud-ichivol-deploy` installÃ©e sur le VPS (auth password root utilisÃ©e une fois pour bootstrap â€” **Ã  rotator** cÃ´tÃ© ops).

### Suite
Portage UI selon [`UI-MAQUETTE-GAP.md`](./UI-MAQUETTE-GAP.md) Â· onglet Journal Market + indicateurs moteur.

---

## 2026-09-25 â€” UI maquette gap MERGÃ‰E (#93) â€” tip `8e2ab82`

- PR : https://github.com/samiriggui-code/IchiVol/pull/93 â€” **MERGÃ‰E** (squash)
- **VÃ©rifiÃ©** : `origin/main` tip = `8e2ab82`
- Audit : [`docs/UI-MAQUETTE-GAP.md`](./UI-MAQUETTE-GAP.md)
- Secrets UI-11p : #91 `b73a20b` ; handoff secrets #92 `5ab809e`
- Deploy VPS : **toujours bloquÃ©** (Hostinger MCP timeout) â€” demandÃ© `HOSTINGER_API_TOKEN` + clÃ© SSH agent sur VPS

### Suite
DÃ©ployer `main` sur VPS â†’ mobile barre + Copilot LLM â†’ portage selon gap doc / Journal Market.

---

## 2026-09-25 â€” UI maquette gap audit + clÃ´ture UI-11p secrets (archive)

- Branche : `cursor/ui-maquette-gap-a2fe`
- **Audit (aucun code produit)** : [`docs/UI-MAQUETTE-GAP.md`](./UI-MAQUETTE-GAP.md) â€” 11 pages maquette (`design-reference/ichivol-workspace`) â†” React, statut section + endpoint rÃ©el ou Â« Ã  dÃ©cider Â», React hors maquette.
- **ClÃ´ture secrets UI-11p** (#91 squash `b73a20b`, handoff #92 â†’ tip `5ab809e`) :
  - smoke : `SMOKE_EMAIL` / `SMOKE_PASS` obligatoires
  - compte local `ui11p-smoke@ichivol.local` : MDP rotatÃ© ; ancien secret â†’ 401 local + prod
  - prod User smoke : **non confirmÃ© SQL** (Hostinger VPS MCP timeout / pas de SSH) â€” login API ne distingue pas absence/mauvais MDP ; TLD `.local` ; Ã  vÃ©rifier au prochain accÃ¨s VPS : `SELECT email FROM "User" WHERE email LIKE '%smoke%';`
- **DÃ©ploiement VPS** : **bloquÃ©** â€” MCP Hostinger VPS/DNS timeout rÃ©pÃ©tÃ©s ; pas de clÃ© SSH sur le VPS. ClÃ© agent gÃ©nÃ©rÃ©e (Ã  attacher) : `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMfFMCvkVPm0+l6YcT/PZXwZVqSQCBw0QYfABQ/jdUKJ cursor-cloud-ichivol-deploy`. Prod bundle encore nav legacy (Cockpit/DÃ©cisionsâ€¦).

### Suite
1. Attacher la clÃ© SSH / rÃ©parer Hostinger MCP â†’ `git pull` + `docker compose â€¦ up -d --build` sur `/opt/ichivol` â†’ vÃ©rif mobile barre + Copilot LLM prod  
2. Portage UI selon `UI-MAQUETTE-GAP.md` (prioritÃ©s synthÃ¨se)  
3. Onglet Journal Market + indicateurs moteur (hors scope de cet audit)

---

## 2026-09-25 â€” UI-11p smoke secrets MERGÃ‰E (#91) â€” tip `b73a20b`

- PR : https://github.com/samiriggui-code/IchiVol/pull/91 â€” **MERGÃ‰E** (squash)
- **VÃ©rifiÃ©** : `origin/main` tip = `b73a20b` (handoff #92 â†’ `5ab809e`)
- Scripts smoke : `SMOKE_EMAIL` / `SMOKE_PASS` obligatoires (exit 2 si absents)
- Compte local `ui11p-smoke@ichivol.local` : MDP rotatÃ© ; ancien secret â†’ 401 en local et sur prod
- Prod encore nav legacy au moment du merge â€” dÃ©ploiement VPS de `main` Ã  faire pour barre UI-11p

### Suite
DÃ©ployer `main` sur VPS â†’ vÃ©rif mobile barre + Copilot LLM prod â†’ onglet Journal Market + indicateurs moteur.

---

## 2026-09-25 â€” UI-11p MERGÃ‰E (#89) â€” merge `5d1edfd`

- PR : https://github.com/samiriggui-code/IchiVol/pull/89 â€” **MERGÃ‰E**
- **VÃ©rifiÃ©** : `origin/main` tip = `5d1edfd` (puis handoff #90 â†’ `929ecae`)
- Front React 11 pages + design-reference ; smoke desktop + mobile 390px ; cleanup WatchlistPage + keenicons dÃ©mos
- Copilot chat bloquÃ© en smoke uniquement faute de clÃ© LLM locale (UI OK)

### Suite
Onglet **Journal** de Market + indicateurs moteur sur le graphe Market.

---

## 2026-09-25 â€” UI-11p â€” smoke rÃ©el + nettoyage (PR â†’ merge si vert)

- Branche : `cursor/ui-workspace-pages-a2fe`
- Tip de dÃ©part : `d2b5d68` (import React 11-pages + design-reference)
- Base : `main` (post-#86)
- **PÃ©rimÃ¨tre** : front only (`ichivol-app/src`, `public/`, `design-reference/`, handoff). **Pas** de touche `engine/` ni `server/`.

### Nettoyage
- SupprimÃ© `WatchlistPage` (plus importÃ© ; redirects `/app/watchlist` conservÃ©s).
- **ConservÃ©** `SynthesePage` + `PaperPage` : toujours montÃ©s comme onglets de `PortfolioPage`.
- SupprimÃ© dÃ©mos keenicons (`demo.html`, `demo-files/`, `selection.json`, Read Me) dans `ichivol-app/public/keenicons/{duotone,outline}/` et le miroir `design-reference/...`.

### Smoke local (engine :8000 + server :8787 + vite :5173)
Compte test local : `ui11p-smoke@ichivol.local` (mot de passe **uniquement** via `SMOKE_EMAIL` / `SMOKE_PASS` â€” pas de dÃ©faut dans les scripts). Captures `/opt/cursor/artifacts/ui11p-smoke/`.

#### Pages `/app/*` (donnÃ©es rÃ©elles, pas dâ€™erreur console hors bruit LLM)
| Route | Verdict | DonnÃ©es vues |
|---|---|---|
| desk | **PASS** | 28 marchÃ©s, pulse 28 NO TRADE, equity ~9â€¯185 â‚¬, pipeline health |
| market | **PASS** | Chart BTC 84â€¯228 + Ichimoku/BOS/CHoCH, watchlist live, moteur Â« PAS DE TRADE Â» |
| opportunites | **PASS** | Liste dÃ©cisions / empty actionnable OK (short off) |
| portefeuille | **PASS** | SynthÃ¨se equity/cash/rÃ©alisÃ©, onglets Compte/Positions/Risque/Tests |
| context | **PASS** | Feeds contexte chargÃ©s |
| journal | **PASS** | Page journal OK |
| operations | **PASS** | ActivitÃ© / opÃ©rations OK |
| strategy-lab | **PASS** | Tabs Compare/Regimes/Experiments/Live/Research ; BTCUSDT 1h |
| agent | **PASS** | UI Copilot + session ; badge Â« LLM : clÃ© manquante Â» |
| agents | **PASS** | Page agents OK |
| settings | **PASS** | Formulaire paramÃ¨tres OK |

Bruit unique observÃ© : `POST /api/settings/llm-test` â†’ **422** (pas de clÃ© LLM dans `.env`) â€” attendu, non bloquant pour les pages.

#### Mobile â‰¤768 px (viewport **390Ã—844**)
Script : `ichivol-app/scripts/smoke-ui11p-mobile.mjs` Â· captures `/opt/cursor/artifacts/ui11p-mobile/`.

| Check | Verdict | DÃ©tail |
|---|---|---|
| Barre du bas | **PASS** | Desk Â· OpportunitÃ©s Â· Portefeuille Â· Copilot Â· Plus (`display:grid`, largeur 390) |
| Plus ouvrir | **PASS** | sheet + backdrop ; liens MarchÃ©, Strategy Lab, Journal, Contexte, Agents, OpÃ©rations, ParamÃ¨tres |
| Plus fermer | **PASS** | clic backdrop â†’ sheet fermÃ© (`hidden` / sans `is-open`) |
| Overflow horizontal | **PASS** | 11/11 routes : `scrollWidth=390`, 0 offender hors viewport |

#### Actions
| Action | Verdict | DÃ©tail |
|---|---|---|
| Paper open â†’ close | **PASS** | `POST .../paper/positions?discretionary=true&notional=400` â†’ 200 ; close â†’ 200 |
| Kill-switch arm/disarm | **PASS** | arm `kill_switch_armed=true` ; disarm `false` (UI bouton ArrÃªt dâ€™urgence + API) |
| Walk-forward | **PASS** | `GET .../strategy-lab/walk-forward?limit=1200` â†’ 200 (folds + oos_summary) |
| Monte-Carlo | **PASS** | `POST .../strategy-lab/monte-carlo` ruleset `IV_ICHIMOKU_RVOL_LONG_001` â†’ 200 (`sufficient=false`, n_trades=4 â€” endpoint OK) |
| Settings save | **PASS** | PATCH theme `light`â†’`dark` â†’ 200 |
| Copilot chat | **BLOQUÃ‰ env** | `POST /api/agent/chat` â†’ 400 Â« Aucune clÃ© LLM rÃ©solue Â» (`OPENROUTER_API_KEY` vide). UI OK ; pas de clÃ© Ã  inventer. |

### Suite aprÃ¨s merge
Onglet **Journal** de Market + indicateurs moteur sur le graphe Market.

---

## 2026-09-24 â€” UI workspace refonte MERGÃ‰E (#86) â€” squash `92f43f7`

- PR : https://github.com/samiriggui-code/IchiVol/pull/86 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `92f43f7`
- Front only : Desk (metrics / pulse / pipeline / top opps), chrome pages, landing brand-first, auth tokens IchiVol
- **Corrections revue Claude (incluses dans le squash)** :
  1. Top opportunitÃ©s = BUY/SELL only ; vide â†’ Â« Aucune opportunitÃ© actionnable Â»
  2. Pipeline `direction` = vraie valeur `stagePass` (0 compris)
  3. Short off baseline : OpportunitÃ©s = BUY ; SELL N en sous-titre ; donut BUY/SELL/WATCH/NO TRADE ; pipeline Â« opportunitÃ©s (BUY) Â»
  4. Sans `overview.risk` â†’ libellÃ© Â« ExposÃ© Â» (jamais investi sous Â« Risque engagÃ© Â»)

### STOP solo rÃ©v.58
**Toujours actif.** Ne pas dÃ©marrer : T13d Â· T13e Â· T11c Â· Sessions / Agents.

---

## 2026-09-24 â€” UI workspace refonte (archive) â€” post-STOP + corrections

- Branche : `cursor/ui-workspace-refonte-a2fe`
- Base : `main` @ `ccc1433` (#85 handoff STOP)
- **PÃ©rimÃ¨tre** : front only â€” Desk enrichi (metrics / pulse / pipeline / top opps depuis screener + paper), chrome pages (eyebrow + question), landing brand-first, auth alignÃ©e tokens IchiVol. Pas dâ€™API inventÃ©e. Tokens camap conservÃ©s (bull/bear/amber alignÃ©s design-reference).

### Hors scope (respect STOP)
T13d Â· T13e Â· T11c Â· Sessions / Agents.

---

## 2026-09-24 â€” T10d/e MERGÃ‰E (#84) â€” squash `9b2991a`

- PR : https://github.com/samiriggui-code/IchiVol/pull/84 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `9b2991a`
- `docs/research/` : PROMOTION-CRITERIA (T10e) + fiches rsi / cmf / obv (T10d)

### STOP solo rÃ©v.58
Liste Â§5 (points 1â€“11) **terminÃ©e**.  
**Ne pas dÃ©marrer** : T13d Â· T13e Â· T11c Â· pages Sessions / Agents Â· ni autre tranche hors brief Claude.

---

## 2026-09-24 â€” T11b MERGÃ‰E (#83) â€” squash `f877e0b`

- PR : https://github.com/samiriggui-code/IchiVol/pull/83 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `f877e0b`
- Cache `observe_lab_context` + mesure TD vs biquote (dry-run report)

**Suite** : T10d/e puis **STOP**.

---

## 2026-09-24 â€” T11a-bis MERGÃ‰E (#82) â€” squash `a033960`

- PR : https://github.com/samiriggui-code/IchiVol/pull/82 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `a033960`

---

## 2026-09-24 â€” T13c MERGÃ‰E (#81) â€” squash `71c162c`

- PR : https://github.com/samiriggui-code/IchiVol/pull/81 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `71c162c`
- Kill switch + daily loss lock (persistÃ©, humain only)
- CI fix : `tests/conftest.py` clear locks between tests (cash=0.5 latchait le baseline)

**Suite** : T11a-bis â†’ T11b (partiel) â†’ T10d/e.

---

## 2026-09-24 â€” T13c (archive) â€” kill switch + verrou perte journaliÃ¨re

- Branche : `cursor/t13c-kill-switch-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/81
- Base : `main` @ `7d7d767` (#80 T13b **MERGÃ‰E**)

### DÃ‰CISION CURSOR
Latch perte jour **ne se lÃ¨ve pas Ã  minuit** â€” humain only.

---

## 2026-09-24 â€” T13b MERGÃ‰E (#80) â€” squash `7d7d767`

- PR : https://github.com/samiriggui-code/IchiVol/pull/80 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `7d7d767`

**Suite** : T13c.

---

## 2026-09-24 â€” T13b (archive) â€” Risk Kernel + onglet Risque

- Branche : `cursor/t13b-risk-kernel-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/80
- Base : `main` @ `30b5968` (#79 T13a **MERGÃ‰E**)
- Paper + UI â€” **dÃ©fauts = comportement actuel** (pas plus strict)

### LivrÃ©
1. `paper/risk_kernel.py` â€” `evaluate(plan, portfolio_state, market_state)` â†’ acceptÃ©/refusÃ© + codes
2. `gates.entry_gate` dÃ©lÃ¨gue Ã  `evaluate_entry_codes` ; `sync_position` + `_open_refusal_detail` passent par le kernel
3. Tests AST (chemins dâ€™ouverture) + paritÃ© (stale/short/risk cap/manual skip)
4. Overview `risk` : capital, exposÃ©, risque utilisÃ©, derniers refus
5. Portefeuille onglet **Risque**

### DÃ‰CISION CURSOR â€” Ã  relire par Claude
- QualitÃ© T11a = code informatif seulement (`quality_*`), jamais refuse
- Pas de nouveau `max_spread` hard gate
- `check_size` dans le kernel avant open (mÃªme issue finale quâ€™avant)

### Hors scope
T13c kill switch Â· cycle ordres T13d

### Auto-revue
- [x] pytest risk_kernel + engine + build
- [ ] pytest PG16 CI
- [x] decision/screener/brokerage : non touchÃ©s

---

## 2026-09-24 â€” T13a MERGÃ‰E (#79) â€” squash `30b5968`

- PR : https://github.com/samiriggui-code/IchiVol/pull/79 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `30b5968`
- TradePlan fields on OrderIntent (serialization only)

**Suite** : T13b.

---

## 2026-09-24 â€” T13a (archive) â€” TradePlan OrderIntent sÃ©rialisation

- Branche : `cursor/t13a-tradeplan-intent-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/79
- Base : `main` @ `bbcb5f4` (#78 T12e **MERGÃ‰E**)
- Paper DTO only â€” **aucun changement des chemins dâ€™ouverture**

### LivrÃ©
1. `OrderIntent` + champs T13a : trigger Â· invalidation Â· stop Â· targets Â· expiration Â· session Â· codes Â· versions
2. `from_dict` rÃ©tro-compatible (clÃ©s absentes â†’ None)
3. Remplissage depuis screener row (pipeline codes, decision.invalidation, ATR stop, timing)
4. Front `paper.ts` types optionnels Â· tests round-trip / stale / legacy

### Hors scope
T13b Risk Kernel Â· confirm path consommant lâ€™intent Â· persistence DB Â· calendrier session rÃ©el

### Auto-revue
- [x] pytest paper intent + timing (DATABASE_URL engine)
- [x] `npm run build`
- [ ] pytest PG16 CI
- [x] decision/screener/brokerage : non touchÃ©s ; paper = intent.py seul

---

## 2026-09-24 â€” T12e MERGÃ‰E (#78) â€” squash `bbcb5f4`

- PR : https://github.com/samiriggui-code/IchiVol/pull/78 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `bbcb5f4`
- ADN Aâ†’F + ETUDE ; deep_history VPS encore Ã  remplir

**Suite** : T13a.

---

## 2026-09-24 â€” T12e (archive) â€” ADN matrice Aâ†’F (#78)

- Branche : `cursor/t12e-adn-ichivol-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/78
- Base : `main` @ `4549a2f` (#77 T14a **MERGÃ‰E**)
- Lab only â€” **aucun changement live**
- Livrable doc : `docs/ETUDE-T12-ADN-ICHIVOL.md`

### LivrÃ©
1. `app/strategy_lab/adn_ichivol.py` â€” LiveScreenerSettings Â· ladder Aâ†’Bâ†’Dâ†’Eâ†’F Â· C parallÃ¨le Â· KEEP/RESEARCH/REJECT
2. Ladder `adn_ichivol` Â· fix coerce `location_stage_pass` / `regime_stage_pass`
3. Tests + `scripts/t12e_adn_study.py` Â· Ã©tude mÃ©thode (pas de KEEP sans deep_history)

### DÃ‰CISION CURSOR â€” Ã  relire par Claude
Settings = dÃ©fauts production nommÃ©s ; C parallÃ¨le ; forex/actions exclus (<2 ans).

### Auto-revue
- [x] pytest T12e + T9g OK
- [ ] pytest PG16 complet (CI)
- [x] decision/screener/paper/brokerage non touchÃ©s
- [ ] deep_history BTC/ETH sur VPS (Binance 451 ici)

---

## 2026-09-24 â€” T14a MERGÃ‰E (#77) â€” squash `4549a2f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/77 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `4549a2f`
- Nav 4 groupes Â· Desk/OpportunitÃ©s/OpÃ©rations/Portefeuille Â· pinned Â· Journal tabs Â· kill stub

**Suite** : T12e #78.

---

## 2026-09-24 â€” T12d MERGÃ‰E (#76) â€” squash `69a11f6`

- PR : https://github.com/samiriggui-code/IchiVol/pull/76 â€” **MERGÃ‰E** squash (solo rÃ©v.58)
- **VÃ©rifiÃ©** : squash `69a11f6` (ancÃªtre de `4549a2f`)
- Fausses cassures nuage Ã  N ; ventilation RVOL/ADX/structure/location/CVD

---

## 2026-09-24 â€” T12d (archive) â€” fausses cassures du nuage

- Branche : `cursor/t12d-false-breaks-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/76
- Base : `main` @ `abe6177` (#75 T12c **MERGÃ‰E**)
- ADD-ONLY Lab â€” **aucun changement live**

### LivrÃ©
1. `strategy_lab/kumo_false_breaks.py` â€” `study_kumo_false_breaks_on_candles`  
   - rising-edge `kumo_breakout_*`  
   - Ã©tiquette Ã  **N** barres explicite : continuation / failure / inside / incomplete  
   - ventilation : RVOL bande, ADX (trending/ranging), structure, location, CVD
2. Tests `test_t12d_kumo_false_breaks.py` (continuation, failure, incomplete, bearish miroir, sÃ©rie rÃ©elle)

### Hors scope
FeatureBar fields Â· HTTP Â· T12e Â· live

### Sonde manuelle
Cassure haussiÃ¨re + prix sous nuage Ã  i+N â†’ `failure` ; toujours au-dessus â†’ `continuation`.

### Auto-revue (Â§2) â€” FAIT
- [x] pytest PG16 : **1086 passed**
- [x] pytest rÃ©seau coupÃ© : **1085 passed, 1 skipped**
- [x] `npm run build` OK
- [x] golden : N/A (aucun golden touchÃ©)
- [x] `git diff` decision/agents/paper/screener/brokerage : **vide**

---

## 2026-09-24 â€” T12c MERGÃ‰E (#75) â€” squash `abe6177`

- PR : https://github.com/samiriggui-code/IchiVol/pull/75 â€” **MERGÃ‰E** squash (solo rÃ©v.58)
- **VÃ©rifiÃ©** : `origin/main` tip = `abe6177`
- RÃ©fÃ©rences Lab buy&hold / Donchian / BOS ; golden additif ; 1080/1079+1skip

**Suite** : T12d fausses cassuresâ€¦

---

## 2026-09-24 â€” T12c (archive EN COURS) â€” rÃ©fÃ©rences buy&hold / Donchian / structure

- Branche : `cursor/t12c-reference-baselines-a2fe`
- Base : `main` @ `36ff85f` (#74 UI exception **MERGÃ‰E**)
- ADD-ONLY Lab â€” **aucun changement live / seuils**

### LivrÃ©
1. `strategy_lab/reference_baselines.py` â€” `run_reference_baselines_on_candles`  
   - buy&hold (`run_backtest` toujours LONG)  
   - Donchian breakout UP seul (ruleset ATR 1R/2R)  
   - structure BOS haussier seul (ruleset ATR 1R/2R)  
   - **mÃªmes** `commission_bps` / `slippage_bps` (dÃ©faut Lab 5+3)
2. Catalog : `IV_REF_DONCHIAN_BO_LONG_001`, `IV_REF_STRUCTURE_BOS_LONG_001` (`meta.reference`/`t12c`)
3. Tests `test_t12c_reference_baselines.py` (frais partagÃ©s, bords 0/1 barre, fee override)

### DÃ‰CISION CURSOR â€” Ã  relire par Claude
Â« Structure seule Â» = rising-edge **`bos_bullish`** (ablation `C_BOS`), **pas** `IV_ICHIMOKU_ONLY_*`.

### Hors scope
HTTP route (appelants = module Python) Â· T12d/e Â· live

### Sonde manuelle
SÃ©rie synthÃ©tique drift : buy&hold exposure > 0.9, â‰¥1 trade.

---

## 2026-09-24 â€” UI exception MERGÃ‰E (#74) â€” squash `36ff85f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/74 â€” **MERGÃ‰E** squash (solo rÃ©v.58)
- **VÃ©rifiÃ©** : `origin/main` tip = `36ff85f`
- Matrice : libellÃ© **RÃ©gime** ; DIR **â†‘/â†“** ; captures `ui74-*-matrix.png`
- Auto-revue : pytest 1074 ON / 1073+1 skip OFF ; npm build OK ; moteur inchangÃ©

**Suite** : T12câ€¦

---

## 2026-09-24 â€” UI exception EN COURS â€” Risqueâ†’RÃ©gime + DIR â†‘/â†“ (rÃ©v.56/58)

- Branche : `cursor/ui-regime-dir-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/74 (**draft**)
- Base : `main` @ `a7b630f` (#73 T12b **MERGÃ‰E**)
- Tip : `99c778e`
- Front only â€” **aucun changement moteur**

### LivrÃ©
1. `stageMatrixLabel('regime')` : **Â« Risque Â» â†’ Â« RÃ©gime Â»**
2. Colonne DIR Matrice : `pass` + LONG â†’ **â†‘** ; `pass` + SHORT â†’ **â†“** (`stageDirectionMatrixLabel`) ; autres statuts inchangÃ©s

### Auto-revue (Â§2) â€” FAIT
- [x] pytest PG16 : **1074 passed** (rÃ©seau ON)
- [x] pytest rÃ©seau coupÃ© (HTTP_PROXY mort) : **1073 passed, 1 skipped** (Binance)
- [x] `npm run build` OK
- [x] golden : N/A (aucun golden touchÃ©)
- [x] `git diff` decision/agents/paper/screener/brokerage : **vide**
- [x] Captures Matrice desktop/mobile Ã— clair/sombre â†’ `/opt/cursor/artifacts/ui74-*-matrix.png`  
  Headers vÃ©rifiÃ©s : `â€¦ Loc Â· RÃ©gime Â· Portes` ; DIR sample = `â†“` (SHORT pass)

### Hors scope
T12c+ Â· T14a Â· moteur Â· libellÃ© carte rÃ©sumÃ© Â« RÃ©gime / Risque Â» (STAGE_META, hors brief)

### Sonde manuelle
Matrice live `/app/decisions` vue Matrice : en-tÃªte **RÃ©gime** ; cellules Dir **â†“** (marchÃ© short) â€” pas Â« OK Â».

---

## 2026-09-24 â€” SYNC Claude rÃ©v.58 â€” MODE SOLO jusquâ€™au retour Claude

Claude indisponible jusquâ€™Ã  demain. **Solo autorisÃ©** sur la liste Â§5 (rÃ©v.58) :
UI exception â†’ T12c â†’ T12d â†’ T12e â†’ T14a â†’ T13a â†’ T13b â†’ T13c â†’ T11a-bis â†’ T11b (partiel) â†’ T10d/e.

Auto-revue Â§2 avant chaque merge ; arrÃªts Â§3 inchangÃ©s ; design UI Â§4.  
ChatGPT = consultatif seulement. Toute dÃ©cision seule = **Â« DÃ‰CISION CURSOR â€” Ã  relire par Claude Â»**.

**STOP aprÃ¨s point 11** : ne pas dÃ©marrer T13d, T13e, T11c, pages Sessions/Agents.

---

## 2026-09-24 â€” T12b MERGÃ‰E (#73) â€” squash `a7b630f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/73 â€” **VALIDÃ‰E** Claude (rÃ©v.58) â†’ **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `a7b630f`
- Suite PG (Claude) : 1 073 ok / 1 skip ; golden additifs ; chemin live inchangÃ© ; paritÃ© via helpers pipeline ; 3 statuts exercÃ©s.

### RÃ©serves Claude (non bloquantes) â€” Ã  traiter plus tard
1. La paritÃ© T12b utilise les **paramÃ¨tres par dÃ©faut** ; **T12e DOIT** utiliser les paramÃ¨tres rÃ©els du screener live (settings).
2. Lâ€™Ã©tape **structure (MTF)** reste hors paritÃ© jusquâ€™Ã  **T3e**.

**Suite** : petite PR UI exception (Risqueâ†’RÃ©gime + DIR â†‘/â†“), puis T12câ€¦

---

## 2026-09-24 â€” SYNC Claude rÃ©v.56 â€” T14 Interface V3

Audit UI ajoutÃ© Ã  la feuille de route (**section T14**).

**Ordre** (rÃ©v.56/58) : â€¦ T12e â†’ **T14a** â†’ T13a â†’ T13b + T14c â†’ â€¦  
Aucune fusion ni suppression de page avant T14a.

### Exception autorisÃ©e â€” EN COURS (voir entrÃ©e UI exception ci-dessus)

---

## 2026-09-24 â€” T12a MERGÃ‰E (#72) â€” squash `5bc1e9c`

- PR : https://github.com/samiriggui-code/IchiVol/pull/72 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `5bc1e9c`
- Historique profond versionnÃ© + validate_candles + qualitÃ© Lab ; correctifs rÃ©v.53/54.

**Suite** : T12b MERGÃ‰E ; UI exception + T12câ€¦

---

## 2026-09-24 â€” T9g-fix MERGÃ‰E (#71) â€” squash `9490e4b`

- PR : https://github.com/samiriggui-code/IchiVol/pull/71 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `9490e4b`
- `review_candidate` + gates ; `min(trades_base, trades_var)` (rÃ©v.50).

**Suite** : T12a EN COURS (historique profond versionnÃ© + validate_candles).

---

## 2026-09-24 â€” SYNC Claude rÃ©v.51 â€” complÃ©tude T12a/b + T11a-bis (aprÃ¨s #71)

ContrÃ´le de complÃ©tude Claude â€” **Ã  appliquer aprÃ¨s merge de #71**,  
**sans changer lâ€™ordre** : T9g-fix â†’ T12a â†’ T12b â†’ T12c â†’ T12d â†’ T12e â†’ T13â€¦  
puis T11a-bis (petite PR post-T12e).

### T12a â€” ajouts obligatoires (brief)

- Jeu versionnÃ© : passe **`validate_candles`** (`market_data/quality.py`) Ã  la construction
- Rapport qualitÃ© (**codes + compte par code**) Ã©crit dans le **manifeste**, Ã  cÃ´tÃ© des sha256
- Ã‰tudes Lab (`walk-forward`, `ablation_oos`, `regime_slices`) **renvoient** ce rapport avec leurs rÃ©sultats
- Jeu marquÃ© dÃ©faillant : **toujours utilisable**, mais **avertissement affichÃ©**

### T12b â€” ajout

- Bandes RVOL **boolÃ©ennes** (faible / normal / Ã©levÃ© / fort / extrÃªme)  
  â†’ pour que la redondance T10c puisse aussi les mesurer

### T11a-bis (aprÃ¨s T12e, une petite PR) â€” oublis T11a

1. `resolution = "raw_fallback"` dans `resolve.py` quand un symbole hors catalogue retombe sur Binance
2. Bougies DB : `volume_type` + `taker_buy_volume` (migration unique ; anciennes lignes `NULL`)
3. Test dâ€™imports garde production : `decision/pipeline.py` et `decision/combiner.py` ne doivent importer, mÃªme indirectement, **ni** `strategy_lab.lab_context` **ni** un indicateur hors `PRODUCTION`

### NotÃ© ailleurs

- Cache `observe_lab_context` â†’ avec **T11b** (~49 % overhead, ~0,7 s/cycle : pas urgent)
- #71 CI verte @ `2e959f2` â€” **pas de merge** tant que Claude nâ€™a pas re-validÃ© le correctif `min(trades)`

---

## 2026-09-24 â€” T9g-fix EN COURS â€” review_candidate + gates

- Branche : `cursor/t9g-fix-gate-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/71 (**draft**)
- Base : `main` @ `33684c0` (#70 Wyckoff)
- Statut : **DRAFT** â€” correctif rÃ©v.50 + CI verte ; **attente re-revue Claude** (pas de merge). Brief T12/T11a-bis : voir SYNC rÃ©v.51.

### LivrÃ©

1. `promote` â†’ **`review_candidate`** (Lab ne promeut jamais)
2. Gates : min_oos_trades dÃ©faut **30** ; majoritÃ© stricte de plis ; coÃ»ts dÃ©favorables (10/8 bps) ; PF OOS non dÃ©gradÃ©
3. Affichage : `hypothesis_id` / `lineage_trial_count` (T10b), `n_bars`, `history_warning` si < 1 an
4. Tests limite par rÃ¨gle ; OpenAPI golden (dÃ©faut min_oos_trades)
5. **Correctif rÃ©v.50** : `total_oos_trades = min(trades_base, trades_var)` (pas `max`)

### RÃ©serve (non bloquante)

`lineage_trial_count` ne compte que les expÃ©riences **persistÃ©es** en Perf DB ; lâ€™Ã©tude courante nâ€™y est **pas** incluse.

### Changement non additif (seul autorisÃ©)

Enum recommandation : `promote` â†’ `review_candidate` â€” justifiÃ© dans la PR.

### Hors scope
T12 Â· FeatureStatus mutation Â· pipeline Â· microstructure

---

## 2026-09-24 â€” Wyckoff REJECTED MERGÃ‰E (#70) â€” squash `33684c0`

- PR : https://github.com/samiriggui-code/IchiVol/pull/70 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : tip attendu `33684c0` sur `origin/main`
- `FeatureStatus.REJECTED` ; toujours calculable Lab. Golden inchangÃ©s.

---

## 2026-09-24 â€” SYNC Claude rÃ©v.49 â€” T13 ajoutÃ©e (NE PAS DÃ‰MARRER)

Addendum feuille de route : tranche **T13 Â« couche de trading contrÃ´lÃ©e Â»**.  
**Aucun code T13 dans cette session.**

### Ordre du jour (rÃ©v. 49) â€” inchangÃ© jusquâ€™Ã  T12e

1. T9g-fix  
2. T12a  
3. T12b  
4. T12c  
5. T12d  
6. T12e  
7. **T13a** â†’ **T13b** â†’ â€¦  
8. Ensuite : T11b-c, T10d-e, T11d-f, T3e MTF, modÃ¨le G  

(microstructure : toujours rien avant T12e)

### Contraintes T13 Ã  respecter dÃ¨s maintenant (sans coder)

- **Risk Kernel** = **une** fonction pure **obligatoire** ; tous les chemins dâ€™ouverture paper devront y passer :
  - `sync_auto_watchlist`
  - `open_user_confirmed`
  - action agent `open_paper_position`
- **Ne pas** ajouter de nouveau chemin dâ€™ouverture qui contournerait le kernel.
- **Aucun** ordre rÃ©el, identifiant broker, ni adaptateur broker rÃ©el dans T13.
- RÃ©utiliser (pas dupliquer) : `paper/gates.py`, `paper/risk.py`, `quote_paper.py`, `brokerage/execution.py`.

### PR ouvertes (attente revue Claude, une Ã  la fois)

| PR | Objet |
|---|---|
| #69 | ce handoff (rÃ©v.48 + rÃ©v.49) |
| #70 | Wyckoff REJECTED |
| #71 | T9g-fix |
| #68 | trade VP â€” diffÃ©rÃ©e post-T12e |

---

## 2026-09-24 â€” SYNC Claude rÃ©v.48 â€” bilan #53â†’#67 + reprise

Revue Claude a posteriori sur `main` @ `23dc4ba` : **rien Ã  revert**  
(suite PG 1 049 ok / 1 skip ; golden additifs ; dÃ©cision inchangÃ©e).

### RÃ¨gle merge (rÃ©tablie)

**Fin du mode solo.** Une PR Ã  la fois ; **aucun merge sans revue Claude**,  
sauf autorisation utilisateur explicite pour une tranche nommÃ©e.  
VÃ©rifier `origin/main` avant dâ€™Ã©crire MERGÃ‰E.

### #67 â€” MERGÃ‰E (correction handoff)

- PR : https://github.com/samiriggui-code/IchiVol/pull/67 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `23dc4ba`
- (Lâ€™entrÃ©e Â« EN COURS / draft Â» plus bas est **obsolÃ¨te** â€” squash dÃ©jÃ  dans main.)

### #68 trade VP

**DiffÃ©rÃ©e** jusquâ€™aprÃ¨s T12e (rÃ©v.48 Â§6).  
PR draft : https://github.com/samiriggui-code/IchiVol/pull/68 â€” ne pas merger.

### Ordre du jour (rÃ©v. 48) â€” **supersÃ©dÃ© par rÃ©v.49** (ci-dessus)

Voir entrÃ©e SYNC rÃ©v.49 : T9g-fix â†’ T12aâ€“e â†’ **T13aâ€¦** ; microstructure aprÃ¨s T12e.

### Point mesurÃ© â€” `observe_lab_context` (sans code)

Benchmark local synthÃ©tique (300 barres Ã— 20 symboles Ã— 3 reps, pas de rÃ©seau) :

| Path | ms / cycle 20 symboles |
|---|---|
| `observe_lab_context` seul | ~238 ms |
| scan_like (agents + REGISTRY + pipeline) | ~489 ms |
| scan_like + observe | ~717 ms |

**Overhead observe / scan_like â‰ˆ 49 %** (part du total â‰ˆ 33 %).  
**> 10 %** â†’ candidat cache (tranche dÃ©diÃ©e, pas dans T9g-fix).

### Suite immÃ©diate

1. PR Wyckoff `FeatureStatus.REJECTED` (commit sÃ©parÃ©, golden inchangÃ©s)  
2. PR **T9g-fix** â€” `promote` â†’ `review_candidate` + gates (revue Claude avant merge)


---

## 2026-09-24 â€” Chart layer=breaks EN COURS â€” BOS / CHoCH producer

- Branche : `cursor/breaks-chart-producer-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/67
- Base : `main` @ `35e14f3` (#66 microstructure)
- Statut : **MERGÃ‰E** squash `23dc4ba` â€” voir entrÃ©e SYNC rÃ©v.48 en tÃªte.

### LivrÃ© (prÃ©vu)

1. `chart_objects/from_breaks.py` â€” StructureEvent BOS/CHoCH via REGISTRY + breakouts
2. `collect.py` merge ; breakouts retirÃ©s de `from_structure` (layer structure = zones/TL)
3. Front : retire `emptyUntil: T9` sur couche Cassures
4. Tests `test_from_breaks.py`

### Hors scope
Trade VP Â· order book Â· dÃ©cision / paper / broker.

---

## 2026-09-24 â€” Binance microstructure Lab MERGÃ‰E (#66) â€” squash `35e14f3`

- PR : https://github.com/samiriggui-code/IchiVol/pull/66 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `35e14f3`
- Cursor solo ; CI verte. Lab-only trade CVD compare.

**Suite solo** : chart `layer=breaks` producer â†’ trade VP Lab â†’ doc sync.

---

## 2026-09-24 â€” Binance microstructure Lab EN COURS â€” trade CVD compare

- Branche : `cursor/binance-microstructure-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/66
- Base : `main` @ `8c6af5e` (#65 ProviderCapabilities)
- Statut : **MERGÃ‰E** via entrÃ©e ci-dessus.

---

## 2026-09-24 â€” ProviderCapabilities MERGÃ‰E (#65) â€” squash `8c6af5e`

- PR : https://github.com/samiriggui-code/IchiVol/pull/65 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `8c6af5e`
- Cursor solo ; CI verte. Inventaire dÃ©claratif only.

---

## 2026-09-24 â€” ProviderCapabilities EN COURS â€” inventaire providers

- Branche : `cursor/provider-capabilities-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/65 (**draft**)
- Base : `main` @ `00ab86a` (#64 T9g)
- Statut : **DRAFT** â€” Cursor solo. DÃ©claratif only ; **pas de nouveau router**. CI en cours.

### LivrÃ©

1. `market_data/capabilities.py` â€” `ProviderCapabilities` (ohlcv/quotes/trades/depth/OI/funding/volume)
2. DÃ©clarations binance / biquote / twelve_data (honnÃªtes vs code rÃ©el)
3. `GET /providers/capabilities` + agent `list_provider_capabilities`
4. Tests + OpenAPI goldens

### Hors scope
OANDA/IBKR adapters Â· WS Â· depth fetch Â· changer paper path.

---

## 2026-09-24 â€” T9g MERGÃ‰E (#64) â€” squash `00ab86a` â€” ablation Ã— WF OOS

- PR : https://github.com/samiriggui-code/IchiVol/pull/64 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `00ab86a`
- Cursor solo ; CI verte. Recommendations display-only.

---

## 2026-09-24 â€” T9g EN COURS â€” ablation Ã— walk-forward OOS

- Branche : `cursor/t9g-ablation-oos-a2fe`
- PR : *(draft Ã  ouvrir)*
- Base : `main` @ `c261f48` (#63 T10c)
- Statut : **EN COURS** â€” Cursor solo. Recommendations display-only ; **pas de mutation FeatureStatus**.

### LivrÃ©

1. `strategy_lab/ablation_oos.py` â€” additive / leave-one-layer Ã— WF OOS
2. `decide_recommendation` â†’ promote | reject | inconclusive
3. `POST /strategy-lab/ablation-oos/study` + agent `run_ablation_oos_study`
4. Tests `test_t9g_ablation_oos.py` + goldens OpenAPI

### Hors scope
Auto FeatureStatus Â· pipeline vote Â· UI tab Â· walk-forward-opt grid.

---

## 2026-09-24 â€” T10c MERGÃ‰E (#63) â€” squash `c261f48` â€” redondance featureÃ—feature

- PR : https://github.com/samiriggui-code/IchiVol/pull/63 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `c261f48`
- Cursor solo ; CI verte. Observation-only ; pas dâ€™auto-reject.

---

## 2026-09-24 â€” T10c EN COURS â€” redondance featureÃ—feature

- Branche : `cursor/t10c-feature-redundancy-a2fe`
- PR : *(draft Ã  ouvrir)*
- Base : `main` @ `1a9fb2a` (handoff T11a)
- Statut : **EN COURS** â€” Cursor solo. **Observation-only** ; **pas dâ€™auto-reject**.

### LivrÃ©

1. `strategy_lab/redundancy.py` â€” overlap / Jaccard / Ï† sur conditions bool Lab
2. `GET /strategy-lab/feature-redundancy/study` + agent `run_feature_redundancy_study`
3. Annote family/status T10a ; disclaimer no pipeline / no auto-reject
4. Tests `test_t10c_feature_redundancy.py` + route research

### Hors scope
Auto-reject Â· mutation FeatureStatus Â· T9g OOS Â· UI Lab tab Â· pipeline vote.

---

## 2026-09-24 â€” T11a MERGÃ‰E (#61) â€” squash `ff43f17` â€” quality + provenance (obs)

- PR : https://github.com/samiriggui-code/IchiVol/pull/61 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `ff43f17`
- Cursor solo ; CI verte. **Observation-only** (pas de hard `badâ†’NO_TRADE`).

**Suite** : T10c EN COURS â†’ T9g.

---

## 2026-09-24 â€” T11a EN COURS â€” quality gate + provenance

- Branche : `cursor/t11a-quality-provenance-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/61 (**draft**)
- Base : `main` @ `934f3e4` (#60 T9f)
- Statut : **DRAFT** â€” Cursor solo. **Observation-only** (pas de `badâ†’NO_TRADE` pipeline). CI en cours.

### LivrÃ© (prÃ©vu)

1. `observe_data_quality` / `observe_data_provenance` (`market_data/observe_quality.py`)
2. Gate display `pass|watch|fail` + `dataset_fingerprint` ; disclaimer no vote
3. `ScreenerRow.data_quality` / `data_provenance` + serializers
4. `AnalysisStage` DATA_QUALITY + prepend optionnel sur handoff (dÃ©cision pipeline inchangÃ©e)
5. Tests `test_t11a_quality_provenance.py`

### Hors scope
Hard gate pipeline Â· T10c redondance Â· T9g ablation OOS Â· T11b+.

---

## 2026-09-24 â€” T9f MERGÃ‰E (#60) â€” squash `934f3e4` â€” Lab fib_* + watchlist badges

- PR : https://github.com/samiriggui-code/IchiVol/pull/60 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `934f3e4`
- Cursor solo ; CI verte. Observation-only.

---

## 2026-09-24 â€” T9f EN COURS â€” Lab fib_* + lab_context watchlist

- Branche : `cursor/t9f-lab-features-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/60 (**draft**)
- Base : `main` @ `84efa9d` (#59 T9e)
- Statut : **DRAFT** â€” Cursor solo. **Observation-only** (pas de pipeline / pas dâ€™auto-reject). CI en cours.

### LivrÃ©

1. FeatureBar `fib_*` (ancre ImpulseEvent actif) + conditions Lab orphelines (`fvg_status`, `impulse_displacement_atr_min`, `fib_*`)
2. `observe_lab_context` â†’ `ScreenerRow.lab_context` + serializers summary/detail
3. Watchlist : badges CHoCH / FVG / Fib **rÃ©els** (placeholders T9f retirÃ©s)
4. Goldens **additifs** only ; tests `test_t9f_lab_features.py`

### Hors scope
Pipeline / paper gate impulse Â· T11a Â· T10c Â· T9g.

---

## 2026-09-24 â€” T9e MERGÃ‰E (#59) â€” squash `84efa9d` â€” Fib ancrÃ© ImpulseEvent

- PR : https://github.com/samiriggui-code/IchiVol/pull/59 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `84efa9d`
- Cursor solo ; CI verte. Gate paper reste `anchor=naive`.

---

## 2026-09-24 â€” T9e EN COURS â€” Fib ancrÃ© sur ImpulseEvent

- Branche : `cursor/t9e-fib-anchor-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/59 (**draft**)
- Base : `main` @ `534ee80` (#58 T9d)
- Statut : **EN COURS** â€” Cursor solo. Gate paper reste `anchor=naive` (compat).

### LivrÃ©

1. `compute_fib_context(..., anchor=naive|impulse|auto)` + `swings_from_impulse`
2. `FibContext` additif : `anchor_source` / bars / `displacement_atr`
3. `from_fibonacci.py` â†’ `layer=fibonacci` (key ratios) ; collect merge
4. Calque Fib sans `emptyUntil`
5. Tests anti-lookahead + gate naive inchangÃ©

### Hors scope
T9f Lab badges Â· pipeline Â· changer le gate paper vers impulse (Claude tranche).

---

## 2026-09-24 â€” T9d MERGÃ‰E (#58) â€” squash `534ee80` â€” FVG causal

- PR : https://github.com/samiriggui-code/IchiVol/pull/58 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `534ee80`
- Cursor solo ; CI verte (fix T1e ratchet via REGISTRY.compute).

---

## 2026-09-24 â€” T9d EN COURS â€” FVG (Fair Value Gap) causal

- Branche : `cursor/t9d-fvg-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/58 (**draft**)
- Base : `main` @ `ef062c2` (#57 T9c)
- Statut : **DRAFT** â€” Cursor solo. Pas de Fib / pas de pipeline. CI en cours.

### LivrÃ©

1. `app/indicators/fvg.py` â€” 3-candle ICT imbalance + fill/invalidation causals
2. Registry `fvg` EXPERIMENTAL ; Lab `fvg_bullish` / `fvg_bearish` / `fvg_active`
3. `from_fvg.py` â†’ rectangles `layer=fvg` ; merge dans `collect.py`
4. Front : rectangles via dual price-lines ; calque FVG plus `emptyUntil`
5. Tests anti-lookahead + non-interfÃ©rence structure/impulse ; goldens additifs

### Hors scope
T9e Fib ancrÃ© Â· T9f badges watchlist Â· breaks layer Â· dÃ©cision / broker.

---

## 2026-09-24 â€” T9c MERGÃ‰E (#57) â€” squash `ef062c2` â€” impulsion / displacement

- PR : https://github.com/samiriggui-code/IchiVol/pull/57 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `ef062c2`
- Cursor solo ; CI verte.

---

## 2026-09-24 â€” T9c EN COURS â€” impulsion / displacement causal

- Branche : `cursor/t9c-impulsion-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/57 (**draft**)
- Base : `main` @ `82e980e` (#56 T10b)
- Statut : **DRAFT** â€” Cursor solo (Claude restreint). Pas de FVG / pas de Fib rewrite / pas de pipeline. CI en cours.

### LivrÃ© (prÃ©vu / en cours)

1. `app/indicators/impulse.py` â€” `ImpulseParams` / `ImpulseEvent` / `ImpulseState` / `compute_impulse`
2. Pivot-to-pivot leg (T9a fractal) ; gate `min_displacement_atr` (+ `min_rvol` optionnel)
3. Registry `impulse` EXPERIMENTAL (`family=structure`)
4. Lab : `impulse_bullish` / `impulse_bearish` / `impulse_displacement_atr` (conditions + FeatureBar)
5. Tests anti-lookahead + seuil + non-interfÃ©rence structure bos/bias
6. Goldens **additifs** only (condition schema/eval + features)

### Hors scope
T9d FVG Â· T9e Fib ancrÃ© Â· chart `layer=breaks` (plus tard) Â· dÃ©cision / paper / broker.

**Claude** : valider dÃ©finition leg vs candle ; seuils a priori.

---

## 2026-09-24 â€” T10b MERGÃ‰E (#56) â€” squash `82e980e` â€” compteur dâ€™essais + complexitÃ©

- PR : https://github.com/samiriggui-code/IchiVol/pull/56 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `82e980e`
- Cursor solo (Claude restreint) ; CI verte (fix assertion untagged lineage = total essais ruleset).
- Display-only : **aucune auto-rejection**.

**Claude** : auditer #56 avec #54/#55/#53.

---

## 2026-09-24 â€” T10b EN COURS â€” hypothesis_id + lineage + complexitÃ© (display-only)

- Branche : `cursor/t10b-hypothesis-lineage-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/56 (**draft**)
- Base : `main` @ `6d1968a` (#53 T9b)
- Statut : **DRAFT** â€” Cursor solo (Claude restreint). **Pas dâ€™auto-reject.** CI en cours.

### LivrÃ©

1. Migration alembic `f2a3b4c5d6e7` : `strategy_lab_experiments.hypothesis_id` nullable + index (non-UNIQUE â€” plusieurs essais / hyp)
2. ORM + `save_experiment(..., hypothesis_id=)` / aussi via `parameters.hypothesis_id`
3. `ruleset_complexity(rules_json)` â€” score display-only (`entry_leaves` / `exit_leaves` / `exit_extras`) ; note Â« no auto-reject Â»
4. `lineage_count` : COUNT par `hypothesis_id` si set, sinon `ruleset_id+symbol+timeframe`
5. API list/get/compare + agent channel enrichis ; filtre `hypothesis_id` sur list
6. UI Lab : colonnes **Essais** + **Cx** sur tables Perf DB / StoredMetrics
7. Tests : `test_t10b_hypothesis_lineage.py` (unit complexity always ; DB lineage skip sans PG)

### Hors scope
T10c redondance ; T9g ablation OOS ; aucun rejet automatique sur complexitÃ© / essais.

**Claude** : auditer post-12h10 avec #54/#55/#53.

---

## 2026-09-24 â€” T9b MERGÃ‰E (#53) â€” squash `6d1968a` â€” CHoCH + break quality

- PR : https://github.com/samiriggui-code/IchiVol/pull/53 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `6d1968a`
- Cursor solo (Claude restreint) ; CI verte avant merge.
- Notes : `bos_bullish` bit-identique (non scindÃ©) ; `choch_*` / `break_quality` EXPERIMENTAL ; `recalc_short_entry_fee` dry-run + idempotent.

**Claude** : auditer #53 Ã  12h10 (post-merge).

---

### Suite de tests â€” Postgres (supervision 2026-09-23)

- **Claude** (revue) : PostgreSQL 16 `ichivol_engine_dev`, migrations alembic appliquÃ©es â†’ lance la suite **complÃ¨te** (paper, backtest evidence, brokerage, market_data inclus).
- **Cursor** (implÃ©mentation) : **pas** dâ€™install Postgres local ; suite sans base comme dâ€™habitude ; reporter les rÃ©sultats dans le handoff. Les Ã©checs liÃ©s Ã  la base sont dÃ©tectÃ©s / renvoyÃ©s par Claude.
- **Baseline avec base propre** (rÃ©fÃ©rence courante, post T0-CI #14) : **0 Ã©chec, 1 skip** rÃ©seau Binance. Toute base **non vierge** (ex. `ichivol_engine_dev` local avec de l'historique rÃ©el de paper trading) peut faire Ã©chouer des tests qui supposent un Ã©tat propre (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_protection.py`, `test_overview_marks_budget` timing) â€” **vÃ©rifier contre `main` avant merge** avant de conclure Ã  une rÃ©gression, ne pas comparer Ã  cette baseline si la base contient dÃ©jÃ  des donnÃ©es.
- **RÃ¨gle de merge** : avec une base propre, **0 Ã©chec** attendu. Tout Ã©chec **nouveau par rapport Ã  `main`** bloque le merge. **Toujours vÃ©rifier `git log origin/main` aprÃ¨s un merge** avant dâ€™annoncer MERGÃ‰E dans le handoff.
- **T0-CI** : greening + isolation baseline â€” **mergÃ©** (PR #14) â€” **validÃ© par Claude**.
- **T2a** : ChartObject â€” **mergÃ©** (PR #15) â€” **validÃ© par Claude**.
- **T0-BROKER** #16 â€” **MERGÃ‰E** (validÃ© Claude).
- **T2b** #17 â€” **MERGÃ‰E** (validÃ© Claude).
- **T3** #18 â€” **MERGÃ‰E** (validÃ© Claude) â€” DSL `all`/`any` + `exit`.
- **T0-UI** #19 â€” **MERGÃ‰E** (acceptÃ© Claude comme T0-UI, pas T4 roadmap).
- **T2c** #20 â€” **MERGÃ‰E** â€” **validÃ© par Claude** (T2a+T2b+T2c = **T2 terminÃ©**).
- **T3c** #21 â€” **MERGÃ‰E** â€” **validÃ© par Claude** (registre conditions ; T3 phase close â€” T3d avec T5b, T3e plus tard).
- **T4a** #22 â€” **MERGÃ‰E** â€” **validÃ© par Claude** (overlay + correction net).
- **T0-METRICS** #23 â€” **MERGÃ‰E** â€” **validÃ© par Claude** (stats nettes ; `cost_log` / `net_v1`).
- **T0-METRICS-2** #24 â€” **MERGÃ‰E** â€” **validÃ© par Claude** (`eod_return` ; lookahead strict).
- **T0-CALC** #25 â€” **MERGÃ‰E** â€” intÃ©grÃ©e par Cursor (Claude indisponible jusquâ€™Ã  18:10 ; CI verte ; brief Claude respectÃ©).
- **Event Intelligence audit** #26 â€” **MERGÃ‰E** (doc).
- **EventAnomalyDetector PHASE 5** #27 â€” **MERGÃ‰E** (observation-only).
- **Event Intelligence PHASE 6** #28 â€” **MERGÃ‰E** (regime study + calibration ; Cursor solo, CI verte).
- **Event Intelligence PHASE 7** #29 â€” **MERGÃ‰E** (SymbolNews + correlate â†’ `EVENT_MARKET` ; Cursor solo, CI verte).
- **T4c** #31 â€” **MERGÃ‰E** (WHY ENTERED / REJECTED / EXITED).
- **T4b** #32 â€” **MERGÃ‰E** (filtres overlay structurÃ©s).
- **T4d** #33 â€” **MERGÃ‰E** (filtre rÃ©gime overlay).
- **T5a** #34 â€” **MERGÃ‰E** (family weights observation-only).
- **T5b** #35 â€” **MERGÃ‰E** (profils poids + Ã©tude historique).
- **T6** #36 â€” **MERGÃ‰E** (AuditReport post-outcome).
- **T7** #37 â€” **MERGÃ‰E** (Monte Carlo / risk of ruin).
- **T3d** #39 â€” **MERGÃ‰E** (propose ruleset edit + condition catalog).
- **Researcher** #41 â€” **MERGÃ‰E** (propose experiment plan).
- **UI Lab Research** #43 â€” **MERGÃ‰E** (validÃ© par Claude, revue exÃ©cutÃ©e en local Laragon/Postgres).
- **T0-NOTIF** #44 â€” **MERGÃ‰E** (validÃ© par Claude, revue exÃ©cutÃ©e en local Laragon/Postgres).
- **T0-MANAGE-a** #45 â€” **MERGÃ‰E** (validÃ© par Claude, revue exÃ©cutÃ©e en local Laragon/Postgres â€” diff rÃ©el + no-lookahead vÃ©rifiÃ© bar par bar).
- **T0-MANAGE-b** #46 â€” **MERGÃ‰E** (validÃ© par Claude â€” watermark, gate legacy/auto et isolation des tests vÃ©rifiÃ©s ; 2 rÃ©serves non bloquantes notÃ©es).
- **T0-MANAGE-c** #47 â€” **MERGÃ‰E** (validÃ© par Claude â€” invariant 1e-9 revÃ©rifiÃ© indÃ©pendamment ; **rÃ©sidu de Jensen mesurÃ© et non bornÃ©, voir entrÃ©e dÃ©diÃ©e**).
- **T0-MANAGE-d** #48 â€” **MERGÃ‰E** squash `a941539` (validÃ© Claude ; suite PG 918â†’928 ok / 1 skip). **Incident process** : handoff avait annoncÃ© MERGÃ‰E avant que `main` ne contienne le squash â€” corrigÃ©.
- **T0-MANAGE-e** #49 â€” **MERGÃ‰E** squash `389fc40` (validÃ© Claude adff686 ; suite PG **935 ok / 1 skip**, 0 rÃ©gression). Sondes : `tighten_stop` en profit â†’ risque = R0 (LONG/SHORT) ; risque signÃ© OK ; combo `partial_tp`+`reinforce` rejetÃ© ; fuzz 300 seeds â†’ 135 adds, jamais > R0, invariant Î£net=Î£bars 3,5e-16. **VÃ©rifiÃ©** `git log origin/main` contient `389fc40`.
- **T0-MANAGE-f** #50 â€” **MERGÃ‰E** squash `7a77424` (validÃ© Claude 102caee ; suite PG **944 ok / 1 skip**, 0 rÃ©gression). **T0-MANAGE aâ†’f terminÃ©.**
- **T0-FIX-SHORT-FEE** #51 â€” **MERGÃ‰E** squash `b9f8421` (validÃ© Claude ; suite PG **948 ok / 1 skip**, 0 rÃ©gression). Sondes SHORT (close / partielâ†’target / renfortâ†’target / Ã©puisement / stop) : cash = rÃ©alisÃ© â‰¤ 5e-13. **VÃ©rifiÃ©** `git log origin/main` contient `b9f8421`. **Dette SHORT entry_fee soldÃ©e** pour clÃ´tures post-fix.
- **T9a** #52 â€” **MERGÃ‰E** squash `985c4e5` (validÃ© Claude ; suite PG **955 ok / 1 skip**). **VÃ©rifiÃ©** `origin/main` tip contenait `985c4e5`.
- **UI-MARKET** #54 â€” **MERGÃ‰E** squash `10631ef` (Cursor solo, Claude restreint ; CI verte). **Ã€ auditer Claude 12h10.**
- **T10a** #55 â€” **MERGÃ‰E** squash `2e3ebc1` (Cursor solo ; CI verte). **Ã€ auditer Claude 12h10.**
- **T9b** #53 â€” **MERGÃ‰E** squash `6d1968a` (Cursor solo, Claude restreint ; CI verte). **Ã€ auditer Claude 12h10.**
- **T10b** #56 â€” **MERGÃ‰E** squash `82e980e` (Cursor solo ; CI verte). **Ã€ auditer Claude 12h10.**
- **T9c** #57 â€” **MERGÃ‰E** squash `ef062c2` (Cursor solo ; CI verte). **Ã€ auditer Claude 12h10.**
- **T9d** #58 â€” **MERGÃ‰E** squash `534ee80`.
- **Job en cours** : **T9e** â€” Fib ancrÃ© â€” `cursor/t9e-fib-anchor-a2fe`. **Cursor solo**.
- **T9** (structure / FVG / Fib) â€” T9a+T9b+T9c+T10a+T10b OK ; T9d en cours.
- âš ï¸ **Dette ouverte (T0-MANAGE-c)** : le max drawdown des rulesets Ã  `partial_tp` est **surestimÃ©** d'un montant qui croÃ®t en volÂ². **Ne pas comparer** partiels vs non-partiels sur le DD avant correction.
- âš ï¸ **Caveat historique SHORT** : positions SHORT **CLOSED avant** `b9f8421` (#51, mergedAt `2026-09-24T07:02:48Z`) ont un `realized` **surÃ©valuÃ© de `entry_fee`**. Compte local Cursor : **CLOSED_SHORT = 0**. Script ponctuel : `scripts/recalc_short_entry_fee.py` â€” filtre par **horodatage exact**, journal `SHORT_FEE_RECALC` idempotent ; **ne pas lancer `--apply`** sans revue ; **pas de migration auto**.
- âš ï¸ **Caveat migration #48** : backfill `initial_entry_fee = entry_fee` courant â€” **faux pour lots dÃ©jÃ  partialisÃ©s avant migration**.
- âš ï¸ **Dette max_exposure** : sÃ©mantiques **divergentes** Lab vs paper â€” Lab = `qty/initial_qty` (1 unitÃ© = 100 % capital ; `levier: true` si > 1) ; paper = `notional â‰¤ max_exposure Ã— equity`. **Ne pas comparer** rulesets Lab `max_exposure>1` aux paper sans le flag `levier`.


---

## 2026-09-24 â€” UI-MARKET MERGÃ‰E (#54) â€” squash `10631ef` â€” Cursor solo (Claude restreint)

- PR : https://github.com/samiriggui-code/IchiVol/pull/54 â€” **MERGÃ‰E** squash
- **VÃ©rifiÃ©** : `origin/main` tip = `10631ef`
- **Contexte** : Claude en mode restriction jusquâ€™Ã  **12h10** ; utilisateur a demandÃ© dâ€™enchaÃ®ner seul (prÃ©cÃ©dent T0-CALC #25).
- **CI avant merge** : `pytest (Postgres 16)` SUCCESS Â· `frontend (npm build)` SUCCESS Â· mergeable CLEAN
- **Auto-revue Cursor** : captures 01â€“07 + `ChartObject.layer` tests + build OK ; Ã©carts volontaires documentÃ©s (pas de 5m, camap-tokens, Journal placeholder).
- **Suite** : T10a dÃ©marrÃ©e immÃ©diatement aprÃ¨s.

**Claude** : auditer #54 Ã  12h10 (post-merge).

---

## 2026-09-24 â€” T10a MERGÃ‰E (#55) â€” squash `2e3ebc1` â€” registry status + source

- Branche : `cursor/t10a-registry-status-a2fe` @ `e49e602`
- PR : https://github.com/samiriggui-code/IchiVol/pull/55 (**draft**) â€” base `main` @ `10631ef` (#54)
- Statut : **MERGÃ‰E** squash `2e3ebc1` (Cursor solo ; CI verte). **Ã€ auditer Claude 12h10.**
- **VÃ©rifiÃ©** : `origin/main` tip = `2e3ebc1`
- Tests locaux : `test_t10a_registry_status` + `test_registry` + `test_indicators_route` + `test_ppo_best_cloud_lab` **OK**

### Objectif
Chaque `IndicatorDefinition` porte `status` / `source` / `confirmation_lag_bars` / `family` / `experiment_refs`. **Aucune sortie de calcul changÃ©e.**

### Statuts (justifiÃ©s par le code)

| id | status | Justification |
| --- | --- | --- |
| ichimoku | PRODUCTION | `agents/ichimoku_agent.py` â†’ combiner + `evidence/context.py` |
| rvol | PRODUCTION | `agents/rvol_agent.py` â†’ combiner + pipeline participation |
| atr | PRODUCTION | `decision/pipeline.py` (AtrState) + `screener/service.py` + `evidence/catalog.py` |
| adx | PRODUCTION | `decision/pipeline.py` (AdxState) + screener |
| cvd | PRODUCTION | `decision/pipeline.py` (CvdState) + screener |
| donchian | PRODUCTION | `decision/pipeline.py` (DonchianState) + screener |
| structure | PRODUCTION | `decision/pipeline.py` (StructureState) + screener ; lag = `swing_lookback` |
| location | PRODUCTION | `decision/pipeline.py` (LocationState) + screener |
| rsi / cmf / obv | CANDIDATE | `api/context.py` seulement (pas chemin dÃ©cision) |
| ichimoku_analytics | EXPERIMENTAL | couche Lab |
| wyckoff | EXPERIMENTAL | README moteur : **non promu** â€” **Claude tranche** |
| ppo / best_cloud | REJECTED | `docs/REVUE-SIM-ET-COUTS-â€¦Â§5` ; Lab toujours calculable |
| best_cloud source | external | Daveatt Â« BEST Cloud ALL MA Â» â€” TV open-source / House Rules ; URL script ; licence relevÃ©e 2026-09-24 |

### Garde-fou
`tests/indicators/test_t10a_registry_status.py` : ids string/AST dans les modules production â†’ doivent Ãªtre PRODUCTION ; ban import PPO/BEST Cloud conservÃ©.

### Hors scope
T10b compteur dâ€™essais ; T10c redondance ; fiches candidats.

**T10a mergÃ©e.** Rebase #53 T9b en cours.

---

## 2026-09-24 â€” ORDRE DU JOUR CONSOLIDÃ‰ (rÃ©v. feuille de route 46)

RÃ©f. Claude Â« IchiVol V3 â€” Feuille de route Â» rÃ©v. 46. Chantier principal **T9**. **T10** / **T11** uniquement lÃ  oÃ¹ prÃ©requis de T9. Rien dâ€™autre.

### Ã‰tat constatÃ©

| Item | Ã‰tat |
| --- | --- |
| `main` | `985c4e5` â€” T9a #52 **MERGÃ‰E** |
| #54 UI-MARKET | **brouillon** â€” Cursor **ne touche plus** ; Claude relit |
| #53 T9b | **brouillon figÃ©** â€” hors ordre ; **pas de rebase** avant T10a |
| T10a | **aprÃ¨s** merge #54 uniquement |

### Ordre (une sous-tranche Ã  la fois)

1. **#54 UI-MARKET** â€” revue Claude â†’ merge  
2. **T10a** â€” statut + source des features dans le registry  
3. **#53 T9b** â€” rebase sur T10a (CHoCH avec statut) â†’ revue Claude â†’ merge  
4. **T10b** â€” compteur dâ€™essais + complexitÃ© (prÃ©requis T9g)  
5. **T9c** impulsion â†’ **T9d** FVG â†’ **T9e** Fib ancrÃ© â†’ **T9f** features Lab  
6. **T11a** â€” quality gate + provenance (avant T9g)  
7. **T10c** â€” redondance feature Ã— feature  
8. **T9g** â€” ablation walk-forward OOS â†’ dÃ©cision  
9. Plus tard : T11b-c, T10d-e, T11d-f, T3e MTF  

RÃ¨gles : une PR Ã  la fois ; pas de merge sans Claude ; vÃ©rifier `main` aprÃ¨s chaque merge ; handoff Ã  jour ; suite PG sans rÃ©gression + `npm run build` ; golden = ajouts seulement sauf dÃ©cision explicite ; aucun lookahead / ordre broker / trading rÃ©el.

### Actions Cursor (2aâ€“d) â€” FAIT

- **a)** Handoff corrigÃ© : #52 mergÃ©e ; #54 / #53 brouillons ; ordre recopiÃ© ci-dessus.  
- **b)** #54 : **aucun commit code supplÃ©mentaire** (seul ce handoff docs).  
- **c)** #53 : reste brouillon ; **pas de rebase**.  
- **d)** **T10a non dÃ©marrÃ©e**.

### Ã‰tat exact #54 (pour revue Claude)

- Branche : `cursor/ui-market-tradingview-a2fe` @ `3d79eed`  
- PR : https://github.com/samiriggui-code/IchiVol/pull/54 (**draft**, OPEN)  
- Base : `main` @ `985c4e5`  
- Tip code UI : `96b1eff` ; tip handoff : `3d79eed` (docs only)  
- **`npm run build`** : **OK** (tsc + vite, 2026-09-24)  
- **`tests/chart_objects/test_chart_object_layer.py`** : **2 passed** (layer additive, id inchangÃ©, rÃ©trocompat sourceâ†’layer)  
- Captures 01â†’07 : artifacts `/opt/cursor/artifacts/0{1..7}-*.png`  
- Front : chrome TradingView (barre 52 / volume dock / colonne 380 / bas 44 / tiroir mobile) ; camap-tokens  
- Moteur : `ChartObject.layer` (structure|fibonacci|fvg|breaks|claude|user_trades|backtest)  
- Ã‰carts volontaires : pas de TF 5m ; Journal placeholder ; Analyse = BiasPanel + CTA paper  

<img alt="01 Desktop dÃ©faut" src="/opt/cursor/artifacts/01-desktop-default.png" />
<img alt="02 Desktop Calques + Backtest" src="/opt/cursor/artifacts/02-desktop-layers-backtest.png" />
<img alt="03 Mobile graphe" src="/opt/cursor/artifacts/03-mobile-chart.png" />
<img alt="04 Mobile tiroir Liste" src="/opt/cursor/artifacts/04-mobile-drawer-list.png" />
<img alt="05 Mobile tiroir Analyse" src="/opt/cursor/artifacts/05-mobile-drawer-analysis.png" />
<img alt="06 Mobile feuille Calques" src="/opt/cursor/artifacts/06-mobile-layers-sheet.png" />
<img alt="07 Mobile recherche" src="/opt/cursor/artifacts/07-mobile-search.png" />

### Note #53 (prÃ©-examen, sans action)

- Golden : ajouts seulement (`choch_bullish`, `choch_bearish`, `break_quality`) â€” bon signe.  
- **`bos_bullish` non scindÃ© BOS/CHoCH** : un Â« BOS haussier Â» en structure baissiÃ¨re reste comptÃ© BOS. Ã€ documenter dans la PR (compat golden) **ou** proposer scission en feature sÃ©parÃ©e **sans** modifier `bos_bullish` â€” au rebase post-T10a.  
- `recalc_short_entry_fee.py` embarquÃ© : prouver idempotence (2Ã— `--apply` = 1Ã—) + couverture SHORT clÃ´turÃ©s le jour du fix ; dry-run dÃ©faut ; sinon PR Ã  part.

### Doutes Cursor avant T10a (aprÃ¨s merge #54)

1. **PÃ©rimÃ¨tre PRODUCTION** : scanner `decision/pipeline.py`, `combiner.py`, screener, paper, `evidence/context.py` â€” risque de faux positifs (import transitif vs lecture rÃ©elle dâ€™un `id`). CritÃ¨re strict : lâ€™**id** string du registry apparaÃ®t dans le chemin dÃ©cisionnel, pas seulement le module indicateur.  
2. **Wyckoff** : statut Ã  proposer depuis le tableau de verdict README moteur â€” **Claude tranche** (Cursor ne dÃ©cide pas seul).  
3. **BEST Cloud licence** : relever licence sur la page Daveatt au moment du commit (peut avoir changÃ©) ; documenter URL + date.  
4. **`confirmation_lag_bars` structure** : aligner sur lookback **droit** du fractal causal T9a ; test de cohÃ©rence params â†” champ â€” OK conceptuellement ; vÃ©rifier quâ€™aucun autre indicateur Â« provisional Â» ne nÃ©cessite un lag non nul dÃ¨s T10a.  
5. **Garde-fou production** : gÃ©nÃ©raliser `test_ppo_best_cloud_lab.py:242` â€” liste des ids productifs Ã  construire par grep/AST, pas Ã  la main, pour Ã©viter la dÃ©rive.  
6. **OpenAPI golden** : ajouts seulement sur `GET /indicators` â€” OK ; sâ€™assurer que `catalog()` / `describe()` ne cassent pas les clients Lab existants (champs optionnels avec dÃ©fauts).

**Brief T10a** (rappel, dÃ©marrage **uniquement** post-merge #54) : branche `cursor/t10a-registry-status` ; `IndicatorDefinition` += status / source / confirmation_lag_bars / family / experiment_refs ; aucune sortie de calcul changÃ©e ; PPO+BEST Cloud â†’ REJECTED (rÃ©v. sim Â§5) ; hors scope T10b/c.

**Cursor sâ€™arrÃªte ici.** Claude relit #54 dÃ¨s que lâ€™utilisateur Ã©crit Â« Handoff Â».


## 2026-09-24 â€” UI-MARKET EN COURS â€” MarchÃ© TradingView (PR draft)

- Branche : `cursor/ui-market-tradingview-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/54 (**draft**)
- Base : `main` @ `985c4e5` (#52)
- Statut : **ATTENTE REVUE CLAUDE** â€” Cursor **ne touche plus au code**. T9b brouillon figÃ© (#53).

### LivrÃ©

1. Barre haute 52 px (symboleâ†’recherche, prix, %, TF unique, Calques, Indicateurs, Â« i Â» source, Marquer un trade)
2. Graphe max height ; volume ~150 px desktop / ~120 px mobile, redimensionnable (persistÃ©)
3. Watchlist triable Symbole / % / RVOL / Score / Contexte + filtres classe + Â« Contexte actif Â»
4. Desktop : colonne droite ~380 px repliable/redim. ; barre bas 44 px (Backtest / Marquer / Journal)
5. Desktop Backtest dockÃ© (~250 px) : stratÃ©gie, Tous/Gains/Pertes/RejetÃ©s, 4 chiffres clÃ©s, liste trades
6. Mobile : tiroir 3 positions Liste / Analyse / Backtest (poignÃ©e au-dessus de la tabbar shell) ; feuilles Calques + Recherche
7. Moteur : `ChartObject.layer` (structure|fibonacci|fvg|breaks|claude|user_trades|backtest) â€” rÃ©trocompat ; id inchangÃ©
8. Pastilles calques + menu (FVG/Fib/Cassures vides jusquâ€™Ã  T9) ; prefs globales

### Ã‰carts volontaires vs captures 01â€“07

| # | Ã‰cart | Pourquoi |
| --- | --- | --- |
| 01 | Pas de TF **5m** | `INTERVALS` moteur = 15m/1h/4h/1d |
| 01â€“07 | Couleurs / polices **camap-tokens** | Contrainte IchiVol (pas maquette pixel) |
| 05 | Analyse = BiasPanel (pipeline Directionâ†’RÃ©gime) + CTA paper | RÃ©utilise le pipeline existant |
| Journal | Placeholder Â« bientÃ´t Â» | Hors scope UI-MARKET |

### Captures (Ã©tats 01â†’07)

<img alt="01 Desktop dÃ©faut" src="/opt/cursor/artifacts/01-desktop-default.png" />
<img alt="02 Desktop Calques + Backtest" src="/opt/cursor/artifacts/02-desktop-layers-backtest.png" />
<img alt="03 Mobile graphe" src="/opt/cursor/artifacts/03-mobile-chart.png" />
<img alt="04 Mobile tiroir Liste" src="/opt/cursor/artifacts/04-mobile-drawer-list.png" />
<img alt="05 Mobile tiroir Analyse" src="/opt/cursor/artifacts/05-mobile-drawer-analysis.png" />
<img alt="06 Mobile feuille Calques" src="/opt/cursor/artifacts/06-mobile-layers-sheet.png" />
<img alt="07 Mobile recherche" src="/opt/cursor/artifacts/07-mobile-search.png" />

**Cursor sâ€™arrÃªte ici** (entrÃ©e historique ; voir ORDRE DU JOUR CONSOLIDÃ‰ en tÃªte).


---

## 2026-09-24 â€” T9a MERGÃ‰E (#52) â€” squash `985c4e5` â€” un seul dÃ©tecteur de swings causal

- Branche merge : squash sur `main` â†’ `985c4e5`
- PR : https://github.com/samiriggui-code/IchiVol/pull/52 â€” **MERGÃ‰E** (validÃ© Claude)
- **VÃ©rifiÃ©** : `git rev-parse origin/main` == `985c4e5`

## 2026-09-24 â€” T9b EN COURS â€” CHoCH + break quality (rebase post-T10a)

- Branche : `cursor/t9b-choch-break-quality-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/53 (**draft**)
- Base cible : `main` @ `2e3ebc1` (#55 T10a)
- Statut : **REBASE EN COURS** â€” Cursor solo (Claude restreint). Pas de FVG / pas de changement dÃ©cision.

### LivrÃ© (contenu #53)

1. `StructureEvent {type BOS|CHOCH, direction, level, bar, break_quality wick|close|confirmed, displacement_atr, rvol}`
2. CHoCH = cassure **contre** le biais ; BOS event = **dans le sens** du biais (MIXED/UNKNOWN â†’ BOS)
3. `confirmed` = params `confirm_bars` **ou** `confirm_displacement_atr`
4. Feature `bos_bullish` / `bos_bearish` **bit-identiques** (golden) ; nouvelles : `choch_bullish` / `choch_bearish` / `break_quality`
5. Anti-lookahead confirmed + mÃ¨che â‰  clÃ´ture
6. `recalc_short_entry_fee.py` : timestamp `#51` mergedAt, journal `SHORT_FEE_RECALC`, test double `--apply`

### DÃ©cisions documentÃ©es (ordre du jour Â§0 / Â§4)

- **`bos_bullish` non scindÃ©** : volontaire â€” compat golden + ablation Lab (`C_BOS`). Un break haussier en biais baissier reste `bos_bullish=True` au bit legacy ; le type riche est dans `StructureEvent.type=CHOCH`. Scission future = **nouvelle** feature, pas de mutation de `bos_bullish`.
- **Statut T10a** : indicateur `structure` reste **PRODUCTION** (pipeline lit bias/BOS). Champs Lab `choch_*` / `break_quality` = **EXPERIMENTAL** jusquâ€™Ã  lecture pipeline (pas encore).
- Fee recalc : dry-run dÃ©faut ; idempotence via journal â€” **`--apply` non lancÃ©**.



### Inventaire (3 dÃ©tecteurs â†’ 1 core)

| Avant | AprÃ¨s |
| --- | --- |
| `indicators/structure.py` boucle fractal inline | consomme `app.indicators.pivots.fractal_confirmed_at` |
| `fibonacci/context.py` `_fractal_pivots` | wrapper mince â†’ `detect_causal_ohlc_fractals` |
| `structure/adapters/{mvpp,trendln,pytrendline}` boucles propres | confirment via `fractal_confirmed_at` / `detect_causal_extrema` |

SpÃ©cifique **conservÃ©** (doc `structure/T9A_ADAPTERS.md`) : MVPP prix adaptatifs + qualitÃ© volume ; trendln clusters/diagonales ; pytrendline ancres provisoires ; structure HH/HL+BOS ; Fib impulse + ratios (defaults 2/2).

### Contrat causal

Pivot Ã  `j` connu seulement Ã  `i = j + right`. Test anti-lookahead : `tests/indicators/test_t9a_causal_pivots.py`. Goldens structure + fibonacci **inchangÃ©es** (parity inline / seed).

**(EntrÃ©e historique Â« EN COURS Â» corrigÃ©e â†’ MERGÃ‰E.)**

---

## 2026-09-24 â€” T0-FIX-SHORT-FEE MERGÃ‰E (#51) â€” squash `b9f8421` â€” dette SHORT soldÃ©e

- Branche merge : squash sur `main` â†’ `b9f8421`
- PR : https://github.com/samiriggui-code/IchiVol/pull/51 â€” **MERGÃ‰E** (validÃ© Claude)
- **VÃ©rifiÃ©** : `git rev-parse origin/main` == `b9f8421` ; `git log` tip = fix SHORT fee.

### Effet

SHORT `realized` dÃ©duit dÃ©sormais `entry_fee` (open + renforts) sur close / partiel / Ã©puisement / preview â€” alignÃ© cash.

### Historique prÃ©-fix

Lots SHORT CLOSED **avant** ce squash : realized **surÃ©valuÃ© de entry_fee**. Compte Cursor (DB locale) : **0** CLOSED SHORT. Script one-off (pas Alembic) : `scripts/recalc_short_entry_fee.py` (dry-run par dÃ©faut ; `--apply` si base avec historique > 0).

---

## 2026-09-24 â€” T0-MANAGE-f MERGÃ‰ (#50) â€” squash `7a77424` â€” T0-MANAGE terminÃ©

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe` â€” PR #50 â€” **MERGÃ‰E** `7a77424`
- Suite PG Claude (re-revue) : **944 ok / 1 skip**, 0 rÃ©gression
- Sondes LONG+SHORT : dÃ©faut sans max_exposure â†’ 2 renforts ; niveau 1R figÃ© (friction) ; risque aprÃ¨s add = R0 ; ligne fermÃ©e = Î£ fills ; LONG cash = rÃ©alisÃ©
- **VÃ©rifiÃ© post-merge** : `origin/main` tip = `7a77424`
- **T0-MANAGE aâ†’f = terminÃ©**

---

## 2026-09-24 â€” T0-MANAGE-f CORRECTIONS revue Claude #50

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/50 (**draft**)
- Statut : **SUPERSEDÃ‰** â€” corrigÃ© puis **MERGÃ‰** `7a77424` (voir entrÃ©e ci-dessus).
- Suite PG Claude (passe 1) : **941 ok / 1 skip**, 0 rÃ©gression ; conservation cash = rÃ©alisÃ© OK.

### Corrections demandÃ©es (fait)

1. **Paper `max_exposure`** : plafond **notional / equity** (`notional_aprÃ¨s_add â‰¤ max_exposure Ã— equity`) via `cap_add_by_notional_equity` â€” dÃ©faut 1.0 **autorise** les ajouts tant que le notional reste â‰¤ equity. Lab garde `cap_add_by_exposure` (qty) ; rÃ©sultats/expÃ©riences avec `max_exposure > 1` marquÃ©s **`levier: true`**.
2. **CLOSE** : `qty` / `entry_fee` / `notional` = `initial_*` + Î£ `paper_reinforce_adds` (pas le seul open initial).
3. **Trigger `at_r_multiple`** : ancrÃ© sur `initial_entry` figÃ© dans le blob (jamais `pos.entry_price` post-VWAP).
4. **Watcher** : simulation d'add avec le **mÃªme fill** que le broker (`apply_entry_friction`) ; plus de fallback silencieux sur prix brut (l'erreur remonte).

### Tests ajoutÃ©s

- Renfort effectif avec dÃ©faut paper (`max_exposure` omis)
- Ligne fermÃ©e = Î£ fills (qty/fee/notional)
- 2 renforts successifs au niveau R figÃ© (dip entre rising-edges)
- SHORT tighten + CLOSED totals
- Lab `is_leverage_exposure` / flag `levier`

---

## 2026-09-24 â€” T0-MANAGE-f EN COURS â€” renforcement paper (PR draft)

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/50 (**draft**)
- Base : `main` @ `389fc40` (#49 squash)
- Statut : **SUPERSEDÃ‰** â€” voir MERGÃ‰ ci-dessus.

### PrÃ©requis tranche (livrÃ©s)

1. **`max_exposure` dÃ©faut 1.0** â€” Lab qty-unit ; paper **notional/equity** (corrigÃ© revue #50)
2. **ContrÃ´le cash/marge** dans `reinforce_add_capital_position` â€” refuse (`None`) si `notional+fee > cash` ; jamais de partial-fill silencieux
3. Gate `user_confirmed` + `protection_reinforce` ; exclusif vs `protection_partial_tp`
4. Trigger paper : `at_r_multiple` sur **entrÃ©e initiale figÃ©e** ; rising-edge latch `prev_match`
5. PrioritÃ© manage : stop > partials > target > reinforce > trail (mÃªme ordre Lab)
6. Migration `paper_reinforce_adds` ; journal `REINFORCE`

### Tests (Cursor)

- Lab `test_t0_manage_e_reinforce` + `tests/paper/test_protection.py` (dont reinforce) : **verts** sur ce HEAD
- PG local : migration `e1f2a3b4c5d6` appliquÃ©e ; tests reinforce paper OK

### Attente Claude

1. Relire le diff PR (corrections)
2. Suite Postgres complÃ¨te
3. Valider notional/equity + CLOSE totals + R figÃ© + fill friction
4. **Pas de merge** / pas de T9 sans ok explicite

**Cursor sâ€™arrÃªte ici.**

---

## 2026-09-24 â€” T0-MANAGE-e MERGÃ‰ (#49) â€” squash `389fc40`

- Branche : `cursor/t0-manage-e-reinforce-lab-a2fe` â€” PR #49 â€” **MERGÃ‰E** `389fc40` (= tip validÃ© adff686)
- Suite PG Claude : **935 ok / 1 skip**, 0 rÃ©gression
- Sondes : tighten_stop en profit â†’ R0 ; risque signÃ© ; rejet combo partial+reinforce ; fuzz 300 seeds / 135 adds jamais > R0 ; Î£net=Î£bars 3,5e-16
- **VÃ©rifiÃ© post-merge** : `origin/main` tip = `389fc40`

---

## 2026-09-24 â€” T0-MANAGE-e CORRECTIONS revue Claude #49

- Branche : `cursor/t0-manage-e-reinforce-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/49 (**draft**)
- Statut : **SUPERSEDÃ‰** â€” corrigÃ© puis **MERGÃ‰** `389fc40` (voir entrÃ©e ci-dessus).
- Process : #48 squash-mergÃ© sur `main` (`a941539`) ; #49 rebasÃ©.

### Corrections demandÃ©es (fait)

1. DÃ©faut `risk_policy` â†’ **`tighten_stop`** (`reduce_qty` reste option)
2. `open_risk` **signÃ©** : LONG `max(0, avgâˆ’stop)Ã—qty` ; SHORT `max(0, stopâˆ’avg)Ã—qty`
3. Parse **rejette** `partial_tp` + `reinforce` ensemble (message clair)
4. Tests : tighten_stop en profit ; rejet combo ; open_risk stop au-delÃ  du prix moyen ; reduce_qty bloque add au-dessus du avg (structurel)

### Non-bloquant

- `max_exposure` (dÃ©faut 1.0) â€” dette avant comparaison rulesets / obligatoire paper â†’ **implÃ©mentÃ© dans #49 + T0-MANAGE-f** ; dette documentation / comparaisons **conservÃ©e**

---

## 2026-09-24 â€” T0-MANAGE-d MERGÃ‰ (#48) â€” squash `a941539`

- Branche : `cursor/t0-manage-d-partial-tp-paper-a2fe` â€” PR #48 â€” **MERGÃ‰E** `a941539`
- Suite PG Claude : **918 ok / 1 skip** (re-revue), puis baseline post-merge **928 ok / 1 skip**
- Sondes : financement Ã  l'Ã©puisement ; `entry_fee` restaurÃ© ; cash=rÃ©alisÃ© LONG ; `pnl_pct` VWAP ; Ã©puisement+target mÃªme barre â†’ une clÃ´ture
- Caveat backfill `initial_entry_fee` (lots dÃ©jÃ  partialisÃ©s avant migration)

---

## 2026-09-23 â€” T0-MANAGE-c MERGÃ‰ (#47) â€” revue Claude en local

- Branche : `cursor/t0-manage-c-partial-tp-lab-a2fe` â€” PR #47 â€” **MERGÃ‰E** `6116850`

### Les 3 corrections demandÃ©es sont en place

1. `Trade.log_return = sign Ã— log(VWAP/entry)` via `partial_tp.log_return_from_vwap` â€” plus de somme pondÃ©rÃ©e de logs. `exit_price` = VWAP : les deux champs restent mutuellement cohÃ©rents pour T4a et `compute_metrics`.
2. PrioritÃ© `stop > partiels (R croissant) > target > signal` â€” commentÃ©e dans le code, conservatisme du stop prÃ©servÃ©. `mfe_r` n'utilise que le high/low de la barre courante (pas de lookahead). `take = min(step.fraction, remaining)` empÃªche de sur-clÃ´turer.
3. Frais et taille : chaque fill est dÃ©composÃ© en sous-trade de fraction `f` de l'entrÃ©e jusqu'Ã  sa propre sortie, ce qui fait Ã©merger naturellement **et** la pondÃ©ration de taille aprÃ¨s chaque partiel **et** les frais corrects (Î£ frais d'entrÃ©e = `cost`, Î£ frais de sortie = `cost`).

### Invariant â€” vÃ©rifiÃ© indÃ©pendamment (pas seulement via le test de Cursor)

Sonde maison sur 9 combinaisons (3 configs de paliers Ã— volatilitÃ©s 2/5/10 %, 12 seeds chacune) :

**pire Ã©cart `Î£ net_log_return(trades)` vs `Î£ bar_returns + eod_return` = 4,44e-16** â€” soit ~7 ordres de grandeur sous le seuil de 1e-9 exigÃ©. L'invariant T0-METRICS-2 tient rÃ©ellement.

### Le rÃ©sidu de Jensen : acceptÃ©, mais mesurÃ© â€” et il n'est pas bornÃ©

La tension signalÃ©e par Cursor est **rÃ©elle**, pas un artefact : un P&L Ã  exposition variable ne peut pas Ãªtre reprÃ©sentÃ© exactement comme une somme de log-returns pondÃ©rÃ©s (les logs ne s'additionnent que pour une taille constante). Le total correct est `log(VWAP/entry)` ; le chemin barre-par-barre somme Ã  `Î£ fÂ·log`. L'Ã©cart est soakÃ© sur la barre de sortie finale.

C'est dÃ©fendable : le **total est exact** (donc `metrics.total_return`, qui est une somme, est juste), seule la **rÃ©partition intra-trade** est approximÃ©e. Et l'erreur va dans le sens conservateur (equity intra-trade lue trop basse, donc DD surestimÃ©, jamais sous-estimÃ©).

**Mais la magnitude n'avait pas Ã©tÃ© chiffrÃ©e.** MesurÃ©e :

| volatilitÃ©/barre | rÃ©sidu par trade |
|---|---|
| 2 % | 5â€“8 bps |
| 5 % | 26â€“47 bps |
| 10 % | **115â€“224 bps** |

Il croÃ®t en volÂ², sans borne. Ã€ 10 % de volatilitÃ© par barre â€” banal en crypto â€” c'est jusqu'Ã  **2,24 % dÃ©placÃ©s sur une seule barre**.

**ConsÃ©quence concrÃ¨te Ã  ne pas oublier** : un ruleset sans partiels a un rÃ©sidu **nul**. Comparer son drawdown Ã  celui d'un ruleset avec partiels, c'est comparer une mesure exacte Ã  une mesure biaisÃ©e Ã  la hausse. Or le Strategy Lab sert prÃ©cisÃ©ment Ã  ce type de comparaison, et l'argument produit du PIPELINE repose justement sur le drawdown (30,1 % â†’ 5,1 %). Les partiels seraient donc pÃ©nalisÃ©s sur le DD par un artefact comptable, pas par leur comportement rÃ©el.

**Pas bloquant ici** (Lab only, rien de live ne consomme Ã§a, totaux exacts), mais Ã  corriger avant tout arbitrage partiels vs non-partiels sur le drawdown. Piste la moins invasive : rÃ©partir le rÃ©sidu au prorata sur les barres de la derniÃ¨re jambe au lieu de le concentrer sur une seule â€” le total reste exact et le pic disparaÃ®t, sans toucher Ã  la propriÃ©tÃ© de troncature openâ†’open de #24.

### Tests (local, Postgres)

- `tests/strategy_lab` : 108/108 OK (golden `ruleset_backtest_golden.json` inchangÃ©)
- `tests/api tests/paper tests/backtest` : 3 Ã©checs, tous prÃ©existants et connus â€” aucun nouveau vs `main`

---

## 2026-09-23 â€” T0-MANAGE-c EN COURS â€” partial TP Strategy Lab (backtest only)

- Branche : `cursor/t0-manage-c-partial-tp-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/47 (**draft**)
- Statut : **ATTENTE CLAUDE** â€” CI Ã  confirmer ; **ne pas merger** ; **pas de T0-MANAGE-d**.

### LivrÃ©

1. `app/strategy_lab/partial_tp.py` â€” `PartialTpStep` / `PartialExit` + niveaux R / VWAP / `log_return_from_vwap`
2. `ExitSpec.partial_tp` â€” parse strict (#45+) : `]0,1[`, somme â‰¤ 1, R strictement croissants, chaque R `< target_atr/stop_atr`, `bool`/clÃ©s inconnues rejetÃ©s
3. `ruleset_backtest.simulate_ruleset_trades` â€” prioritÃ© **stop > partials > target > signal > trail** ; `Trade` agrÃ©gÃ© via VWAP ; `RulesetTradeDetail.partial_exits`
4. `_apply_fills_hold_returns` â€” chemin taille-pondÃ©rÃ© + frais `costÃ—fraction` par fill ; **rÃ©sidu de Jensen** (Î£ fÂ·log vs log(VWAP)) absorbÃ© sur la derniÃ¨re barre de sortie pour tenir T0-METRICS-2
5. Tests `test_t0_manage_c_partial_tp.py` â€” parse, VWAPâ‰ weighted-log, stop>partial, partial>target mÃªme barre, **invariant Î£ net == Î£ bars** avec partiels, golden inchangÃ©

### Non-fait

- Paper (T0-MANAGE-d) ; renforcement ; UI ; builtins catalog

### Tests locaux (Cursor)

```text
pytest tests/strategy_lab/test_t0_manage_c_partial_tp.py \
       tests/strategy_lab/test_t0_manage_a_trail.py \
       tests/strategy_lab/test_ruleset_backtest.py \
       tests/strategy_lab/test_ruleset_backtest_golden.py \
       tests/backtest/test_t0_metrics_net.py \
       tests/strategy_lab/test_ruleset.py -q
# 55 passed
```

### Note revue (rÃ©conciliation corr. 1 â†” 3)

`Trade.log_return = signÂ·log(VWAP/entry)` (corr. Claude #1). Le chemin barre taille-pondÃ©rÃ© somme naturellement Î£ fÂ·log (Jensen). Le delta est soakÃ© sur la barre de sortie finale â€” invariant 1e-9 tenu ; les barres intermÃ©diaires restent size-weighted.

---

## 2026-09-23 â€” T0-MANAGE-b MERGÃ‰ (#46) â€” revue Claude en local

- Branche : `cursor/t0-manage-b-trail-paper-a2fe` â€” PR #46 â€” **MERGÃ‰E** `93003a1`

### VÃ©rifiÃ© (diff rÃ©el, pas le rÃ©sumÃ©)

1. **Chemin de calcul unique respectÃ©** â€” `protection.py` appelle `stop_trail.update_trailing_stop`, aucune rÃ©implÃ©mentation parallÃ¨le de la logique de trail. C'Ã©tait le point de vigilance nÂ°1 du brief.
2. **No-lookahead** â€” mÃªme contrat qu'en Lab : check de sortie au stop courant *puis* ratchet ; le nouveau niveau ne s'applique qu'Ã  la barre suivante.
3. **Watermark** â€” piÃ¨ge correctement Ã©vitÃ© : sur le chemin trail le watermark avance **toujours** (`if trail_cfg is not None or â€¦`). Sans Ã§a, un scan ultÃ©rieur rejouerait des barres dÃ©jÃ  passÃ©es contre un stop dÃ©jÃ  remontÃ© et **inventerait de faux stop hits**. C'est le bug non Ã©vident de cette tranche, il est traitÃ© et documentÃ© dans le code.
4. **Gate** â€” `trail_cfg = None if legacy else â€¦` + `source == user_confirmed` + config `protection_trail` explicite : ni les lots `auto_watchlist`, ni les positions legacy, ni l'historique reconstruit ne peuvent Ãªtre trailÃ©s. Test dÃ©diÃ© pour chacun.
5. **Ratchet doublement garanti** â€” `update_trailing_stop` (max/min) *et* garde dÃ©fensive dans `_persist_trail_stop` avant Ã©criture DB.
6. **Aucun test affaibli** â€” les modifications de tests existants sont des corrections d'**isolation** (`assert [r["status"] for r in rep] == ["closed"]` â†’ lookup par `position.id`), pas des assouplissements : la mÃªme exigence sÃ©mantique est conservÃ©e, seule la portÃ©e est correctement limitÃ©e Ã  la position du test. Effet de bord bÃ©nÃ©fique : les 4 faux Ã©checs `test_protection.py` sur base non vierge disparaissent (7 â†’ 3 Ã©checs sur la suite large en local).

### Tests (local, Postgres)

- `tests/paper/test_protection.py` : 16/16 OK
- `tests/paper tests/api tests/strategy_lab` : 3 Ã©checs, tous prÃ©existants et connus (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_overview_marks_budget` timing) â€” aucun nouveau vs `main`.

### RÃ©serves non bloquantes (Ã  traiter plus tard, pas de retouche demandÃ©e maintenant)

1. **`atr_ref` par dÃ©faut = distance au stop, pas l'ATR.** Dans `resolve_paper_trail`, quand `atr_ref` n'est pas fourni : `atr_ref = abs(entry_price - initial_stop)`. Or le stop initial vaut `stop_atr Ã— ATR`. Avec `stop_atr = 2.0`, un `atr_trail_mult: 1.5` traÃ®ne donc en rÃ©alitÃ© Ã  **3Ã— ATR**, pas 1,5Ã—. Pas dangereux (stop plus large = jamais de clÃ´ture prÃ©maturÃ©e) mais l'intention exprimÃ©e n'est pas celle appliquÃ©e. Ã€ rÃ©soudre en passant l'ATR rÃ©el, ou en documentant explicitement que le multiplicateur est relatif au risque initial et non Ã  l'ATR.
2. **Parse plus permissif qu'en Lab.** `_parse_trail_raw` n'Ã©carte pas `bool` (`breakeven_at_r: true` â†’ `1.0`) et ignore les clÃ©s inconnues, alors que `_parse_trail_spec` (Lab, #45) rejette les deux. Chemin interne, risque faible, mais deux portes d'entrÃ©e pour la mÃªme config devraient valider pareil.

---

## 2026-09-23 â€” T0-MANAGE-b EN COURS â€” trail / breakeven paper (protection)

- Branche : `cursor/t0-manage-b-trail-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/46 (**draft**)
- Statut : **ATTENTE CLAUDE** â€” CI Ã  confirmer ; **ne pas merger** ; **pas de T0-MANAGE-c**.

### LivrÃ©

1. `app/paper/protection_trail.py` â€” gate `user_confirmed` + `protection_trail` explicite (`entry_signal` > `strategy_profile`) ; `freeze_trail_anchor` pour figer `initial_stop` / ATR aprÃ¨s le 1er cycle
2. `app/paper/protection.py` â€” `find_breach_with_trail` : check exit puis `stop_trail.update_trailing_stop` (mÃªme chemin Lab) ; watermark toujours avancÃ© sur le chemin trail (pas de re-scan des barres passÃ©es contre un stop dÃ©jÃ  ratchetÃ©) ; journal `PROTECTION_TRAIL_UPDATED` ; legacy / historique : jamais de trail sur reconstruction
3. Tests `tests/paper/test_protection.py` â€” gate resolve ; BE next-bar only ; ratchet ATR ; cycle DB portfolio trail â†’ BE puis close ; `auto_watchlist` ignore le trail portefeuille ; sans config = inchangÃ©
4. Assertions DB scopÃ©es par `position.id` (base locale non vierge avec lots ouverts type NDX)

### Non-fait

- Pas de prise de profit partielle (T0-MANAGE-c/d)
- Pas de renforcement (T0-MANAGE-e/f)
- Trail non activÃ© par dÃ©faut ; pas dâ€™UI dÃ©diÃ©e

### Tests locaux (Cursor)

- `pytest tests/paper/test_protection.py tests/strategy_lab/test_t0_manage_a_trail.py` : 24/24 OK (venv engine)

---

## 2026-09-23 â€” T0-MANAGE-a MERGÃ‰ (#45) â€” revue Claude en local

- Branche : `cursor/t0-manage-a-trail-lab-a2fe` â€” PR https://github.com/samiriggui-code/IchiVol/pull/45 â€” **MERGÃ‰E** `e6118c7`
- **Revue** : diff rÃ©el relu (`stop_trail.py`, `ruleset.py`, `ruleset_backtest.py`) â€” confirmÃ© aucun lookahead : le stop vÃ©rifiÃ© Ã  la barre `j` vient de la mise Ã  jour calculÃ©e Ã  la barre `j-1` (jamais la barre courante en avance) ; ratchet appliquÃ© via `max`/`min` strict (LONG ne recule jamais Ã  la baisse, SHORT jamais Ã  la hausse) ; breakeven couvre bien le round-trip de frais ; validation de parse stricte (clÃ©s inconnues rejetÃ©es, `bool` rejetÃ© comme nombre, valeurs â‰¤ 0 rejetÃ©es).
- `pytest tests/strategy_lab/test_t0_manage_a_trail.py tests/strategy_lab/test_ruleset_backtest.py tests/strategy_lab/test_ruleset_backtest_golden.py tests/strategy_lab/test_ruleset.py` : 33/33 OK
- `pytest tests/strategy_lab tests/api` (suite large) : mÃªmes 2 Ã©checs prÃ©existants liÃ©s aux donnÃ©es rÃ©elles de `ichivol_engine_dev` (pas de rÃ©gression, cf. note baseline en haut de ce fichier)
- Golden `ruleset_backtest_golden.json` inchangÃ© (trail absent partout dans le catalogue actuel) â€” confirmÃ©.
- **Prochain job : T0-MANAGE-b** (paper) â€” voir spec ci-dessous.

---

## 2026-09-23 â€” T0-MANAGE-a EN COURS â€” trail / breakeven Strategy Lab (backtest only)

- Branche : `cursor/t0-manage-a-trail-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/45 (**draft**)
- Statut : **ATTENTE CLAUDE** â€” CI Ã  confirmer ; **ne pas merger** ; **pas de T0-MANAGE-b**.

### LivrÃ©

1. `app/strategy_lab/stop_trail.py` â€” `TrailSpec` + `update_trailing_stop` / ratchet / breakeven (frais RT) / ATR trail (helpers purs, prÃªts pour paper T0-MANAGE-b)
2. `ExitSpec.trail` optionnel â€” parse / `to_dict` ; `breakeven_at_r` et/ou `atr_trail_mult` (> 0)
3. `ruleset_backtest.simulate_ruleset_trades` â€” stop initial figÃ© Ã  lâ€™entrÃ©e ; **recalcul bar-par-bar aprÃ¨s** checks stop/target/signal (nouveau niveau = barre suivante) ; jamais de recul
4. PrioritÃ© intra-bar inchangÃ©e : stop > target > signal > max_hold/eod
5. Tests `test_t0_manage_a_trail.py` â€” property ratchet (200), breakeven exact Ã  1R, ATR trail, parse roundtrip, pas de trail = comportement fixe
6. Golden `ruleset_backtest_golden.json` â€” **inchangÃ©** (trail absent)

### Validation locale (Cursor, sans Postgres)

```text
pytest tests/strategy_lab/test_t0_manage_a_trail.py \
       tests/strategy_lab/test_ruleset_backtest.py \
       tests/strategy_lab/test_ruleset_backtest_golden.py -q
# 21 passed
```

### Non-faits (volontaire)

Paper / protection ; partial TP ; renforcement ; UI ; auto-apply trail sur catalog builtins.

### Attente

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  revue Claude (diff rÃ©el + suite Postgres complÃ¨te).

---

## 2026-09-23 â€” T0-MANAGE â€” dÃ©coupage dÃ©taillÃ© (prÃªt pour Cursor)

Spec originale (une phrase, doc Feuille de route) : *stop suiveur ou remontÃ© Ã  l'entrÃ©e, prise de profit partielle, renforcement â€” le risque total ne dÃ©passe jamais le risque initial. Chaque outil testÃ© d'abord en Strategy Lab (DSL + backtest net), activable en paper seulement aprÃ¨s.*

Rien de Ã§a n'existe en code aujourd'hui. DÃ©coupage en 6 sous-tranches, **une PR par sous-tranche**, ordre imposÃ© (chaque paire *Lab d'abord, paper ensuite* ; ne pas sauter Ã  la reinforcement avant que stop/TP partiel soient validÃ©s) :

### T0-MANAGE-a â€” Stop suiveur / breakeven â€” Strategy Lab (backtest only)

- Ã‰tendre `ExitSpec` (`app/strategy_lab/ruleset.py`) : nouveau champ optionnel, ex. `trail: TrailSpec | None` avec soit `breakeven_at_r: float` (remonte le stop au prix d'entrÃ©e + frais une fois `r_multiple` atteint), soit `atr_trail_mult: float` (stop = `close Â± atr_trail_mult * ATR`, ne se resserre jamais cÃ´tÃ© perte â€” ratchet unidirectionnel).
- `app/strategy_lab/ruleset_backtest.py` : aujourd'hui `_levels()` calcule stop/target **une fois** Ã  l'entrÃ©e (ligne ~228, boucle Â« une position Ã  la fois Â»). Il faut recalculer le stop **bar par bar aprÃ¨s l'entrÃ©e**, sans lookahead (le nouveau stop d'un bar N ne peut utiliser que high/low/close â‰¤ bar N), et ne jamais le reculer par rapport Ã  sa valeur prÃ©cÃ©dente.
- PrioritÃ© intra-bar existante (stop > target > signal > max_hold/eod) inchangÃ©e ; seul le niveau du stop devient mobile.
- Tests : ratchet ne recule jamais (property test, N sÃ©quences alÃ©atoires) ; breakeven se dÃ©clenche exactement Ã  `r_multiple` atteint, pas avant ; golden `ruleset_backtest_golden.json` **inchangÃ©** pour les rulesets existants (trail absent = comportement actuel).
- **Non-fait** : rien en paper ; pas de prise de profit partielle ; pas de renforcement.

### T0-MANAGE-b â€” Stop suiveur / breakeven â€” paper (aprÃ¨s validation Lab)

- Ne dÃ©marre qu'aprÃ¨s revue Claude de T0-MANAGE-a.
- Brancher sur `app/paper/protection.py` (dÃ©jÃ  un watcher bar-par-bar indÃ©pendant des signaux, avec le mÃªme principe no-lookahead dÃ©crit dans son docstring) â€” appliquer la mÃªme logique de stop mobile validÃ©e en backtest.
- Gate explicite : activable par position ou par portefeuille (pas par dÃ©faut sur tout l'historique) ; seulement `user_confirmed` dans un premier temps (comme T0-NOTIF).
- Invariant : le stop ne recule jamais ; jamais d'ouverture/fermeture hors de la logique protection existante.
- Tests : reprendre les fixtures de `tests/paper/test_protection.py` + cas trail-spÃ©cifiques.

### T0-MANAGE-c â€” Prise de profit partielle â€” Strategy Lab (backtest only)

- `PaperPosition` / `Trade` sont aujourd'hui **single-fill** (un seul `qty`, un seul `exit_price`). Une prise de profit partielle est un changement de modÃ¨le, pas juste une rÃ¨gle DSL.
- DSL : nouveau champ `partial_tp: list[{r_multiple: float, fraction: float}]` sur `ExitSpec` (ex. `[{r_multiple: 1.0, fraction: 0.5}]` = clÃ´turer 50 % Ã  1R).
- Backtest : `Trade` doit pouvoir reprÃ©senter plusieurs fills de sortie (ou une liste de `PartialExit`) ; PnL net = somme pondÃ©rÃ©e ; `r_multiple` du reliquat recalculÃ© sur la qty restante.
- Tests : invariant Î£ (qty partielle Ã— pnl) + (qty restante Ã— pnl finale) == pnl total sur qty pleine ; golden inchangÃ© si `partial_tp` absent.
- **Non-fait** : paper ; renforcement.

### T0-MANAGE-d â€” Prise de profit partielle â€” paper (aprÃ¨s validation Lab)

- Ã‰tendre `PaperPosition` (nouvelle table `paper_partial_exits` plutÃ´t que muter les colonnes existantes â€” garder `paper_positions` single-row pour la position "vivante", journaliser chaque prise partielle comme une ligne, pattern proche de `ledger_transactions`/`ledger_legs`).
- `qty` de la position OPEN diminue Ã  chaque prise partielle ; `realized_pnl` cumule ; la position reste `OPEN` tant qu'il reste de la qty.
- UI : historique des prises partielles sur la fiche position (Paper).
- Tests : qty ne peut jamais devenir nÃ©gative ; fermeture finale (stop/target/signal) solde le reliquat exact.

### T0-MANAGE-e â€” Renforcement (pyramiding) â€” Strategy Lab (backtest only)

- DSL : condition de dÃ©clenchement du renforcement (`ConditionGroup` rÃ©utilisÃ©) + rÃ¨gle de sizing de l'ajout.
- **Invariant non nÃ©gociable** (c'est la seule contrainte donnÃ©e dans la spec originale) : aprÃ¨s renforcement, le risque total ouvert (distance au stop Ã— qty totale, prix moyen pondÃ©rÃ©) **ne doit jamais dÃ©passer** le risque initial de la position avant renforcement. Si l'ajout au sizing normal violerait Ã§a, soit la qty ajoutÃ©e est rÃ©duite, soit le stop est resserrÃ© pour compenser â€” Ã  trancher en revue avant merge (Cursor propose les deux options, Claude choisit).
- Tests : construire des cas oÃ¹ renforcement + stop initial dÃ©passeraient le risque â†’ doit Ãªtre bloquÃ©/rÃ©duit, jamais silencieusement ignorÃ©.
- **Non-fait** : paper.

### T0-MANAGE-f â€” Renforcement â€” paper (aprÃ¨s validation Lab)

- Brancher sur `app/paper/broker.py` (ordre d'ajout) avec la mÃªme vÃ©rification d'invariant *avant* exÃ©cution â€” refuser l'ordre plutÃ´t que l'exÃ©cuter hors invariant.
- **PrÃ©requis tranche** : `max_exposure` (dÃ©faut **1.0**) + contrÃ´le cash/marge disponible **avant chaque ajout**.
- Isolation : ne touche pas aux positions `auto_watchlist` sans confirmation utilisateur explicite (mÃªme logique que T2c pour les user trade points).

### AprÃ¨s T0-MANAGE â€” T9 (roadmap, ne pas dÃ©marrer avant)

- **T9** â€” structure / FVG / Fib (nouvelle tranche feuille de route). **BloquÃ©e** jusqu'Ã  clÃ´ture complÃ¨te de T0-MANAGE (f inclus, revue Claude + merge).

### Grille commune (rappel garde-fous projet, s'applique aux 6 sous-tranches)

- Aucun lookahead : un stop mobile au bar N ne connaÃ®t que les bars â‰¤ N.
- Un seul chemin de calcul : le backtest (Lab) et le paper doivent appeler la **mÃªme** fonction de calcul de stop mobile / partial fill / invariant de risque â€” pas deux implÃ©mentations qui divergent.
- DÃ©terministe, testÃ© avant merge, revue Claude explicite avant chaque merge (rappel incident 18 PR).

### Attente Claude

Cursor attaque **T0-MANAGE-a seul**, PR draft, CI verte, handoff mis Ã  jour, **s'arrÃªte** avant merge et avant T0-MANAGE-b.

---

## 2026-09-23 â€” T0-NOTIF MERGÃ‰ (#44) + UI Lab Research MERGÃ‰ (#43) â€” revue Claude en local

- **Contexte** : reprise du canal Cursor â†” Claude **en local** (Laragon + PostgreSQL 16, mÃªme `ichivol_engine_dev` que la review cloud) aprÃ¨s clonage Ã  jour de `main` (`9ead9e8`, 205 commits, roadmap V3 T0â†’T7 + EIL + Researcher).
- **Revue** : diff des deux PR relu, migrations alembic + Prisma appliquÃ©es, suites de tests + builds relancÃ©s localement sur chaque branche avant merge.

### #43 â€” UI Lab Research

- `pytest tests/api/test_strategy_lab_research_routes.py` : 5/5 OK
- `pytest tests/api tests/paper` (engine complet) : mÃªmes Ã©checs prÃ©existants que sur `main` (donnÃ©es rÃ©elles en base, pas de rÃ©gression â€” voir note ci-dessous)
- `npm run build` (frontend) : OK
- **Merge** : squash, `db5261a`, branche supprimÃ©e

### #44 â€” T0-NOTIF

- `pytest tests/paper/test_scenarios.py` : 10/10 OK
- Migration Prisma `20260923170000_t0_notif_push` appliquÃ©e sur `ichivol_dev`
- `npm test` (server, incl. `positionWatch.test.ts` â€” dÃ©dup, proximitÃ©, grep "aucun open/close paper") : 27/27 OK
- `npm run build` (server + frontend) : OK
- Invariant informative-only confirmÃ© (grep source : pas d'appel open/close paper)
- **Merge** : squash aprÃ¨s rÃ©solution conflit doc avec #43, branche supprimÃ©e

### Note â€” Ã©checs pytest engine non liÃ©s aux PR (dÃ©jÃ  prÃ©sents sur `main` avant ces deux merges)

`ichivol_engine_dev` en local est la base **de travail rÃ©elle** (pas une base de test jetable comme le conteneur Postgres Ã©phÃ©mÃ¨re de la CI GitHub Actions) â€” elle contient de l'historique de positions rÃ©el. 7 tests supposant une base vierge Ã©chouent pour cette raison (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_protection.py` Ã—4, `test_overview_marks_budget` timing) â€” **aucun n'est une rÃ©gression de #43/#44**, vÃ©rifiÃ© en comparant Ã  l'Ã©tat de `main` avant ces merges. Un vrai bug de portabilitÃ© Windows a aussi Ã©tÃ© trouvÃ© et corrigÃ© au passage : `tests/indicators/test_registry_ratchet.py` comparait des chemins avec `/` alors que `Path.relative_to` renvoie du `\` sous Windows (`str(...)` â†’ `.as_posix()`).

---

## 2026-09-23 â€” T0-NOTIF â€” alertes push tÃ©lÃ©phone â€” PRÃŠT REVUE CLAUDE

- Branche : `cursor/t0-notif-push-a2fe`
- PR : (draft â€” lien aprÃ¨s create)
- Base : `main` (ne touche **pas** T0-CALC / EIL / T4b-d / T5a-b / T6 / T7 / T3d / Researcher)

### Objectif

Alerte **informative** sur tÃ©lÃ©phone (Web Push VAPID / PWA) quand une position paper OUVERTE approche objectif/stop, accÃ©lÃ¨re (RVOL + BOS moteur), ou flip Ichimoku. **Jamais dâ€™ordre.**

### LivrÃ©

1. **Infra push** : `PushSubscription` Prisma + migration ; `web-push` ; `sendPushToUser` / `sendPushRaw` (never throw, 410/404 â†’ delete) ; `public/sw.js` + `manifest.webmanifest` ; env `VAPID_*` (jamais commitÃ©s)
2. **Kinds** (ajoutÃ©s) : `position_target_near` | `position_stop_near` | `position_accel` | `position_direction_flip`
3. **Watcher sÃ©parÃ©** `positionWatch.ts` (~60s) â€” **ne modifie pas** `watch.ts` ; filtre `user_confirmed` OPEN + `user_id`
4. **ProximitÃ©** : `scenarios.level_remaining_frac` / `compute_level_proximity` + `GET /paper/positions/{id}/proximity` (mÃªme gÃ©omÃ©trie que T0-CALC)
5. **Accel** : RVOL â‰¥ `rvolConfirm` settings **et** `bos_confirms_direction` du pipeline (pas recalcul local)
6. **DÃ©dup** : cooldown + resserrement de bande (20â†’10â†’5) / `stateKey`
7. **API** : `GET push-vapid-public`, `POST/DELETE push-subscribe` ; prefs `Setting.pushAlertPrefs`
8. **Front** : Settings Â« Alertes push Â» ; deep link `/app/paper?position=&symbol=` ; cloche â†’ Paper
9. **Tests** : server dedup / proximity parity / push soft-fail / grep no-order ; engine proximity unit ; OpenAPI goldens (proximity)

### Flux tÃ©lÃ©phone (si non testable ici)

1. DÃ©ployer avec `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`
2. Android Chrome ou iOS 16.4+ PWA (Â« Ajouter Ã  lâ€™Ã©cran dâ€™accueil Â»)
3. Settings â†’ Activer les alertes (permission) â†’ Enregistrer prefs
4. Position OPEN near target â†’ notif systÃ¨me + ligne cloche ; tap â†’ fiche Paper

### Invariants

- Aucun `open`/`close` paper dans `positionWatch.ts`
- Push Ã©choue â†’ notif in-app quand mÃªme crÃ©Ã©e
- Autre user : positions filtrÃ©es par `user_id` ; notifs scoped `userId`

### Non-faits

Stop suiveur / renforcement (T0-MANAGE) ; actions rapides Â« clore en un tap Â» ; UI Lab #43 (branche sÃ©parÃ©e).

### Attente Claude

1. Relire le diff PR
2. Suite Postgres complÃ¨te sur ce HEAD
3. Valider informative-only + dÃ©dup + proximitÃ© = scenarios
4. Marche Ã  suivre : merge / retouches

**Cursor sâ€™arrÃªte ici** â€” pas de merge, pas de job suivant sans revue explicite.

---

## 2026-09-23 â€” UI Lab Research â€” PRÃŠT REVUE CLAUDE (#43)

- Branche : `cursor/lab-ui-research-t5-t7-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/43 â€” **draft**
- HEAD : `d4deb50` (code `01e79b0` + docs ; CI verte sur `a5a13a1` = mÃªme code)
- Base : `main` @ `9ead9e8` (post Researcher #41/#42)

### Statut CI (Engine CI)

- **VERTE** (HEAD `a5a13a1`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35887098403
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Contexte Vague

AprÃ¨s T1â€“T7 + T3d + Researcher (tous mergÃ©s), suite optionnelle = **UI Lab** (exposÃ©) ou **T3e MTF** (FeatureBar mono-TF â€” trop gros). Cursor a livrÃ© **UI Lab Research** ; T3e **non dÃ©marrÃ©**.

### LivrÃ© (observation-only)

1. **HTTP** `app/api/strategy_lab_research.py` (montÃ© aprÃ¨s `strategy_lab_wf` dans `routes.py`) :
   - `GET /api/engine/strategy-lab/family-weight-profiles`
   - `GET /api/engine/strategy-lab/family-weights/compare`
   - `GET /api/engine/strategy-lab/family-weights/study`
   - `POST /api/engine/strategy-lab/audit-report`
   - `POST /api/engine/strategy-lab/monte-carlo`
   - `POST /api/engine/strategy-lab/propose-experiment-plan`
2. **UI** onglet **Research** sur Strategy Lab (`LabResearchPanel.tsx` + `labResearch.ts`) â€” catalogue poids, compare, Ã©tude, AuditReport, plan Researcher, Monte Carlo
3. Goldens OpenAPI + `route_order` refresh ; `tests/api/test_strategy_lab_research_routes.py` (5 tests)
4. CDC checkbox UI Lab Research (ouverte tant que non mergÃ©e)

### Invariants respectÃ©s

- EVENT â‰  SIGNAL inchangÃ©
- Pas de mutation score live / gate / combiner / confidence
- HypothÃ¨ses Audit + plan Researcher restent `status=proposed`
- Monte Carlo / family weights = research only (disclaimers conservÃ©s)
- Pas dâ€™auto-run des steps Researcher ; pas dâ€™Ã©criture Perf DB depuis propose

### Fichiers (diff vs main)

| Zone | Fichiers |
|------|----------|
| Engine API | `strategy_lab_research.py`, `routes.py` |
| Tests | `test_strategy_lab_research_routes.py`, openapi + route_order goldens |
| Front | `LabResearchPanel.tsx`, `labResearch.ts`, `BacktestsPage.tsx` |
| Docs | `HANDOFF-CURSOR-V3.md`, `CAHIER-DES-CHARGES.md` |

### Non-faits (hors scope #43)

- **T3e MTF DSL** (FeatureBar multi-TF)
- Chat NL / Ã©diteur conversationnel T3d
- Auto-run plan Researcher / auto-apply catalog
- Poids familles en live score
- Rename fichier `BacktestsPage.tsx` â†’ `StrategyLabPage`

### Attente Claude

1. Relire le diff PR #43
2. Suite Postgres complÃ¨te sur ce HEAD (baseline 0 Ã©chec post T0-CI)
3. Valider observation-only (pas de dÃ©rive gate/score)
4. Marche Ã  suivre : **merge** / retouches / enchaÃ®ner T3e

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  la revue Claude.

---

## 2026-09-23 â€” RESEARCHER MERGÃ‰ (#41) â€” propose experiment plan

- Branche : `cursor/researcher-propose-experiment-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/41 â€” **MERGÃ‰E** `64bba88`
- Statut : CI verte ; merge Cursor.

### LivrÃ©

1. `app/researcher/` â€” `propose_experiment_plan(AuditReport)` â†’ steps Lab (`proposed`)
2. Agent `propose_experiment_plan` â€” jamais auto-run / Perf DB

### Non-faits

ExÃ©cution auto des steps ; UI ; T3e MTF.

---

## 2026-09-23 â€” T3d MERGÃ‰ (#39) â€” propose ruleset edit

- Branche : `cursor/t3d-ruleset-propose-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/39 â€” **MERGÃ‰E** `80508c1`
- Statut : CI verte ; merge Cursor.

### LivrÃ©

1. `propose_edit.py` â€” patch ops â†’ `parse_ruleset` ; status toujours `proposed`
2. Catalogue conditions GET `/rulesets` + `list_condition_catalog`
3. `POST /ruleset/propose` + agent `propose_ruleset_edit`
4. OpenAPI golden refresh

### Non-faits

Chat UI ; LLM moteur ; T3e MTF ; auto-apply catalog.

---

## 2026-09-23 â€” T7 MERGÃ‰ (#37) â€” Monte Carlo / risk of ruin â†’ V3 T1â€“T7 DONE

- Branche : `cursor/t7-monte-carlo-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/37 â€” **MERGÃ‰E** `dacbfe0`
- Statut : CI verte ; merge Cursor. **Roadmap V3 T1â†’T7 close.**

### LivrÃ©

1. `app/risk/monte_carlo.py` â€” bootstrap net trade returns â†’ equity paths
2. `risk_of_ruin` (equity â‰¤ ruin_floor) ; percentiles final equity / max DD
3. Gate `min_trades` (dÃ©faut 20) â†’ `sufficient=false` sinon
4. Agent `run_monte_carlo`

### Hors roadmap T (ouverts plus tard)

T3d chat NL / Ã©diteur conversationnel ; T3e MTF DSL ; Researcher loop (auto Experiment) ; UI Lab pour T5â€“T7 ; poids en live score.

---

## 2026-09-23 â€” T6 MERGÃ‰ (#36) â€” AuditReport

- Branche : `cursor/t6-auditor-report-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/36 â€” **MERGÃ‰E** `a2591bf`
- Statut : CI verte ; merge Cursor.

### LivrÃ©

1. `app/auditor/` â€” `AuditReport` + `AuditHypothesis` (`proposed` only)
2. `build_audit_report_from_trade` depuis `RulesetTradeDetail` (WHY + net)
3. Agent `build_audit_report`

### Non-faits

Auto-apply hypothÃ¨ses ; Researcher loop ; UI.

---

## 2026-09-23 â€” T5b MERGÃ‰ (#35) â€” profils poids backtestables

- Branche : `cursor/t5b-weight-profiles-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/35 â€” **MERGÃ‰E** `bacd7bf`
- Statut : CI verte ; merge Cursor.

### LivrÃ©

1. Catalogue `FamilyWeightProfile` (balanced / direction_heavy / participation_heavy / structure_heavy)
2. `compare_family_weight_profiles(pipeline)` â€” table observation
3. `run_family_weights_study` â€” BUY/SELL pipeline bars Ã— forward log returns (causal)
4. Agent : `list_family_weight_profiles`, `compare_family_weights`, `run_family_weights_study`

### Non-faits

Aucun poids en live score ; T6 Auditor ; T7 Monte Carlo ; chat NL / T3d.

---

## 2026-09-23 â€” T5a MERGÃ‰ (#34) â€” family weights observation-only

- Branche : `cursor/t5a-family-weights-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/34 â€” **MERGÃ‰E** `c8c2bc7`
- Statut : CI verte ; merge Cursor.

### LivrÃ©

1. `app/confluence/` â€” `FamilyWeightsConfig` versionnÃ© (`family_weights_v0`) + `observe_family_weights(pipeline)`
2. Familles = StageId pipeline (direction/participation/structure/location/regime)
3. `ScreenerRow.family_weights` + serializers summary/detail ; agent `get_family_weights`
4. Tests `tests/confluence/` (invariants + non-mutation pipeline)

### Non-faits (volontaire)

Aucun changement decision/confidence/combiner/gates ; T5b backtest poids ; chat NL ; T6 Auditor ; T7 Monte Carlo.

---

## 2026-09-23 â€” T4d MERGÃ‰ (#33) â€” filtre rÃ©gime overlay

- Branche : `cursor/t4d-regime-overlay-filter-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/33 â€” **MERGÃ‰E** `079f4cd`
- Statut : CI verte ; merge Cursor (solo).

### LivrÃ©

1. `regime_labels` au signal bar (`classify_regimes`) sur trades / rejected
2. Filtre AND `regime_label` (TRENDING/RANGING/BULL/â€¦) API + agent + sheet
3. OpenAPI golden refresh

### Non-faits

T5a family weights ; chat NL ; changement fills.

---

## 2026-09-23 â€” T4b MERGÃ‰ (#32) â€” filtre overlay

- Branche : `cursor/t4b-overlay-filter-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/32 â€” **MERGÃ‰E**
- Statut : CI verte (OpenAPI golden fix) ; merge Cursor.

---

### LivrÃ©

1. `chart_objects/filter_trades.py` â€” filtres AND outcome / exit_reason / direction / why_entered_key
2. API overlay Ã©tendue + `filters` echo + `n_trades_filtered`
3. Agent read-only `filter_backtest_overlay`
4. Sheet : selects Sortie / Sens (pas de chat NL)
5. Tests unitaires + API

### Non-faits

Filtres rÃ©gime ; T5 confluence ; chat NL dans le sheet ; changement fills/metrics.

---

## 2026-09-23 â€” T4c MERGÃ‰ (#31) â€” WHY overlay

- Branche : `cursor/t4c-why-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/31 â€” **MERGÃ‰E**
- Statut : CI verte ; merge Cursor.

---

### LivrÃ©

1. `evaluator.explain_group` â€” trace pass/fail par feuille (`all`/`any`) sans changer le match
2. `RulesetTradeDetail.why_entered` / `why_exited` ; `RejectedSignal` + `RulesetBacktestResult.rejected`
3. Overlay API : `why_*` sur trades + liste `rejected` ; markers chart `kind=rejected`
4. UI sheet : dÃ©tail WHY ENTERED / EXITED + liste rejetÃ©s
5. Tests `test_t4c_why.py` + parity T4a (golden backtest **inchangÃ©**)

### Non-faits

T4b filtre conversationnel ; filtres rÃ©gime ; T5 confluence ; aucun changement de fills/metrics.

---

## 2026-09-23 â€” EVENT INTELLIGENCE PHASE 7 â€” correlate + SymbolNews â†’ MAIN

- Branche : `cursor/event-correlate-context-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/29 â€” **MERGÃ‰E**
- Statut : CI verte ; merge Cursor (Claude absente). EIL phases 1â€“7 observation **terminÃ©es**.

### LivrÃ©

1. Types : `EventCategory`, `ExternalEventRef`, `EventContextBundle`
2. `app/events/news.py` â€” SymbolNews causal (`published_at â‰¤ T` + relevance symbole)
3. `app/events/classifier.py` â€” taxonomie heuristique (jamais BUY/SELL)
4. `app/events/macro.py` â€” calendar â†’ candidats causals
5. `app/events/correlate.py` â€” match â†’ `EVENT_MARKET` si confidence â‰¥ seuil ; sinon `UNKNOWN_EVENT`
6. Branchement observation-only `scan_symbol` + serializers `event_context` ; agent `get_event_context`
7. Tests anti-lookahead news future / lag / weak match

### Non-faits (hors EIL observation)

Promotion seuils live (walk-forward), FinBERT, CorporateEventProvider scrapers, UI, changement de gates pipeline.

---

## 2026-09-23 â€” EVENT INTELLIGENCE PHASE 6 â€” regime study + calibration â†’ MAIN

- Branche : `cursor/event-regime-study-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/28 â€” **MERGÃ‰E**
- Statut : CI verte ; merge Cursor (Claude absente).

### LivrÃ©

1. `app/events/regime_study.py` â€” event-study PIPELINE stratifiÃ© par `NORMAL_MARKET` / `UNKNOWN_EVENT` (MFE/MAE, horizons, deltas observÃ©s)
2. `app/events/calibrate.py` â€” quantiles causaux â†’ suggestions p99 **sans** muter les seuils live
3. Agent read-only : `run_anomaly_regime_study`, `calibrate_anomaly_thresholds`
4. Tests `tests/events/test_regime_study.py`
5. CDC PHASE 6 cochÃ©

### Non-faits (ouverts en PHASE 7)

SymbolNews, EventClassifier, `EVENT_MARKET`, changement de gates, UI.

---

## 2026-09-23 â€” EVENT INTELLIGENCE PHASE 5 â€” Anomaly Detector (observation-only)

- Branche : `cursor/event-anomaly-detector-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/27 (**draft**)
- Statut : **ATTENTE Claude** â€” CI **VERTE** ; Cursor solo jusquâ€™Ã  18:10 puis revue.
### LivrÃ©

1. `app/events/` â€” `detect_anomaly` causal (past-only z-scores, range/gap vs ATR, RVOL)
2. RÃ©gimes : `NORMAL_MARKET` | `UNKNOWN_EVENT` (pas de `EVENT_MARKET` sans match news â€” PHASE 6+)
3. Branchement `ScreenerRow.market_anomaly` + serializers summary/detail â€” **nâ€™altÃ¨re pas** decision/confidence/pipeline
4. Tests `tests/events/test_anomaly.py` (lookahead / shock / quiet)
5. CDC : T0-CALC + EIL audit + PHASE 5 cochÃ©s ; PHASE 6â€“7 ouverts

### Non-faits (volontaire)

News / earnings / FinBERT / vote pipeline / calibration empirique des seuils.

---

## 2026-09-23 â€” EVENT INTELLIGENCE LAYER â€” AUDIT (PHASES 1â€“4) â†’ MAIN

- Branche : `cursor/event-intelligence-audit-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/26
- Doc : `docs/EVENT-INTELLIGENCE-LAYER-AUDIT.md`
- Statut : rebase sur main post-#25 ; merge Cursor (Claude absente) â€” **doc only**.

### LivrÃ©

1. Audit IchiVol : indicateurs / REGISTRY / pipeline / combiner / calendar+news / Claude / 3 pipelines / collision `EventObservation` Lab
2. KEEP/ADAPT/REJECT sur 7 repos de rÃ©fÃ©rence
3. Architecture : `EventAnomalyDetector` â†’ rÃ©gimes NORMAL/EVENT/UNKNOWN â†’ context â†’ Claude explain ; **EVENT â‰  SIGNAL**
4. Contrats Python (design) + plan phases 5â€“7

### Suite (Cursor solo jusquâ€™Ã  18:10)

PHASE 5 : `EventAnomalyDetector` causal + tests anti-lookahead + branchement **observation-only** (pas de vote pipeline).

---

## 2026-09-23 â€” T0-CALC MERGÃ‰ (#25) â€” Cursor (Claude absente)

- Branche : `cursor/t0-calc-scenarios-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/25 â€” **MERGÃ‰E**
- Statut : intÃ©grÃ©e au chantier V3 (scÃ©narios historiques fiche dâ€™achat + positions). CI verte. Brief Claude respectÃ©.

---

## 2026-09-23 â€” T0-METRICS-2 VALIDÃ‰ par Claude â€” MERGÃ‰ (#24)

- Branche : `cursor/t0-metrics-2-engine-costs-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/24 â€” **MERGÃ‰E** `351dbe9`
- Statut : **validÃ© par Claude** (`eod_return` sÃ©parÃ© de `bar_returns` ; `test_engine_lookahead.py` **identique Ã  main** ; 300 sÃ©quences alÃ©atoires ; suite Postgres 0 Ã©chec).
- Remarque Claude : ne jamais affaiblir un test de non-fuite â€” corriger le code, pas le test.

---

## 2026-09-23 â€” T0-METRICS-2 EN COURS â€” frais engine (flip / EOD / close)

- Branche : `cursor/t0-metrics-2-engine-costs-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/24 (**draft**)
- Commit(s) : `96e5696` (feat) ; fix `eod_return` (voir HEAD)
- Statut : **ATTENTE CI** puis **ATTENTE CLAUDE**.

### Corrections `run_backtest`

1. **Flip** Lâ†”S : `r -= 2 Ã— one_way` ; attribution `one_way` sortie + `one_way` entrÃ©e
2. **EOD** : frais de sortie + mark-to-close dans **`BacktestResult.eod_return`** (pas dans `bar_returns`)
3. **Prix unique EOD** : trade @ `last.close` ; `eod_return = sign Ã— log(last.close/last.open) âˆ’ one_way`
4. **`bar_returns` strictement openâ†’open** â€” propriÃ©tÃ© de troncature restaurÃ©e (test lookahead **inchangÃ©**)

### ComptabilitÃ©

- Invariant : `Î£ net_log_return(trades) == Î£ bar_returns + eod_return` (1e-9)
- `metrics.total_return = exp(Î£ bars + eod) âˆ’ 1` ; max DD inclut un dernier point dâ€™equity avec `eod_return`

### Consommateurs de `bar_returns` / total / equity (audit)

| Consommateur | Chemin | Inclut `eod_return` ? |
|--------------|--------|------------------------|
| `compute_metrics` | `metrics.py` | **oui** (total_return + max_dd) |
| `experiments.compare` | via `compute_metrics` | oui |
| `evidence._snapshot_row` | via `exp.metrics` | oui |
| walk-forward / regime_slices / ruleset_backtest | `compute_metrics` (ruleset `eod_return=0`) | N/A ruleset |
| `serializers.backtest_dict` | expose `eod_return` | champ API |
| `serializers.metrics_dict` / UI | `metrics.total_return` | oui (via metrics) |
| Front BacktestsPage | `metrics.total_return` only | oui |

Aucun autre lecteur direct de `bar_returns` pour un total equity hors `compute_metrics`.

### Tests

- Invariant 1e-9 : mid-close, EOD closeâ‰ open, flip Lâ†’S / Sâ†’L, flips enchaÃ®nÃ©s
- PropriÃ©tÃ© : 200 sÃ©quences alÃ©atoires
- Lookahead truncation : **strict** (aucune exclusion de barre)
- Local : `pytest tests/backtest tests/indicators tests/strategy_lab` â€” **0 Ã©chec**

### `metrics_basis`

- Engine / experiments / evidence / agent cmd â†’ **`net_v2`**
- `ruleset_backtest` reste **`net_v1`**
- UI : labels distincts ; alerte si mÃ©lange brut / v1 / v2

### Impact (bougies synthÃ©tiques seed 42, 500 bars, coÃ»ts 5+3 bps) â€” confirmÃ© aprÃ¨s `eod_return`

| experiment | n | flips | eod | tot avantâ†’aprÃ¨s | dd avantâ†’aprÃ¨s | WR avantâ†’aprÃ¨s | Exp avantâ†’aprÃ¨s |
|------------|---|-------|-----|-----------------|----------------|----------------|-----------------|
| `ICHIMOKU_ONLY` | 40 | 6 | 1 | -28.32% â†’ -28.94% | 32.25% â†’ 32.57% | 5.00% â†’ 5.00% | -0.83% â†’ -0.85% |
| `ICHIMOKU_RVOL_ENTRY_GATE` | 31 | 0 | 1 | -24.57% â†’ -24.86% | 29.90% â†’ 29.90% | 3.23% â†’ 3.23% | -0.91% â†’ -0.91% |
| `PIPELINE` | 5 | 0 | 0 | -2.22% â†’ -2.22% | 3.17% â†’ 3.17% | 20.00% â†’ 20.00% | -0.44% â†’ -0.44% |

### Goldens

- `ruleset_backtest_golden.json` : **inchangÃ©**

### Attente

CI verte â†’ **ATTENTE Claude**.

---

## 2026-09-23 â€” T0-METRICS VALIDÃ‰ par Claude â€” MERGÃ‰ (#23)

- Branche : `cursor/t0-metrics-net-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/23 â€” **MERGÃ‰E** `7d74fa1`
- Statut : **validÃ© par Claude** (WR/exp/PF nets ; `*_gross` ; invariant ; `metrics_basis=net_v1` ; alembic unique).

---

## 2026-09-23 â€” T0-METRICS EN COURS â€” stats par trade nettes de frais

- Branche : `cursor/t0-metrics-net-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/23 (**draft**)
- Commit(s) : `98eb8a7` (feat) ; `d90883f` (handoff PR)
- Statut : **ATTENTE CLAUDE** â€” CI **VERTE** ; **ne pas merger** avant revue.

### LivrÃ©

1. `round_trip_cost_log` / `one_way_cost_log` dans `app/backtest/engine.py` (prÃ¨s de `Trade`) â€” T4a rÃ©utilise `Trade.net_log_return` (plus de formule locale)
2. `Trade.cost_log` + propriÃ©tÃ© `net_log_return` ; `log_return` reste **brut**
3. Rempli : `ruleset_backtest` = `2Ã—cost` (comme `_apply_hold_returns`) ; `engine.run_backtest` = frais **rÃ©ellement** Ã©crits dans `bar_returns` (open / close / flip)
4. `metrics.py` : WR / expectancy / PF sur **net** ; champs `*_gross` pour transparence
5. Perf DB / snapshots : `metrics_basis="net_v1"` sur **nouveaux** enregistrements (pas de rÃ©Ã©criture historique) ; UI Compare / Experiments / Perf DB : colonne **Base** (`net` vs `brut (ancien)`), alerte si mÃ©lange
6. Tests : gagnant brut / perdant net â†’ WR ; invariant Î£ net == Î£ bar_returns (ruleset + engine mid/EOD flat) ; Ã©cart EOD closeâ‰ open **documentÃ©** (non corrigÃ©)

### Engine â€” invariant (vÃ©rif avant correction)

| Cas | Î£ net âˆ’ Î£ bars (naive 2Ã—cost) | Avec `cost_log` exact |
|-----|-------------------------------|------------------------|
| Mid-close NEUTRALâ†’Lâ†’N | ~0 | OK (1e-9) |
| EOD force-close, open=close | âˆ’1Ã—one_way (sortie non tarifÃ©e dans bars) | OK si `cost_log`=entry only |
| Flip Lâ†’S (1 fee pour close+open) | âˆ’2Ã—one_way | OK si attribution flip â†’ trade fermÃ© |
| EOD `last.close â‰  last.open` | Ã©cart â‰ˆ `log(close/open)` | **Ã‰CHEC volontaire** â€” mark trade vs open-to-open ; **non corrigÃ©** dans cette PR |

### Tableau avant / aprÃ¨s (seed 7, 600 bougies synthÃ©tiques, coÃ»ts 5+3 bps)

| ruleset | n | WR brut | WR net | Exp brut | Exp net | PF brut | PF net | Î”exp (bps) |
|---------|---|--------|--------|----------|---------|---------|--------|------------|
| `IV_EXP_A_KUMO_BO_001` | 15 | 33.33% | 33.33% | -0.43% | -0.59% | 0.8022 | 0.7408 | 15.9 |
| `IV_ICHIMOKU_ONLY_LONG_001` | 8 | 12.50% | 12.50% | -1.89% | -2.05% | 0.3096 | 0.2876 | 15.7 |
| `IV_EXP_B_KUMO_RVOL_001` | 7 | 28.57% | 28.57% | -1.23% | -1.39% | 0.4779 | 0.4373 | 15.8 |

Aucun basculement WR sur ces fixtures (sorties ATR larges) ; expectancy surestimÃ©e dâ€™~16 bps/trade (coÃ»t RT).

### Goldens

- `ruleset_backtest_golden.json` : **inchangÃ©** (trades/indices/prix/raisons seulement â€” pas de mÃ©triques)
- Aucune fixture golden de mÃ©triques WR/PF/expectancy Ã  rÃ©gÃ©nÃ©rer

### Migration

- `a7b8c9d0e1f2_metrics_basis_net_v1` â€” colonne `metrics_basis` nullable sur `strategy_lab_experiments` + `backtest_snapshots`

### CI Actions

- **VERTE** (HEAD `d90883f`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35864600608
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Attente

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  la revue Claude.

---

## 2026-09-23 â€” T4a VALIDÃ‰ par Claude â€” MERGÃ‰ (#22)

- Branche : `cursor/t4a-backtest-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 â€” **MERGÃ‰E** `ad10720`
- Statut : **validÃ© par Claude** (net = log_return âˆ’ 2Ã—cost ; invariant Claude 6,5e-16 ; Postgres 0 Ã©chec).

### Correction net (prÃ©-merge)

`return_pct_net` / `return_pct_gross` / `r_multiple_gross` ; outcome sur net ; front NET principal.

---

## 2026-09-23 â€” T4a CORRECTION NET â€” ATTENTE Claude (revalidation)

- Branche : `cursor/t4a-backtest-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 (**draft**)
- Commit fix : `6627277` (feat initial `4d68375`)
- Statut : **supersÃ©dÃ©** â€” validÃ© + mergÃ© (voir entrÃ©e ci-dessus).

### Correction demandÃ©e (brut Ã©tiquetÃ© Â« net Â»)

`Trade.log_return` = brut (`sign Ã— log(exit/entry)`). Les coÃ»ts ne sont dÃ©duits que dans `bar_returns` via `_apply_hold_returns` :
- mÃªme barre : `â€¦ âˆ’ 2 * cost` (l.105)
- entrÃ©e : `r -= cost` (l.119â€“120) ; sortie : `âˆ’ cost` (l.124â€“126) ; cas limite l.132
â†’ aller-retour = **`2 Ã— cost`**, `cost = (commission_bps + slippage_bps) / 10_000`.

### LivrÃ© (fix)

1. `return_pct_net = exp(log_return âˆ’ 2Ã—cost) âˆ’ 1` ; `return_pct_gross = exp(log_return) âˆ’ 1`
2. `outcome` sur **net** ; `r_multiple_gross` (prix vs stop)
3. Origin + `trades` exposent les deux ; front : **NET** principal, brut secondaire
4. Test : +5 bps brut / 16 bps RT (5+3 commission/slippage) â†’ `outcome=loss`

### CI Actions

- **VERTE** (HEAD `6627277`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35862821454
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Suite aprÃ¨s merge

**T0-METRICS** â€” stats par trade nettes de frais (`cost_log` / `net_log_return` / `*_gross` / `metrics_basis`).

### Attente

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  revalidation Claude â†’ merge â†’ puis T0-METRICS.

---

## 2026-09-23 â€” T4a EN COURS â€” backtest visuel (trades sur chart)

- Branche : `cursor/t4a-backtest-overlay-a2fe` (Claude : `v3/t4a-backtest-overlay`)
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 (**draft**)
- Commit(s) : `4d68375`
- Statut : **supersÃ©dÃ©** par correction net `6627277` (ci-dessus).

### Objectif

Lancer une stratÃ©gie catalogue sur un symbole â†’ trades sur le chart ; filtre Tous / Gagnants / Perdants.

### LivrÃ©

1. `chart_objects/from_backtest.py` â€” 4 objets/trade (ENTRY/STOP/TARGET/MARKER), `source=backtest`, `origin` complet
2. `POST /api/engine/strategy-lab/backtest-overlay` â€” filtre outcome serveur ; counts globaux
3. Front MarchÃ© : bouton Backtest + sheet (catalogue, Afficher/Effacer, filtre, dÃ©tail trade) ; objets BACKTEST en plus des overlays existants
4. Tests paritÃ© golden seeds ; OpenAPI/route_order ajouts seuls

### CI Actions

- **VERTE** (HEAD `4d68375`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35861496555
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Hors scope

WHY ENTERED/REJECTED/EXITED (T4c) ; filtre conversationnel Claude (T4b) ; filtres rÃ©gime.

---

## 2026-09-23 â€” T3c VALIDÃ‰ par Claude â€” MERGÃ‰ (#21)

- Branche : `cursor/t3c-condition-registry-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/21 â€” **MERGÃ‰E** `0609965`
- Statut : **validÃ© par Claude** (fixtures avant refactor ; goldens rejouÃ©s sur ancien main ; Postgres 0 Ã©chec).

**T3 phase close** pour cette vague (T3d â†’ T5b ; T3e MTF plus tard).

---

## 2026-09-23 â€” T3c EN COURS â€” registre conditions + CONDITION_SCHEMA dÃ©rivÃ©

- Branche : `cursor/t3c-condition-registry-a2fe` (Claude : `v3/t3c-condition-registry` â€” prÃ©fixe cloud `cursor/â€¦-a2fe`)
- PR : https://github.com/samiriggui-code/IchiVol/pull/21 (**draft**)
- Commit(s) : `0545826` (fixtures **avant** refactor) ; `51834cd` (registre) ; `1ad9588` (handoff PR)
- Statut : **ATTENTE CLAUDE** â€” CI **VERTE** ; **ne pas merger** avant revue.

### Objectif

Une condition DSL = une dÃ©claration (`ConditionSpec`) ; `CONDITION_SCHEMA` et `_condition_holds` dÃ©rivÃ©s du registre.

### LivrÃ©

1. Fixtures prÃ©-refactor : `condition_schema_golden.json`, `condition_eval_golden.json` + tests Ã©galitÃ© stricte
2. `app/strategy_lab/conditions.py` â€” `ConditionSpec` + `CONDITION_REGISTRY` (copie exacte des expressions `_condition_holds`)
3. `CONDITION_SCHEMA` / `CONDITION_ENUMS` dÃ©rivÃ©s ; evaluator dispatch via registre ; cliquet AST `key == "â€¦"`
4. Contrats : indicator_id âˆˆ REGISTRY âˆª {structure,derived} ; pas de doublons ; test Â« une dÃ©claration Â»
5. `ruleset_backtest_golden` **inchangÃ©** ; OpenAPI **inchangÃ©**

### Note validation `allowed_values`

`CONDITION_ENUMS` **existait dÃ©jÃ ** avant T3c (mÃªme valeurs). DÃ©placÃ© sur `ConditionSpec.allowed_values` â†’ dÃ©rivation. **Aucun builtin ne viole** les enums (re-parse catalog OK). Pas de correction catalog.

### CI Actions

- **VERTE** (HEAD `1ad9588`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35860079478
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Arbitrages T3 (Claude â€” Ã  respecter)

- **T3b StrategyCompiler** : **non** â€” `ruleset_backtest` exÃ©cute dÃ©jÃ  le DSL ; pas de couche compilation.
- **MTF DSL** â†’ **T3e** (features multi-TF absentes ; ne bloque pas T4/T5).
- **`risk{}` cosmÃ©tique** : **abandonnÃ©** â€” `stop_atr` / `target_atr` restent top-level.

### Hors scope T3c

Nouvelles conditions ; MTF (T3e) ; Ã©diteur conversationnel (T3d).

### Attente

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  la revue Claude.

---

## 2026-09-23 â€” T2c VALIDÃ‰ par Claude â€” MERGÃ‰ (#20)

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 â€” **MERGÃ‰E** `7e7cac7`
- Statut : **validÃ© par Claude** (5 corrections OK ; Postgres 0 Ã©chec ; golden ajouts seuls).

### LivrÃ© (rappel)

`POST â€¦/setup` atomique + grounding ; sens dÃ©duit ; R UI ; Twelve Data OK (cache 90s partagÃ© OHLCV) ; `as_of` groundÃ©.

**T2 terminÃ©** (T2a + T2b + T2c).

---

## 2026-09-23 â€” T2c corrections revue Claude â€” setup atomique + as_of

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 (**draft**)
- Commit(s) : `368c5de` (fix), `bd533d1` (handoff)
- Statut : **ATTENTE CLAUDE** â€” corrections appliquÃ©es ; CI **VERTE** ; **ne pas merger** avant revalidation.

### Correctifs demandÃ©s â†’ livrÃ©s

1. **Setup atomique** â€” taps en mÃ©moire â†’ rÃ©cap Valider/Annuler ; Annuler = 0 Ã©criture ; Valider = `POST /chart-objects/{symbol}/setup` (3 points, 1 transaction). POST unitaire conservÃ©.
2. **Sens dÃ©duit** â€” `stop < entry` â†’ long ; `stop > entry` â†’ short ; gÃ©omÃ©trie serveur LONG `stop < entry < target` / SHORT inverse ; `origin.direction` sur les 3 ; Valider dÃ©sactivÃ© cÃ´tÃ© front si incohÃ©rent.
3. **Ratio R** â€” distances stop/cible (prix + %) + R = |Î”target|/|Î”stop| (0,01) dans `MarkTradeSheet`.
4. **Twelve Data** â€” exclusion `canMarkTrade` / fetch overlays retirÃ©e. Raison initiale : Ã©conomie crÃ©dits (GET chart-objects refetch OHLCV). Claude : cache 90s + grounding OK â†’ bouton visible ; erreur claire Ã  la validation.
5. **as_of grounding** â€” `assert_object_grounded` vÃ©rifie `obj.as_of` sur la sÃ©rie (ou marge projetÃ©e). Test : `draw_zone` agent sans points + `as_of` futur â†’ rejetÃ©.

### Tests

- `/setup` LONG cohÃ©rent ; LONG target mauvais cÃ´tÃ© â†’ 422 + 0 objet ; point non groundÃ© â†’ 422 + 0 objet ; SHORT ; as_of futur
- `pytest tests/chart_objects/` + goldens ; `npm run build` OK

### CI Actions

- **VERTE** (HEAD `bd533d1`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35858843441
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Attente

**Revalidation Claude** â†’ merge si OK. **Cursor sâ€™arrÃªte ici.**

---

## 2026-09-23 â€” T2c EN COURS â€” USER trade points (ENTRY/STOP/TARGET)

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 (**draft**)
- Commit(s) : `4606c03` (feat T2c), `e49696c` (handoff ATTENTE)
- Statut : *(supersÃ©dÃ© â€” voir corrections revue Claude ci-dessus)*

### Contexte

Les 4 merges (#16â†’#19) sont **faits** sur `main` (`2b0bd96`).  
Job demandÃ© par Claude : POST/DELETE chart-objects **source=user** + mode UI Â« Marquer un trade Â» (mobile-friendly).

### PÃ©rimÃ¨tre T2c (cette PR)

1. **API** `POST /api/engine/chart-objects/{symbol}` â€” force `source=user` ; types **entry|stop|target** uniquement ; grounding OHLCV (mÃªme helper T2b) ; `setup_id` dans `origin` (+ `subtype=setup:â€¦` pour ids stables)
2. **API** `DELETE /api/engine/chart-objects/item/{object_id}` â€” soft-delete **USER only** (ne touche pas CLAUDE)
3. **Node** : proxy `DELETE /api/engine/*` (auth)
4. **Front** : client write + mode Â« Marquer un trade Â» sur MarchÃ© (tap chart â†’ ENTRY â†’ STOP â†’ TARGET)
5. Tests + goldens OpenAPI / `route_order` (additions)

### LivrÃ© (impl)

- `app/chart_objects/user_write.py` + routes POST/DELETE
- `tests/chart_objects/test_t2c_user_write.py` (5 tests)
- Front : `MarkTradeSheet`, `PriceChart` pickMode, bouton MarchÃ©
- Node DELETE proxy

### Validation locale

```text
pytest tests/chart_objects/ -q   # 37 passed
tsc -b                           # OK
```

### CI Actions

- **VERTE** (HEAD `e49696c`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35857843322
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Hors scope

- T4 visual WHY (roadmap)
- Draw palette complÃ¨te USER (zones/trendlinesâ€¦)
- Colonne `setup_id` dÃ©diÃ©e (pas de migration â€” JSON `origin`)
- Multi-user ownership sur overlays

### Attente Claude

Draft â†’ handoff Ã  jour â†’ **revue** (suite Postgres complÃ¨te sur `main` + ce diff) â†’ marche Ã  suivre.

**Cursor sâ€™arrÃªte ici** jusquâ€™Ã  la revue Claude.

---

## 2026-09-23 â€” BILAN â€” 4 merges done (#16â†’#19) â†’ T2c

### Merges exÃ©cutÃ©s (ordre Claude)

| # | PR | Sujet | Merged SHA / note |
|---|-----|--------|-------------------|
| 1 | [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidÃ©litÃ© | `2670f96` â†’ main |
| 2 | [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw + grounding | `b500944` |
| 3 | [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 `all`/`any` + `exit` + golden | `b0c9584` |
| 4 | [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | **T0-UI** Strategy Lab (pas T4 roadmap) | `2b0bd96` |

`main` HEAD post-merges : **`2b0bd96`**.

### Note naming

#19 = **T0-UI** (rename + onglets DB). Roadmap **T4** = backtest visuel WHY â€” **pas commencÃ©**.

### Suite

Branche T2c ouverte ; dÃ©tail dans lâ€™entrÃ©e **T2c EN COURS** ci-dessus.  
**Claude** : relancer suite Postgres complÃ¨te sur `main` `2b0bd96` (baseline 0 Ã©chec attendu post T0-CI).

---

## 2026-09-23 â€” T0-UI â€” Strategy Lab (rename + onglets DB) (rename + onglets DB)

- Branche : `cursor/t4-strategy-lab-ui-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/19 (**draft**)
- Commit(s) : `9737a1f`

### Note

**Pas T4** de la feuille de route (T4 = backtest visuel WHY ENTERED/REJECTED/EXITED). Ceci = T0-UI.

### LivrÃ©

- Route `/app/strategy-lab` ; `/app/backtests` â†’ redirect
- Nav + Overview + ActivitÃ© : label **Strategy Lab**
- Onglets **Compare | Regimes | Experiments | Live**
- Compare â†’ `GET /strategy-lab/compare` (DB)
- Regimes / Experiments â†’ `listStoredExperiments` (+ filtre `market_regime`)
- Live = ancien fan-out 7 recalculs (secondaire)
- Clients : `compareStoredRulesets`, `getStoredExperiment`, `market_regime` sur list

### Non fait

- Rename fichier â†’ `StrategyLabPage.tsx`
- DÃ©tail experiment `{id}`
- Masquer complÃ¨tement Live / WF-opt par dÃ©faut

### Validation locale

```text
./node_modules/.bin/tsc -b   # OK
```

### Revue Claude

Draft â€” **ne pas merger** avant revue. Orthogonal Ã  #16/#17/#18.

---

---

## 2026-09-23 â€” EN COURS â€” merges Claude (#16â†’#19) puis T2c

### Progression

| PR | Statut |
|----|--------|
| #16 T0-BROKER | **MERGÃ‰E** |
| #17 T2b | **MERGÃ‰E** |
| #18 T3 | rebase/merge main fait â€” **CI puis merge** (cette branche) |
| #19 T0-UI | aprÃ¨s #18 |

### Checks #18 âŠ• main (#16+#17)

- Conflit handoff rÃ©solu ; README auto-merge
- `alembic heads` : une seule (`f6a7b8c9d0e1`)
- Fixture golden backtest conservÃ©e

### AprÃ¨s #18+#19

Handoff Â« 4 merges done Â» â†’ T2c (USER ENTRY/STOP/TARGET) â†’ draft â†’ attendre Claude.

---


---

## 2026-09-23 â€” T3 correction Claude â€” golden backtest builtins

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : 

### Correctif demandÃ©

Preuve que le **rÃ©sultat** backtest des builtins est inchangÃ© vs `main` (pas seulement le parse).

### LivrÃ©

- Fixture `tests/strategy_lab/fixtures/ruleset_backtest_golden.json` gÃ©nÃ©rÃ©e sur **`main` af0006d** (pre-T3) â€” seeds 7/42, 300 bars, tous `list_builtin_rulesets()`
- `test_ruleset_backtest_golden.py` â€” Ã©galitÃ© stricte trades (entry/exit index, prix, raison, stop/target)

### Validation locale

```text
pytest tests/strategy_lab/test_ruleset_backtest_golden.py -q   # PASS
```

### CI Actions

- **VERTE** (HEAD `8c301c6`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35855152500
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

**Revalidation demandÃ©e** avant merge. Pas de nouveau lot.

---

---

## 2026-09-23 â€” T3 slice 2 â€” `exit` (max_hold + conditions signal)

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : `a767cc1` (feat), `8996a09` / `9d1bcb6` (handoff)

### LivrÃ©

- `ExitSpec` optionnel dans `ruleset.py` (`max_hold_bars`, `conditions` = mÃªme `ConditionGroup`)
- ATR `stop_atr` / `target_atr` restent top-level ; refus de les mettre sous `exit`
- Backtest : prioritÃ© `stop` > `target` > `signal` (fill = close) > `max_hold` / `eod`
- `max_hold` : kwarg call-site gagne, sinon `ruleset.exit.max_hold_bars`
- `evaluator.bar_matches_group` partagÃ© entry/exit
- Perf DB `exit_rule` : `atr_stop_target[+signal][+max_hold=N]`
- Tests backtest + parse + `apply_params` prÃ©serve `exit`

### Non fait

- Nesting `risk{}` cosmÃ©tique
- MTF / trailing / partials / `close_confirmation` entry wiring

### Validation locale

```text
pytest tests/strategy_lab/ -q
# 68 passed
```

### CI Actions

- **VERTE** (HEAD `9d1bcb6`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35852517274
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

MÃªme draft PR #18 â€” **ne pas merger** avant revue.

---

---

## 2026-09-23 â€” T3 slice 1 â€” DSL v3 `all` / `any` (rÃ©trocompat flat)

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : `ff0fc50`

### LivrÃ©

- `ConditionGroup` (`all_of` / `any_of`) dans `app/strategy_lab/ruleset.py`
- Parse : flat `{key: val}` â‰¡ `all` ; forme nested `{"all":â€¦,"any":â€¦}` ; refuse le mix flat + clÃ©s composition
- `to_dict()` : flat legacy si `all` seul (catalog / Perf DB inchangÃ©s)
- `evaluator.bar_matches` : `(âˆ€ all) âˆ§ (âˆƒ any)` ; groupes vides = vacuous true
- `optimization.apply_params` prÃ©serve `any_of` quand le base est composÃ©
- Tests : `test_ruleset.py` (+ `test_apply_params_preserves_any_of`)
- README engine : ligne schema Rules Engine mise Ã  jour

### Non fait (tranches suivantes T3)

- Exit rules / risk block / MTF dans le DSL
- Nesting rÃ©cursif `all`/`any` sous un groupe
- Migration catalog built-ins vers `any` (volontairement flat)

### Validation locale (Cursor, sans Postgres)

```text
pytest tests/strategy_lab/ -q
# 62 passed
```

### Revue Claude

Draft â€” **ne pas merger** avant revue. Suite Postgres complÃ¨te quand Claude revient.

---

---

## 2026-09-23 â€” EN COURS â€” exÃ©cution marche Ã  suivre Claude

Claude a validÃ© #16/#17/#18 et acceptÃ© #19 (renommÃ©e **T0-UI**, pas T4 roadmap).  
Cursor exÃ©cute lâ€™ordre de merge puis dÃ©marre **T2c**.

### Ordre merges (un par un, rebase + CI verte)

| # | PR | Statut Cursor |
|---|-----|----------------|
| 1 | [#16](https://github.com/samiriggui-code/IchiVol/pull/16) T0-BROKER | **MERGÃ‰E** `2670f96` (2026-09-23T11:39Z) |
| 2 | [#17](https://github.com/samiriggui-code/IchiVol/pull/17) T2b | merge main fait ; CI **VERTE** head `e9c7ad2` â€” **merge imminent** |
| 3 | [#18](https://github.com/samiriggui-code/IchiVol/pull/18) T3 | en attente (aprÃ¨s #17) |
| 4 | [#19](https://github.com/samiriggui-code/IchiVol/pull/19) T0-UI | titre/handoff renommÃ©s T0-UI ; merge aprÃ¨s #18 |

### Checks faits sur #17 âŠ• main(#16)

- `openapi_golden` / `route_order_golden` : auto-merge ; `route_order` contient toutes les routes main (56) â€” rien perdu
- `alembic heads` : **une seule** tÃªte `f6a7b8c9d0e1`
- Handoff conflict rÃ©solu (sections T2b + broker conservÃ©es)

### AprÃ¨s les 4 merges

1. Handoff Â« 4 merges done Â» sur main
2. Branche T2c `cursor/t2c-user-trade-points-a2fe` (Claude avait dit `v3/t2c-user-trade-points` â€” prÃ©fixe cloud `cursor/â€¦-a2fe` ; notÃ© ici si Claude prÃ©fÃ¨re `v3/`)
3. Job T2c : POST/DELETE chart-objects USER + mode Â« Marquer un trade Â» mobile

### RÃ¨gle rappelÃ©e

Une sous-tranche Ã  la fois ; draft â†’ handoff â†’ **attendre revue Claude** avant la suivante.

---

2026-09-23 â€” ATTENTE CLAUDE â€” bilan Cursor pendant ton absence

**Cursor sâ€™arrÃªte ici.** Pas de nouveau code tant que Claude nâ€™a pas revu et donnÃ© la marche Ã  suivre.

Contexte : Claude indisponible (restriction puis revue reportÃ©e). Cursor a continuÃ© seul sur des drafts. **Aucun merge** de ces PRs sans validation Claude.

### File dâ€™attente (drafts â€” Ã  revoir)

| PR | Sujet | Branche | Head | CI Actions |
|----|--------|---------|------|------------|
| [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidÃ©litÃ© (reconcile, marks, financing) | `v3/t0-broker-fidelity` | `f904951` | VERTE [35849205949](https://github.com/samiriggui-code/IchiVol/actions/runs/35849205949) |
| [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw_* + store USER/CLAUDE (+ passe 2 durcissement) | `cursor/t2b-agent-draw-a2fe` | `3ece878` | VERTE (voir entrÃ©e T2b) |
| [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 slice 1+2 (`all`/`any` + `exit`) | `cursor/t3-dsl-v3-a2fe` | `8973a42` | VERTE [35852790018](https://github.com/samiriggui-code/IchiVol/actions/runs/35852790018) |
| [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | T4 UI Strategy Lab (rename + onglets DB) | `cursor/t4-strategy-lab-ui-a2fe` | `8eec800` | (voir check Actions sur la PR) |

### DÃ©jÃ  sur `main` (validÃ© avant / pendant)

- T0-CI #14, T2a #15 â€” mergÃ©s, validÃ©s Claude.

### Ce que Cursor a tranchÃ© seul (Ã  confirmer ou corriger)

1. **T3** : slices `all`/`any` + `exit` livrÃ©s ; **pas** de `risk{}` cosmÃ©tique ni MTF (FeatureBar mono-TF â€” trop gros). Suite T3 DSL = revue #18 puis dÃ©cision Claude.
2. **T4** dÃ©marrÃ© (UI) pendant que #16/#17/#18 attendent â€” orthogonal moteur. DB-first Compare/Regimes/Experiments ; Live = ancien recalcul.
3. **T2b** : passe 2 aprÃ¨s critique Â« trop rapide vs T1 Â» (force source=claude, points schema, front render, refresh chart).

### DemandÃ© Ã  Claude

1. Suite **Postgres complÃ¨te** sur #16 et #17 (et #18/#19 si pertinent) â€” Cursor nâ€™a pas de Postgres local.
2. Revue des 4 drafts : merge / rebase / redo / kill.
3. **Marche Ã  suivre** pour Cursor (ordre des lots, quoi ne pas toucher).

### RÃ¨gle

Cursor **attend** cette marche Ã  suivre. Ne pas enchaÃ®ner un nouveau lot sans consignes Claude.

---

## 2026-09-23 â€” T2b correction Claude â€” grounding anti-hallucination

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (**draft**)
- Commit(s) : 

### Correctif demandÃ©

Avant persist agent `draw_*` : vÃ©rifier times/prices contre OHLCV rÃ©el (`resolve_and_fetch`).

### LivrÃ©

- `app/chart_objects/grounding.py` â€” `assert_object_grounded`
  - time âˆˆ timestamps sÃ©rie, ou `[last, last+5 bars]` si `origin.projected`
  - price âˆˆ `[min(low)*0.5, max(high)*1.5]` sur 300 derniÃ¨res bougies
  - `price_low` / `price_high` (ZONE) idem
- `_draw_and_persist` appelle grounding â†’ `CommandError("point_not_grounded: â€¦")`
- Tests : `test_grounding.py` (prix 100Ã—, futur hors proj, zone OK, structure OK)

### Validation locale

```text
pytest tests/chart_objects/ -q   # PASS
```

### CI Actions

- **VERTE** (HEAD `9601274`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35855150230
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

**Revalidation demandÃ©e** avant merge.

---

---

## 2026-09-23 â€” ATTENTE CLAUDE â€” bilan Cursor pendant ton absence

**Cursor sâ€™arrÃªte ici.** Pas de nouveau code tant que Claude nâ€™a pas revu et donnÃ© la marche Ã  suivre.

Contexte : Claude indisponible (restriction puis revue reportÃ©e). Cursor a continuÃ© seul sur des drafts. **Aucun merge** de ces PRs sans validation Claude.

### File dâ€™attente (drafts â€” Ã  revoir)

| PR | Sujet | Branche | Head | CI Actions |
|----|--------|---------|------|------------|
| [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidÃ©litÃ© (reconcile, marks, financing) | `v3/t0-broker-fidelity` | `f904951` | VERTE [35849205949](https://github.com/samiriggui-code/IchiVol/actions/runs/35849205949) |
| [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw_* + store USER/CLAUDE (+ passe 2 durcissement) | `cursor/t2b-agent-draw-a2fe` | `3ece878` | VERTE (voir entrÃ©e T2b) |
| [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 slice 1+2 (`all`/`any` + `exit`) | `cursor/t3-dsl-v3-a2fe` | `8973a42` | VERTE [35852790018](https://github.com/samiriggui-code/IchiVol/actions/runs/35852790018) |
| [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | T4 UI Strategy Lab (rename + onglets DB) | `cursor/t4-strategy-lab-ui-a2fe` | `8eec800` | (voir check Actions sur la PR) |

### DÃ©jÃ  sur `main` (validÃ© avant / pendant)

- T0-CI #14, T2a #15 â€” mergÃ©s, validÃ©s Claude.

### Ce que Cursor a tranchÃ© seul (Ã  confirmer ou corriger)

1. **T3** : slices `all`/`any` + `exit` livrÃ©s ; **pas** de `risk{}` cosmÃ©tique ni MTF (FeatureBar mono-TF â€” trop gros). Suite T3 DSL = revue #18 puis dÃ©cision Claude.
2. **T4** dÃ©marrÃ© (UI) pendant que #16/#17/#18 attendent â€” orthogonal moteur. DB-first Compare/Regimes/Experiments ; Live = ancien recalcul.
3. **T2b** : passe 2 aprÃ¨s critique Â« trop rapide vs T1 Â» (force source=claude, points schema, front render, refresh chart).

### DemandÃ© Ã  Claude

1. Suite **Postgres complÃ¨te** sur #16 et #17 (et #18/#19 si pertinent) â€” Cursor nâ€™a pas de Postgres local.
2. Revue des 4 drafts : merge / rebase / redo / kill.
3. **Marche Ã  suivre** pour Cursor (ordre des lots, quoi ne pas toucher).

### RÃ¨gle

Cursor **attend** cette marche Ã  suivre. Ne pas enchaÃ®ner un nouveau lot sans consignes Claude.

---

---

## 2026-09-23 â€” T2b passe 2 â€” durcissement (suite critique pass 1 trop lÃ©ger)

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (draft)
- **Contexte** : le 1er push T2b (~10 min) livrait un squelette backend aprÃ¨s T2a dÃ©jÃ  mergÃ©. Trop rapide vs dÃ©coupage Claude sur T1 â€” **trous rÃ©els** (source=user impersonable, schema `points` = string[], front ne chargeait que `engine`, rendu sans horizontal/entry/stop, README stale).

### Correctifs passe 2

1. Agent `draw_*` **force `source=claude`** ; refuse `user` / `engine`
2. `delete_chart_object` **claude-only** (ne touche pas USER)
3. `get_chart_objects` dÃ©faut = HTTP (`engine`) â€” passer `user,claude` explicitement
4. Copilot : `points` â†’ `array<{time,price}>` (plus `string[]`)
5. Front : `getChartObjects` dÃ©faut `engine,user,claude` ; PriceChart rend horizontal/entry/stop/target + ray/text
6. Tests : isolation USER, merge HTTP, parity `get_structure`â†”HTTP, trend_line points, schema TS
7. `engine/README.md` section agent mise Ã  jour (WRITE chart scopes)

### CI / suite DB

- CI Actions passe 1 : **VERTE** (`72ef89d`, run `35849205234`)
- CI Actions passe 2 : **VERTE** (`c5767a7`, run `35850222353`) â€” `pytest` + `frontend` success
- **Suite Postgres complÃ¨te** : **Claude Ã  ~13:10** (Cursor note ici, ne bloque pas sur Ã§a)
- Passe 2 suite : refresh Market chart aprÃ¨s `draw_*` / `delete_chart_object` (event bus) â€” CI **VERTE** `2a6d8ed` https://github.com/samiriggui-code/IchiVol/actions/runs/35850595467
- **Head PR #17** : `2a6d8ed` â€” prÃªt revue Claude (suite DB complÃ¨te ~13:10)

### Toujours hors scope / dette assumÃ©e

- Multi-tenant `user_id` sur overlays (global symbol/tf) â€” dette connue, pas T2b
- Rectangle/channel rendu gÃ©nÃ©rique riche â€” partiel
- STRATEGY/BACKTEST store â€” T4
- Suite DB paper/brokerage complÃ¨te â€” **Claude 13:10**
- Refresh Market aprÃ¨s draw : **fait** (`chartObjectsEvents` bus) sur ce push

---

---

## 2026-09-23 â€” T2b â€” Agent draw_* + get_structure + store USER/CLAUDE (passe 1)

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (draft) â€” **pas de merge avant revue Claude**
- Base : `main` (post-#14+#15)
- **Note auto-critique** : squelette trop mince â€” voir **passe 2** ci-dessus. T2a (#15) couvrait dÃ©jÃ  modÃ¨le + GET + rendu Structure ; T2b = store + agent + fil Copilot, pas Â« tout T2 en 10 min Â».

### LivrÃ© (passe 1)

1. **Persistance** `chart_object_overlays` (alembic `f6a7b8c9d0e1`) + store
2. **Collect** merge ENGINE + store sur `GET /chart-objects`
3. Agent : `get_structure`, `get_chart_objects`, `draw_*`, `delete_chart_object` + capabilities write chart
4. Copilot allowlist chart write
5. `structure/payload.py` partagÃ©

### Tests locaux (passe 1)

- chart_objects + agent + OpenAPI + build : PASS ; CI verte ensuite

### Hors scope

- STRATEGY / BACKTEST (T4) ; VSB (T5) ; merge #16 ; T3+

---

---

## 2026-09-23 â€” T0-BROKER â€” FidÃ©litÃ© paper broker + corrections revue Claude

- Branche : `v3/t0-broker-fidelity` (rebasÃ©e sur `main` aprÃ¨s #14+#15)
- PR : https://github.com/samiriggui-code/IchiVol/pull/16 (draft) â€” **pas de merge avant revue Claude**
- **Annule et remplace** le brief T0-UI : journal dâ€™ordres + P&L rÃ©alisÃ© dÃ©jÃ  sur SynthÃ¨se â€” **non refaits**.
- Workflow CI : **retirÃ©** le commit `d80382f` (arrivÃ© via #14 sur `main`).

### ValidÃ© (inchangÃ©)

- reconcile + badge ComptabilitÃ© ; liquidation_value ; marks Ã¢ge/pÃ©remption
- financing idempotent ; pas de rÃ©troactif avant 2026-09-23 ; rÃ©alisÃ© de clÃ´ture dÃ©duit le financement sans double dÃ©bit cash
- tests FID_* jetables ; golden API ajouts seuls

### Corrections revue Claude (cette itÃ©ration)

**A) SHORT PnL** â€” formule corrigÃ©e `(entry âˆ’ exit) / entry` et `qty Ã— (entry âˆ’ exit)` :
| Fichier | Occurrences |
|---------|-------------|
| `app/paper/broker.py` | `close_capital_position` realized/cash/`pnl_pct` ; `update_excursions` MFE/MAE ; helpers `short_pnl_pct` / `short_realized_currency` |
| `app/paper/liquidation.py` | preview SHORT cash_delta / realized |
| `app/paper/engine.py` | `_close_legacy` pnl_pct |
| `app/paper/reconcile.py` | reconstruction cash SHORT + check **lecture seule** `short_pnl_legacy_formula` (CLOSED avant 2026-09-23, Ã©cart stockÃ© âˆ’ correct ; **aucune rÃ©Ã©criture**) |

Shadow / research_lab / evidence Ã©taient dÃ©jÃ  corrects â€” non touchÃ©s.

**B) Financing** â€” `fee_profiles.FINANCING_*` : `(benchmarkâ‰ˆ4.3% + markupÂ±2.5%)/365Ã—10000` bps/j (~1.86 long, ~0.49 short) ASSUMPTION 2026-09-23 ; CostsPanel affiche les taux.

**C) Marks** â€” overview `block_on_provider=False` + budget 2 s ; `_try_acquire_credit_slot` Twelve Data ; test limiteur saturÃ© < 3 s.

**D) Isolation routes** â€” `test_open_paper_position_accepts_a_non_crypto_symbol` + garde baseline âˆ’5 % â†’ monkeypatch `ensure_baseline_portfolio` vers portefeuille jetable.


### CI Actions

- **VERTE** sur `5965b55` : https://github.com/samiriggui-code/IchiVol/actions/runs/35847816190
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Tests locaux (Postgres)

- `tests/paper` + golden API + brokerage ledger : **verts**
- `npm run build` : **OK**

### Non fait

- Merge #16 (CI verte, attend Claude) ; T2b dÃ©marrÃ© en parallÃ¨le (PR #17)

---

## 2026-09-23 â€” T0-CI â€” isolation baseline (revue Claude PR #14)

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergÃ©e**) â€” **validÃ© par Claude**
- Commit(s) : `8306028` (isolation baseline + disposable opens + garde snapshots)

### Correctif

Les helpers `_heal_baseline_if_halted` / `_restore_baseline` ne remettent **plus** le cash Ã  `initial_cash` ni ne vident toutes les `PaperEquitySnapshot` de la baseline.

- Capture en dÃ©but de test : cash, `realized_pnl`, ids de snapshots existants
- En fin : ne supprime QUE les snapshots crÃ©Ã©s pendant le test ; restaure cash / realized capturÃ©s
- Opens qui ont besoin dâ€™un livre propre â†’ portefeuille **jetable** (profil baseline copiÃ©) ; `open_user_confirmed(..., portfolio=)` optionnel
- Garde module : snapshot Â« historique Â» 2020-01-01 insÃ©rÃ© avant la suite `test_engine` â†’ doit survivre Ã  tous les tests

### Validation locale

- `tests/paper/test_engine.py` + suite complÃ¨te `tests` : PASS

### CI Actions

- **VERTE** : https://github.com/samiriggui-code/IchiVol/actions/runs/35843919501 (`3d0aa79`)
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

Historique baseline injectÃ© puis `tests/paper` + `tests/api` : historique survit, cash inchangÃ©, **0 Ã©chec** sur base vierge â†’ **merge**.

---

## 2026-09-23 â€” T0-CI greening â€” rewrite 13 paper/API tests + honest 422 + frontend job

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergÃ©e**) â€” **validÃ© par Claude**
- Commit(s) : `28929be` (13 tests + honest 422 + frontend job), `b1e5773` (baseline heal), `8aa8f9e` (handoff SHAs)
- **CI Actions VERTE** : https://github.com/samiriggui-code/IchiVol/actions/runs/35841290882
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### LivrÃ©

1. **13 tests rÃ©Ã©crits** pour le profil baseline 2026-09-21 (`require_atr_stop`, `allow_short=False`, `exit_mode=direction`) :
   - `tests/paper/test_engine.py` â€” `stop_distance`, portefeuilles jetables (`exit_mode=decision` / `allow_short`), `direction_flipped`, ATR stub sur rows auto, heal `daily_loss_halt`
   - `tests/api/test_routes.py` â€” ATR stub + BUY/LONG multi-classe ; cleanup ledger/cash
2. **422 honnÃªte** dans `app/api/paper_orders.py` : `no_atr_stop` / `short_not_allowed` / gates au lieu du faux message WATCH ; test `test_open_paper_position_reports_no_atr_stop_honestly`
3. **CI** `.github/workflows/engine-ci.yml` : job `frontend-build` (`npm ci` + `npm run build` sous `ichivol-app`)

### Validation

- Locale Cursor (Postgres 16) : 16/16 ciblÃ©s PASS ; suite complÃ¨te `tests` PASS
- GitHub Actions run `35841290882` sur `8aa8f9e` : **2/2 jobs verts**

### Hors scope

- Merge aprÃ¨s revue Claude (rejoue avec sa base)
- Skip Binance inchangÃ©

---

## 2026-09-23 â€” T0-CI â€” Postgres Actions + diagnostic des 13 paper failures

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergÃ©e**) â€” **validÃ© par Claude**
- Commit(s) : `c7f13b9` (workflow + diagnostic handoff)

### LivrÃ©

1. **Diagnostic des 13** (reproduits ici sur Postgres 16 frais + alembic head ; **exactement** les mÃªmes 13 noms que la baseline Claude).
2. **CI GitHub Actions** `.github/workflows/engine-ci.yml` :
   - service `postgres:16-alpine`, DB `ichivol_engine_dev`, user/password `postgres`/`root`
   - `DATABASE_URL=postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev` (dÃ©faut `app/config.py` / `.env.example`)
   - `alembic upgrade head` puis `pytest tests -v`
   - `ENABLE_BACKTEST_EVIDENCE/SIGNAL_TRACKING/PROTECTION_MONITOR=false` pour Ã©viter le bruit background
   - **CI honnÃªte** : pas de liste xfail / ignore â€” la suite tourne entiÃ¨re ; le job restera **rouge** tant que les 13 ne sont pas rÃ©Ã©crits. Aucune convention xfail prÃ©existante dans le repo.

### Cause racine (pas un bug V3)

Les Ã©checs viennent du **profil baseline figÃ© le 2026-09-21** (`BASELINE_PROFILE` dans `app/paper/strategy_profiles.py`), pas dâ€™une rÃ©gression code path rÃ©cente :

| ClÃ© profil | Effet sur les vieux tests |
|------------|---------------------------|
| `one_position_per_symbol` / `one_entry_per_signal_run` / `daily_loss_limit_pct` / `max_open_risk_pct` | `paper_gates.has_gates` = True â†’ `entry_gate` refuse sans ATR (`no_atr_stop`) |
| `require_atr_stop: True` | pas de repli Â« legacy open Â» une fois le gate actif |
| `allow_short: False` | tout `SELL`/`SHORT` â†’ `None` |
| `exit_mode: "direction"` | `WATCH` ne ferme plus ; flip â†’ `direction_flipped` (pas `pipeline_flipped` / `pipeline_downgraded`) |

Les tests modernes (`tests/paper/test_fwd_profiles.py`, `test_open_flow.py`, `test_manual_buy.py`, â€¦) passent dÃ©jÃ  avec stop ATR + portefeuilles jetables. `tests/paper/test_engine.py` et 2 fixtures API nâ€™ont **pas** Ã©tÃ© alignÃ©s.

Sur un open ratÃ©, la route `POST /paper/positions` mappe tout `position is None` vers `422 not_actionable: â€¦ WATCH/NO_TRADE` â€” message **trompeur** quand la vraie raison est `no_atr_stop` / `short_not_allowed` (dÃ©tail UX mineur, pas la cause des 13).

### Tableau diagnostic (13)

| Test | Classe | Cause probable | Action recommandÃ©e |
|------|--------|----------------|--------------------|
| `test_sync_position_opens_a_long_on_buy_with_no_existing_position` | obsolete test | Appel sans `stop_distance` â†’ gate `no_atr_stop` â†’ `None` | **fix test** : passer `stop_distance>0` (comme `test_fwd_profiles`) |
| `test_sync_position_holds_an_open_position_while_still_supported` | obsolete test | MÃªme open bloquÃ© â†’ pas de position Ã  tenir | **fix test** (+ stop) |
| `test_sync_position_closes_when_decision_downgrades_to_watch` | obsolete test | Open bloquÃ© **et** `exit_mode=direction` (WATCH+mÃªme direction ne ferme plus) | **fix test** : scÃ©nario `direction` (cf. `test_t1_*`) ou portefeuille jetable `exit_mode` legacy |
| `test_sync_position_closes_when_pipeline_direction_flips` | obsolete test | Open bloquÃ© ; mÃªme avec open, raison attendue serait `direction_flipped` | **fix test** |
| `test_short_position_pnl_is_positive_when_price_falls` | obsolete test | `allow_short=False` sur baseline | **fix test** : portefeuille jetable `allow_short=True` **ou** drop (shorts volontairement off) |
| `test_sync_auto_watchlist_processes_multiple_rows_and_commits` | obsolete test | Fake rows sans ATR â†’ aucun open | **fix test** : ATR / `stop` sur les rows |
| `test_open_user_confirmed_is_idempotent` | obsolete test | Sans stop â†’ pas de 1er open (`created1=False`) | **fix test** : `stop_distance` |
| `test_close_manually_closes_an_open_position` | obsolete test | Open impossible sans stop | **fix test** |
| `test_close_manually_returns_none_for_an_already_closed_position` | obsolete test | idem | **fix test** |
| `test_list_positions_filters_by_source_user_and_status` | obsolete test | user open sans stop + auto SHORT interdit | **fix test** : stop + LONG (ou pf `allow_short`) |
| `test_open_user_confirmed_locks_symbol_already_open_on_portfolio` | obsolete test | 1er open sans stop Ã©choue | **fix test** |
| `test_open_paper_position_opens_on_an_actionable_decision` | env/fixture | `ScreenerRow` fake sans `atr` â†’ `stop=None` â†’ mÃªme gate ; 422 (detail WATCH trompeur) | **fix test** : stub `atr.suggested_stop_distance` ; mock aussi `scan_symbol` sur le close |
| `test_open_paper_position_accepts_a_non_crypto_symbol` | obsolete test + fixture | `SELL`/`SHORT` + `allow_short=False` (+ pas dâ€™ATR) â†’ 422 | **fix test** : `BUY`/`LONG` + ATR stub (multi-classe â‰  short) |

**Skip Binance** (hors des 13) : `tests/market_data/test_binance.py` â€” `skipif` si `data-api.binance.vision` injoignable (HTTP 451 / rÃ©seau). Normal en CI sans accÃ¨s Binance.

**Vrai bug ?** Non pour le comportement dâ€™open/close baseline (dÃ©cision produit 2026-09-21, couverte ailleurs). Seul point code optionnel : message 422 trop gÃ©nÃ©rique quand `open_user_confirmed` renvoie `None` pour une autre raison que WATCH â€” **fix code** cosmÃ©tique, hors pÃ©rimÃ¨tre T0-CI si on veut rester minimal.

### Mapping CI â†” baseline

| Situation | Attendu |
|-----------|---------|
| PR actuelle T0-CI / `main` tant que les 13 existent | job `pytest (Postgres 16)` **fail** avec les **mÃªmes 13** (+ skip Binance) |
| PR qui ajoute un 14e Ã©chec | **rÃ©gression** â†’ bloquer merge (rÃ¨gle Claude inchangÃ©e) |
| Follow-up qui rÃ©Ã©crit `test_engine.py` + 2 fixtures API | CI **vert** |

Pas de `xfail` documentÃ© : prÃ©fÃ¨re un signal rouge honnÃªte.

### Non fait / hors pÃ©rimÃ¨tre

- RÃ©Ã©criture des 13 tests (follow-up T0-CI-green)
- DÃ©coupage `routes.py` (T1g), structure, registry

### Tests (cette branche)

- Repro locale Cursor : Postgres 16 + alembic â†’ `tests/paper/test_engine.py` + `tests/api/test_routes.py` â†’ **13 failed, 28 passed** (les 2 paper qui passent encore : WATCH no-op + open non-actionable)
- Suite complÃ¨te non exigÃ©e ici pour greening ; le workflow Actions est le filet permanent

---

## 2026-09-23 â€” T2a â€” ChartObject (typed overlays from engine)

- Branche : `v3/t2a-chart-objects`
- PR : https://github.com/samiriggui-code/IchiVol/pull/15 (**mergÃ©e**) â€” **validÃ© par Claude**
- Commit(s) : `3672f5d` (feat) ; `a41ef76` / `ad3f9a3` / `6b96c94` / `b9a9dd0` (handoff) ; `428c1f9` (fix detector window bars)
- Base : `main` aprÃ¨s merge PR #14 (T0-CI)

- **Fix (pytrendline bar indices)** : `start_bar`/`end_bar` sont relatifs Ã  la fenÃªtre du dÃ©tecteur (`meta["bars"]`, pytrendline cap 150), pas Ã  `window_bars` (300). `_line_dict` dans `get_structure` et `_line_endpoints` dans `from_structure` utilisent dÃ©sormais `window[-bars:]` / `candles[-bars:]` par dÃ©tecteur. Sans pytrendline, `bars == window_bars` â†’ rÃ©ponse `/structure` inchangÃ©e. **Revue Claude** : dÃ©calage corrigÃ© dans ChartObjects et `/structure`, vÃ©rifiÃ© sur la reproduction ; aucun golden existant modifiÃ©.

- LivrÃ© :
  - ModÃ¨le `app/chart_objects/types.py` â€” `ChartObject` frozen, id dÃ©terministe (sha256[:24] de type/source/symbol/tf/coords arrondis/subtype), validation par type, `to_dict`/`from_dict`
  - Producteur `from_structure.py` â€” sÃ©lection **identique** Ã  `structure.ts` `toStructureOverlay` (MAX_ZONES=3, MAX_TRENDLINES=2, score desc, lignes drawable seulement) ; zones consensus â†’ ZONE ; trendlines dÃ©tecteurs â†’ TREND_LINE ; breakouts â†’ MARKER
  - Confiance : `clamp(score / max_score_pool, 0, 1)` (docstring)
  - API `GET /api/engine/chart-objects/{symbol}?timeframe=&limit=&sources=engine` â€” router dÃ©diÃ© `api/chart_objects.py`, branchÃ© en fin dâ€™agrÃ©gateur `routes.py` ; sources non-ENGINE â†’ liste vide (pas dâ€™erreur)
  - Front : `src/lib/chartObjects.ts` + `PriceChart.renderChartObjects` (ZONE = 2 price lines pointillÃ©es Â« S/R Ã—n Â», TREND_LINE = LineSeries dashed, MARKER = circle) ; `MarketPage` appelle `getChartObjects` ; `toStructureOverlay` / `getEngineStructure` retirÃ©s
  - Goldens OpenAPI + `route_order` : **ajouts seuls** (`/chart-objects/{symbol}`)

- Tests :
  - `tests/chart_objects/` â€” round-trip, validation, id stable, sÃ©lection parity seeds 7 & 42, causalitÃ© `as_of`
  - `tests/chart_objects/test_detector_window_alignment.py` â€” indices relatifs Ã  `meta["bars"]` ; pytrendline seed 7 â‰  offset 150 ; `/structure` sans pytrendline identique
  - `tests/api/test_chart_objects_route.py` â€” ENGINE OK ; user/claude â†’ `objects=[]`
  - `test_api_surface_golden` â†’ vert
  - `npm run build` â†’ OK

- Hors scope (T2b/T5) : outils dessin Claude, persistence USER/CLAUDE, ENTRY/STOP/TARGET

---

## 2026-09-23 â€” T1g â€” DÃ©coupage de `api/routes.py` (zÃ©ro changement de comportement)

- Branche : `v3/t1g-split-routes`
- PR : https://github.com/samiriggui-code/IchiVol/pull/13 (**mergÃ©e** dans `main` @ `a19f924`) â€” **validÃ© par Claude**
- Commit(s) : `d58adca` (golden OpenAPI + ordre des routes **avant** refactor) ; `67ae482` (dÃ©coupage)

- LivrÃ© :
  - Modules domaine : `market.py`, `context.py`, `decisions.py`, `backtest.py`, `rulesets.py`, `strategy_lab.py` + `strategy_lab_wf.py`, `paper.py` + `paper_orders.py`, `agent.py`, `common.py`
  - `routes.py` = agrÃ©gateur qui `include_router` **dans lâ€™ordre dâ€™origine** (main.py inchangÃ©)
  - Fragments de routers lÃ  oÃ¹ le domaine nâ€™est pas contigu (market head/screener/correlations ; paper before/after shadow ; backtest evidence/symbol/shadow)
  - Tags inchangÃ©s (`["engine"]`) ; helpers partagÃ©s dans `common.py`
  - Golden : `tests/api/fixtures/openapi_golden.json`, `route_order_golden.json` + `test_api_surface_golden.py`

- Monkeypatch mis Ã  jour (cible dÃ©placÃ©e, comportement inchangÃ©) :
  - `tests/api/test_routes.py` â€” `scan_symbol` aussi sur `decisions` / `paper` / `paper_orders` ; `compute_correlation_matrix` aussi sur `market`
  - `tests/api/test_open_flow.py` â€” `scan_symbol` aussi sur `paper` / `paper_orders`
  - `test_structure_line_dict.py` â€” toujours via rÃ©export `routes._line_dict`

- Fixtures : seuls les 2 nouveaux golden API ajoutÃ©s ; `git diff main -- '**/fixtures/*'` hors ceux-lÃ  â†’ vide

- Lignes `app/api/` (tous â‰¤ ~400) : routes 46, agent 92, context 90, common 185, decisions 155, rulesets 145, backtest 171, strategy_lab 208, strategy_lab_wf 240, paper 269, paper_orders 232, market 268

- Tests :
  - `test_api_surface_golden` â†’ vert (OpenAPI + ordre)
  - `tests/api/` â†’ seuls les **2** `open_paper_position` connus (baseline 13, DB dispo ici) ; pas de nouvelle rÃ©gression
  - Claude avec Postgres : baseline **13** Ã©checs

- Non fait Ã  lâ€™Ã©poque : T0-CI (branche parallÃ¨le) ; T2 ChartObject â€” **T1 terminÃ©** (T1â†’T1g). T2a = cette branche.

---

## 2026-09-23 â€” T1f-2 â€” Plus de repaint dans pytrendline

- Branche : `v3/t1f2-pytrendline-no-repaint`
- PR : https://github.com/samiriggui-code/IchiVol/pull/12 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `81a5db1` (comportement + tests + golden legacy) ; `9831db9` (handoff PR #12)

- **Note backtests** : les backtests du profil `STRUCTURE_PYTRENDLINE` faits **avant** la PR #12 ne sont **plus comparables** (le gate a changÃ© avec lâ€™exclusion des pivots provisoires).

- LivrÃ© :
  - `StructureEngineParams.allow_provisional_anchors: bool = False` â€” `True` = ancien comportement (tests / A-B uniquement, jamais en profil live)
  - `pytrendline._detect_side` : fit uniquement sur pivots `provisional=False` (sauf flag) ; pas de repli sur les ancres si trop peu de fractals confirmÃ©s
  - Ancres premiÃ¨re/derniÃ¨re toujours prÃ©sentes dans `MarketStructure.pivots` (marking T1f)
  - `TrendlineSegment.fit_pivot_bars` â€” paire dâ€™ancres du fit (non exposÃ©e API)
  - Tests : (c) inversÃ© (lignes = pivots confirmÃ©s) ; stabilitÃ© des lignes (identique ou disparue, jamais mutÃ©e) ; golden `allow_provisional_anchors=True`

- Fixtures :
  - **Aucune fixture existante ne dÃ©pendait de pytrendline** (consensus dÃ©faut / baseline inchangÃ©s).
  - **Ajout** : `tests/structure/fixtures/pytrendline_provisional_anchors_golden.json` â€” capture de lâ€™ancien comportement (`allow_provisional_anchors=True`) pour seeds 7 & 42 :
    | seed | lignes | zones |
    |------|--------|-------|
    | 7 | 10 | 10 |
    | 42 | 10 | 10 |
  - `git diff main -- '**/fixtures/*'` hors ce fichier â†’ vide

- Mesure dâ€™impact (synthÃ©tique 300 barres ; BTCUSDT 1h : **pas de cache**, Binance HTTP 451) :

  | seed | lignes avant â†’ aprÃ¨s | zones avant â†’ aprÃ¨s | composition lignes |
  |------|----------------------|---------------------|--------------------|
  | 7 | 10 â†’ 10 (plafond `max_lines_per_side`) | 10 â†’ 10 | 7 partagÃ©es, 3 seules-avant, 3 seules-aprÃ¨s ; mids zones â‰  |
  | 42 | 10 â†’ 10 | 10 â†’ 10 | 6 partagÃ©es, 4 / 4 ; mids zones â‰  |

  Gate `STRUCTURE_PYTRENDLINE` sur 12 fenÃªtres `tâˆˆ{80..300}` (BUY+SELL) :

  | seed | BUY acceptÃ©s avant â†’ aprÃ¨s | BUY bloquÃ©s | SELL acceptÃ©s | SELL bloquÃ©s |
  |------|----------------------------|-------------|---------------|--------------|
  | 7 | 5 â†’ **4** | 7 â†’ **8** | 5 â†’ **7** | 7 â†’ **5** |
  | 42 | 6 â†’ **9** | 6 â†’ **3** | 1 â†’ **4** | 11 â†’ **8** |

  â†’ Le gate change bien (zones dÃ©rivÃ©es des lignes). Consensus dÃ©faut (mvpp+trendln) et `ICHIVOL_BASELINE_V1` non touchÃ©s.

- Choix faits :
  - Flag sur `StructureEngineParams` (pas un arg ad-hoc du seul adaptateur) pour que le gate / service hÃ©ritent du dÃ©faut sÃ»r.
  - `fit_pivot_bars` pour tester la non-mutation sans ambiguÃ¯tÃ© des `pivot_bars` (touches).

- Doutes / points Ã  vÃ©rifier par Claude : **validÃ© par Claude**.

- Non fait / hors pÃ©rimÃ¨tre :
  - mvpp / trendln / consensus dÃ©faut
  - dÃ©coupage `routes.py` (T1g)
  - T0-CI (branche sÃ©parÃ©e)
  - MergÃ© dans `main` aprÃ¨s validation Claude.

- Tests :
  - `tests/structure/` â†’ all green (causality + engines + gate + golden atr)
  - suite complÃ¨te **sans Postgres** (Cursor) â†’ **4 failed** connexion DB connus ; fixtures hors nouveau golden inchangÃ©es
  - revue Claude avec base : baseline **13** Ã©checs paper/api ; tout Ã©cart = rÃ©gression

---

## 2026-09-23 â€” T1f â€” Pivots confirmÃ©s + repaint mesurÃ© (mark-only)

- Branche : `v3/t1f-pivot-confirmation`
- PR : https://github.com/samiriggui-code/IchiVol/pull/11 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `37ac28f` (mÃ©tadonnÃ©es + adaptateurs + tests de causalitÃ©) ; `74a0c8f` / `c1ff782` / `ef85f57` (rapport handoff)

- LivrÃ© :
  - `PivotPoint.confirmed_bar` / `PivotPoint.provisional` (optionnels, dÃ©fauts `None` / `False`)
  - Remplissage adaptateurs : mvpp `j+right` ; trendln `i` ; pytrendline fractals `i`, ancres premiÃ¨re/derniÃ¨re `provisional=True` + `confirmed_bar=last` ; consensus propage les pivots sources
  - `tests/structure/test_structure_causality.py` â€” (a) `confirmed_bar <= t-1` ; (b) stabilitÃ© non-provisoire (fenÃªtre commune + exclusion left-lookback pour pytrendline `max_bars=150`) ; (c) preuve de repaint pytrendline (ancre provisoire absente Ã  `t+1`)
  - API `/structure` : toujours `pivot_count` seulement â€” **pas** d'exposition des nouveaux champs
  - `git diff main -- '**/fixtures/*'` â†’ vide

- Mesure d'impact (2 seeds synthÃ©tiques 300 barres ; BTCUSDT 1h cache/live indisponible ici â€” Binance 451) :

  | Jeu | Trendlines pytrendline avec â‰¥1 pivot provisoire | Consensus trendlines (objet) | Zones consensus (avec pyt) liÃ©es Ã  une ligne provisoire |
  |-----|-----------------------------------------------|------------------------------|---------------------------------------------------------|
  | seed 7 | **3/10 (30 %)** | **0** (consensus ne porte pas de trendlines) | 1/4 zones Ã  source PYTRENDLINE (25 % de ces zones) ; 3/30 lignes union dÃ©tecteurs (10 %) |
  | seed 42 | **4/10 (40 %)** | **0** | 4/7 zones pyt (57 %) ; 4/30 lignes union (13 %) |

  - Consensus **par dÃ©faut** (mvpp+trendln, sans pyt) : aucun pivot provisoire â†’ 0 % d'impact provisoire.
  - Profils paper : `STRUCTURE_PYTRENDLINE` utilise `structure_detectors=["pytrendline"]` â†’ zones gate potentiellement contaminÃ©es ; consensus multi-dÃ©tecteurs avec `include_pytrendline` aussi.

- Gate / breakouts (`structure/gate.py`, `service.detect_market_structure`) :
  - **Oui** : le gate et les breakouts utilisent les **zones consensus** (pas les pivots ni les trendlines directement).
  - Les zones pytrendline sont dÃ©rivÃ©es de `line.price_at(last_bar)` â€” donc une ligne ancrÃ©e sur un pivot provisoire **peut** dÃ©placer une zone opposante du gate quand pyt est inclus.
  - Baseline `ICHIVOL_BASELINE_V1` : `structure_filter=None` â†’ pas d'impact.

- Choix faits :
  - Mark-only : aucun changement de fit / seuils / exclusion de pivots.
  - Consensus : propage `pivots` des sources (pour tests/mesure) ; zones/scores inchangÃ©s.
  - StabilitÃ© pytrendline : identitÃ© en indices absolus (`bar_index + offset`) ; hors fenÃªtre commune ou dans `left_ctx` du bord gauche aprÃ¨s glissement â†’ exclus (artefact de fenÃªtre, documentÃ©).

- Doutes / points Ã  vÃ©rifier par Claude : **validÃ©** â€” dÃ©cision Claude : exclure les pivots provisoires du fit pytrendline (T1f-2), sans seuil.

- Non fait / hors pÃ©rimÃ¨tre :
  - Exclusion des pivots provisoires / changement de comportement â†’ **T1f-2**
  - `StructureState` indicators / ChartObject / dÃ©coupage `routes.py` (T1g)
  - MergÃ© dans `main` aprÃ¨s validation Claude.

- Tests :
  - `test_structure_causality.py` â†’ **18 passed**
  - suite `tests/structure/` â†’ all green
  - suite complÃ¨te **sans Postgres** (Cursor) â†’ **4 failed** connexion DB (connus localement) ; fixtures inchangÃ©es
  - revue Claude **avec Postgres** : baseline = les **13** Ã©checs historiques ci-dessus ; tout Ã©cart = rÃ©gression bloquante
  - T0-CI non dÃ©marrÃ© ici (branche sÃ©parÃ©e si lancÃ© en parallÃ¨le)

---

## 2026-09-23 â€” T1e â€” Fin de la migration REGISTRY (cliquet vide)

- Branche : `v3/t1e-registry-remaining`
- PR : https://github.com/samiriggui-code/IchiVol/pull/10 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `0227abf` (fixtures golden **avant** refactor) ; `a4497a9` (migration + cliquet vide)

- LivrÃ© :
  - `app/api/routes.py` â€” `GET /context/{symbol}` via `REGISTRY.compute_many(rsi/cmf/obv/atr)`
  - `app/agent_channel/commands.py` â€” `REGISTRY.compute` ichimoku/rvol (`compute_correlation_matrix` inchangÃ©)
  - `app/backtest/experiments.py` â€” `compute_many` structure/atr/location/cvd/adx/donchian/wyckoff
  - `app/strategy_lab/regime.py` â€” `compute_many` adx+atr
  - `app/synthetic/validation.py` â€” `compute_many` structure/atr/location/adx
  - `app/structure/atr_utils.py` â€” `REGISTRY.compute("atr")`
  - fixtures golden + tests d'Ã©galitÃ© stricte
  - `test_registry_ratchet.py` â€” `ALLOWED_DIRECT_CALLERS = âˆ…` ; scan de tout `app/` hors `indicators/` ; exceptions documentÃ©es pour `compute_oi_funding` / `compute_projected_kumo`

- Tests :
  - golden + cliquet OK ; suites indicators/strategy_lab/backtest/synthetic/structure/api (hors evidence route Postgres) â†’ **339 passed**, 23 skipped
  - suite complÃ¨te â†’ **4 failed** Postgres connus
  - `grep compute_<id>(` hors `app/indicators/` â†’ vide

- Choix faits :
  - experiments : adx/donchian/wyckoff aussi migrÃ©s (nÃ©cessitÃ© cliquet vide).
  - Cliquet : interdiction pure + scan rÃ©cursif de tout `app/`.

- Doutes / points Ã  vÃ©rifier par Claude : aucun restant â€” **validÃ© par Claude**.

- Non fait / reste Ã  faire :
  - dÃ©coupage `routes.py` (T1g), structure unifiÃ©e / confirmed_at (T1f), CONDITION_SCHEMA
  - MergÃ© dans `main` aprÃ¨s validation Claude.

---

## 2026-09-23 â€” T1d â€” Chemin live via le REGISTRY

- Branche : `v3/t1d-live-path-registry`
- PR : https://github.com/samiriggui-code/IchiVol/pull/9 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `89caa75` (fixtures golden **avant** refactor) ; `51b0edf` (migration + ratchet)

- LivrÃ© :
  - `ichivol-app/engine/app/screener/service.py` â€” `REGISTRY.compute_many` (structure/atr/location/cvd/adx/donchian) ; `compute_oi_funding` reste direct
  - `ichivol-app/engine/app/context/gate.py` â€” `compute_many` pour atr/rsi/cmf/obv selon le profil
  - `ichivol-app/engine/app/evidence/catalog.py` â€” `compute_many` structure+atr
  - `ichivol-app/engine/app/agents/ichimoku_agent.py` â€” `REGISTRY.compute("ichimoku")`
  - `ichivol-app/engine/app/agents/rvol_agent.py` â€” `REGISTRY.compute("rvol")`
  - fixtures golden (seeds 7 & 42) sous `tests/{screener,context,evidence,agents}/fixtures/`
  - tests d'Ã©galitÃ© stricte + `ALLOWED_DIRECT_CALLERS` rÃ©duit aux 6 modules T1e

- Tests :
  - suites indicators/strategy_lab/screener/context/evidence/agents + indicators_route (hors persistence Postgres) â†’ **317 passed**, 2 skipped
  - suite complÃ¨te â†’ **4 failed** Postgres connus uniquement
  - cliquet ratchet vert (5 modules retirÃ©s)

- Choix faits :
  - Screener : cvd/adx/donchian aussi via `compute_many` (sinon le module resterait dans le cliquet).
  - Gate : un seul `compute_many` des indicateurs demandÃ©s par le profil.
  - Signatures publiques / seuils inchangÃ©s.

- Doutes / points Ã  vÃ©rifier par Claude : aucun restant â€” **validÃ© par Claude** (cvd/adx/donchian screener OK).

- Non fait / reste Ã  faire :
  - T1e : modules restants + cliquet vide.
  - CONDITION_SCHEMA, structure unifiÃ©e.
  - MergÃ© dans `main` aprÃ¨s validation Claude.

---

## 2026-09-23 â€” T1c â€” Features Strategy Lab via REGISTRY (`compute_many`)

- Branche : `v3/t1c-registry-features`
- PR : https://github.com/samiriggui-code/IchiVol/pull/8 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `5b56470` (fixture golden **avant** refactor) ; `3550c0c` (registry + features + ratchet) ; nested params `cb300c2`

- LivrÃ© :
  - `ichivol-app/engine/app/indicators/registry.py` â€” `depends_on`, `compute_many` (topo + dÃ©dup + cycle), enregistrement `ichimoku_analytics` / `location` / `wyckoff` ; `oi_funding` hors registry (docstring)
  - `ichivol-app/engine/app/strategy_lab/features.py` â€” un seul `REGISTRY.compute_many(...)` ; signatures / `FeatureBar` inchangÃ©s
  - `ichivol-app/engine/tests/strategy_lab/fixtures/features_golden.json` â€” FeatureBars seeds 7 & 42 (300 barres), commit **avant** le refactor
  - `ichivol-app/engine/tests/strategy_lab/test_features_golden.py` â€” Ã©galitÃ© stricte vs fixture
  - `ichivol-app/engine/tests/indicators/test_registry_ratchet.py` â€” cliquet `ALLOWED_DIRECT_CALLERS` (features.py absent)
  - `ichivol-app/engine/tests/indicators/test_registry.py` â€” compute_many / cycle / warmup deps ; `test_no_lookahead` couvre les 3 nouveaux via `REGISTRY.compute`

- Tests :
  - `pytest tests/indicators tests/strategy_lab tests/api/test_indicators_route.py` â†’ **241 passed, 1 skipped**
  - suite complÃ¨te â†’ **4 failed** Postgres connus uniquement

- Choix faits :
  - Wrappers registry pour analytics/location/wyckoff : `compute_fn(candles, params, deps)` ; analytics reÃ§oit `ichi`/`atr` dÃ©jÃ  calculÃ©s (pas de double compute).
  - `REGISTRY.compute(id)` sur un indicateur dÃ©pendant dÃ©lÃ¨gue Ã  `compute_many` pour rÃ©soudre les deps.
  - Warmup dÃ©pendant = `max(own, deps.warmup())`.
  - Fixture golden gÃ©nÃ©rÃ©e et commitÃ©e **avant** toute modification de `features.py` / registry deps.

- Doutes / points Ã  vÃ©rifier par Claude : aucun restant â€” **validÃ© par Claude** (nested params corrigÃ©s).

- Corrections revue Claude :
  - `build_params` fusionne rÃ©cursivement les dataclasses imbriquÃ©es ; clÃ© inconnue â†’ `InvalidParamsError` avec chemin (`location.volume_profile.foo`) ; API â†’ 422.
  - Endpoint series utilise `REGISTRY.compute` (rÃ©sout deps location/wyckoff/analytics).
- Non fait / reste Ã  faire :
  - Migration des autres modules â†’ T1d.
  - CONDITION_SCHEMA (T3 DSL), structure unifiÃ©e, dÃ©coupage `routes.py`.
  - MergÃ© dans `main` aprÃ¨s validation Claude.

---

## 2026-09-23 â€” T1b â€” Front servi par le moteur (Ichimoku / RVOL / kumo projetÃ©)

- Branche : `v3/t1b-front-engine-indicators`
- PR : https://github.com/samiriggui-code/IchiVol/pull/7 (mergÃ©e) â€” **validÃ© par Claude**
- Commit(s) : `25e2249` (code initial) ; handoff `417da25`â€¦ ; corrections revue Claude `30991c7`

- LivrÃ© :
  - `docs/HANDOFF-CURSOR-V3.md` â€” canal handoff V3 (entrÃ©e T1 + T1b)
  - `ichivol-app/engine/app/indicators/ichimoku.py` â€” `compute_projected_kumo` (display-only ; ne touche pas `IchimokuState` / `compute_ichimoku`)
  - `ichivol-app/engine/app/api/indicators.py` â€” `GET /indicators/ichimoku/{symbol}/projection` : compute sur **tout** le fetch `limit+warmup`, filtre `time_projected >= window[0].time` ; params via `REGISTRY.get("ichimoku").build_params` / `.warmup`
  - `ichivol-app/engine/tests/indicators/test_projected_kumo.py` â€” Ã©galitÃ© i+d, garde import, **warmup fenÃªtre** (600â†’limit 300 â†’ 1er `time_projected` = dÃ©but fenÃªtre)
  - `ichivol-app/engine/tests/api/test_indicators_route.py` â€” projection garde warmup + params 422 via registry
  - `ichivol-app/src/lib/engineIndicators.ts` â€” client registry ; `mapEngineIchimokuToPoints` sans repli `closeByTime` (chikou=`null` si idx absent)
  - `ichivol-app/src/lib/signals.ts` â€” `buildVolumePulse` depuis sÃ©ries moteur
  - `ichivol-app/src/components/PriceChart.tsx` â€” overlays async moteur ; prix seul si erreur
  - `ichivol-app/src/pages/MarketPage.tsx` â€” props `symbol`/`timeframe`/`onLive`
  - `ichivol-app/src/index.css` â€” message discret overlays
  - `ichivol-app/src/lib/ichimoku.ts` â€” **supprimÃ©**

- Tests (aprÃ¨s corrections revue) :
  - `cd ichivol-app/engine && .venv/bin/python -m pytest tests/indicators tests/api/test_indicators_route.py -q` â†’ **tous OK** (169 passed au dernier run)
  - `cd ichivol-app && npm run build` â†’ **OK**
  - Ã‰checs Postgres connus hors scope (suite complÃ¨te) : inchangÃ©s

- Choix faits :
  - Nuage futur via helper sÃ©parÃ© + endpoint dÃ©diÃ© (pas de changement de `compute_ichimoku`).
  - Warmup : ne pas tronquer avant `compute_projected_kumo` â€” sinon ~`senkou_b` barres sans nuage en tÃªte de fenÃªtre.
  - Params projection alignÃ©s sur lâ€™endpoint series (`InvalidParamsError` â†’ 422).
  - Chikou affichage uniquement ; pas de fallback close non dÃ©calÃ©.

- Doutes / points Ã  vÃ©rifier par Claude :
  - Aucun restant â€” **validÃ© par Claude**.

- Non fait / reste Ã  faire :
  - Structure unifiÃ©e, dÃ©coupage `routes.py`, `ChartObject` (hors pÃ©rimÃ¨tre T1b).
  - MergÃ© dans `main` (fast-forward). Suite : T1c.

---

## 2026-09-23 â€” T1 (Ã©tapes 1â€“3) â€” IndicatorRegistry + API /indicators

- Branche : `v3/t1-indicator-registry`
- PR : https://github.com/samiriggui-code/IchiVol/pull/6 (mergÃ©e)
- Commit(s) : `39fad41` (registry + API), `88fdb1f` (borne `limit` 1..5000), merge `b832bb4` dans `main`
- Statut : **validÃ© par Claude**

- LivrÃ© :
  - `ichivol-app/engine/app/indicators/registry.py` â€” `IndicatorRegistry` / `REGISTRY`, catalog, `build_params`, warmup, serialize
  - `ichivol-app/engine/app/api/indicators.py` â€” `GET /indicators`, `GET /indicators/{id}/{symbol}`
  - `ichivol-app/engine/app/main.py` â€” montage du router indicators
  - `ichivol-app/engine/tests/indicators/test_registry.py` â€” tests registry
  - `ichivol-app/engine/tests/api/test_indicators_route.py` â€” tests route + bornes `limit=0` / `limit=-5` â†’ 422

- Tests :
  - Suite indicators / registry + `test_indicator_limit_bounds_422` : OK sur la PR (fix `limit` avant merge pour Ã©viter `states[-0:]` = sÃ©rie entiÃ¨re).
  - Ã‰checs Postgres connus hors pÃ©rimÃ¨tre T1 (inchangÃ©s).

- Choix faits :
  - Registry thin wrapper autour des `compute_*` existants (pas de rÃ©Ã©criture de formules).
  - `Query(ge=1, le=5000)` sur `limit` aprÃ¨s revue Claude (bug `limit=0` / nÃ©gatif).

- Doutes / points Ã  vÃ©rifier par Claude : aucun restant â€” **validÃ©**.

- Non fait / reste Ã  faire : consommÃ© par le front â†’ T1b (ci-dessus).

## UI-port pages (PR #109) â€” 2026-09-25
- Branche `cursor/ui-port-pages-a2fe` tip `ab33224` Â· draft
- RAPPORT 11Ã—0 Â· ACTIONS-METIER.md Â· paper open/close smoke PASS
- VPS `RELEASE=ab33224` backup `pre-uiport-paper-20260925-140655.tgz`
- **Pas de merge** avant Claude + Samir OK
## 2026-09-25 â€” Chantier 2 E1 Eve runtime (P1) â€” draft

- Branche `cursor/eve-runtime-a2fe` (suite E0 @ `cac24f4` / tip handoff prÃ©cÃ©dent)
- **E1 livrÃ© (server only, paper)** :
  1. Outil `schedule_recheck` (reason â‰¥10, next_closed_candle +60s, upsert open recheck) + wiring Claude tools
  2. Skills markdown on-demand (`server/src/agent/skills/*.md` + `loadSkills`)
  3. Missions **1 symbole** (`createMission`) â€” Eve chat = **threads Copilot** (pas de 2e chat)
  4. `missionRunner` : gate fraÃ®cheur `stale`/`data_late` â†’ **pas de wake LLM**, defer + log ; condition â†’ defer E2 (plus de stub-complete)
  5. API stubs : `GET /api/agents`, `GET /api/agents/:id/tasks`, `GET /api/agents/logs`, `POST /api/agents/missions`
- Garde-fous : paper only ; LLM sans DB/broker direct ; `humanConfirmDefault` / `autoOpen: false`
- Tests : `npm test` dans `ichivol-app/server` â€” **56 pass** (E0 + E1 `e1Runtime.test.ts`)
- **Draft PR #111 â€” pas de merge**

### Gaps / suite E2
1. `evaluate_watch_condition` engine (RVOL/ADX/pipeline DSL) â€” wake LLM seulement si met
2. Budget LLM journalier / max rechecks symbole (contrainte partielle via upsert)
3. UI AgentsPage brancher sur `/api/agents*`

---

## 2026-09-25 â€” Chantier 2 E0 Eve runtime (P0) â€” draft

- Branche `cursor/eve-runtime-a2fe` depuis `main` @ `225549d` (#109 squash-merged)
- **Option D hybride** : patterns Comp AI (file Postgres + SKIP LOCKED + leases + poke) dans IchiVol server â€” **pas** de container Eve
- Prisma : `AgentTask` (`agent_tasks`) + `AgentLog` (`agent_logs`) â€” migration `20260925143000_agent_runtime_e0`
- Runtime server : `tasks.ts` (schedule/claim/complete/reconcile), `staleTasks.ts`, `runtime/dispatcher.ts` (worker minute + stub process), `POST /api/agent/runtime/poke` (Bearer `AGENT_BRIDGE_SECRET`)
- Paper only ; LLM non rÃ©veillÃ© en E0 ; `evaluate_watch_condition` / `schedule_recheck` â†’ **E1/E2**
- Tests : `npm test` dans `ichivol-app/server` â€” 41 pass (dont 6 E0 : claim concurrent, stale lease, idempotency)
- **Draft PR â€” pas de merge** ; parent ManagePullRequest

### Gaps / suite E1
1. Outil `schedule_recheck` (raison â‰¥10 car.) + wiring Claude tools
2. Ne plus stub-complÃ©ter les tÃ¢ches Ã  condition â€” attendre E2 `evaluate_watch_condition`
3. `missionRunner` bornÃ© (budget LLM) sur wake rÃ©el

---

## 2026-09-25 â€” UI-port #109 MERGÃ‰E + VPS â€” tip `225549d`

- PR : https://github.com/samiriggui-code/IchiVol/pull/109 â€” **MERGÃ‰E** (squash) â†’ tip `225549d`
- Contenu : 11 pages portÃ©es + correctifs Portefeuille (toutes positions) + OpportunitÃ©s Â« Enregistrer la dÃ©cision Â»
- **VPS** : https://ichivol.global-it-ss.com â€” `RELEASE=225549d main` Â· rebuild `web` Â· public/health **200**
- Backup : `/opt/ichivol-backup/pre-uiport-merge-20260925-141927.tgz` (+ `pre-uiport-merge-src-*`)
- #108 fermÃ©e (incluse dans #109) ; remotes `cursor/ui-port-marche-a2fe` + `cursor/ui-clean-a2fe` supprimÃ©es

### Suite
Chantier 1 fiches (parallÃ¨le) + Chantier 2 E0 runtime (cette branche) â€” draft, pas de merge.

---

