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
- **Règle de merge** : avec la base, tout échec **hors** de ces 13 = régression → **bloque le merge**.
- **T0-CI** : greening + correctif isolation baseline (entrée ci-dessous) — **pas de merge avant revalidation Claude**.

---

## 2026-09-23 — T0-CI — isolation baseline (revue Claude PR #14)

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (draft) — **pas de merge avant revalidation Claude**
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

### Attente

Claude revalide avec sa base (historique paper intact).

---

## 2026-09-23 — T0-CI greening — rewrite 13 paper/API tests + honest 422 + frontend job

- Branche : `cursor/t0-ci-postgres-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (draft) — **pas de merge avant revue Claude**
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
- PR : https://github.com/samiriggui-code/IchiVol/pull/14 (draft) — **pas de merge avant revue Claude**
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
- PR : *(draft à créer par parent ManagePullRequest — ne pas merger)*
- Base : `main` @ `a19f924` (après merge PR #13 T1g)

- Livré :
  - Modèle `app/chart_objects/types.py` — `ChartObject` frozen, id déterministe (sha256[:24] de type/source/symbol/tf/coords arrondis/subtype), validation par type, `to_dict`/`from_dict`
  - Producteur `from_structure.py` — sélection **identique** à `structure.ts` `toStructureOverlay` (MAX_ZONES=3, MAX_TRENDLINES=2, score desc, lignes drawable seulement) ; zones consensus → ZONE ; trendlines détecteurs → TREND_LINE ; breakouts → MARKER
  - Confiance : `clamp(score / max_score_pool, 0, 1)` (docstring)
  - API `GET /api/engine/chart-objects/{symbol}?timeframe=&limit=&sources=engine` — router dédié `api/chart_objects.py`, branché en fin d’agrégateur `routes.py` ; sources non-ENGINE → liste vide (pas d’erreur)
  - Front : `src/lib/chartObjects.ts` + `PriceChart.renderChartObjects` (ZONE = 2 price lines pointillées « S/R ×n », TREND_LINE = LineSeries dashed, MARKER = circle) ; `MarketPage` appelle `getChartObjects` ; `toStructureOverlay` / `getEngineStructure` retirés
  - Goldens OpenAPI + `route_order` : **ajouts seuls** (`/chart-objects/{symbol}`)

- Tests :
  - `tests/chart_objects/` — round-trip, validation, id stable, sélection parity seeds 7 & 42, causalité `as_of`
  - `tests/api/test_chart_objects_route.py` — ENGINE OK ; user/claude → `objects=[]`
  - `test_api_surface_golden` → vert
  - `npm run build` → OK

- Hors scope (T2b/T5) : outils dessin Claude, persistence USER/CLAUDE, ENTRY/STOP/TARGET

- Non fait : merge ; T0-CI

---

## 2026-09-23 — T1g — Découpage de `api/routes.py` (zéro changement de comportement)

- Branche : `v3/t1g-split-routes`
- PR : https://github.com/samiriggui-code/IchiVol/pull/13 (mergée) — **validé par Claude**
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

- Non fait à l’époque : T0-CI (branche parallèle) ; T2 ChartObject — **T1 terminé** (T1→T1g).

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
