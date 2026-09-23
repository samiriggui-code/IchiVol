# Handoff Cursor ↔ Claude — IchiVol V3

Canal unique entre Cursor (implémentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff de la PR associée.

**Convention** : à chaque PR, ajouter une nouvelle entrée **en haut** ; ne jamais effacer les anciennes.

### Suite de tests — Postgres (supervision 2026-09-23)

- **Claude** (revue) : PostgreSQL 16 `ichivol_engine_dev`, migrations alembic appliquées → lance la suite **complète** (paper, backtest evidence, brokerage, market_data inclus).
- **Cursor** (implémentation) : **pas** d’install Postgres local ; suite sans base comme d’habitude ; reporter les résultats dans le handoff. Les échecs liés à la base sont détectés / renvoyés par Claude.
- **Baseline avec base** (mesurée par Claude, identique sur `main` `fe5b28f` = V3 jusqu’à T1e et sur `8a26a97` = avant V3) :
  - **13 échecs** : 11× `tests/paper/test_engine.py` + 2× `tests/api/test_routes.py` (`open_paper_position`)
  - **1 skip** réseau Binance
  - **Aucune régression V3** (même compte avant/après)
- **Règle de merge** : avec la base, **0 échec** attendu (T0-CI #14 mergé). Tout échec bloque le merge.
- **T0-CI** : greening + isolation baseline — **mergé** (PR #14) — **validé par Claude**.
- **T2a** : ChartObject — **mergé** (PR #15) — **validé par Claude**.
- **T0-BROKER** #16 — **MERGÉE** (validé Claude).
- **T2b** #17 — **MERGÉE** (validé Claude).
- **T3** #18 — **MERGÉE** (validé Claude) — DSL `all`/`any` + `exit`.
- **T0-UI** #19 — **MERGÉE** (accepté Claude comme T0-UI, pas T4 roadmap).
- **T2c** #20 — **MERGÉE** — **validé par Claude** (T2a+T2b+T2c = **T2 terminé**).
- **T3c** #21 — **MERGÉE** — **validé par Claude** (registre conditions ; T3 phase close — T3d avec T5b, T3e plus tard).
- **T4a** #22 — **MERGÉE** — **validé par Claude** (overlay + correction net).
- **Job en cours** : **T0-METRICS** — stats par trade nettes de frais — branche `cursor/t0-metrics-net-a2fe`.


---

## 2026-09-23 — T0-METRICS EN COURS — stats par trade nettes de frais

- Branche : `cursor/t0-metrics-net-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/23 (**draft**)
- Commit(s) : `98eb8a7` (feat) ; `d90883f` (handoff PR)
- Statut : **ATTENTE CLAUDE** — CI **VERTE** ; **ne pas merger** avant revue.

### Livré

1. `round_trip_cost_log` / `one_way_cost_log` dans `app/backtest/engine.py` (près de `Trade`) — T4a réutilise `Trade.net_log_return` (plus de formule locale)
2. `Trade.cost_log` + propriété `net_log_return` ; `log_return` reste **brut**
3. Rempli : `ruleset_backtest` = `2×cost` (comme `_apply_hold_returns`) ; `engine.run_backtest` = frais **réellement** écrits dans `bar_returns` (open / close / flip)
4. `metrics.py` : WR / expectancy / PF sur **net** ; champs `*_gross` pour transparence
5. Perf DB / snapshots : `metrics_basis="net_v1"` sur **nouveaux** enregistrements (pas de réécriture historique) ; UI Compare / Experiments / Perf DB : colonne **Base** (`net` vs `brut (ancien)`), alerte si mélange
6. Tests : gagnant brut / perdant net → WR ; invariant Σ net == Σ bar_returns (ruleset + engine mid/EOD flat) ; écart EOD close≠open **documenté** (non corrigé)

### Engine — invariant (vérif avant correction)

| Cas | Σ net − Σ bars (naive 2×cost) | Avec `cost_log` exact |
|-----|-------------------------------|------------------------|
| Mid-close NEUTRAL→L→N | ~0 | OK (1e-9) |
| EOD force-close, open=close | −1×one_way (sortie non tarifée dans bars) | OK si `cost_log`=entry only |
| Flip L→S (1 fee pour close+open) | −2×one_way | OK si attribution flip → trade fermé |
| EOD `last.close ≠ last.open` | écart ≈ `log(close/open)` | **ÉCHEC volontaire** — mark trade vs open-to-open ; **non corrigé** dans cette PR |

### Tableau avant / après (seed 7, 600 bougies synthétiques, coûts 5+3 bps)

| ruleset | n | WR brut | WR net | Exp brut | Exp net | PF brut | PF net | Δexp (bps) |
|---------|---|--------|--------|----------|---------|---------|--------|------------|
| `IV_EXP_A_KUMO_BO_001` | 15 | 33.33% | 33.33% | -0.43% | -0.59% | 0.8022 | 0.7408 | 15.9 |
| `IV_ICHIMOKU_ONLY_LONG_001` | 8 | 12.50% | 12.50% | -1.89% | -2.05% | 0.3096 | 0.2876 | 15.7 |
| `IV_EXP_B_KUMO_RVOL_001` | 7 | 28.57% | 28.57% | -1.23% | -1.39% | 0.4779 | 0.4373 | 15.8 |

Aucun basculement WR sur ces fixtures (sorties ATR larges) ; expectancy surestimée d’~16 bps/trade (coût RT).

### Goldens

- `ruleset_backtest_golden.json` : **inchangé** (trades/indices/prix/raisons seulement — pas de métriques)
- Aucune fixture golden de métriques WR/PF/expectancy à régénérer

### Migration

- `a7b8c9d0e1f2_metrics_basis_net_v1` — colonne `metrics_basis` nullable sur `strategy_lab_experiments` + `backtest_snapshots`

### Attente

CI verte → handoff lien Actions → **ATTENTE Claude** (draft).

---

## 2026-09-23 — T4a VALIDÉ par Claude — MERGÉ (#22)

- Branche : `cursor/t4a-backtest-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 — **MERGÉE** `ad10720`
- Statut : **validé par Claude** (net = log_return − 2×cost ; invariant Claude 6,5e-16 ; Postgres 0 échec).

### Correction net (pré-merge)

`return_pct_net` / `return_pct_gross` / `r_multiple_gross` ; outcome sur net ; front NET principal.

---

## 2026-09-23 — T4a CORRECTION NET — ATTENTE Claude (revalidation)

- Branche : `cursor/t4a-backtest-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 (**draft**)
- Commit fix : `6627277` (feat initial `4d68375`)
- Statut : **supersédé** — validé + mergé (voir entrée ci-dessus).

### Correction demandée (brut étiqueté « net »)

`Trade.log_return` = brut (`sign × log(exit/entry)`). Les coûts ne sont déduits que dans `bar_returns` via `_apply_hold_returns` :
- même barre : `… − 2 * cost` (l.105)
- entrée : `r -= cost` (l.119–120) ; sortie : `− cost` (l.124–126) ; cas limite l.132
→ aller-retour = **`2 × cost`**, `cost = (commission_bps + slippage_bps) / 10_000`.

### Livré (fix)

1. `return_pct_net = exp(log_return − 2×cost) − 1` ; `return_pct_gross = exp(log_return) − 1`
2. `outcome` sur **net** ; `r_multiple_gross` (prix vs stop)
3. Origin + `trades` exposent les deux ; front : **NET** principal, brut secondaire
4. Test : +5 bps brut / 16 bps RT (5+3 commission/slippage) → `outcome=loss`

### CI Actions

- **VERTE** (HEAD `6627277`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35862821454
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Suite après merge

**T0-METRICS** — stats par trade nettes de frais (`cost_log` / `net_log_return` / `*_gross` / `metrics_basis`).

### Attente

**Cursor s’arrête ici** jusqu’à revalidation Claude → merge → puis T0-METRICS.

---

## 2026-09-23 — T4a EN COURS — backtest visuel (trades sur chart)

- Branche : `cursor/t4a-backtest-overlay-a2fe` (Claude : `v3/t4a-backtest-overlay`)
- PR : https://github.com/samiriggui-code/IchiVol/pull/22 (**draft**)
- Commit(s) : `4d68375`
- Statut : **supersédé** par correction net `6627277` (ci-dessus).

### Objectif

Lancer une stratégie catalogue sur un symbole → trades sur le chart ; filtre Tous / Gagnants / Perdants.

### Livré

1. `chart_objects/from_backtest.py` — 4 objets/trade (ENTRY/STOP/TARGET/MARKER), `source=backtest`, `origin` complet
2. `POST /api/engine/strategy-lab/backtest-overlay` — filtre outcome serveur ; counts globaux
3. Front Marché : bouton Backtest + sheet (catalogue, Afficher/Effacer, filtre, détail trade) ; objets BACKTEST en plus des overlays existants
4. Tests parité golden seeds ; OpenAPI/route_order ajouts seuls

### CI Actions

- **VERTE** (HEAD `4d68375`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35861496555
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Hors scope

WHY ENTERED/REJECTED/EXITED (T4c) ; filtre conversationnel Claude (T4b) ; filtres régime.

---

## 2026-09-23 — T3c VALIDÉ par Claude — MERGÉ (#21)

- Branche : `cursor/t3c-condition-registry-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/21 — **MERGÉE** `0609965`
- Statut : **validé par Claude** (fixtures avant refactor ; goldens rejoués sur ancien main ; Postgres 0 échec).

**T3 phase close** pour cette vague (T3d → T5b ; T3e MTF plus tard).

---

## 2026-09-23 — T3c EN COURS — registre conditions + CONDITION_SCHEMA dérivé

- Branche : `cursor/t3c-condition-registry-a2fe` (Claude : `v3/t3c-condition-registry` — préfixe cloud `cursor/…-a2fe`)
- PR : https://github.com/samiriggui-code/IchiVol/pull/21 (**draft**)
- Commit(s) : `0545826` (fixtures **avant** refactor) ; `51834cd` (registre) ; `1ad9588` (handoff PR)
- Statut : **ATTENTE CLAUDE** — CI **VERTE** ; **ne pas merger** avant revue.

### Objectif

Une condition DSL = une déclaration (`ConditionSpec`) ; `CONDITION_SCHEMA` et `_condition_holds` dérivés du registre.

### Livré

1. Fixtures pré-refactor : `condition_schema_golden.json`, `condition_eval_golden.json` + tests égalité stricte
2. `app/strategy_lab/conditions.py` — `ConditionSpec` + `CONDITION_REGISTRY` (copie exacte des expressions `_condition_holds`)
3. `CONDITION_SCHEMA` / `CONDITION_ENUMS` dérivés ; evaluator dispatch via registre ; cliquet AST `key == "…"`
4. Contrats : indicator_id ∈ REGISTRY ∪ {structure,derived} ; pas de doublons ; test « une déclaration »
5. `ruleset_backtest_golden` **inchangé** ; OpenAPI **inchangé**

### Note validation `allowed_values`

`CONDITION_ENUMS` **existait déjà** avant T3c (même valeurs). Déplacé sur `ConditionSpec.allowed_values` → dérivation. **Aucun builtin ne viole** les enums (re-parse catalog OK). Pas de correction catalog.

### CI Actions

- **VERTE** (HEAD `1ad9588`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35860079478
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Arbitrages T3 (Claude — à respecter)

- **T3b StrategyCompiler** : **non** — `ruleset_backtest` exécute déjà le DSL ; pas de couche compilation.
- **MTF DSL** → **T3e** (features multi-TF absentes ; ne bloque pas T4/T5).
- **`risk{}` cosmétique** : **abandonné** — `stop_atr` / `target_atr` restent top-level.

### Hors scope T3c

Nouvelles conditions ; MTF (T3e) ; éditeur conversationnel (T3d).

### Attente

**Cursor s’arrête ici** jusqu’à la revue Claude.

---

## 2026-09-23 — T2c VALIDÉ par Claude — MERGÉ (#20)

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 — **MERGÉE** `7e7cac7`
- Statut : **validé par Claude** (5 corrections OK ; Postgres 0 échec ; golden ajouts seuls).

### Livré (rappel)

`POST …/setup` atomique + grounding ; sens déduit ; R UI ; Twelve Data OK (cache 90s partagé OHLCV) ; `as_of` groundé.

**T2 terminé** (T2a + T2b + T2c).

---

## 2026-09-23 — T2c corrections revue Claude — setup atomique + as_of

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 (**draft**)
- Commit(s) : `368c5de` (fix), `bd533d1` (handoff)
- Statut : **ATTENTE CLAUDE** — corrections appliquées ; CI **VERTE** ; **ne pas merger** avant revalidation.

### Correctifs demandés → livrés

1. **Setup atomique** — taps en mémoire → récap Valider/Annuler ; Annuler = 0 écriture ; Valider = `POST /chart-objects/{symbol}/setup` (3 points, 1 transaction). POST unitaire conservé.
2. **Sens déduit** — `stop < entry` → long ; `stop > entry` → short ; géométrie serveur LONG `stop < entry < target` / SHORT inverse ; `origin.direction` sur les 3 ; Valider désactivé côté front si incohérent.
3. **Ratio R** — distances stop/cible (prix + %) + R = |Δtarget|/|Δstop| (0,01) dans `MarkTradeSheet`.
4. **Twelve Data** — exclusion `canMarkTrade` / fetch overlays retirée. Raison initiale : économie crédits (GET chart-objects refetch OHLCV). Claude : cache 90s + grounding OK → bouton visible ; erreur claire à la validation.
5. **as_of grounding** — `assert_object_grounded` vérifie `obj.as_of` sur la série (ou marge projetée). Test : `draw_zone` agent sans points + `as_of` futur → rejeté.

### Tests

- `/setup` LONG cohérent ; LONG target mauvais côté → 422 + 0 objet ; point non groundé → 422 + 0 objet ; SHORT ; as_of futur
- `pytest tests/chart_objects/` + goldens ; `npm run build` OK

### CI Actions

- **VERTE** (HEAD `bd533d1`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35858843441
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Attente

**Revalidation Claude** → merge si OK. **Cursor s’arrête ici.**

---

## 2026-09-23 — T2c EN COURS — USER trade points (ENTRY/STOP/TARGET)

- Branche : `cursor/t2c-user-trade-points-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/20 (**draft**)
- Commit(s) : `4606c03` (feat T2c), `e49696c` (handoff ATTENTE)
- Statut : *(supersédé — voir corrections revue Claude ci-dessus)*

### Contexte

Les 4 merges (#16→#19) sont **faits** sur `main` (`2b0bd96`).  
Job demandé par Claude : POST/DELETE chart-objects **source=user** + mode UI « Marquer un trade » (mobile-friendly).

### Périmètre T2c (cette PR)

1. **API** `POST /api/engine/chart-objects/{symbol}` — force `source=user` ; types **entry|stop|target** uniquement ; grounding OHLCV (même helper T2b) ; `setup_id` dans `origin` (+ `subtype=setup:…` pour ids stables)
2. **API** `DELETE /api/engine/chart-objects/item/{object_id}` — soft-delete **USER only** (ne touche pas CLAUDE)
3. **Node** : proxy `DELETE /api/engine/*` (auth)
4. **Front** : client write + mode « Marquer un trade » sur Marché (tap chart → ENTRY → STOP → TARGET)
5. Tests + goldens OpenAPI / `route_order` (additions)

### Livré (impl)

- `app/chart_objects/user_write.py` + routes POST/DELETE
- `tests/chart_objects/test_t2c_user_write.py` (5 tests)
- Front : `MarkTradeSheet`, `PriceChart` pickMode, bouton Marché
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
- Draw palette complète USER (zones/trendlines…)
- Colonne `setup_id` dédiée (pas de migration — JSON `origin`)
- Multi-user ownership sur overlays

### Attente Claude

Draft → handoff à jour → **revue** (suite Postgres complète sur `main` + ce diff) → marche à suivre.

**Cursor s’arrête ici** jusqu’à la revue Claude.

---

## 2026-09-23 — BILAN — 4 merges done (#16→#19) → T2c

### Merges exécutés (ordre Claude)

| # | PR | Sujet | Merged SHA / note |
|---|-----|--------|-------------------|
| 1 | [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidélité | `2670f96` → main |
| 2 | [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw + grounding | `b500944` |
| 3 | [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 `all`/`any` + `exit` + golden | `b0c9584` |
| 4 | [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | **T0-UI** Strategy Lab (pas T4 roadmap) | `2b0bd96` |

`main` HEAD post-merges : **`2b0bd96`**.

### Note naming

#19 = **T0-UI** (rename + onglets DB). Roadmap **T4** = backtest visuel WHY — **pas commencé**.

### Suite

Branche T2c ouverte ; détail dans l’entrée **T2c EN COURS** ci-dessus.  
**Claude** : relancer suite Postgres complète sur `main` `2b0bd96` (baseline 0 échec attendu post T0-CI).

---

## 2026-09-23 — T0-UI — Strategy Lab (rename + onglets DB) (rename + onglets DB)

- Branche : `cursor/t4-strategy-lab-ui-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/19 (**draft**)
- Commit(s) : `9737a1f`

### Note

**Pas T4** de la feuille de route (T4 = backtest visuel WHY ENTERED/REJECTED/EXITED). Ceci = T0-UI.

### Livré

- Route `/app/strategy-lab` ; `/app/backtests` → redirect
- Nav + Overview + Activité : label **Strategy Lab**
- Onglets **Compare | Regimes | Experiments | Live**
- Compare → `GET /strategy-lab/compare` (DB)
- Regimes / Experiments → `listStoredExperiments` (+ filtre `market_regime`)
- Live = ancien fan-out 7 recalculs (secondaire)
- Clients : `compareStoredRulesets`, `getStoredExperiment`, `market_regime` sur list

### Non fait

- Rename fichier → `StrategyLabPage.tsx`
- Détail experiment `{id}`
- Masquer complètement Live / WF-opt par défaut

### Validation locale

```text
./node_modules/.bin/tsc -b   # OK
```

### Revue Claude

Draft — **ne pas merger** avant revue. Orthogonal à #16/#17/#18.

---

---

## 2026-09-23 — EN COURS — merges Claude (#16→#19) puis T2c

### Progression

| PR | Statut |
|----|--------|
| #16 T0-BROKER | **MERGÉE** |
| #17 T2b | **MERGÉE** |
| #18 T3 | rebase/merge main fait — **CI puis merge** (cette branche) |
| #19 T0-UI | après #18 |

### Checks #18 ⊕ main (#16+#17)

- Conflit handoff résolu ; README auto-merge
- `alembic heads` : une seule (`f6a7b8c9d0e1`)
- Fixture golden backtest conservée

### Après #18+#19

Handoff « 4 merges done » → T2c (USER ENTRY/STOP/TARGET) → draft → attendre Claude.

---


---

## 2026-09-23 — T3 correction Claude — golden backtest builtins

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : 

### Correctif demandé

Preuve que le **résultat** backtest des builtins est inchangé vs `main` (pas seulement le parse).

### Livré

- Fixture `tests/strategy_lab/fixtures/ruleset_backtest_golden.json` générée sur **`main` af0006d** (pre-T3) — seeds 7/42, 300 bars, tous `list_builtin_rulesets()`
- `test_ruleset_backtest_golden.py` — égalité stricte trades (entry/exit index, prix, raison, stop/target)

### Validation locale

```text
pytest tests/strategy_lab/test_ruleset_backtest_golden.py -q   # PASS
```

### CI Actions

- **VERTE** (HEAD `8c301c6`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35855152500
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

**Revalidation demandée** avant merge. Pas de nouveau lot.

---

---

## 2026-09-23 — T3 slice 2 — `exit` (max_hold + conditions signal)

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : `a767cc1` (feat), `8996a09` / `9d1bcb6` (handoff)

### Livré

- `ExitSpec` optionnel dans `ruleset.py` (`max_hold_bars`, `conditions` = même `ConditionGroup`)
- ATR `stop_atr` / `target_atr` restent top-level ; refus de les mettre sous `exit`
- Backtest : priorité `stop` > `target` > `signal` (fill = close) > `max_hold` / `eod`
- `max_hold` : kwarg call-site gagne, sinon `ruleset.exit.max_hold_bars`
- `evaluator.bar_matches_group` partagé entry/exit
- Perf DB `exit_rule` : `atr_stop_target[+signal][+max_hold=N]`
- Tests backtest + parse + `apply_params` préserve `exit`

### Non fait

- Nesting `risk{}` cosmétique
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

Même draft PR #18 — **ne pas merger** avant revue.

---

---

## 2026-09-23 — T3 slice 1 — DSL v3 `all` / `any` (rétrocompat flat)

- Branche : `cursor/t3-dsl-v3-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/18 (**draft**)
- Commit(s) : `ff0fc50`

### Livré

- `ConditionGroup` (`all_of` / `any_of`) dans `app/strategy_lab/ruleset.py`
- Parse : flat `{key: val}` ≡ `all` ; forme nested `{"all":…,"any":…}` ; refuse le mix flat + clés composition
- `to_dict()` : flat legacy si `all` seul (catalog / Perf DB inchangés)
- `evaluator.bar_matches` : `(∀ all) ∧ (∃ any)` ; groupes vides = vacuous true
- `optimization.apply_params` préserve `any_of` quand le base est composé
- Tests : `test_ruleset.py` (+ `test_apply_params_preserves_any_of`)
- README engine : ligne schema Rules Engine mise à jour

### Non fait (tranches suivantes T3)

- Exit rules / risk block / MTF dans le DSL
- Nesting récursif `all`/`any` sous un groupe
- Migration catalog built-ins vers `any` (volontairement flat)

### Validation locale (Cursor, sans Postgres)

```text
pytest tests/strategy_lab/ -q
# 62 passed
```

### Revue Claude

Draft — **ne pas merger** avant revue. Suite Postgres complète quand Claude revient.

---

---

## 2026-09-23 — EN COURS — exécution marche à suivre Claude

Claude a validé #16/#17/#18 et accepté #19 (renommée **T0-UI**, pas T4 roadmap).  
Cursor exécute l’ordre de merge puis démarre **T2c**.

### Ordre merges (un par un, rebase + CI verte)

| # | PR | Statut Cursor |
|---|-----|----------------|
| 1 | [#16](https://github.com/samiriggui-code/IchiVol/pull/16) T0-BROKER | **MERGÉE** `2670f96` (2026-09-23T11:39Z) |
| 2 | [#17](https://github.com/samiriggui-code/IchiVol/pull/17) T2b | merge main fait ; CI **VERTE** head `e9c7ad2` — **merge imminent** |
| 3 | [#18](https://github.com/samiriggui-code/IchiVol/pull/18) T3 | en attente (après #17) |
| 4 | [#19](https://github.com/samiriggui-code/IchiVol/pull/19) T0-UI | titre/handoff renommés T0-UI ; merge après #18 |

### Checks faits sur #17 ⊕ main(#16)

- `openapi_golden` / `route_order_golden` : auto-merge ; `route_order` contient toutes les routes main (56) — rien perdu
- `alembic heads` : **une seule** tête `f6a7b8c9d0e1`
- Handoff conflict résolu (sections T2b + broker conservées)

### Après les 4 merges

1. Handoff « 4 merges done » sur main
2. Branche T2c `cursor/t2c-user-trade-points-a2fe` (Claude avait dit `v3/t2c-user-trade-points` — préfixe cloud `cursor/…-a2fe` ; noté ici si Claude préfère `v3/`)
3. Job T2c : POST/DELETE chart-objects USER + mode « Marquer un trade » mobile

### Règle rappelée

Une sous-tranche à la fois ; draft → handoff → **attendre revue Claude** avant la suivante.

---

2026-09-23 — ATTENTE CLAUDE — bilan Cursor pendant ton absence

**Cursor s’arrête ici.** Pas de nouveau code tant que Claude n’a pas revu et donné la marche à suivre.

Contexte : Claude indisponible (restriction puis revue reportée). Cursor a continué seul sur des drafts. **Aucun merge** de ces PRs sans validation Claude.

### File d’attente (drafts — à revoir)

| PR | Sujet | Branche | Head | CI Actions |
|----|--------|---------|------|------------|
| [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidélité (reconcile, marks, financing) | `v3/t0-broker-fidelity` | `f904951` | VERTE [35849205949](https://github.com/samiriggui-code/IchiVol/actions/runs/35849205949) |
| [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw_* + store USER/CLAUDE (+ passe 2 durcissement) | `cursor/t2b-agent-draw-a2fe` | `3ece878` | VERTE (voir entrée T2b) |
| [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 slice 1+2 (`all`/`any` + `exit`) | `cursor/t3-dsl-v3-a2fe` | `8973a42` | VERTE [35852790018](https://github.com/samiriggui-code/IchiVol/actions/runs/35852790018) |
| [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | T4 UI Strategy Lab (rename + onglets DB) | `cursor/t4-strategy-lab-ui-a2fe` | `8eec800` | (voir check Actions sur la PR) |

### Déjà sur `main` (validé avant / pendant)

- T0-CI #14, T2a #15 — mergés, validés Claude.

### Ce que Cursor a tranché seul (à confirmer ou corriger)

1. **T3** : slices `all`/`any` + `exit` livrés ; **pas** de `risk{}` cosmétique ni MTF (FeatureBar mono-TF — trop gros). Suite T3 DSL = revue #18 puis décision Claude.
2. **T4** démarré (UI) pendant que #16/#17/#18 attendent — orthogonal moteur. DB-first Compare/Regimes/Experiments ; Live = ancien recalcul.
3. **T2b** : passe 2 après critique « trop rapide vs T1 » (force source=claude, points schema, front render, refresh chart).

### Demandé à Claude

1. Suite **Postgres complète** sur #16 et #17 (et #18/#19 si pertinent) — Cursor n’a pas de Postgres local.
2. Revue des 4 drafts : merge / rebase / redo / kill.
3. **Marche à suivre** pour Cursor (ordre des lots, quoi ne pas toucher).

### Règle

Cursor **attend** cette marche à suivre. Ne pas enchaîner un nouveau lot sans consignes Claude.

---

## 2026-09-23 — T2b correction Claude — grounding anti-hallucination

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (**draft**)
- Commit(s) : 

### Correctif demandé

Avant persist agent `draw_*` : vérifier times/prices contre OHLCV réel (`resolve_and_fetch`).

### Livré

- `app/chart_objects/grounding.py` — `assert_object_grounded`
  - time ∈ timestamps série, ou `[last, last+5 bars]` si `origin.projected`
  - price ∈ `[min(low)*0.5, max(high)*1.5]` sur 300 dernières bougies
  - `price_low` / `price_high` (ZONE) idem
- `_draw_and_persist` appelle grounding → `CommandError("point_not_grounded: …")`
- Tests : `test_grounding.py` (prix 100×, futur hors proj, zone OK, structure OK)

### Validation locale

```text
pytest tests/chart_objects/ -q   # PASS
```

### CI Actions

- **VERTE** (HEAD `9601274`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35855150230
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

**Revalidation demandée** avant merge.

---

---

## 2026-09-23 — ATTENTE CLAUDE — bilan Cursor pendant ton absence

**Cursor s’arrête ici.** Pas de nouveau code tant que Claude n’a pas revu et donné la marche à suivre.

Contexte : Claude indisponible (restriction puis revue reportée). Cursor a continué seul sur des drafts. **Aucun merge** de ces PRs sans validation Claude.

### File d’attente (drafts — à revoir)

| PR | Sujet | Branche | Head | CI Actions |
|----|--------|---------|------|------------|
| [#16](https://github.com/samiriggui-code/IchiVol/pull/16) | T0-BROKER fidélité (reconcile, marks, financing) | `v3/t0-broker-fidelity` | `f904951` | VERTE [35849205949](https://github.com/samiriggui-code/IchiVol/actions/runs/35849205949) |
| [#17](https://github.com/samiriggui-code/IchiVol/pull/17) | T2b agent draw_* + store USER/CLAUDE (+ passe 2 durcissement) | `cursor/t2b-agent-draw-a2fe` | `3ece878` | VERTE (voir entrée T2b) |
| [#18](https://github.com/samiriggui-code/IchiVol/pull/18) | T3 DSL v3 slice 1+2 (`all`/`any` + `exit`) | `cursor/t3-dsl-v3-a2fe` | `8973a42` | VERTE [35852790018](https://github.com/samiriggui-code/IchiVol/actions/runs/35852790018) |
| [#19](https://github.com/samiriggui-code/IchiVol/pull/19) | T4 UI Strategy Lab (rename + onglets DB) | `cursor/t4-strategy-lab-ui-a2fe` | `8eec800` | (voir check Actions sur la PR) |

### Déjà sur `main` (validé avant / pendant)

- T0-CI #14, T2a #15 — mergés, validés Claude.

### Ce que Cursor a tranché seul (à confirmer ou corriger)

1. **T3** : slices `all`/`any` + `exit` livrés ; **pas** de `risk{}` cosmétique ni MTF (FeatureBar mono-TF — trop gros). Suite T3 DSL = revue #18 puis décision Claude.
2. **T4** démarré (UI) pendant que #16/#17/#18 attendent — orthogonal moteur. DB-first Compare/Regimes/Experiments ; Live = ancien recalcul.
3. **T2b** : passe 2 après critique « trop rapide vs T1 » (force source=claude, points schema, front render, refresh chart).

### Demandé à Claude

1. Suite **Postgres complète** sur #16 et #17 (et #18/#19 si pertinent) — Cursor n’a pas de Postgres local.
2. Revue des 4 drafts : merge / rebase / redo / kill.
3. **Marche à suivre** pour Cursor (ordre des lots, quoi ne pas toucher).

### Règle

Cursor **attend** cette marche à suivre. Ne pas enchaîner un nouveau lot sans consignes Claude.

---

---

## 2026-09-23 — T2b passe 2 — durcissement (suite critique pass 1 trop léger)

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (draft)
- **Contexte** : le 1er push T2b (~10 min) livrait un squelette backend après T2a déjà mergé. Trop rapide vs découpage Claude sur T1 — **trous réels** (source=user impersonable, schema `points` = string[], front ne chargeait que `engine`, rendu sans horizontal/entry/stop, README stale).

### Correctifs passe 2

1. Agent `draw_*` **force `source=claude`** ; refuse `user` / `engine`
2. `delete_chart_object` **claude-only** (ne touche pas USER)
3. `get_chart_objects` défaut = HTTP (`engine`) — passer `user,claude` explicitement
4. Copilot : `points` → `array<{time,price}>` (plus `string[]`)
5. Front : `getChartObjects` défaut `engine,user,claude` ; PriceChart rend horizontal/entry/stop/target + ray/text
6. Tests : isolation USER, merge HTTP, parity `get_structure`↔HTTP, trend_line points, schema TS
7. `engine/README.md` section agent mise à jour (WRITE chart scopes)

### CI / suite DB

- CI Actions passe 1 : **VERTE** (`72ef89d`, run `35849205234`)
- CI Actions passe 2 : **VERTE** (`c5767a7`, run `35850222353`) — `pytest` + `frontend` success
- **Suite Postgres complète** : **Claude à ~13:10** (Cursor note ici, ne bloque pas sur ça)
- Passe 2 suite : refresh Market chart après `draw_*` / `delete_chart_object` (event bus) — CI **VERTE** `2a6d8ed` https://github.com/samiriggui-code/IchiVol/actions/runs/35850595467
- **Head PR #17** : `2a6d8ed` — prêt revue Claude (suite DB complète ~13:10)

### Toujours hors scope / dette assumée

- Multi-tenant `user_id` sur overlays (global symbol/tf) — dette connue, pas T2b
- Rectangle/channel rendu générique riche — partiel
- STRATEGY/BACKTEST store — T4
- Suite DB paper/brokerage complète — **Claude 13:10**
- Refresh Market après draw : **fait** (`chartObjectsEvents` bus) sur ce push

---

---

## 2026-09-23 — T2b — Agent draw_* + get_structure + store USER/CLAUDE (passe 1)

- Branche : `cursor/t2b-agent-draw-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/17 (draft) — **pas de merge avant revue Claude**
- Base : `main` (post-#14+#15)
- **Note auto-critique** : squelette trop mince — voir **passe 2** ci-dessus. T2a (#15) couvrait déjà modèle + GET + rendu Structure ; T2b = store + agent + fil Copilot, pas « tout T2 en 10 min ».

### Livré (passe 1)

1. **Persistance** `chart_object_overlays` (alembic `f6a7b8c9d0e1`) + store
2. **Collect** merge ENGINE + store sur `GET /chart-objects`
3. Agent : `get_structure`, `get_chart_objects`, `draw_*`, `delete_chart_object` + capabilities write chart
4. Copilot allowlist chart write
5. `structure/payload.py` partagé

### Tests locaux (passe 1)

- chart_objects + agent + OpenAPI + build : PASS ; CI verte ensuite

### Hors scope

- STRATEGY / BACKTEST (T4) ; VSB (T5) ; merge #16 ; T3+

---

---

## 2026-09-23 — T0-BROKER — Fidélité paper broker + corrections revue Claude

- Branche : `v3/t0-broker-fidelity` (rebasée sur `main` après #14+#15)
- PR : https://github.com/samiriggui-code/IchiVol/pull/16 (draft) — **pas de merge avant revue Claude**
- **Annule et remplace** le brief T0-UI : journal d’ordres + P&L réalisé déjà sur Synthèse — **non refaits**.
- Workflow CI : **retiré** le commit `d80382f` (arrivé via #14 sur `main`).

### Validé (inchangé)

- reconcile + badge Comptabilité ; liquidation_value ; marks âge/péremption
- financing idempotent ; pas de rétroactif avant 2026-09-23 ; réalisé de clôture déduit le financement sans double débit cash
- tests FID_* jetables ; golden API ajouts seuls

### Corrections revue Claude (cette itération)

**A) SHORT PnL** — formule corrigée `(entry − exit) / entry` et `qty × (entry − exit)` :
| Fichier | Occurrences |
|---------|-------------|
| `app/paper/broker.py` | `close_capital_position` realized/cash/`pnl_pct` ; `update_excursions` MFE/MAE ; helpers `short_pnl_pct` / `short_realized_currency` |
| `app/paper/liquidation.py` | preview SHORT cash_delta / realized |
| `app/paper/engine.py` | `_close_legacy` pnl_pct |
| `app/paper/reconcile.py` | reconstruction cash SHORT + check **lecture seule** `short_pnl_legacy_formula` (CLOSED avant 2026-09-23, écart stocké − correct ; **aucune réécriture**) |

Shadow / research_lab / evidence étaient déjà corrects — non touchés.

**B) Financing** — `fee_profiles.FINANCING_*` : `(benchmark≈4.3% + markup±2.5%)/365×10000` bps/j (~1.86 long, ~0.49 short) ASSUMPTION 2026-09-23 ; CostsPanel affiche les taux.

**C) Marks** — overview `block_on_provider=False` + budget 2 s ; `_try_acquire_credit_slot` Twelve Data ; test limiteur saturé < 3 s.

**D) Isolation routes** — `test_open_paper_position_accepts_a_non_crypto_symbol` + garde baseline −5 % → monkeypatch `ensure_baseline_portfolio` vers portefeuille jetable.


### CI Actions

- **VERTE** sur `5965b55` : https://github.com/samiriggui-code/IchiVol/actions/runs/35847816190
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Tests locaux (Postgres)

- `tests/paper` + golden API + brokerage ledger : **verts**
- `npm run build` : **OK**

### Non fait

- Merge #16 (CI verte, attend Claude) ; T2b démarré en parallèle (PR #17)

---

## 2026-09-23 — T0-CI — isolation baseline (revue Claude PR #14)

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergée**) — **validé par Claude**
- Commit(s) : `8306028` (isolation baseline + disposable opens + garde snapshots)

### Correctif

Les helpers `_heal_baseline_if_halted` / `_restore_baseline` ne remettent **plus** le cash à `initial_cash` ni ne vident toutes les `PaperEquitySnapshot` de la baseline.

- Capture en début de test : cash, `realized_pnl`, ids de snapshots existants
- En fin : ne supprime QUE les snapshots créés pendant le test ; restaure cash / realized capturés
- Opens qui ont besoin d’un livre propre → portefeuille **jetable** (profil baseline copié) ; `open_user_confirmed(..., portfolio=)` optionnel
- Garde module : snapshot « historique » 2020-01-01 inséré avant la suite `test_engine` → doit survivre à tous les tests

### Validation locale

- `tests/paper/test_engine.py` + suite complète `tests` : PASS

### CI Actions

- **VERTE** : https://github.com/samiriggui-code/IchiVol/actions/runs/35843919501 (`3d0aa79`)
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Revue Claude

Historique baseline injecté puis `tests/paper` + `tests/api` : historique survit, cash inchangé, **0 échec** sur base vierge → **merge**.

---

## 2026-09-23 — T0-CI greening — rewrite 13 paper/API tests + honest 422 + frontend job

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergée**) — **validé par Claude**
- Commit(s) : `28929be` (13 tests + honest 422 + frontend job), `b1e5773` (baseline heal), `8aa8f9e` (handoff SHAs)
- **CI Actions VERTE** : https://github.com/samiriggui-code/IchiVol/actions/runs/35841290882
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Livré

1. **13 tests réécrits** pour le profil baseline 2026-09-21 (`require_atr_stop`, `allow_short=False`, `exit_mode=direction`) :
   - `tests/paper/test_engine.py` — `stop_distance`, portefeuilles jetables (`exit_mode=decision` / `allow_short`), `direction_flipped`, ATR stub sur rows auto, heal `daily_loss_halt`
   - `tests/api/test_routes.py` — ATR stub + BUY/LONG multi-classe ; cleanup ledger/cash
2. **422 honnête** dans `app/api/paper_orders.py` : `no_atr_stop` / `short_not_allowed` / gates au lieu du faux message WATCH ; test `test_open_paper_position_reports_no_atr_stop_honestly`
3. **CI** `.github/workflows/engine-ci.yml` : job `frontend-build` (`npm ci` + `npm run build` sous `ichivol-app`)

### Validation

- Locale Cursor (Postgres 16) : 16/16 ciblés PASS ; suite complète `tests` PASS
- GitHub Actions run `35841290882` sur `8aa8f9e` : **2/2 jobs verts**

### Hors scope

- Merge après revue Claude (rejoue avec sa base)
- Skip Binance inchangé

---

## 2026-09-23 — T0-CI — Postgres Actions + diagnostic des 13 paper failures

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (**mergée**) — **validé par Claude**
- Commit(s) : `c7f13b9` (workflow + diagnostic handoff)

### Livré

1. **Diagnostic des 13** (reproduits ici sur Postgres 16 frais + alembic head ; **exactement** les mêmes 13 noms que la baseline Claude).
2. **CI GitHub Actions** `.github/workflows/engine-ci.yml` :
   - service `postgres:16-alpine`, DB `ichivol_engine_dev`, user/password `postgres`/`root`
   - `DATABASE_URL=postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev` (défaut `app/config.py` / `.env.example`)
   - `alembic upgrade head` puis `pytest tests -v`
   - `ENABLE_BACKTEST_EVIDENCE/SIGNAL_TRACKING/PROTECTION_MONITOR=false` pour éviter le bruit background
   - **CI honnête** : pas de liste xfail / ignore — la suite tourne entière ; le job restera **rouge** tant que les 13 ne sont pas réécrits. Aucune convention xfail préexistante dans le repo.

### Cause racine (pas un bug V3)

Les échecs viennent du **profil baseline figé le 2026-09-21** (`BASELINE_PROFILE` dans `app/paper/strategy_profiles.py`), pas d’une régression code path récente :

| Clé profil | Effet sur les vieux tests |
|------------|---------------------------|
| `one_position_per_symbol` / `one_entry_per_signal_run` / `daily_loss_limit_pct` / `max_open_risk_pct` | `paper_gates.has_gates` = True → `entry_gate` refuse sans ATR (`no_atr_stop`) |
| `require_atr_stop: True` | pas de repli « legacy open » une fois le gate actif |
| `allow_short: False` | tout `SELL`/`SHORT` → `None` |
| `exit_mode: "direction"` | `WATCH` ne ferme plus ; flip → `direction_flipped` (pas `pipeline_flipped` / `pipeline_downgraded`) |

Les tests modernes (`tests/paper/test_fwd_profiles.py`, `test_open_flow.py`, `test_manual_buy.py`, …) passent déjà avec stop ATR + portefeuilles jetables. `tests/paper/test_engine.py` et 2 fixtures API n’ont **pas** été alignés.

Sur un open raté, la route `POST /paper/positions` mappe tout `position is None` vers `422 not_actionable: … WATCH/NO_TRADE` — message **trompeur** quand la vraie raison est `no_atr_stop` / `short_not_allowed` (détail UX mineur, pas la cause des 13).

### Tableau diagnostic (13)

| Test | Classe | Cause probable | Action recommandée |
|------|--------|----------------|--------------------|
| `test_sync_position_opens_a_long_on_buy_with_no_existing_position` | obsolete test | Appel sans `stop_distance` → gate `no_atr_stop` → `None` | **fix test** : passer `stop_distance>0` (comme `test_fwd_profiles`) |
| `test_sync_position_holds_an_open_position_while_still_supported` | obsolete test | Même open bloqué → pas de position à tenir | **fix test** (+ stop) |
| `test_sync_position_closes_when_decision_downgrades_to_watch` | obsolete test | Open bloqué **et** `exit_mode=direction` (WATCH+même direction ne ferme plus) | **fix test** : scénario `direction` (cf. `test_t1_*`) ou portefeuille jetable `exit_mode` legacy |
| `test_sync_position_closes_when_pipeline_direction_flips` | obsolete test | Open bloqué ; même avec open, raison attendue serait `direction_flipped` | **fix test** |
| `test_short_position_pnl_is_positive_when_price_falls` | obsolete test | `allow_short=False` sur baseline | **fix test** : portefeuille jetable `allow_short=True` **ou** drop (shorts volontairement off) |
| `test_sync_auto_watchlist_processes_multiple_rows_and_commits` | obsolete test | Fake rows sans ATR → aucun open | **fix test** : ATR / `stop` sur les rows |
| `test_open_user_confirmed_is_idempotent` | obsolete test | Sans stop → pas de 1er open (`created1=False`) | **fix test** : `stop_distance` |
| `test_close_manually_closes_an_open_position` | obsolete test | Open impossible sans stop | **fix test** |
| `test_close_manually_returns_none_for_an_already_closed_position` | obsolete test | idem | **fix test** |
| `test_list_positions_filters_by_source_user_and_status` | obsolete test | user open sans stop + auto SHORT interdit | **fix test** : stop + LONG (ou pf `allow_short`) |
| `test_open_user_confirmed_locks_symbol_already_open_on_portfolio` | obsolete test | 1er open sans stop échoue | **fix test** |
| `test_open_paper_position_opens_on_an_actionable_decision` | env/fixture | `ScreenerRow` fake sans `atr` → `stop=None` → même gate ; 422 (detail WATCH trompeur) | **fix test** : stub `atr.suggested_stop_distance` ; mock aussi `scan_symbol` sur le close |
| `test_open_paper_position_accepts_a_non_crypto_symbol` | obsolete test + fixture | `SELL`/`SHORT` + `allow_short=False` (+ pas d’ATR) → 422 | **fix test** : `BUY`/`LONG` + ATR stub (multi-classe ≠ short) |

**Skip Binance** (hors des 13) : `tests/market_data/test_binance.py` — `skipif` si `data-api.binance.vision` injoignable (HTTP 451 / réseau). Normal en CI sans accès Binance.

**Vrai bug ?** Non pour le comportement d’open/close baseline (décision produit 2026-09-21, couverte ailleurs). Seul point code optionnel : message 422 trop générique quand `open_user_confirmed` renvoie `None` pour une autre raison que WATCH — **fix code** cosmétique, hors périmètre T0-CI si on veut rester minimal.

### Mapping CI ↔ baseline

| Situation | Attendu |
|-----------|---------|
| PR actuelle T0-CI / `main` tant que les 13 existent | job `pytest (Postgres 16)` **fail** avec les **mêmes 13** (+ skip Binance) |
| PR qui ajoute un 14e échec | **régression** → bloquer merge (règle Claude inchangée) |
| Follow-up qui réécrit `test_engine.py` + 2 fixtures API | CI **vert** |

Pas de `xfail` documenté : préfère un signal rouge honnête.

### Non fait / hors périmètre

- Réécriture des 13 tests (follow-up T0-CI-green)
- Découpage `routes.py` (T1g), structure, registry

### Tests (cette branche)

- Repro locale Cursor : Postgres 16 + alembic → `tests/paper/test_engine.py` + `tests/api/test_routes.py` → **13 failed, 28 passed** (les 2 paper qui passent encore : WATCH no-op + open non-actionable)
- Suite complète non exigée ici pour greening ; le workflow Actions est le filet permanent

---

## 2026-09-23 — T2a — ChartObject (typed overlays from engine)

- Branche : `v3/t2a-chart-objects`
- PR : https://github.com/samiriggui-code/IchiVol/pull/15 (**mergée**) — **validé par Claude**
- Commit(s) : `3672f5d` (feat) ; `a41ef76` / `ad3f9a3` / `6b96c94` / `b9a9dd0` (handoff) ; `428c1f9` (fix detector window bars)
- Base : `main` après merge PR #14 (T0-CI)

- **Fix (pytrendline bar indices)** : `start_bar`/`end_bar` sont relatifs à la fenêtre du détecteur (`meta["bars"]`, pytrendline cap 150), pas à `window_bars` (300). `_line_dict` dans `get_structure` et `_line_endpoints` dans `from_structure` utilisent désormais `window[-bars:]` / `candles[-bars:]` par détecteur. Sans pytrendline, `bars == window_bars` → réponse `/structure` inchangée. **Revue Claude** : décalage corrigé dans ChartObjects et `/structure`, vérifié sur la reproduction ; aucun golden existant modifié.

- Livré :
  - Modèle `app/chart_objects/types.py` — `ChartObject` frozen, id déterministe (sha256[:24] de type/source/symbol/tf/coords arrondis/subtype), validation par type, `to_dict`/`from_dict`
  - Producteur `from_structure.py` — sélection **identique** à `structure.ts` `toStructureOverlay` (MAX_ZONES=3, MAX_TRENDLINES=2, score desc, lignes drawable seulement) ; zones consensus → ZONE ; trendlines détecteurs → TREND_LINE ; breakouts → MARKER
  - Confiance : `clamp(score / max_score_pool, 0, 1)` (docstring)
  - API `GET /api/engine/chart-objects/{symbol}?timeframe=&limit=&sources=engine` — router dédié `api/chart_objects.py`, branché en fin d’agrégateur `routes.py` ; sources non-ENGINE → liste vide (pas d’erreur)
  - Front : `src/lib/chartObjects.ts` + `PriceChart.renderChartObjects` (ZONE = 2 price lines pointillées « S/R ×n », TREND_LINE = LineSeries dashed, MARKER = circle) ; `MarketPage` appelle `getChartObjects` ; `toStructureOverlay` / `getEngineStructure` retirés
  - Goldens OpenAPI + `route_order` : **ajouts seuls** (`/chart-objects/{symbol}`)

- Tests :
  - `tests/chart_objects/` — round-trip, validation, id stable, sélection parity seeds 7 & 42, causalité `as_of`
  - `tests/chart_objects/test_detector_window_alignment.py` — indices relatifs à `meta["bars"]` ; pytrendline seed 7 ≠ offset 150 ; `/structure` sans pytrendline identique
  - `tests/api/test_chart_objects_route.py` — ENGINE OK ; user/claude → `objects=[]`
  - `test_api_surface_golden` → vert
  - `npm run build` → OK

- Hors scope (T2b/T5) : outils dessin Claude, persistence USER/CLAUDE, ENTRY/STOP/TARGET

---

## 2026-09-23 — T1g — Découpage de `api/routes.py` (zéro changement de comportement)

- Branche : `v3/t1g-split-routes`
- PR : https://github.com/samiriggui-code/IchiVol/pull/13 (**mergée** dans `main` @ `a19f924`) — **validé par Claude**
- Commit(s) : `d58adca` (golden OpenAPI + ordre des routes **avant** refactor) ; `67ae482` (découpage)

- Livré :
  - Modules domaine : `market.py`, `context.py`, `decisions.py`, `backtest.py`, `rulesets.py`, `strategy_lab.py` + `strategy_lab_wf.py`, `paper.py` + `paper_orders.py`, `agent.py`, `common.py`
  - `routes.py` = agrégateur qui `include_router` **dans l’ordre d’origine** (main.py inchangé)
  - Fragments de routers là où le domaine n’est pas contigu (market head/screener/correlations ; paper before/after shadow ; backtest evidence/symbol/shadow)
  - Tags inchangés (`["engine"]`) ; helpers partagés dans `common.py`
  - Golden : `tests/api/fixtures/openapi_golden.json`, `route_order_golden.json` + `test_api_surface_golden.py`

- Monkeypatch mis à jour (cible déplacée, comportement inchangé) :
  - `tests/api/test_routes.py` — `scan_symbol` aussi sur `decisions` / `paper` / `paper_orders` ; `compute_correlation_matrix` aussi sur `market`
  - `tests/api/test_open_flow.py` — `scan_symbol` aussi sur `paper` / `paper_orders`
  - `test_structure_line_dict.py` — toujours via réexport `routes._line_dict`

- Fixtures : seuls les 2 nouveaux golden API ajoutés ; `git diff main -- '**/fixtures/*'` hors ceux-là → vide

- Lignes `app/api/` (tous ≤ ~400) : routes 46, agent 92, context 90, common 185, decisions 155, rulesets 145, backtest 171, strategy_lab 208, strategy_lab_wf 240, paper 269, paper_orders 232, market 268

- Tests :
  - `test_api_surface_golden` → vert (OpenAPI + ordre)
  - `tests/api/` → seuls les **2** `open_paper_position` connus (baseline 13, DB dispo ici) ; pas de nouvelle régression
  - Claude avec Postgres : baseline **13** échecs

- Non fait à l’époque : T0-CI (branche parallèle) ; T2 ChartObject — **T1 terminé** (T1→T1g). T2a = cette branche.

---

## 2026-09-23 — T1f-2 — Plus de repaint dans pytrendline

- Branche : `v3/t1f2-pytrendline-no-repaint`
- PR : https://github.com/samiriggui-code/IchiVol/pull/12 (mergée) — **validé par Claude**
- Commit(s) : `81a5db1` (comportement + tests + golden legacy) ; `9831db9` (handoff PR #12)

- **Note backtests** : les backtests du profil `STRUCTURE_PYTRENDLINE` faits **avant** la PR #12 ne sont **plus comparables** (le gate a changé avec l’exclusion des pivots provisoires).

- Livré :
  - `StructureEngineParams.allow_provisional_anchors: bool = False` — `True` = ancien comportement (tests / A-B uniquement, jamais en profil live)
  - `pytrendline._detect_side` : fit uniquement sur pivots `provisional=False` (sauf flag) ; pas de repli sur les ancres si trop peu de fractals confirmés
  - Ancres première/dernière toujours présentes dans `MarketStructure.pivots` (marking T1f)
  - `TrendlineSegment.fit_pivot_bars` — paire d’ancres du fit (non exposée API)
  - Tests : (c) inversé (lignes = pivots confirmés) ; stabilité des lignes (identique ou disparue, jamais mutée) ; golden `allow_provisional_anchors=True`

- Fixtures :
  - **Aucune fixture existante ne dépendait de pytrendline** (consensus défaut / baseline inchangés).
  - **Ajout** : `tests/structure/fixtures/pytrendline_provisional_anchors_golden.json` — capture de l’ancien comportement (`allow_provisional_anchors=True`) pour seeds 7 & 42 :
    | seed | lignes | zones |
    |------|--------|-------|
    | 7 | 10 | 10 |
    | 42 | 10 | 10 |
  - `git diff main -- '**/fixtures/*'` hors ce fichier → vide

- Mesure d’impact (synthétique 300 barres ; BTCUSDT 1h : **pas de cache**, Binance HTTP 451) :

  | seed | lignes avant → après | zones avant → après | composition lignes |
  |------|----------------------|---------------------|--------------------|
  | 7 | 10 → 10 (plafond `max_lines_per_side`) | 10 → 10 | 7 partagées, 3 seules-avant, 3 seules-après ; mids zones ≠ |
  | 42 | 10 → 10 | 10 → 10 | 6 partagées, 4 / 4 ; mids zones ≠ |

  Gate `STRUCTURE_PYTRENDLINE` sur 12 fenêtres `t∈{80..300}` (BUY+SELL) :

  | seed | BUY acceptés avant → après | BUY bloqués | SELL acceptés | SELL bloqués |
  |------|----------------------------|-------------|---------------|--------------|
  | 7 | 5 → **4** | 7 → **8** | 5 → **7** | 7 → **5** |
  | 42 | 6 → **9** | 6 → **3** | 1 → **4** | 11 → **8** |

  → Le gate change bien (zones dérivées des lignes). Consensus défaut (mvpp+trendln) et `ICHIVOL_BASELINE_V1` non touchés.

- Choix faits :
  - Flag sur `StructureEngineParams` (pas un arg ad-hoc du seul adaptateur) pour que le gate / service héritent du défaut sûr.
  - `fit_pivot_bars` pour tester la non-mutation sans ambiguïté des `pivot_bars` (touches).

- Doutes / points à vérifier par Claude : **validé par Claude**.

- Non fait / hors périmètre :
  - mvpp / trendln / consensus défaut
  - découpage `routes.py` (T1g)
  - T0-CI (branche séparée)
  - Mergé dans `main` après validation Claude.

- Tests :
  - `tests/structure/` → all green (causality + engines + gate + golden atr)
  - suite complète **sans Postgres** (Cursor) → **4 failed** connexion DB connus ; fixtures hors nouveau golden inchangées
  - revue Claude avec base : baseline **13** échecs paper/api ; tout écart = régression

---

## 2026-09-23 — T1f — Pivots confirmés + repaint mesuré (mark-only)

- Branche : `v3/t1f-pivot-confirmation`
- PR : https://github.com/samiriggui-code/IchiVol/pull/11 (mergée) — **validé par Claude**
- Commit(s) : `37ac28f` (métadonnées + adaptateurs + tests de causalité) ; `74a0c8f` / `c1ff782` / `ef85f57` (rapport handoff)

- Livré :
  - `PivotPoint.confirmed_bar` / `PivotPoint.provisional` (optionnels, défauts `None` / `False`)
  - Remplissage adaptateurs : mvpp `j+right` ; trendln `i` ; pytrendline fractals `i`, ancres première/dernière `provisional=True` + `confirmed_bar=last` ; consensus propage les pivots sources
  - `tests/structure/test_structure_causality.py` — (a) `confirmed_bar <= t-1` ; (b) stabilité non-provisoire (fenêtre commune + exclusion left-lookback pour pytrendline `max_bars=150`) ; (c) preuve de repaint pytrendline (ancre provisoire absente à `t+1`)
  - API `/structure` : toujours `pivot_count` seulement — **pas** d'exposition des nouveaux champs
  - `git diff main -- '**/fixtures/*'` → vide

- Mesure d'impact (2 seeds synthétiques 300 barres ; BTCUSDT 1h cache/live indisponible ici — Binance 451) :

  | Jeu | Trendlines pytrendline avec ≥1 pivot provisoire | Consensus trendlines (objet) | Zones consensus (avec pyt) liées à une ligne provisoire |
  |-----|-----------------------------------------------|------------------------------|---------------------------------------------------------|
  | seed 7 | **3/10 (30 %)** | **0** (consensus ne porte pas de trendlines) | 1/4 zones à source PYTRENDLINE (25 % de ces zones) ; 3/30 lignes union détecteurs (10 %) |
  | seed 42 | **4/10 (40 %)** | **0** | 4/7 zones pyt (57 %) ; 4/30 lignes union (13 %) |

  - Consensus **par défaut** (mvpp+trendln, sans pyt) : aucun pivot provisoire → 0 % d'impact provisoire.
  - Profils paper : `STRUCTURE_PYTRENDLINE` utilise `structure_detectors=["pytrendline"]` → zones gate potentiellement contaminées ; consensus multi-détecteurs avec `include_pytrendline` aussi.

- Gate / breakouts (`structure/gate.py`, `service.detect_market_structure`) :
  - **Oui** : le gate et les breakouts utilisent les **zones consensus** (pas les pivots ni les trendlines directement).
  - Les zones pytrendline sont dérivées de `line.price_at(last_bar)` — donc une ligne ancrée sur un pivot provisoire **peut** déplacer une zone opposante du gate quand pyt est inclus.
  - Baseline `ICHIVOL_BASELINE_V1` : `structure_filter=None` → pas d'impact.

- Choix faits :
  - Mark-only : aucun changement de fit / seuils / exclusion de pivots.
  - Consensus : propage `pivots` des sources (pour tests/mesure) ; zones/scores inchangés.
  - Stabilité pytrendline : identité en indices absolus (`bar_index + offset`) ; hors fenêtre commune ou dans `left_ctx` du bord gauche après glissement → exclus (artefact de fenêtre, documenté).

- Doutes / points à vérifier par Claude : **validé** — décision Claude : exclure les pivots provisoires du fit pytrendline (T1f-2), sans seuil.

- Non fait / hors périmètre :
  - Exclusion des pivots provisoires / changement de comportement → **T1f-2**
  - `StructureState` indicators / ChartObject / découpage `routes.py` (T1g)
  - Mergé dans `main` après validation Claude.

- Tests :
  - `test_structure_causality.py` → **18 passed**
  - suite `tests/structure/` → all green
  - suite complète **sans Postgres** (Cursor) → **4 failed** connexion DB (connus localement) ; fixtures inchangées
  - revue Claude **avec Postgres** : baseline = les **13** échecs historiques ci-dessus ; tout écart = régression bloquante
  - T0-CI non démarré ici (branche séparée si lancé en parallèle)

---

## 2026-09-23 — T1e — Fin de la migration REGISTRY (cliquet vide)

- Branche : `v3/t1e-registry-remaining`
- PR : https://github.com/samiriggui-code/IchiVol/pull/10 (mergée) — **validé par Claude**
- Commit(s) : `0227abf` (fixtures golden **avant** refactor) ; `a4497a9` (migration + cliquet vide)

- Livré :
  - `app/api/routes.py` — `GET /context/{symbol}` via `REGISTRY.compute_many(rsi/cmf/obv/atr)`
  - `app/agent_channel/commands.py` — `REGISTRY.compute` ichimoku/rvol (`compute_correlation_matrix` inchangé)
  - `app/backtest/experiments.py` — `compute_many` structure/atr/location/cvd/adx/donchian/wyckoff
  - `app/strategy_lab/regime.py` — `compute_many` adx+atr
  - `app/synthetic/validation.py` — `compute_many` structure/atr/location/adx
  - `app/structure/atr_utils.py` — `REGISTRY.compute("atr")`
  - fixtures golden + tests d'égalité stricte
  - `test_registry_ratchet.py` — `ALLOWED_DIRECT_CALLERS = ∅` ; scan de tout `app/` hors `indicators/` ; exceptions documentées pour `compute_oi_funding` / `compute_projected_kumo`

- Tests :
  - golden + cliquet OK ; suites indicators/strategy_lab/backtest/synthetic/structure/api (hors evidence route Postgres) → **339 passed**, 23 skipped
  - suite complète → **4 failed** Postgres connus
  - `grep compute_<id>(` hors `app/indicators/` → vide

- Choix faits :
  - experiments : adx/donchian/wyckoff aussi migrés (nécessité cliquet vide).
  - Cliquet : interdiction pure + scan récursif de tout `app/`.

- Doutes / points à vérifier par Claude : aucun restant — **validé par Claude**.

- Non fait / reste à faire :
  - découpage `routes.py` (T1g), structure unifiée / confirmed_at (T1f), CONDITION_SCHEMA
  - Mergé dans `main` après validation Claude.

---

## 2026-09-23 — T1d — Chemin live via le REGISTRY

- Branche : `v3/t1d-live-path-registry`
- PR : https://github.com/samiriggui-code/IchiVol/pull/9 (mergée) — **validé par Claude**
- Commit(s) : `89caa75` (fixtures golden **avant** refactor) ; `51b0edf` (migration + ratchet)

- Livré :
  - `ichivol-app/engine/app/screener/service.py` — `REGISTRY.compute_many` (structure/atr/location/cvd/adx/donchian) ; `compute_oi_funding` reste direct
  - `ichivol-app/engine/app/context/gate.py` — `compute_many` pour atr/rsi/cmf/obv selon le profil
  - `ichivol-app/engine/app/evidence/catalog.py` — `compute_many` structure+atr
  - `ichivol-app/engine/app/agents/ichimoku_agent.py` — `REGISTRY.compute("ichimoku")`
  - `ichivol-app/engine/app/agents/rvol_agent.py` — `REGISTRY.compute("rvol")`
  - fixtures golden (seeds 7 & 42) sous `tests/{screener,context,evidence,agents}/fixtures/`
  - tests d'égalité stricte + `ALLOWED_DIRECT_CALLERS` réduit aux 6 modules T1e

- Tests :
  - suites indicators/strategy_lab/screener/context/evidence/agents + indicators_route (hors persistence Postgres) → **317 passed**, 2 skipped
  - suite complète → **4 failed** Postgres connus uniquement
  - cliquet ratchet vert (5 modules retirés)

- Choix faits :
  - Screener : cvd/adx/donchian aussi via `compute_many` (sinon le module resterait dans le cliquet).
  - Gate : un seul `compute_many` des indicateurs demandés par le profil.
  - Signatures publiques / seuils inchangés.

- Doutes / points à vérifier par Claude : aucun restant — **validé par Claude** (cvd/adx/donchian screener OK).

- Non fait / reste à faire :
  - T1e : modules restants + cliquet vide.
  - CONDITION_SCHEMA, structure unifiée.
  - Mergé dans `main` après validation Claude.

---

## 2026-09-23 — T1c — Features Strategy Lab via REGISTRY (`compute_many`)

- Branche : `v3/t1c-registry-features`
- PR : https://github.com/samiriggui-code/IchiVol/pull/8 (mergée) — **validé par Claude**
- Commit(s) : `5b56470` (fixture golden **avant** refactor) ; `3550c0c` (registry + features + ratchet) ; nested params `cb300c2`

- Livré :
  - `ichivol-app/engine/app/indicators/registry.py` — `depends_on`, `compute_many` (topo + dédup + cycle), enregistrement `ichimoku_analytics` / `location` / `wyckoff` ; `oi_funding` hors registry (docstring)
  - `ichivol-app/engine/app/strategy_lab/features.py` — un seul `REGISTRY.compute_many(...)` ; signatures / `FeatureBar` inchangés
  - `ichivol-app/engine/tests/strategy_lab/fixtures/features_golden.json` — FeatureBars seeds 7 & 42 (300 barres), commit **avant** le refactor
  - `ichivol-app/engine/tests/strategy_lab/test_features_golden.py` — égalité stricte vs fixture
  - `ichivol-app/engine/tests/indicators/test_registry_ratchet.py` — cliquet `ALLOWED_DIRECT_CALLERS` (features.py absent)
  - `ichivol-app/engine/tests/indicators/test_registry.py` — compute_many / cycle / warmup deps ; `test_no_lookahead` couvre les 3 nouveaux via `REGISTRY.compute`

- Tests :
  - `pytest tests/indicators tests/strategy_lab tests/api/test_indicators_route.py` → **241 passed, 1 skipped**
  - suite complète → **4 failed** Postgres connus uniquement

- Choix faits :
  - Wrappers registry pour analytics/location/wyckoff : `compute_fn(candles, params, deps)` ; analytics reçoit `ichi`/`atr` déjà calculés (pas de double compute).
  - `REGISTRY.compute(id)` sur un indicateur dépendant délègue à `compute_many` pour résoudre les deps.
  - Warmup dépendant = `max(own, deps.warmup())`.
  - Fixture golden générée et commitée **avant** toute modification de `features.py` / registry deps.

- Doutes / points à vérifier par Claude : aucun restant — **validé par Claude** (nested params corrigés).

- Corrections revue Claude :
  - `build_params` fusionne récursivement les dataclasses imbriquées ; clé inconnue → `InvalidParamsError` avec chemin (`location.volume_profile.foo`) ; API → 422.
  - Endpoint series utilise `REGISTRY.compute` (résout deps location/wyckoff/analytics).
- Non fait / reste à faire :
  - Migration des autres modules → T1d.
  - CONDITION_SCHEMA (T3 DSL), structure unifiée, découpage `routes.py`.
  - Mergé dans `main` après validation Claude.

---

## 2026-09-23 — T1b — Front servi par le moteur (Ichimoku / RVOL / kumo projeté)

- Branche : `v3/t1b-front-engine-indicators`
- PR : https://github.com/samiriggui-code/IchiVol/pull/7 (mergée) — **validé par Claude**
- Commit(s) : `25e2249` (code initial) ; handoff `417da25`… ; corrections revue Claude `30991c7`

- Livré :
  - `docs/HANDOFF-CURSOR-V3.md` — canal handoff V3 (entrée T1 + T1b)
  - `ichivol-app/engine/app/indicators/ichimoku.py` — `compute_projected_kumo` (display-only ; ne touche pas `IchimokuState` / `compute_ichimoku`)
  - `ichivol-app/engine/app/api/indicators.py` — `GET /indicators/ichimoku/{symbol}/projection` : compute sur **tout** le fetch `limit+warmup`, filtre `time_projected >= window[0].time` ; params via `REGISTRY.get("ichimoku").build_params` / `.warmup`
  - `ichivol-app/engine/tests/indicators/test_projected_kumo.py` — égalité i+d, garde import, **warmup fenêtre** (600→limit 300 → 1er `time_projected` = début fenêtre)
  - `ichivol-app/engine/tests/api/test_indicators_route.py` — projection garde warmup + params 422 via registry
  - `ichivol-app/src/lib/engineIndicators.ts` — client registry ; `mapEngineIchimokuToPoints` sans repli `closeByTime` (chikou=`null` si idx absent)
  - `ichivol-app/src/lib/signals.ts` — `buildVolumePulse` depuis séries moteur
  - `ichivol-app/src/components/PriceChart.tsx` — overlays async moteur ; prix seul si erreur
  - `ichivol-app/src/pages/MarketPage.tsx` — props `symbol`/`timeframe`/`onLive`
  - `ichivol-app/src/index.css` — message discret overlays
  - `ichivol-app/src/lib/ichimoku.ts` — **supprimé**

- Tests (après corrections revue) :
  - `cd ichivol-app/engine && .venv/bin/python -m pytest tests/indicators tests/api/test_indicators_route.py -q` → **tous OK** (169 passed au dernier run)
  - `cd ichivol-app && npm run build` → **OK**
  - Échecs Postgres connus hors scope (suite complète) : inchangés

- Choix faits :
  - Nuage futur via helper séparé + endpoint dédié (pas de changement de `compute_ichimoku`).
  - Warmup : ne pas tronquer avant `compute_projected_kumo` — sinon ~`senkou_b` barres sans nuage en tête de fenêtre.
  - Params projection alignés sur l’endpoint series (`InvalidParamsError` → 422).
  - Chikou affichage uniquement ; pas de fallback close non décalé.

- Doutes / points à vérifier par Claude :
  - Aucun restant — **validé par Claude**.

- Non fait / reste à faire :
  - Structure unifiée, découpage `routes.py`, `ChartObject` (hors périmètre T1b).
  - Mergé dans `main` (fast-forward). Suite : T1c.

---

## 2026-09-23 — T1 (étapes 1–3) — IndicatorRegistry + API /indicators

- Branche : `v3/t1-indicator-registry`
- PR : https://github.com/samiriggui-code/IchiVol/pull/6 (mergée)
- Commit(s) : `39fad41` (registry + API), `88fdb1f` (borne `limit` 1..5000), merge `b832bb4` dans `main`
- Statut : **validé par Claude**

- Livré :
  - `ichivol-app/engine/app/indicators/registry.py` — `IndicatorRegistry` / `REGISTRY`, catalog, `build_params`, warmup, serialize
  - `ichivol-app/engine/app/api/indicators.py` — `GET /indicators`, `GET /indicators/{id}/{symbol}`
  - `ichivol-app/engine/app/main.py` — montage du router indicators
  - `ichivol-app/engine/tests/indicators/test_registry.py` — tests registry
  - `ichivol-app/engine/tests/api/test_indicators_route.py` — tests route + bornes `limit=0` / `limit=-5` → 422

- Tests :
  - Suite indicators / registry + `test_indicator_limit_bounds_422` : OK sur la PR (fix `limit` avant merge pour éviter `states[-0:]` = série entière).
  - Échecs Postgres connus hors périmètre T1 (inchangés).

- Choix faits :
  - Registry thin wrapper autour des `compute_*` existants (pas de réécriture de formules).
  - `Query(ge=1, le=5000)` sur `limit` après revue Claude (bug `limit=0` / négatif).

- Doutes / points à vérifier par Claude : aucun restant — **validé**.

- Non fait / reste à faire : consommé par le front → T1b (ci-dessus).
