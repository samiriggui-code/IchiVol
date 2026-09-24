# Handoff Cursor ↔ Claude — IchiVol V3

Canal unique entre Cursor (implémentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff de la PR associée.

**Convention** : à chaque PR, ajouter une nouvelle entrée **en haut** ; ne jamais effacer les anciennes.

---

## 2026-09-24 — T12e EN COURS — ADN matrice A→F (#78)

- Branche : `cursor/t12e-adn-ichivol-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/78
- Base : `main` @ `4549a2f` (#77 T14a **MERGÉE**)
- Lab only — **aucun changement live**
- Livrable doc : `docs/ETUDE-T12-ADN-ICHIVOL.md`

### Livré
1. `app/strategy_lab/adn_ichivol.py` — LiveScreenerSettings · ladder A→B→D→E→F · C parallèle · KEEP/RESEARCH/REJECT
2. Ladder `adn_ichivol` · fix coerce `location_stage_pass` / `regime_stage_pass`
3. Tests + `scripts/t12e_adn_study.py` · étude méthode (pas de KEEP sans deep_history)

### DÉCISION CURSOR — à relire par Claude
Settings = défauts production nommés ; C parallèle ; forex/actions exclus (<2 ans).

### Auto-revue
- [x] pytest T12e + T9g OK
- [ ] pytest PG16 complet (CI)
- [x] decision/screener/paper/brokerage non touchés
- [ ] deep_history BTC/ETH sur VPS (Binance 451 ici)

---

## 2026-09-24 — T14a MERGÉE (#77) — squash `4549a2f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/77 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `4549a2f`
- Nav 4 groupes · Desk/Opportunités/Opérations/Portefeuille · pinned · Journal tabs · kill stub

**Suite** : T12e #78.

---

## 2026-09-24 — T12d MERGÉE (#76) — squash `69a11f6`

- PR : https://github.com/samiriggui-code/IchiVol/pull/76 — **MERGÉE** squash (solo rév.58)
- **Vérifié** : squash `69a11f6` (ancêtre de `4549a2f`)
- Fausses cassures nuage à N ; ventilation RVOL/ADX/structure/location/CVD

---

## 2026-09-24 — T12d (archive) — fausses cassures du nuage

- Branche : `cursor/t12d-false-breaks-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/76
- Base : `main` @ `abe6177` (#75 T12c **MERGÉE**)
- ADD-ONLY Lab — **aucun changement live**

### Livré
1. `strategy_lab/kumo_false_breaks.py` — `study_kumo_false_breaks_on_candles`  
   - rising-edge `kumo_breakout_*`  
   - étiquette à **N** barres explicite : continuation / failure / inside / incomplete  
   - ventilation : RVOL bande, ADX (trending/ranging), structure, location, CVD
2. Tests `test_t12d_kumo_false_breaks.py` (continuation, failure, incomplete, bearish miroir, série réelle)

### Hors scope
FeatureBar fields · HTTP · T12e · live

### Sonde manuelle
Cassure haussière + prix sous nuage à i+N → `failure` ; toujours au-dessus → `continuation`.

### Auto-revue (§2) — FAIT
- [x] pytest PG16 : **1086 passed**
- [x] pytest réseau coupé : **1085 passed, 1 skipped**
- [x] `npm run build` OK
- [x] golden : N/A (aucun golden touché)
- [x] `git diff` decision/agents/paper/screener/brokerage : **vide**

---

## 2026-09-24 — T12c MERGÉE (#75) — squash `abe6177`

- PR : https://github.com/samiriggui-code/IchiVol/pull/75 — **MERGÉE** squash (solo rév.58)
- **Vérifié** : `origin/main` tip = `abe6177`
- Références Lab buy&hold / Donchian / BOS ; golden additif ; 1080/1079+1skip

**Suite** : T12d fausses cassures…

---

## 2026-09-24 — T12c (archive EN COURS) — références buy&hold / Donchian / structure

- Branche : `cursor/t12c-reference-baselines-a2fe`
- Base : `main` @ `36ff85f` (#74 UI exception **MERGÉE**)
- ADD-ONLY Lab — **aucun changement live / seuils**

### Livré
1. `strategy_lab/reference_baselines.py` — `run_reference_baselines_on_candles`  
   - buy&hold (`run_backtest` toujours LONG)  
   - Donchian breakout UP seul (ruleset ATR 1R/2R)  
   - structure BOS haussier seul (ruleset ATR 1R/2R)  
   - **mêmes** `commission_bps` / `slippage_bps` (défaut Lab 5+3)
2. Catalog : `IV_REF_DONCHIAN_BO_LONG_001`, `IV_REF_STRUCTURE_BOS_LONG_001` (`meta.reference`/`t12c`)
3. Tests `test_t12c_reference_baselines.py` (frais partagés, bords 0/1 barre, fee override)

### DÉCISION CURSOR — à relire par Claude
« Structure seule » = rising-edge **`bos_bullish`** (ablation `C_BOS`), **pas** `IV_ICHIMOKU_ONLY_*`.

### Hors scope
HTTP route (appelants = module Python) · T12d/e · live

### Sonde manuelle
Série synthétique drift : buy&hold exposure > 0.9, ≥1 trade.

---

## 2026-09-24 — UI exception MERGÉE (#74) — squash `36ff85f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/74 — **MERGÉE** squash (solo rév.58)
- **Vérifié** : `origin/main` tip = `36ff85f`
- Matrice : libellé **Régime** ; DIR **↑/↓** ; captures `ui74-*-matrix.png`
- Auto-revue : pytest 1074 ON / 1073+1 skip OFF ; npm build OK ; moteur inchangé

**Suite** : T12c…

---

## 2026-09-24 — UI exception EN COURS — Risque→Régime + DIR ↑/↓ (rév.56/58)

- Branche : `cursor/ui-regime-dir-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/74 (**draft**)
- Base : `main` @ `a7b630f` (#73 T12b **MERGÉE**)
- Tip : `99c778e`
- Front only — **aucun changement moteur**

### Livré
1. `stageMatrixLabel('regime')` : **« Risque » → « Régime »**
2. Colonne DIR Matrice : `pass` + LONG → **↑** ; `pass` + SHORT → **↓** (`stageDirectionMatrixLabel`) ; autres statuts inchangés

### Auto-revue (§2) — FAIT
- [x] pytest PG16 : **1074 passed** (réseau ON)
- [x] pytest réseau coupé (HTTP_PROXY mort) : **1073 passed, 1 skipped** (Binance)
- [x] `npm run build` OK
- [x] golden : N/A (aucun golden touché)
- [x] `git diff` decision/agents/paper/screener/brokerage : **vide**
- [x] Captures Matrice desktop/mobile × clair/sombre → `/opt/cursor/artifacts/ui74-*-matrix.png`  
  Headers vérifiés : `… Loc · Régime · Portes` ; DIR sample = `↓` (SHORT pass)

### Hors scope
T12c+ · T14a · moteur · libellé carte résumé « Régime / Risque » (STAGE_META, hors brief)

### Sonde manuelle
Matrice live `/app/decisions` vue Matrice : en-tête **Régime** ; cellules Dir **↓** (marché short) — pas « OK ».

---

## 2026-09-24 — SYNC Claude rév.58 — MODE SOLO jusqu’au retour Claude

Claude indisponible jusqu’à demain. **Solo autorisé** sur la liste §5 (rév.58) :
UI exception → T12c → T12d → T12e → T14a → T13a → T13b → T13c → T11a-bis → T11b (partiel) → T10d/e.

Auto-revue §2 avant chaque merge ; arrêts §3 inchangés ; design UI §4.  
ChatGPT = consultatif seulement. Toute décision seule = **« DÉCISION CURSOR — à relire par Claude »**.

**STOP après point 11** : ne pas démarrer T13d, T13e, T11c, pages Sessions/Agents.

---

## 2026-09-24 — T12b MERGÉE (#73) — squash `a7b630f`

- PR : https://github.com/samiriggui-code/IchiVol/pull/73 — **VALIDÉE** Claude (rév.58) → **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `a7b630f`
- Suite PG (Claude) : 1 073 ok / 1 skip ; golden additifs ; chemin live inchangé ; parité via helpers pipeline ; 3 statuts exercés.

### Réserves Claude (non bloquantes) — à traiter plus tard
1. La parité T12b utilise les **paramètres par défaut** ; **T12e DOIT** utiliser les paramètres réels du screener live (settings).
2. L’étape **structure (MTF)** reste hors parité jusqu’à **T3e**.

**Suite** : petite PR UI exception (Risque→Régime + DIR ↑/↓), puis T12c…

---

## 2026-09-24 — SYNC Claude rév.56 — T14 Interface V3

Audit UI ajouté à la feuille de route (**section T14**).

**Ordre** (rév.56/58) : … T12e → **T14a** → T13a → T13b + T14c → …  
Aucune fusion ni suppression de page avant T14a.

### Exception autorisée — EN COURS (voir entrée UI exception ci-dessus)

---

## 2026-09-24 — T12a MERGÉE (#72) — squash `5bc1e9c`

- PR : https://github.com/samiriggui-code/IchiVol/pull/72 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `5bc1e9c`
- Historique profond versionné + validate_candles + qualité Lab ; correctifs rév.53/54.

**Suite** : T12b MERGÉE ; UI exception + T12c…

---

## 2026-09-24 — T9g-fix MERGÉE (#71) — squash `9490e4b`

- PR : https://github.com/samiriggui-code/IchiVol/pull/71 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `9490e4b`
- `review_candidate` + gates ; `min(trades_base, trades_var)` (rév.50).

**Suite** : T12a EN COURS (historique profond versionné + validate_candles).

---

## 2026-09-24 — SYNC Claude rév.51 — complétude T12a/b + T11a-bis (après #71)

Contrôle de complétude Claude — **à appliquer après merge de #71**,  
**sans changer l’ordre** : T9g-fix → T12a → T12b → T12c → T12d → T12e → T13…  
puis T11a-bis (petite PR post-T12e).

### T12a — ajouts obligatoires (brief)

- Jeu versionné : passe **`validate_candles`** (`market_data/quality.py`) à la construction
- Rapport qualité (**codes + compte par code**) écrit dans le **manifeste**, à côté des sha256
- Études Lab (`walk-forward`, `ablation_oos`, `regime_slices`) **renvoient** ce rapport avec leurs résultats
- Jeu marqué défaillant : **toujours utilisable**, mais **avertissement affiché**

### T12b — ajout

- Bandes RVOL **booléennes** (faible / normal / élevé / fort / extrême)  
  → pour que la redondance T10c puisse aussi les mesurer

### T11a-bis (après T12e, une petite PR) — oublis T11a

1. `resolution = "raw_fallback"` dans `resolve.py` quand un symbole hors catalogue retombe sur Binance
2. Bougies DB : `volume_type` + `taker_buy_volume` (migration unique ; anciennes lignes `NULL`)
3. Test d’imports garde production : `decision/pipeline.py` et `decision/combiner.py` ne doivent importer, même indirectement, **ni** `strategy_lab.lab_context` **ni** un indicateur hors `PRODUCTION`

### Noté ailleurs

- Cache `observe_lab_context` → avec **T11b** (~49 % overhead, ~0,7 s/cycle : pas urgent)
- #71 CI verte @ `2e959f2` — **pas de merge** tant que Claude n’a pas re-validé le correctif `min(trades)`

---

## 2026-09-24 — T9g-fix EN COURS — review_candidate + gates

- Branche : `cursor/t9g-fix-gate-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/71 (**draft**)
- Base : `main` @ `33684c0` (#70 Wyckoff)
- Statut : **DRAFT** — correctif rév.50 + CI verte ; **attente re-revue Claude** (pas de merge). Brief T12/T11a-bis : voir SYNC rév.51.

### Livré

1. `promote` → **`review_candidate`** (Lab ne promeut jamais)
2. Gates : min_oos_trades défaut **30** ; majorité stricte de plis ; coûts défavorables (10/8 bps) ; PF OOS non dégradé
3. Affichage : `hypothesis_id` / `lineage_trial_count` (T10b), `n_bars`, `history_warning` si < 1 an
4. Tests limite par règle ; OpenAPI golden (défaut min_oos_trades)
5. **Correctif rév.50** : `total_oos_trades = min(trades_base, trades_var)` (pas `max`)

### Réserve (non bloquante)

`lineage_trial_count` ne compte que les expériences **persistées** en Perf DB ; l’étude courante n’y est **pas** incluse.

### Changement non additif (seul autorisé)

Enum recommandation : `promote` → `review_candidate` — justifié dans la PR.

### Hors scope
T12 · FeatureStatus mutation · pipeline · microstructure

---

## 2026-09-24 — Wyckoff REJECTED MERGÉE (#70) — squash `33684c0`

- PR : https://github.com/samiriggui-code/IchiVol/pull/70 — **MERGÉE** squash
- **Vérifié** : tip attendu `33684c0` sur `origin/main`
- `FeatureStatus.REJECTED` ; toujours calculable Lab. Golden inchangés.

---

## 2026-09-24 — SYNC Claude rév.49 — T13 ajoutée (NE PAS DÉMARRER)

Addendum feuille de route : tranche **T13 « couche de trading contrôlée »**.  
**Aucun code T13 dans cette session.**

### Ordre du jour (rév. 49) — inchangé jusqu’à T12e

1. T9g-fix  
2. T12a  
3. T12b  
4. T12c  
5. T12d  
6. T12e  
7. **T13a** → **T13b** → …  
8. Ensuite : T11b-c, T10d-e, T11d-f, T3e MTF, modèle G  

(microstructure : toujours rien avant T12e)

### Contraintes T13 à respecter dès maintenant (sans coder)

- **Risk Kernel** = **une** fonction pure **obligatoire** ; tous les chemins d’ouverture paper devront y passer :
  - `sync_auto_watchlist`
  - `open_user_confirmed`
  - action agent `open_paper_position`
- **Ne pas** ajouter de nouveau chemin d’ouverture qui contournerait le kernel.
- **Aucun** ordre réel, identifiant broker, ni adaptateur broker réel dans T13.
- Réutiliser (pas dupliquer) : `paper/gates.py`, `paper/risk.py`, `quote_paper.py`, `brokerage/execution.py`.

### PR ouvertes (attente revue Claude, une à la fois)

| PR | Objet |
|---|---|
| #69 | ce handoff (rév.48 + rév.49) |
| #70 | Wyckoff REJECTED |
| #71 | T9g-fix |
| #68 | trade VP — différée post-T12e |

---

## 2026-09-24 — SYNC Claude rév.48 — bilan #53→#67 + reprise

Revue Claude a posteriori sur `main` @ `23dc4ba` : **rien à revert**  
(suite PG 1 049 ok / 1 skip ; golden additifs ; décision inchangée).

### Règle merge (rétablie)

**Fin du mode solo.** Une PR à la fois ; **aucun merge sans revue Claude**,  
sauf autorisation utilisateur explicite pour une tranche nommée.  
Vérifier `origin/main` avant d’écrire MERGÉE.

### #67 — MERGÉE (correction handoff)

- PR : https://github.com/samiriggui-code/IchiVol/pull/67 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `23dc4ba`
- (L’entrée « EN COURS / draft » plus bas est **obsolète** — squash déjà dans main.)

### #68 trade VP

**Différée** jusqu’après T12e (rév.48 §6).  
PR draft : https://github.com/samiriggui-code/IchiVol/pull/68 — ne pas merger.

### Ordre du jour (rév. 48) — **supersédé par rév.49** (ci-dessus)

Voir entrée SYNC rév.49 : T9g-fix → T12a–e → **T13a…** ; microstructure après T12e.

### Point mesuré — `observe_lab_context` (sans code)

Benchmark local synthétique (300 barres × 20 symboles × 3 reps, pas de réseau) :

| Path | ms / cycle 20 symboles |
|---|---|
| `observe_lab_context` seul | ~238 ms |
| scan_like (agents + REGISTRY + pipeline) | ~489 ms |
| scan_like + observe | ~717 ms |

**Overhead observe / scan_like ≈ 49 %** (part du total ≈ 33 %).  
**> 10 %** → candidat cache (tranche dédiée, pas dans T9g-fix).

### Suite immédiate

1. PR Wyckoff `FeatureStatus.REJECTED` (commit séparé, golden inchangés)  
2. PR **T9g-fix** — `promote` → `review_candidate` + gates (revue Claude avant merge)


---

## 2026-09-24 — Chart layer=breaks EN COURS — BOS / CHoCH producer

- Branche : `cursor/breaks-chart-producer-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/67
- Base : `main` @ `35e14f3` (#66 microstructure)
- Statut : **MERGÉE** squash `23dc4ba` — voir entrée SYNC rév.48 en tête.

### Livré (prévu)

1. `chart_objects/from_breaks.py` — StructureEvent BOS/CHoCH via REGISTRY + breakouts
2. `collect.py` merge ; breakouts retirés de `from_structure` (layer structure = zones/TL)
3. Front : retire `emptyUntil: T9` sur couche Cassures
4. Tests `test_from_breaks.py`

### Hors scope
Trade VP · order book · décision / paper / broker.

---

## 2026-09-24 — Binance microstructure Lab MERGÉE (#66) — squash `35e14f3`

- PR : https://github.com/samiriggui-code/IchiVol/pull/66 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `35e14f3`
- Cursor solo ; CI verte. Lab-only trade CVD compare.

**Suite solo** : chart `layer=breaks` producer → trade VP Lab → doc sync.

---

## 2026-09-24 — Binance microstructure Lab EN COURS — trade CVD compare

- Branche : `cursor/binance-microstructure-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/66
- Base : `main` @ `8c6af5e` (#65 ProviderCapabilities)
- Statut : **MERGÉE** via entrée ci-dessus.

---

## 2026-09-24 — ProviderCapabilities MERGÉE (#65) — squash `8c6af5e`

- PR : https://github.com/samiriggui-code/IchiVol/pull/65 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `8c6af5e`
- Cursor solo ; CI verte. Inventaire déclaratif only.

---

## 2026-09-24 — ProviderCapabilities EN COURS — inventaire providers

- Branche : `cursor/provider-capabilities-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/65 (**draft**)
- Base : `main` @ `00ab86a` (#64 T9g)
- Statut : **DRAFT** — Cursor solo. Déclaratif only ; **pas de nouveau router**. CI en cours.

### Livré

1. `market_data/capabilities.py` — `ProviderCapabilities` (ohlcv/quotes/trades/depth/OI/funding/volume)
2. Déclarations binance / biquote / twelve_data (honnêtes vs code réel)
3. `GET /providers/capabilities` + agent `list_provider_capabilities`
4. Tests + OpenAPI goldens

### Hors scope
OANDA/IBKR adapters · WS · depth fetch · changer paper path.

---

## 2026-09-24 — T9g MERGÉE (#64) — squash `00ab86a` — ablation × WF OOS

- PR : https://github.com/samiriggui-code/IchiVol/pull/64 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `00ab86a`
- Cursor solo ; CI verte. Recommendations display-only.

---

## 2026-09-24 — T9g EN COURS — ablation × walk-forward OOS

- Branche : `cursor/t9g-ablation-oos-a2fe`
- PR : *(draft à ouvrir)*
- Base : `main` @ `c261f48` (#63 T10c)
- Statut : **EN COURS** — Cursor solo. Recommendations display-only ; **pas de mutation FeatureStatus**.

### Livré

1. `strategy_lab/ablation_oos.py` — additive / leave-one-layer × WF OOS
2. `decide_recommendation` → promote | reject | inconclusive
3. `POST /strategy-lab/ablation-oos/study` + agent `run_ablation_oos_study`
4. Tests `test_t9g_ablation_oos.py` + goldens OpenAPI

### Hors scope
Auto FeatureStatus · pipeline vote · UI tab · walk-forward-opt grid.

---

## 2026-09-24 — T10c MERGÉE (#63) — squash `c261f48` — redondance feature×feature

- PR : https://github.com/samiriggui-code/IchiVol/pull/63 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `c261f48`
- Cursor solo ; CI verte. Observation-only ; pas d’auto-reject.

---

## 2026-09-24 — T10c EN COURS — redondance feature×feature

- Branche : `cursor/t10c-feature-redundancy-a2fe`
- PR : *(draft à ouvrir)*
- Base : `main` @ `1a9fb2a` (handoff T11a)
- Statut : **EN COURS** — Cursor solo. **Observation-only** ; **pas d’auto-reject**.

### Livré

1. `strategy_lab/redundancy.py` — overlap / Jaccard / φ sur conditions bool Lab
2. `GET /strategy-lab/feature-redundancy/study` + agent `run_feature_redundancy_study`
3. Annote family/status T10a ; disclaimer no pipeline / no auto-reject
4. Tests `test_t10c_feature_redundancy.py` + route research

### Hors scope
Auto-reject · mutation FeatureStatus · T9g OOS · UI Lab tab · pipeline vote.

---

## 2026-09-24 — T11a MERGÉE (#61) — squash `ff43f17` — quality + provenance (obs)

- PR : https://github.com/samiriggui-code/IchiVol/pull/61 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `ff43f17`
- Cursor solo ; CI verte. **Observation-only** (pas de hard `bad→NO_TRADE`).

**Suite** : T10c EN COURS → T9g.

---

## 2026-09-24 — T11a EN COURS — quality gate + provenance

- Branche : `cursor/t11a-quality-provenance-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/61 (**draft**)
- Base : `main` @ `934f3e4` (#60 T9f)
- Statut : **DRAFT** — Cursor solo. **Observation-only** (pas de `bad→NO_TRADE` pipeline). CI en cours.

### Livré (prévu)

1. `observe_data_quality` / `observe_data_provenance` (`market_data/observe_quality.py`)
2. Gate display `pass|watch|fail` + `dataset_fingerprint` ; disclaimer no vote
3. `ScreenerRow.data_quality` / `data_provenance` + serializers
4. `AnalysisStage` DATA_QUALITY + prepend optionnel sur handoff (décision pipeline inchangée)
5. Tests `test_t11a_quality_provenance.py`

### Hors scope
Hard gate pipeline · T10c redondance · T9g ablation OOS · T11b+.

---

## 2026-09-24 — T9f MERGÉE (#60) — squash `934f3e4` — Lab fib_* + watchlist badges

- PR : https://github.com/samiriggui-code/IchiVol/pull/60 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `934f3e4`
- Cursor solo ; CI verte. Observation-only.

---

## 2026-09-24 — T9f EN COURS — Lab fib_* + lab_context watchlist

- Branche : `cursor/t9f-lab-features-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/60 (**draft**)
- Base : `main` @ `84efa9d` (#59 T9e)
- Statut : **DRAFT** — Cursor solo. **Observation-only** (pas de pipeline / pas d’auto-reject). CI en cours.

### Livré

1. FeatureBar `fib_*` (ancre ImpulseEvent actif) + conditions Lab orphelines (`fvg_status`, `impulse_displacement_atr_min`, `fib_*`)
2. `observe_lab_context` → `ScreenerRow.lab_context` + serializers summary/detail
3. Watchlist : badges CHoCH / FVG / Fib **réels** (placeholders T9f retirés)
4. Goldens **additifs** only ; tests `test_t9f_lab_features.py`

### Hors scope
Pipeline / paper gate impulse · T11a · T10c · T9g.

---

## 2026-09-24 — T9e MERGÉE (#59) — squash `84efa9d` — Fib ancré ImpulseEvent

- PR : https://github.com/samiriggui-code/IchiVol/pull/59 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `84efa9d`
- Cursor solo ; CI verte. Gate paper reste `anchor=naive`.

---

## 2026-09-24 — T9e EN COURS — Fib ancré sur ImpulseEvent

- Branche : `cursor/t9e-fib-anchor-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/59 (**draft**)
- Base : `main` @ `534ee80` (#58 T9d)
- Statut : **EN COURS** — Cursor solo. Gate paper reste `anchor=naive` (compat).

### Livré

1. `compute_fib_context(..., anchor=naive|impulse|auto)` + `swings_from_impulse`
2. `FibContext` additif : `anchor_source` / bars / `displacement_atr`
3. `from_fibonacci.py` → `layer=fibonacci` (key ratios) ; collect merge
4. Calque Fib sans `emptyUntil`
5. Tests anti-lookahead + gate naive inchangé

### Hors scope
T9f Lab badges · pipeline · changer le gate paper vers impulse (Claude tranche).

---

## 2026-09-24 — T9d MERGÉE (#58) — squash `534ee80` — FVG causal

- PR : https://github.com/samiriggui-code/IchiVol/pull/58 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `534ee80`
- Cursor solo ; CI verte (fix T1e ratchet via REGISTRY.compute).

---

## 2026-09-24 — T9d EN COURS — FVG (Fair Value Gap) causal

- Branche : `cursor/t9d-fvg-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/58 (**draft**)
- Base : `main` @ `ef062c2` (#57 T9c)
- Statut : **DRAFT** — Cursor solo. Pas de Fib / pas de pipeline. CI en cours.

### Livré

1. `app/indicators/fvg.py` — 3-candle ICT imbalance + fill/invalidation causals
2. Registry `fvg` EXPERIMENTAL ; Lab `fvg_bullish` / `fvg_bearish` / `fvg_active`
3. `from_fvg.py` → rectangles `layer=fvg` ; merge dans `collect.py`
4. Front : rectangles via dual price-lines ; calque FVG plus `emptyUntil`
5. Tests anti-lookahead + non-interférence structure/impulse ; goldens additifs

### Hors scope
T9e Fib ancré · T9f badges watchlist · breaks layer · décision / broker.

---

## 2026-09-24 — T9c MERGÉE (#57) — squash `ef062c2` — impulsion / displacement

- PR : https://github.com/samiriggui-code/IchiVol/pull/57 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `ef062c2`
- Cursor solo ; CI verte.

---

## 2026-09-24 — T9c EN COURS — impulsion / displacement causal

- Branche : `cursor/t9c-impulsion-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/57 (**draft**)
- Base : `main` @ `82e980e` (#56 T10b)
- Statut : **DRAFT** — Cursor solo (Claude restreint). Pas de FVG / pas de Fib rewrite / pas de pipeline. CI en cours.

### Livré (prévu / en cours)

1. `app/indicators/impulse.py` — `ImpulseParams` / `ImpulseEvent` / `ImpulseState` / `compute_impulse`
2. Pivot-to-pivot leg (T9a fractal) ; gate `min_displacement_atr` (+ `min_rvol` optionnel)
3. Registry `impulse` EXPERIMENTAL (`family=structure`)
4. Lab : `impulse_bullish` / `impulse_bearish` / `impulse_displacement_atr` (conditions + FeatureBar)
5. Tests anti-lookahead + seuil + non-interférence structure bos/bias
6. Goldens **additifs** only (condition schema/eval + features)

### Hors scope
T9d FVG · T9e Fib ancré · chart `layer=breaks` (plus tard) · décision / paper / broker.

**Claude** : valider définition leg vs candle ; seuils a priori.

---

## 2026-09-24 — T10b MERGÉE (#56) — squash `82e980e` — compteur d’essais + complexité

- PR : https://github.com/samiriggui-code/IchiVol/pull/56 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `82e980e`
- Cursor solo (Claude restreint) ; CI verte (fix assertion untagged lineage = total essais ruleset).
- Display-only : **aucune auto-rejection**.

**Claude** : auditer #56 avec #54/#55/#53.

---

## 2026-09-24 — T10b EN COURS — hypothesis_id + lineage + complexité (display-only)

- Branche : `cursor/t10b-hypothesis-lineage-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/56 (**draft**)
- Base : `main` @ `6d1968a` (#53 T9b)
- Statut : **DRAFT** — Cursor solo (Claude restreint). **Pas d’auto-reject.** CI en cours.

### Livré

1. Migration alembic `f2a3b4c5d6e7` : `strategy_lab_experiments.hypothesis_id` nullable + index (non-UNIQUE — plusieurs essais / hyp)
2. ORM + `save_experiment(..., hypothesis_id=)` / aussi via `parameters.hypothesis_id`
3. `ruleset_complexity(rules_json)` — score display-only (`entry_leaves` / `exit_leaves` / `exit_extras`) ; note « no auto-reject »
4. `lineage_count` : COUNT par `hypothesis_id` si set, sinon `ruleset_id+symbol+timeframe`
5. API list/get/compare + agent channel enrichis ; filtre `hypothesis_id` sur list
6. UI Lab : colonnes **Essais** + **Cx** sur tables Perf DB / StoredMetrics
7. Tests : `test_t10b_hypothesis_lineage.py` (unit complexity always ; DB lineage skip sans PG)

### Hors scope
T10c redondance ; T9g ablation OOS ; aucun rejet automatique sur complexité / essais.

**Claude** : auditer post-12h10 avec #54/#55/#53.

---

## 2026-09-24 — T9b MERGÉE (#53) — squash `6d1968a` — CHoCH + break quality

- PR : https://github.com/samiriggui-code/IchiVol/pull/53 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `6d1968a`
- Cursor solo (Claude restreint) ; CI verte avant merge.
- Notes : `bos_bullish` bit-identique (non scindé) ; `choch_*` / `break_quality` EXPERIMENTAL ; `recalc_short_entry_fee` dry-run + idempotent.

**Claude** : auditer #53 à 12h10 (post-merge).

---

### Suite de tests — Postgres (supervision 2026-09-23)

- **Claude** (revue) : PostgreSQL 16 `ichivol_engine_dev`, migrations alembic appliquées → lance la suite **complète** (paper, backtest evidence, brokerage, market_data inclus).
- **Cursor** (implémentation) : **pas** d’install Postgres local ; suite sans base comme d’habitude ; reporter les résultats dans le handoff. Les échecs liés à la base sont détectés / renvoyés par Claude.
- **Baseline avec base propre** (référence courante, post T0-CI #14) : **0 échec, 1 skip** réseau Binance. Toute base **non vierge** (ex. `ichivol_engine_dev` local avec de l'historique réel de paper trading) peut faire échouer des tests qui supposent un état propre (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_protection.py`, `test_overview_marks_budget` timing) — **vérifier contre `main` avant merge** avant de conclure à une régression, ne pas comparer à cette baseline si la base contient déjà des données.
- **Règle de merge** : avec une base propre, **0 échec** attendu. Tout échec **nouveau par rapport à `main`** bloque le merge. **Toujours vérifier `git log origin/main` après un merge** avant d’annoncer MERGÉE dans le handoff.
- **T0-CI** : greening + isolation baseline — **mergé** (PR #14) — **validé par Claude**.
- **T2a** : ChartObject — **mergé** (PR #15) — **validé par Claude**.
- **T0-BROKER** #16 — **MERGÉE** (validé Claude).
- **T2b** #17 — **MERGÉE** (validé Claude).
- **T3** #18 — **MERGÉE** (validé Claude) — DSL `all`/`any` + `exit`.
- **T0-UI** #19 — **MERGÉE** (accepté Claude comme T0-UI, pas T4 roadmap).
- **T2c** #20 — **MERGÉE** — **validé par Claude** (T2a+T2b+T2c = **T2 terminé**).
- **T3c** #21 — **MERGÉE** — **validé par Claude** (registre conditions ; T3 phase close — T3d avec T5b, T3e plus tard).
- **T4a** #22 — **MERGÉE** — **validé par Claude** (overlay + correction net).
- **T0-METRICS** #23 — **MERGÉE** — **validé par Claude** (stats nettes ; `cost_log` / `net_v1`).
- **T0-METRICS-2** #24 — **MERGÉE** — **validé par Claude** (`eod_return` ; lookahead strict).
- **T0-CALC** #25 — **MERGÉE** — intégrée par Cursor (Claude indisponible jusqu’à 18:10 ; CI verte ; brief Claude respecté).
- **Event Intelligence audit** #26 — **MERGÉE** (doc).
- **EventAnomalyDetector PHASE 5** #27 — **MERGÉE** (observation-only).
- **Event Intelligence PHASE 6** #28 — **MERGÉE** (regime study + calibration ; Cursor solo, CI verte).
- **Event Intelligence PHASE 7** #29 — **MERGÉE** (SymbolNews + correlate → `EVENT_MARKET` ; Cursor solo, CI verte).
- **T4c** #31 — **MERGÉE** (WHY ENTERED / REJECTED / EXITED).
- **T4b** #32 — **MERGÉE** (filtres overlay structurés).
- **T4d** #33 — **MERGÉE** (filtre régime overlay).
- **T5a** #34 — **MERGÉE** (family weights observation-only).
- **T5b** #35 — **MERGÉE** (profils poids + étude historique).
- **T6** #36 — **MERGÉE** (AuditReport post-outcome).
- **T7** #37 — **MERGÉE** (Monte Carlo / risk of ruin).
- **T3d** #39 — **MERGÉE** (propose ruleset edit + condition catalog).
- **Researcher** #41 — **MERGÉE** (propose experiment plan).
- **UI Lab Research** #43 — **MERGÉE** (validé par Claude, revue exécutée en local Laragon/Postgres).
- **T0-NOTIF** #44 — **MERGÉE** (validé par Claude, revue exécutée en local Laragon/Postgres).
- **T0-MANAGE-a** #45 — **MERGÉE** (validé par Claude, revue exécutée en local Laragon/Postgres — diff réel + no-lookahead vérifié bar par bar).
- **T0-MANAGE-b** #46 — **MERGÉE** (validé par Claude — watermark, gate legacy/auto et isolation des tests vérifiés ; 2 réserves non bloquantes notées).
- **T0-MANAGE-c** #47 — **MERGÉE** (validé par Claude — invariant 1e-9 revérifié indépendamment ; **résidu de Jensen mesuré et non borné, voir entrée dédiée**).
- **T0-MANAGE-d** #48 — **MERGÉE** squash `a941539` (validé Claude ; suite PG 918→928 ok / 1 skip). **Incident process** : handoff avait annoncé MERGÉE avant que `main` ne contienne le squash — corrigé.
- **T0-MANAGE-e** #49 — **MERGÉE** squash `389fc40` (validé Claude adff686 ; suite PG **935 ok / 1 skip**, 0 régression). Sondes : `tighten_stop` en profit → risque = R0 (LONG/SHORT) ; risque signé OK ; combo `partial_tp`+`reinforce` rejeté ; fuzz 300 seeds → 135 adds, jamais > R0, invariant Σnet=Σbars 3,5e-16. **Vérifié** `git log origin/main` contient `389fc40`.
- **T0-MANAGE-f** #50 — **MERGÉE** squash `7a77424` (validé Claude 102caee ; suite PG **944 ok / 1 skip**, 0 régression). **T0-MANAGE a→f terminé.**
- **T0-FIX-SHORT-FEE** #51 — **MERGÉE** squash `b9f8421` (validé Claude ; suite PG **948 ok / 1 skip**, 0 régression). Sondes SHORT (close / partiel→target / renfort→target / épuisement / stop) : cash = réalisé ≤ 5e-13. **Vérifié** `git log origin/main` contient `b9f8421`. **Dette SHORT entry_fee soldée** pour clôtures post-fix.
- **T9a** #52 — **MERGÉE** squash `985c4e5` (validé Claude ; suite PG **955 ok / 1 skip**). **Vérifié** `origin/main` tip contenait `985c4e5`.
- **UI-MARKET** #54 — **MERGÉE** squash `10631ef` (Cursor solo, Claude restreint ; CI verte). **À auditer Claude 12h10.**
- **T10a** #55 — **MERGÉE** squash `2e3ebc1` (Cursor solo ; CI verte). **À auditer Claude 12h10.**
- **T9b** #53 — **MERGÉE** squash `6d1968a` (Cursor solo, Claude restreint ; CI verte). **À auditer Claude 12h10.**
- **T10b** #56 — **MERGÉE** squash `82e980e` (Cursor solo ; CI verte). **À auditer Claude 12h10.**
- **T9c** #57 — **MERGÉE** squash `ef062c2` (Cursor solo ; CI verte). **À auditer Claude 12h10.**
- **T9d** #58 — **MERGÉE** squash `534ee80`.
- **Job en cours** : **T9e** — Fib ancré — `cursor/t9e-fib-anchor-a2fe`. **Cursor solo**.
- **T9** (structure / FVG / Fib) — T9a+T9b+T9c+T10a+T10b OK ; T9d en cours.
- ⚠️ **Dette ouverte (T0-MANAGE-c)** : le max drawdown des rulesets à `partial_tp` est **surestimé** d'un montant qui croît en vol². **Ne pas comparer** partiels vs non-partiels sur le DD avant correction.
- ⚠️ **Caveat historique SHORT** : positions SHORT **CLOSED avant** `b9f8421` (#51, mergedAt `2026-09-24T07:02:48Z`) ont un `realized` **surévalué de `entry_fee`**. Compte local Cursor : **CLOSED_SHORT = 0**. Script ponctuel : `scripts/recalc_short_entry_fee.py` — filtre par **horodatage exact**, journal `SHORT_FEE_RECALC` idempotent ; **ne pas lancer `--apply`** sans revue ; **pas de migration auto**.
- ⚠️ **Caveat migration #48** : backfill `initial_entry_fee = entry_fee` courant — **faux pour lots déjà partialisés avant migration**.
- ⚠️ **Dette max_exposure** : sémantiques **divergentes** Lab vs paper — Lab = `qty/initial_qty` (1 unité = 100 % capital ; `levier: true` si > 1) ; paper = `notional ≤ max_exposure × equity`. **Ne pas comparer** rulesets Lab `max_exposure>1` aux paper sans le flag `levier`.


---

## 2026-09-24 — UI-MARKET MERGÉE (#54) — squash `10631ef` — Cursor solo (Claude restreint)

- PR : https://github.com/samiriggui-code/IchiVol/pull/54 — **MERGÉE** squash
- **Vérifié** : `origin/main` tip = `10631ef`
- **Contexte** : Claude en mode restriction jusqu’à **12h10** ; utilisateur a demandé d’enchaîner seul (précédent T0-CALC #25).
- **CI avant merge** : `pytest (Postgres 16)` SUCCESS · `frontend (npm build)` SUCCESS · mergeable CLEAN
- **Auto-revue Cursor** : captures 01–07 + `ChartObject.layer` tests + build OK ; écarts volontaires documentés (pas de 5m, camap-tokens, Journal placeholder).
- **Suite** : T10a démarrée immédiatement après.

**Claude** : auditer #54 à 12h10 (post-merge).

---

## 2026-09-24 — T10a MERGÉE (#55) — squash `2e3ebc1` — registry status + source

- Branche : `cursor/t10a-registry-status-a2fe` @ `e49e602`
- PR : https://github.com/samiriggui-code/IchiVol/pull/55 (**draft**) — base `main` @ `10631ef` (#54)
- Statut : **MERGÉE** squash `2e3ebc1` (Cursor solo ; CI verte). **À auditer Claude 12h10.**
- **Vérifié** : `origin/main` tip = `2e3ebc1`
- Tests locaux : `test_t10a_registry_status` + `test_registry` + `test_indicators_route` + `test_ppo_best_cloud_lab` **OK**

### Objectif
Chaque `IndicatorDefinition` porte `status` / `source` / `confirmation_lag_bars` / `family` / `experiment_refs`. **Aucune sortie de calcul changée.**

### Statuts (justifiés par le code)

| id | status | Justification |
| --- | --- | --- |
| ichimoku | PRODUCTION | `agents/ichimoku_agent.py` → combiner + `evidence/context.py` |
| rvol | PRODUCTION | `agents/rvol_agent.py` → combiner + pipeline participation |
| atr | PRODUCTION | `decision/pipeline.py` (AtrState) + `screener/service.py` + `evidence/catalog.py` |
| adx | PRODUCTION | `decision/pipeline.py` (AdxState) + screener |
| cvd | PRODUCTION | `decision/pipeline.py` (CvdState) + screener |
| donchian | PRODUCTION | `decision/pipeline.py` (DonchianState) + screener |
| structure | PRODUCTION | `decision/pipeline.py` (StructureState) + screener ; lag = `swing_lookback` |
| location | PRODUCTION | `decision/pipeline.py` (LocationState) + screener |
| rsi / cmf / obv | CANDIDATE | `api/context.py` seulement (pas chemin décision) |
| ichimoku_analytics | EXPERIMENTAL | couche Lab |
| wyckoff | EXPERIMENTAL | README moteur : **non promu** — **Claude tranche** |
| ppo / best_cloud | REJECTED | `docs/REVUE-SIM-ET-COUTS-…§5` ; Lab toujours calculable |
| best_cloud source | external | Daveatt « BEST Cloud ALL MA » — TV open-source / House Rules ; URL script ; licence relevée 2026-09-24 |

### Garde-fou
`tests/indicators/test_t10a_registry_status.py` : ids string/AST dans les modules production → doivent être PRODUCTION ; ban import PPO/BEST Cloud conservé.

### Hors scope
T10b compteur d’essais ; T10c redondance ; fiches candidats.

**T10a mergée.** Rebase #53 T9b en cours.

---

## 2026-09-24 — ORDRE DU JOUR CONSOLIDÉ (rév. feuille de route 46)

Réf. Claude « IchiVol V3 — Feuille de route » rév. 46. Chantier principal **T9**. **T10** / **T11** uniquement là où prérequis de T9. Rien d’autre.

### État constaté

| Item | État |
| --- | --- |
| `main` | `985c4e5` — T9a #52 **MERGÉE** |
| #54 UI-MARKET | **brouillon** — Cursor **ne touche plus** ; Claude relit |
| #53 T9b | **brouillon figé** — hors ordre ; **pas de rebase** avant T10a |
| T10a | **après** merge #54 uniquement |

### Ordre (une sous-tranche à la fois)

1. **#54 UI-MARKET** — revue Claude → merge  
2. **T10a** — statut + source des features dans le registry  
3. **#53 T9b** — rebase sur T10a (CHoCH avec statut) → revue Claude → merge  
4. **T10b** — compteur d’essais + complexité (prérequis T9g)  
5. **T9c** impulsion → **T9d** FVG → **T9e** Fib ancré → **T9f** features Lab  
6. **T11a** — quality gate + provenance (avant T9g)  
7. **T10c** — redondance feature × feature  
8. **T9g** — ablation walk-forward OOS → décision  
9. Plus tard : T11b-c, T10d-e, T11d-f, T3e MTF  

Règles : une PR à la fois ; pas de merge sans Claude ; vérifier `main` après chaque merge ; handoff à jour ; suite PG sans régression + `npm run build` ; golden = ajouts seulement sauf décision explicite ; aucun lookahead / ordre broker / trading réel.

### Actions Cursor (2a–d) — FAIT

- **a)** Handoff corrigé : #52 mergée ; #54 / #53 brouillons ; ordre recopié ci-dessus.  
- **b)** #54 : **aucun commit code supplémentaire** (seul ce handoff docs).  
- **c)** #53 : reste brouillon ; **pas de rebase**.  
- **d)** **T10a non démarrée**.

### État exact #54 (pour revue Claude)

- Branche : `cursor/ui-market-tradingview-a2fe` @ `3d79eed`  
- PR : https://github.com/samiriggui-code/IchiVol/pull/54 (**draft**, OPEN)  
- Base : `main` @ `985c4e5`  
- Tip code UI : `96b1eff` ; tip handoff : `3d79eed` (docs only)  
- **`npm run build`** : **OK** (tsc + vite, 2026-09-24)  
- **`tests/chart_objects/test_chart_object_layer.py`** : **2 passed** (layer additive, id inchangé, rétrocompat source→layer)  
- Captures 01→07 : artifacts `/opt/cursor/artifacts/0{1..7}-*.png`  
- Front : chrome TradingView (barre 52 / volume dock / colonne 380 / bas 44 / tiroir mobile) ; camap-tokens  
- Moteur : `ChartObject.layer` (structure|fibonacci|fvg|breaks|claude|user_trades|backtest)  
- Écarts volontaires : pas de TF 5m ; Journal placeholder ; Analyse = BiasPanel + CTA paper  

<img alt="01 Desktop défaut" src="/opt/cursor/artifacts/01-desktop-default.png" />
<img alt="02 Desktop Calques + Backtest" src="/opt/cursor/artifacts/02-desktop-layers-backtest.png" />
<img alt="03 Mobile graphe" src="/opt/cursor/artifacts/03-mobile-chart.png" />
<img alt="04 Mobile tiroir Liste" src="/opt/cursor/artifacts/04-mobile-drawer-list.png" />
<img alt="05 Mobile tiroir Analyse" src="/opt/cursor/artifacts/05-mobile-drawer-analysis.png" />
<img alt="06 Mobile feuille Calques" src="/opt/cursor/artifacts/06-mobile-layers-sheet.png" />
<img alt="07 Mobile recherche" src="/opt/cursor/artifacts/07-mobile-search.png" />

### Note #53 (pré-examen, sans action)

- Golden : ajouts seulement (`choch_bullish`, `choch_bearish`, `break_quality`) — bon signe.  
- **`bos_bullish` non scindé BOS/CHoCH** : un « BOS haussier » en structure baissière reste compté BOS. À documenter dans la PR (compat golden) **ou** proposer scission en feature séparée **sans** modifier `bos_bullish` — au rebase post-T10a.  
- `recalc_short_entry_fee.py` embarqué : prouver idempotence (2× `--apply` = 1×) + couverture SHORT clôturés le jour du fix ; dry-run défaut ; sinon PR à part.

### Doutes Cursor avant T10a (après merge #54)

1. **Périmètre PRODUCTION** : scanner `decision/pipeline.py`, `combiner.py`, screener, paper, `evidence/context.py` — risque de faux positifs (import transitif vs lecture réelle d’un `id`). Critère strict : l’**id** string du registry apparaît dans le chemin décisionnel, pas seulement le module indicateur.  
2. **Wyckoff** : statut à proposer depuis le tableau de verdict README moteur — **Claude tranche** (Cursor ne décide pas seul).  
3. **BEST Cloud licence** : relever licence sur la page Daveatt au moment du commit (peut avoir changé) ; documenter URL + date.  
4. **`confirmation_lag_bars` structure** : aligner sur lookback **droit** du fractal causal T9a ; test de cohérence params ↔ champ — OK conceptuellement ; vérifier qu’aucun autre indicateur « provisional » ne nécessite un lag non nul dès T10a.  
5. **Garde-fou production** : généraliser `test_ppo_best_cloud_lab.py:242` — liste des ids productifs à construire par grep/AST, pas à la main, pour éviter la dérive.  
6. **OpenAPI golden** : ajouts seulement sur `GET /indicators` — OK ; s’assurer que `catalog()` / `describe()` ne cassent pas les clients Lab existants (champs optionnels avec défauts).

**Brief T10a** (rappel, démarrage **uniquement** post-merge #54) : branche `cursor/t10a-registry-status` ; `IndicatorDefinition` += status / source / confirmation_lag_bars / family / experiment_refs ; aucune sortie de calcul changée ; PPO+BEST Cloud → REJECTED (rév. sim §5) ; hors scope T10b/c.

**Cursor s’arrête ici.** Claude relit #54 dès que l’utilisateur écrit « Handoff ».


## 2026-09-24 — UI-MARKET EN COURS — Marché TradingView (PR draft)

- Branche : `cursor/ui-market-tradingview-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/54 (**draft**)
- Base : `main` @ `985c4e5` (#52)
- Statut : **ATTENTE REVUE CLAUDE** — Cursor **ne touche plus au code**. T9b brouillon figé (#53).

### Livré

1. Barre haute 52 px (symbole→recherche, prix, %, TF unique, Calques, Indicateurs, « i » source, Marquer un trade)
2. Graphe max height ; volume ~150 px desktop / ~120 px mobile, redimensionnable (persisté)
3. Watchlist triable Symbole / % / RVOL / Score / Contexte + filtres classe + « Contexte actif »
4. Desktop : colonne droite ~380 px repliable/redim. ; barre bas 44 px (Backtest / Marquer / Journal)
5. Desktop Backtest docké (~250 px) : stratégie, Tous/Gains/Pertes/Rejetés, 4 chiffres clés, liste trades
6. Mobile : tiroir 3 positions Liste / Analyse / Backtest (poignée au-dessus de la tabbar shell) ; feuilles Calques + Recherche
7. Moteur : `ChartObject.layer` (structure|fibonacci|fvg|breaks|claude|user_trades|backtest) — rétrocompat ; id inchangé
8. Pastilles calques + menu (FVG/Fib/Cassures vides jusqu’à T9) ; prefs globales

### Écarts volontaires vs captures 01–07

| # | Écart | Pourquoi |
| --- | --- | --- |
| 01 | Pas de TF **5m** | `INTERVALS` moteur = 15m/1h/4h/1d |
| 01–07 | Couleurs / polices **camap-tokens** | Contrainte IchiVol (pas maquette pixel) |
| 05 | Analyse = BiasPanel (pipeline Direction→Régime) + CTA paper | Réutilise le pipeline existant |
| Journal | Placeholder « bientôt » | Hors scope UI-MARKET |

### Captures (états 01→07)

<img alt="01 Desktop défaut" src="/opt/cursor/artifacts/01-desktop-default.png" />
<img alt="02 Desktop Calques + Backtest" src="/opt/cursor/artifacts/02-desktop-layers-backtest.png" />
<img alt="03 Mobile graphe" src="/opt/cursor/artifacts/03-mobile-chart.png" />
<img alt="04 Mobile tiroir Liste" src="/opt/cursor/artifacts/04-mobile-drawer-list.png" />
<img alt="05 Mobile tiroir Analyse" src="/opt/cursor/artifacts/05-mobile-drawer-analysis.png" />
<img alt="06 Mobile feuille Calques" src="/opt/cursor/artifacts/06-mobile-layers-sheet.png" />
<img alt="07 Mobile recherche" src="/opt/cursor/artifacts/07-mobile-search.png" />

**Cursor s’arrête ici** (entrée historique ; voir ORDRE DU JOUR CONSOLIDÉ en tête).


---

## 2026-09-24 — T9a MERGÉE (#52) — squash `985c4e5` — un seul détecteur de swings causal

- Branche merge : squash sur `main` → `985c4e5`
- PR : https://github.com/samiriggui-code/IchiVol/pull/52 — **MERGÉE** (validé Claude)
- **Vérifié** : `git rev-parse origin/main` == `985c4e5`

## 2026-09-24 — T9b EN COURS — CHoCH + break quality (rebase post-T10a)

- Branche : `cursor/t9b-choch-break-quality-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/53 (**draft**)
- Base cible : `main` @ `2e3ebc1` (#55 T10a)
- Statut : **REBASE EN COURS** — Cursor solo (Claude restreint). Pas de FVG / pas de changement décision.

### Livré (contenu #53)

1. `StructureEvent {type BOS|CHOCH, direction, level, bar, break_quality wick|close|confirmed, displacement_atr, rvol}`
2. CHoCH = cassure **contre** le biais ; BOS event = **dans le sens** du biais (MIXED/UNKNOWN → BOS)
3. `confirmed` = params `confirm_bars` **ou** `confirm_displacement_atr`
4. Feature `bos_bullish` / `bos_bearish` **bit-identiques** (golden) ; nouvelles : `choch_bullish` / `choch_bearish` / `break_quality`
5. Anti-lookahead confirmed + mèche ≠ clôture
6. `recalc_short_entry_fee.py` : timestamp `#51` mergedAt, journal `SHORT_FEE_RECALC`, test double `--apply`

### Décisions documentées (ordre du jour §0 / §4)

- **`bos_bullish` non scindé** : volontaire — compat golden + ablation Lab (`C_BOS`). Un break haussier en biais baissier reste `bos_bullish=True` au bit legacy ; le type riche est dans `StructureEvent.type=CHOCH`. Scission future = **nouvelle** feature, pas de mutation de `bos_bullish`.
- **Statut T10a** : indicateur `structure` reste **PRODUCTION** (pipeline lit bias/BOS). Champs Lab `choch_*` / `break_quality` = **EXPERIMENTAL** jusqu’à lecture pipeline (pas encore).
- Fee recalc : dry-run défaut ; idempotence via journal — **`--apply` non lancé**.



### Inventaire (3 détecteurs → 1 core)

| Avant | Après |
| --- | --- |
| `indicators/structure.py` boucle fractal inline | consomme `app.indicators.pivots.fractal_confirmed_at` |
| `fibonacci/context.py` `_fractal_pivots` | wrapper mince → `detect_causal_ohlc_fractals` |
| `structure/adapters/{mvpp,trendln,pytrendline}` boucles propres | confirment via `fractal_confirmed_at` / `detect_causal_extrema` |

Spécifique **conservé** (doc `structure/T9A_ADAPTERS.md`) : MVPP prix adaptatifs + qualité volume ; trendln clusters/diagonales ; pytrendline ancres provisoires ; structure HH/HL+BOS ; Fib impulse + ratios (defaults 2/2).

### Contrat causal

Pivot à `j` connu seulement à `i = j + right`. Test anti-lookahead : `tests/indicators/test_t9a_causal_pivots.py`. Goldens structure + fibonacci **inchangées** (parity inline / seed).

**(Entrée historique « EN COURS » corrigée → MERGÉE.)**

---

## 2026-09-24 — T0-FIX-SHORT-FEE MERGÉE (#51) — squash `b9f8421` — dette SHORT soldée

- Branche merge : squash sur `main` → `b9f8421`
- PR : https://github.com/samiriggui-code/IchiVol/pull/51 — **MERGÉE** (validé Claude)
- **Vérifié** : `git rev-parse origin/main` == `b9f8421` ; `git log` tip = fix SHORT fee.

### Effet

SHORT `realized` déduit désormais `entry_fee` (open + renforts) sur close / partiel / épuisement / preview — aligné cash.

### Historique pré-fix

Lots SHORT CLOSED **avant** ce squash : realized **surévalué de entry_fee**. Compte Cursor (DB locale) : **0** CLOSED SHORT. Script one-off (pas Alembic) : `scripts/recalc_short_entry_fee.py` (dry-run par défaut ; `--apply` si base avec historique > 0).

---

## 2026-09-24 — T0-MANAGE-f MERGÉ (#50) — squash `7a77424` — T0-MANAGE terminé

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe` — PR #50 — **MERGÉE** `7a77424`
- Suite PG Claude (re-revue) : **944 ok / 1 skip**, 0 régression
- Sondes LONG+SHORT : défaut sans max_exposure → 2 renforts ; niveau 1R figé (friction) ; risque après add = R0 ; ligne fermée = Σ fills ; LONG cash = réalisé
- **Vérifié post-merge** : `origin/main` tip = `7a77424`
- **T0-MANAGE a→f = terminé**

---

## 2026-09-24 — T0-MANAGE-f CORRECTIONS revue Claude #50

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/50 (**draft**)
- Statut : **SUPERSEDÉ** — corrigé puis **MERGÉ** `7a77424` (voir entrée ci-dessus).
- Suite PG Claude (passe 1) : **941 ok / 1 skip**, 0 régression ; conservation cash = réalisé OK.

### Corrections demandées (fait)

1. **Paper `max_exposure`** : plafond **notional / equity** (`notional_après_add ≤ max_exposure × equity`) via `cap_add_by_notional_equity` — défaut 1.0 **autorise** les ajouts tant que le notional reste ≤ equity. Lab garde `cap_add_by_exposure` (qty) ; résultats/expériences avec `max_exposure > 1` marqués **`levier: true`**.
2. **CLOSE** : `qty` / `entry_fee` / `notional` = `initial_*` + Σ `paper_reinforce_adds` (pas le seul open initial).
3. **Trigger `at_r_multiple`** : ancré sur `initial_entry` figé dans le blob (jamais `pos.entry_price` post-VWAP).
4. **Watcher** : simulation d'add avec le **même fill** que le broker (`apply_entry_friction`) ; plus de fallback silencieux sur prix brut (l'erreur remonte).

### Tests ajoutés

- Renfort effectif avec défaut paper (`max_exposure` omis)
- Ligne fermée = Σ fills (qty/fee/notional)
- 2 renforts successifs au niveau R figé (dip entre rising-edges)
- SHORT tighten + CLOSED totals
- Lab `is_leverage_exposure` / flag `levier`

---

## 2026-09-24 — T0-MANAGE-f EN COURS — renforcement paper (PR draft)

- Branche : `cursor/t0-manage-f-reinforce-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/50 (**draft**)
- Base : `main` @ `389fc40` (#49 squash)
- Statut : **SUPERSEDÉ** — voir MERGÉ ci-dessus.

### Prérequis tranche (livrés)

1. **`max_exposure` défaut 1.0** — Lab qty-unit ; paper **notional/equity** (corrigé revue #50)
2. **Contrôle cash/marge** dans `reinforce_add_capital_position` — refuse (`None`) si `notional+fee > cash` ; jamais de partial-fill silencieux
3. Gate `user_confirmed` + `protection_reinforce` ; exclusif vs `protection_partial_tp`
4. Trigger paper : `at_r_multiple` sur **entrée initiale figée** ; rising-edge latch `prev_match`
5. Priorité manage : stop > partials > target > reinforce > trail (même ordre Lab)
6. Migration `paper_reinforce_adds` ; journal `REINFORCE`

### Tests (Cursor)

- Lab `test_t0_manage_e_reinforce` + `tests/paper/test_protection.py` (dont reinforce) : **verts** sur ce HEAD
- PG local : migration `e1f2a3b4c5d6` appliquée ; tests reinforce paper OK

### Attente Claude

1. Relire le diff PR (corrections)
2. Suite Postgres complète
3. Valider notional/equity + CLOSE totals + R figé + fill friction
4. **Pas de merge** / pas de T9 sans ok explicite

**Cursor s’arrête ici.**

---

## 2026-09-24 — T0-MANAGE-e MERGÉ (#49) — squash `389fc40`

- Branche : `cursor/t0-manage-e-reinforce-lab-a2fe` — PR #49 — **MERGÉE** `389fc40` (= tip validé adff686)
- Suite PG Claude : **935 ok / 1 skip**, 0 régression
- Sondes : tighten_stop en profit → R0 ; risque signé ; rejet combo partial+reinforce ; fuzz 300 seeds / 135 adds jamais > R0 ; Σnet=Σbars 3,5e-16
- **Vérifié post-merge** : `origin/main` tip = `389fc40`

---

## 2026-09-24 — T0-MANAGE-e CORRECTIONS revue Claude #49

- Branche : `cursor/t0-manage-e-reinforce-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/49 (**draft**)
- Statut : **SUPERSEDÉ** — corrigé puis **MERGÉ** `389fc40` (voir entrée ci-dessus).
- Process : #48 squash-mergé sur `main` (`a941539`) ; #49 rebasé.

### Corrections demandées (fait)

1. Défaut `risk_policy` → **`tighten_stop`** (`reduce_qty` reste option)
2. `open_risk` **signé** : LONG `max(0, avg−stop)×qty` ; SHORT `max(0, stop−avg)×qty`
3. Parse **rejette** `partial_tp` + `reinforce` ensemble (message clair)
4. Tests : tighten_stop en profit ; rejet combo ; open_risk stop au-delà du prix moyen ; reduce_qty bloque add au-dessus du avg (structurel)

### Non-bloquant

- `max_exposure` (défaut 1.0) — dette avant comparaison rulesets / obligatoire paper → **implémenté dans #49 + T0-MANAGE-f** ; dette documentation / comparaisons **conservée**

---

## 2026-09-24 — T0-MANAGE-d MERGÉ (#48) — squash `a941539`

- Branche : `cursor/t0-manage-d-partial-tp-paper-a2fe` — PR #48 — **MERGÉE** `a941539`
- Suite PG Claude : **918 ok / 1 skip** (re-revue), puis baseline post-merge **928 ok / 1 skip**
- Sondes : financement à l'épuisement ; `entry_fee` restauré ; cash=réalisé LONG ; `pnl_pct` VWAP ; épuisement+target même barre → une clôture
- Caveat backfill `initial_entry_fee` (lots déjà partialisés avant migration)

---

## 2026-09-23 — T0-MANAGE-c MERGÉ (#47) — revue Claude en local

- Branche : `cursor/t0-manage-c-partial-tp-lab-a2fe` — PR #47 — **MERGÉE** `6116850`

### Les 3 corrections demandées sont en place

1. `Trade.log_return = sign × log(VWAP/entry)` via `partial_tp.log_return_from_vwap` — plus de somme pondérée de logs. `exit_price` = VWAP : les deux champs restent mutuellement cohérents pour T4a et `compute_metrics`.
2. Priorité `stop > partiels (R croissant) > target > signal` — commentée dans le code, conservatisme du stop préservé. `mfe_r` n'utilise que le high/low de la barre courante (pas de lookahead). `take = min(step.fraction, remaining)` empêche de sur-clôturer.
3. Frais et taille : chaque fill est décomposé en sous-trade de fraction `f` de l'entrée jusqu'à sa propre sortie, ce qui fait émerger naturellement **et** la pondération de taille après chaque partiel **et** les frais corrects (Σ frais d'entrée = `cost`, Σ frais de sortie = `cost`).

### Invariant — vérifié indépendamment (pas seulement via le test de Cursor)

Sonde maison sur 9 combinaisons (3 configs de paliers × volatilités 2/5/10 %, 12 seeds chacune) :

**pire écart `Σ net_log_return(trades)` vs `Σ bar_returns + eod_return` = 4,44e-16** — soit ~7 ordres de grandeur sous le seuil de 1e-9 exigé. L'invariant T0-METRICS-2 tient réellement.

### Le résidu de Jensen : accepté, mais mesuré — et il n'est pas borné

La tension signalée par Cursor est **réelle**, pas un artefact : un P&L à exposition variable ne peut pas être représenté exactement comme une somme de log-returns pondérés (les logs ne s'additionnent que pour une taille constante). Le total correct est `log(VWAP/entry)` ; le chemin barre-par-barre somme à `Σ f·log`. L'écart est soaké sur la barre de sortie finale.

C'est défendable : le **total est exact** (donc `metrics.total_return`, qui est une somme, est juste), seule la **répartition intra-trade** est approximée. Et l'erreur va dans le sens conservateur (equity intra-trade lue trop basse, donc DD surestimé, jamais sous-estimé).

**Mais la magnitude n'avait pas été chiffrée.** Mesurée :

| volatilité/barre | résidu par trade |
|---|---|
| 2 % | 5–8 bps |
| 5 % | 26–47 bps |
| 10 % | **115–224 bps** |

Il croît en vol², sans borne. À 10 % de volatilité par barre — banal en crypto — c'est jusqu'à **2,24 % déplacés sur une seule barre**.

**Conséquence concrète à ne pas oublier** : un ruleset sans partiels a un résidu **nul**. Comparer son drawdown à celui d'un ruleset avec partiels, c'est comparer une mesure exacte à une mesure biaisée à la hausse. Or le Strategy Lab sert précisément à ce type de comparaison, et l'argument produit du PIPELINE repose justement sur le drawdown (30,1 % → 5,1 %). Les partiels seraient donc pénalisés sur le DD par un artefact comptable, pas par leur comportement réel.

**Pas bloquant ici** (Lab only, rien de live ne consomme ça, totaux exacts), mais à corriger avant tout arbitrage partiels vs non-partiels sur le drawdown. Piste la moins invasive : répartir le résidu au prorata sur les barres de la dernière jambe au lieu de le concentrer sur une seule — le total reste exact et le pic disparaît, sans toucher à la propriété de troncature open→open de #24.

### Tests (local, Postgres)

- `tests/strategy_lab` : 108/108 OK (golden `ruleset_backtest_golden.json` inchangé)
- `tests/api tests/paper tests/backtest` : 3 échecs, tous préexistants et connus — aucun nouveau vs `main`

---

## 2026-09-23 — T0-MANAGE-c EN COURS — partial TP Strategy Lab (backtest only)

- Branche : `cursor/t0-manage-c-partial-tp-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/47 (**draft**)
- Statut : **ATTENTE CLAUDE** — CI à confirmer ; **ne pas merger** ; **pas de T0-MANAGE-d**.

### Livré

1. `app/strategy_lab/partial_tp.py` — `PartialTpStep` / `PartialExit` + niveaux R / VWAP / `log_return_from_vwap`
2. `ExitSpec.partial_tp` — parse strict (#45+) : `]0,1[`, somme ≤ 1, R strictement croissants, chaque R `< target_atr/stop_atr`, `bool`/clés inconnues rejetés
3. `ruleset_backtest.simulate_ruleset_trades` — priorité **stop > partials > target > signal > trail** ; `Trade` agrégé via VWAP ; `RulesetTradeDetail.partial_exits`
4. `_apply_fills_hold_returns` — chemin taille-pondéré + frais `cost×fraction` par fill ; **résidu de Jensen** (Σ f·log vs log(VWAP)) absorbé sur la dernière barre de sortie pour tenir T0-METRICS-2
5. Tests `test_t0_manage_c_partial_tp.py` — parse, VWAP≠weighted-log, stop>partial, partial>target même barre, **invariant Σ net == Σ bars** avec partiels, golden inchangé

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

### Note revue (réconciliation corr. 1 ↔ 3)

`Trade.log_return = sign·log(VWAP/entry)` (corr. Claude #1). Le chemin barre taille-pondéré somme naturellement Σ f·log (Jensen). Le delta est soaké sur la barre de sortie finale — invariant 1e-9 tenu ; les barres intermédiaires restent size-weighted.

---

## 2026-09-23 — T0-MANAGE-b MERGÉ (#46) — revue Claude en local

- Branche : `cursor/t0-manage-b-trail-paper-a2fe` — PR #46 — **MERGÉE** `93003a1`

### Vérifié (diff réel, pas le résumé)

1. **Chemin de calcul unique respecté** — `protection.py` appelle `stop_trail.update_trailing_stop`, aucune réimplémentation parallèle de la logique de trail. C'était le point de vigilance n°1 du brief.
2. **No-lookahead** — même contrat qu'en Lab : check de sortie au stop courant *puis* ratchet ; le nouveau niveau ne s'applique qu'à la barre suivante.
3. **Watermark** — piège correctement évité : sur le chemin trail le watermark avance **toujours** (`if trail_cfg is not None or …`). Sans ça, un scan ultérieur rejouerait des barres déjà passées contre un stop déjà remonté et **inventerait de faux stop hits**. C'est le bug non évident de cette tranche, il est traité et documenté dans le code.
4. **Gate** — `trail_cfg = None if legacy else …` + `source == user_confirmed` + config `protection_trail` explicite : ni les lots `auto_watchlist`, ni les positions legacy, ni l'historique reconstruit ne peuvent être trailés. Test dédié pour chacun.
5. **Ratchet doublement garanti** — `update_trailing_stop` (max/min) *et* garde défensive dans `_persist_trail_stop` avant écriture DB.
6. **Aucun test affaibli** — les modifications de tests existants sont des corrections d'**isolation** (`assert [r["status"] for r in rep] == ["closed"]` → lookup par `position.id`), pas des assouplissements : la même exigence sémantique est conservée, seule la portée est correctement limitée à la position du test. Effet de bord bénéfique : les 4 faux échecs `test_protection.py` sur base non vierge disparaissent (7 → 3 échecs sur la suite large en local).

### Tests (local, Postgres)

- `tests/paper/test_protection.py` : 16/16 OK
- `tests/paper tests/api tests/strategy_lab` : 3 échecs, tous préexistants et connus (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_overview_marks_budget` timing) — aucun nouveau vs `main`.

### Réserves non bloquantes (à traiter plus tard, pas de retouche demandée maintenant)

1. **`atr_ref` par défaut = distance au stop, pas l'ATR.** Dans `resolve_paper_trail`, quand `atr_ref` n'est pas fourni : `atr_ref = abs(entry_price - initial_stop)`. Or le stop initial vaut `stop_atr × ATR`. Avec `stop_atr = 2.0`, un `atr_trail_mult: 1.5` traîne donc en réalité à **3× ATR**, pas 1,5×. Pas dangereux (stop plus large = jamais de clôture prématurée) mais l'intention exprimée n'est pas celle appliquée. À résoudre en passant l'ATR réel, ou en documentant explicitement que le multiplicateur est relatif au risque initial et non à l'ATR.
2. **Parse plus permissif qu'en Lab.** `_parse_trail_raw` n'écarte pas `bool` (`breakeven_at_r: true` → `1.0`) et ignore les clés inconnues, alors que `_parse_trail_spec` (Lab, #45) rejette les deux. Chemin interne, risque faible, mais deux portes d'entrée pour la même config devraient valider pareil.

---

## 2026-09-23 — T0-MANAGE-b EN COURS — trail / breakeven paper (protection)

- Branche : `cursor/t0-manage-b-trail-paper-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/46 (**draft**)
- Statut : **ATTENTE CLAUDE** — CI à confirmer ; **ne pas merger** ; **pas de T0-MANAGE-c**.

### Livré

1. `app/paper/protection_trail.py` — gate `user_confirmed` + `protection_trail` explicite (`entry_signal` > `strategy_profile`) ; `freeze_trail_anchor` pour figer `initial_stop` / ATR après le 1er cycle
2. `app/paper/protection.py` — `find_breach_with_trail` : check exit puis `stop_trail.update_trailing_stop` (même chemin Lab) ; watermark toujours avancé sur le chemin trail (pas de re-scan des barres passées contre un stop déjà ratcheté) ; journal `PROTECTION_TRAIL_UPDATED` ; legacy / historique : jamais de trail sur reconstruction
3. Tests `tests/paper/test_protection.py` — gate resolve ; BE next-bar only ; ratchet ATR ; cycle DB portfolio trail → BE puis close ; `auto_watchlist` ignore le trail portefeuille ; sans config = inchangé
4. Assertions DB scopées par `position.id` (base locale non vierge avec lots ouverts type NDX)

### Non-fait

- Pas de prise de profit partielle (T0-MANAGE-c/d)
- Pas de renforcement (T0-MANAGE-e/f)
- Trail non activé par défaut ; pas d’UI dédiée

### Tests locaux (Cursor)

- `pytest tests/paper/test_protection.py tests/strategy_lab/test_t0_manage_a_trail.py` : 24/24 OK (venv engine)

---

## 2026-09-23 — T0-MANAGE-a MERGÉ (#45) — revue Claude en local

- Branche : `cursor/t0-manage-a-trail-lab-a2fe` — PR https://github.com/samiriggui-code/IchiVol/pull/45 — **MERGÉE** `e6118c7`
- **Revue** : diff réel relu (`stop_trail.py`, `ruleset.py`, `ruleset_backtest.py`) — confirmé aucun lookahead : le stop vérifié à la barre `j` vient de la mise à jour calculée à la barre `j-1` (jamais la barre courante en avance) ; ratchet appliqué via `max`/`min` strict (LONG ne recule jamais à la baisse, SHORT jamais à la hausse) ; breakeven couvre bien le round-trip de frais ; validation de parse stricte (clés inconnues rejetées, `bool` rejeté comme nombre, valeurs ≤ 0 rejetées).
- `pytest tests/strategy_lab/test_t0_manage_a_trail.py tests/strategy_lab/test_ruleset_backtest.py tests/strategy_lab/test_ruleset_backtest_golden.py tests/strategy_lab/test_ruleset.py` : 33/33 OK
- `pytest tests/strategy_lab tests/api` (suite large) : mêmes 2 échecs préexistants liés aux données réelles de `ichivol_engine_dev` (pas de régression, cf. note baseline en haut de ce fichier)
- Golden `ruleset_backtest_golden.json` inchangé (trail absent partout dans le catalogue actuel) — confirmé.
- **Prochain job : T0-MANAGE-b** (paper) — voir spec ci-dessous.

---

## 2026-09-23 — T0-MANAGE-a EN COURS — trail / breakeven Strategy Lab (backtest only)

- Branche : `cursor/t0-manage-a-trail-lab-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/45 (**draft**)
- Statut : **ATTENTE CLAUDE** — CI à confirmer ; **ne pas merger** ; **pas de T0-MANAGE-b**.

### Livré

1. `app/strategy_lab/stop_trail.py` — `TrailSpec` + `update_trailing_stop` / ratchet / breakeven (frais RT) / ATR trail (helpers purs, prêts pour paper T0-MANAGE-b)
2. `ExitSpec.trail` optionnel — parse / `to_dict` ; `breakeven_at_r` et/ou `atr_trail_mult` (> 0)
3. `ruleset_backtest.simulate_ruleset_trades` — stop initial figé à l’entrée ; **recalcul bar-par-bar après** checks stop/target/signal (nouveau niveau = barre suivante) ; jamais de recul
4. Priorité intra-bar inchangée : stop > target > signal > max_hold/eod
5. Tests `test_t0_manage_a_trail.py` — property ratchet (200), breakeven exact à 1R, ATR trail, parse roundtrip, pas de trail = comportement fixe
6. Golden `ruleset_backtest_golden.json` — **inchangé** (trail absent)

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

**Cursor s’arrête ici** jusqu’à revue Claude (diff réel + suite Postgres complète).

---

## 2026-09-23 — T0-MANAGE — découpage détaillé (prêt pour Cursor)

Spec originale (une phrase, doc Feuille de route) : *stop suiveur ou remonté à l'entrée, prise de profit partielle, renforcement — le risque total ne dépasse jamais le risque initial. Chaque outil testé d'abord en Strategy Lab (DSL + backtest net), activable en paper seulement après.*

Rien de ça n'existe en code aujourd'hui. Découpage en 6 sous-tranches, **une PR par sous-tranche**, ordre imposé (chaque paire *Lab d'abord, paper ensuite* ; ne pas sauter à la reinforcement avant que stop/TP partiel soient validés) :

### T0-MANAGE-a — Stop suiveur / breakeven — Strategy Lab (backtest only)

- Étendre `ExitSpec` (`app/strategy_lab/ruleset.py`) : nouveau champ optionnel, ex. `trail: TrailSpec | None` avec soit `breakeven_at_r: float` (remonte le stop au prix d'entrée + frais une fois `r_multiple` atteint), soit `atr_trail_mult: float` (stop = `close ± atr_trail_mult * ATR`, ne se resserre jamais côté perte — ratchet unidirectionnel).
- `app/strategy_lab/ruleset_backtest.py` : aujourd'hui `_levels()` calcule stop/target **une fois** à l'entrée (ligne ~228, boucle « une position à la fois »). Il faut recalculer le stop **bar par bar après l'entrée**, sans lookahead (le nouveau stop d'un bar N ne peut utiliser que high/low/close ≤ bar N), et ne jamais le reculer par rapport à sa valeur précédente.
- Priorité intra-bar existante (stop > target > signal > max_hold/eod) inchangée ; seul le niveau du stop devient mobile.
- Tests : ratchet ne recule jamais (property test, N séquences aléatoires) ; breakeven se déclenche exactement à `r_multiple` atteint, pas avant ; golden `ruleset_backtest_golden.json` **inchangé** pour les rulesets existants (trail absent = comportement actuel).
- **Non-fait** : rien en paper ; pas de prise de profit partielle ; pas de renforcement.

### T0-MANAGE-b — Stop suiveur / breakeven — paper (après validation Lab)

- Ne démarre qu'après revue Claude de T0-MANAGE-a.
- Brancher sur `app/paper/protection.py` (déjà un watcher bar-par-bar indépendant des signaux, avec le même principe no-lookahead décrit dans son docstring) — appliquer la même logique de stop mobile validée en backtest.
- Gate explicite : activable par position ou par portefeuille (pas par défaut sur tout l'historique) ; seulement `user_confirmed` dans un premier temps (comme T0-NOTIF).
- Invariant : le stop ne recule jamais ; jamais d'ouverture/fermeture hors de la logique protection existante.
- Tests : reprendre les fixtures de `tests/paper/test_protection.py` + cas trail-spécifiques.

### T0-MANAGE-c — Prise de profit partielle — Strategy Lab (backtest only)

- `PaperPosition` / `Trade` sont aujourd'hui **single-fill** (un seul `qty`, un seul `exit_price`). Une prise de profit partielle est un changement de modèle, pas juste une règle DSL.
- DSL : nouveau champ `partial_tp: list[{r_multiple: float, fraction: float}]` sur `ExitSpec` (ex. `[{r_multiple: 1.0, fraction: 0.5}]` = clôturer 50 % à 1R).
- Backtest : `Trade` doit pouvoir représenter plusieurs fills de sortie (ou une liste de `PartialExit`) ; PnL net = somme pondérée ; `r_multiple` du reliquat recalculé sur la qty restante.
- Tests : invariant Σ (qty partielle × pnl) + (qty restante × pnl finale) == pnl total sur qty pleine ; golden inchangé si `partial_tp` absent.
- **Non-fait** : paper ; renforcement.

### T0-MANAGE-d — Prise de profit partielle — paper (après validation Lab)

- Étendre `PaperPosition` (nouvelle table `paper_partial_exits` plutôt que muter les colonnes existantes — garder `paper_positions` single-row pour la position "vivante", journaliser chaque prise partielle comme une ligne, pattern proche de `ledger_transactions`/`ledger_legs`).
- `qty` de la position OPEN diminue à chaque prise partielle ; `realized_pnl` cumule ; la position reste `OPEN` tant qu'il reste de la qty.
- UI : historique des prises partielles sur la fiche position (Paper).
- Tests : qty ne peut jamais devenir négative ; fermeture finale (stop/target/signal) solde le reliquat exact.

### T0-MANAGE-e — Renforcement (pyramiding) — Strategy Lab (backtest only)

- DSL : condition de déclenchement du renforcement (`ConditionGroup` réutilisé) + règle de sizing de l'ajout.
- **Invariant non négociable** (c'est la seule contrainte donnée dans la spec originale) : après renforcement, le risque total ouvert (distance au stop × qty totale, prix moyen pondéré) **ne doit jamais dépasser** le risque initial de la position avant renforcement. Si l'ajout au sizing normal violerait ça, soit la qty ajoutée est réduite, soit le stop est resserré pour compenser — à trancher en revue avant merge (Cursor propose les deux options, Claude choisit).
- Tests : construire des cas où renforcement + stop initial dépasseraient le risque → doit être bloqué/réduit, jamais silencieusement ignoré.
- **Non-fait** : paper.

### T0-MANAGE-f — Renforcement — paper (après validation Lab)

- Brancher sur `app/paper/broker.py` (ordre d'ajout) avec la même vérification d'invariant *avant* exécution — refuser l'ordre plutôt que l'exécuter hors invariant.
- **Prérequis tranche** : `max_exposure` (défaut **1.0**) + contrôle cash/marge disponible **avant chaque ajout**.
- Isolation : ne touche pas aux positions `auto_watchlist` sans confirmation utilisateur explicite (même logique que T2c pour les user trade points).

### Après T0-MANAGE — T9 (roadmap, ne pas démarrer avant)

- **T9** — structure / FVG / Fib (nouvelle tranche feuille de route). **Bloquée** jusqu'à clôture complète de T0-MANAGE (f inclus, revue Claude + merge).

### Grille commune (rappel garde-fous projet, s'applique aux 6 sous-tranches)

- Aucun lookahead : un stop mobile au bar N ne connaît que les bars ≤ N.
- Un seul chemin de calcul : le backtest (Lab) et le paper doivent appeler la **même** fonction de calcul de stop mobile / partial fill / invariant de risque — pas deux implémentations qui divergent.
- Déterministe, testé avant merge, revue Claude explicite avant chaque merge (rappel incident 18 PR).

### Attente Claude

Cursor attaque **T0-MANAGE-a seul**, PR draft, CI verte, handoff mis à jour, **s'arrête** avant merge et avant T0-MANAGE-b.

---

## 2026-09-23 — T0-NOTIF MERGÉ (#44) + UI Lab Research MERGÉ (#43) — revue Claude en local

- **Contexte** : reprise du canal Cursor ↔ Claude **en local** (Laragon + PostgreSQL 16, même `ichivol_engine_dev` que la review cloud) après clonage à jour de `main` (`9ead9e8`, 205 commits, roadmap V3 T0→T7 + EIL + Researcher).
- **Revue** : diff des deux PR relu, migrations alembic + Prisma appliquées, suites de tests + builds relancés localement sur chaque branche avant merge.

### #43 — UI Lab Research

- `pytest tests/api/test_strategy_lab_research_routes.py` : 5/5 OK
- `pytest tests/api tests/paper` (engine complet) : mêmes échecs préexistants que sur `main` (données réelles en base, pas de régression — voir note ci-dessous)
- `npm run build` (frontend) : OK
- **Merge** : squash, `db5261a`, branche supprimée

### #44 — T0-NOTIF

- `pytest tests/paper/test_scenarios.py` : 10/10 OK
- Migration Prisma `20260923170000_t0_notif_push` appliquée sur `ichivol_dev`
- `npm test` (server, incl. `positionWatch.test.ts` — dédup, proximité, grep "aucun open/close paper") : 27/27 OK
- `npm run build` (server + frontend) : OK
- Invariant informative-only confirmé (grep source : pas d'appel open/close paper)
- **Merge** : squash après résolution conflit doc avec #43, branche supprimée

### Note — échecs pytest engine non liés aux PR (déjà présents sur `main` avant ces deux merges)

`ichivol_engine_dev` en local est la base **de travail réelle** (pas une base de test jetable comme le conteneur Postgres éphémère de la CI GitHub Actions) — elle contient de l'historique de positions réel. 7 tests supposant une base vierge échouent pour cette raison (`test_account_identity_after_refresh`, `test_open_paper_position_reports_no_atr_stop_honestly`, `test_protection.py` ×4, `test_overview_marks_budget` timing) — **aucun n'est une régression de #43/#44**, vérifié en comparant à l'état de `main` avant ces merges. Un vrai bug de portabilité Windows a aussi été trouvé et corrigé au passage : `tests/indicators/test_registry_ratchet.py` comparait des chemins avec `/` alors que `Path.relative_to` renvoie du `\` sous Windows (`str(...)` → `.as_posix()`).

---

## 2026-09-23 — T0-NOTIF — alertes push téléphone — PRÊT REVUE CLAUDE

- Branche : `cursor/t0-notif-push-a2fe`
- PR : (draft — lien après create)
- Base : `main` (ne touche **pas** T0-CALC / EIL / T4b-d / T5a-b / T6 / T7 / T3d / Researcher)

### Objectif

Alerte **informative** sur téléphone (Web Push VAPID / PWA) quand une position paper OUVERTE approche objectif/stop, accélère (RVOL + BOS moteur), ou flip Ichimoku. **Jamais d’ordre.**

### Livré

1. **Infra push** : `PushSubscription` Prisma + migration ; `web-push` ; `sendPushToUser` / `sendPushRaw` (never throw, 410/404 → delete) ; `public/sw.js` + `manifest.webmanifest` ; env `VAPID_*` (jamais commités)
2. **Kinds** (ajoutés) : `position_target_near` | `position_stop_near` | `position_accel` | `position_direction_flip`
3. **Watcher séparé** `positionWatch.ts` (~60s) — **ne modifie pas** `watch.ts` ; filtre `user_confirmed` OPEN + `user_id`
4. **Proximité** : `scenarios.level_remaining_frac` / `compute_level_proximity` + `GET /paper/positions/{id}/proximity` (même géométrie que T0-CALC)
5. **Accel** : RVOL ≥ `rvolConfirm` settings **et** `bos_confirms_direction` du pipeline (pas recalcul local)
6. **Dédup** : cooldown + resserrement de bande (20→10→5) / `stateKey`
7. **API** : `GET push-vapid-public`, `POST/DELETE push-subscribe` ; prefs `Setting.pushAlertPrefs`
8. **Front** : Settings « Alertes push » ; deep link `/app/paper?position=&symbol=` ; cloche → Paper
9. **Tests** : server dedup / proximity parity / push soft-fail / grep no-order ; engine proximity unit ; OpenAPI goldens (proximity)

### Flux téléphone (si non testable ici)

1. Déployer avec `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`
2. Android Chrome ou iOS 16.4+ PWA (« Ajouter à l’écran d’accueil »)
3. Settings → Activer les alertes (permission) → Enregistrer prefs
4. Position OPEN near target → notif système + ligne cloche ; tap → fiche Paper

### Invariants

- Aucun `open`/`close` paper dans `positionWatch.ts`
- Push échoue → notif in-app quand même créée
- Autre user : positions filtrées par `user_id` ; notifs scoped `userId`

### Non-faits

Stop suiveur / renforcement (T0-MANAGE) ; actions rapides « clore en un tap » ; UI Lab #43 (branche séparée).

### Attente Claude

1. Relire le diff PR
2. Suite Postgres complète sur ce HEAD
3. Valider informative-only + dédup + proximité = scenarios
4. Marche à suivre : merge / retouches

**Cursor s’arrête ici** — pas de merge, pas de job suivant sans revue explicite.

---

## 2026-09-23 — UI Lab Research — PRÊT REVUE CLAUDE (#43)

- Branche : `cursor/lab-ui-research-t5-t7-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/43 — **draft**
- HEAD : `d4deb50` (code `01e79b0` + docs ; CI verte sur `a5a13a1` = même code)
- Base : `main` @ `9ead9e8` (post Researcher #41/#42)

### Statut CI (Engine CI)

- **VERTE** (HEAD `a5a13a1`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35887098403
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Contexte Vague

Après T1–T7 + T3d + Researcher (tous mergés), suite optionnelle = **UI Lab** (exposé) ou **T3e MTF** (FeatureBar mono-TF — trop gros). Cursor a livré **UI Lab Research** ; T3e **non démarré**.

### Livré (observation-only)

1. **HTTP** `app/api/strategy_lab_research.py` (monté après `strategy_lab_wf` dans `routes.py`) :
   - `GET /api/engine/strategy-lab/family-weight-profiles`
   - `GET /api/engine/strategy-lab/family-weights/compare`
   - `GET /api/engine/strategy-lab/family-weights/study`
   - `POST /api/engine/strategy-lab/audit-report`
   - `POST /api/engine/strategy-lab/monte-carlo`
   - `POST /api/engine/strategy-lab/propose-experiment-plan`
2. **UI** onglet **Research** sur Strategy Lab (`LabResearchPanel.tsx` + `labResearch.ts`) — catalogue poids, compare, étude, AuditReport, plan Researcher, Monte Carlo
3. Goldens OpenAPI + `route_order` refresh ; `tests/api/test_strategy_lab_research_routes.py` (5 tests)
4. CDC checkbox UI Lab Research (ouverte tant que non mergée)

### Invariants respectés

- EVENT ≠ SIGNAL inchangé
- Pas de mutation score live / gate / combiner / confidence
- Hypothèses Audit + plan Researcher restent `status=proposed`
- Monte Carlo / family weights = research only (disclaimers conservés)
- Pas d’auto-run des steps Researcher ; pas d’écriture Perf DB depuis propose

### Fichiers (diff vs main)

| Zone | Fichiers |
|------|----------|
| Engine API | `strategy_lab_research.py`, `routes.py` |
| Tests | `test_strategy_lab_research_routes.py`, openapi + route_order goldens |
| Front | `LabResearchPanel.tsx`, `labResearch.ts`, `BacktestsPage.tsx` |
| Docs | `HANDOFF-CURSOR-V3.md`, `CAHIER-DES-CHARGES.md` |

### Non-faits (hors scope #43)

- **T3e MTF DSL** (FeatureBar multi-TF)
- Chat NL / éditeur conversationnel T3d
- Auto-run plan Researcher / auto-apply catalog
- Poids familles en live score
- Rename fichier `BacktestsPage.tsx` → `StrategyLabPage`

### Attente Claude

1. Relire le diff PR #43
2. Suite Postgres complète sur ce HEAD (baseline 0 échec post T0-CI)
3. Valider observation-only (pas de dérive gate/score)
4. Marche à suivre : **merge** / retouches / enchaîner T3e

**Cursor s’arrête ici** jusqu’à la revue Claude.

---

## 2026-09-23 — RESEARCHER MERGÉ (#41) — propose experiment plan

- Branche : `cursor/researcher-propose-experiment-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/41 — **MERGÉE** `64bba88`
- Statut : CI verte ; merge Cursor.

### Livré

1. `app/researcher/` — `propose_experiment_plan(AuditReport)` → steps Lab (`proposed`)
2. Agent `propose_experiment_plan` — jamais auto-run / Perf DB

### Non-faits

Exécution auto des steps ; UI ; T3e MTF.

---

## 2026-09-23 — T3d MERGÉ (#39) — propose ruleset edit

- Branche : `cursor/t3d-ruleset-propose-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/39 — **MERGÉE** `80508c1`
- Statut : CI verte ; merge Cursor.

### Livré

1. `propose_edit.py` — patch ops → `parse_ruleset` ; status toujours `proposed`
2. Catalogue conditions GET `/rulesets` + `list_condition_catalog`
3. `POST /ruleset/propose` + agent `propose_ruleset_edit`
4. OpenAPI golden refresh

### Non-faits

Chat UI ; LLM moteur ; T3e MTF ; auto-apply catalog.

---

## 2026-09-23 — T7 MERGÉ (#37) — Monte Carlo / risk of ruin → V3 T1–T7 DONE

- Branche : `cursor/t7-monte-carlo-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/37 — **MERGÉE** `dacbfe0`
- Statut : CI verte ; merge Cursor. **Roadmap V3 T1→T7 close.**

### Livré

1. `app/risk/monte_carlo.py` — bootstrap net trade returns → equity paths
2. `risk_of_ruin` (equity ≤ ruin_floor) ; percentiles final equity / max DD
3. Gate `min_trades` (défaut 20) → `sufficient=false` sinon
4. Agent `run_monte_carlo`

### Hors roadmap T (ouverts plus tard)

T3d chat NL / éditeur conversationnel ; T3e MTF DSL ; Researcher loop (auto Experiment) ; UI Lab pour T5–T7 ; poids en live score.

---

## 2026-09-23 — T6 MERGÉ (#36) — AuditReport

- Branche : `cursor/t6-auditor-report-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/36 — **MERGÉE** `a2591bf`
- Statut : CI verte ; merge Cursor.

### Livré

1. `app/auditor/` — `AuditReport` + `AuditHypothesis` (`proposed` only)
2. `build_audit_report_from_trade` depuis `RulesetTradeDetail` (WHY + net)
3. Agent `build_audit_report`

### Non-faits

Auto-apply hypothèses ; Researcher loop ; UI.

---

## 2026-09-23 — T5b MERGÉ (#35) — profils poids backtestables

- Branche : `cursor/t5b-weight-profiles-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/35 — **MERGÉE** `bacd7bf`
- Statut : CI verte ; merge Cursor.

### Livré

1. Catalogue `FamilyWeightProfile` (balanced / direction_heavy / participation_heavy / structure_heavy)
2. `compare_family_weight_profiles(pipeline)` — table observation
3. `run_family_weights_study` — BUY/SELL pipeline bars × forward log returns (causal)
4. Agent : `list_family_weight_profiles`, `compare_family_weights`, `run_family_weights_study`

### Non-faits

Aucun poids en live score ; T6 Auditor ; T7 Monte Carlo ; chat NL / T3d.

---

## 2026-09-23 — T5a MERGÉ (#34) — family weights observation-only

- Branche : `cursor/t5a-family-weights-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/34 — **MERGÉE** `c8c2bc7`
- Statut : CI verte ; merge Cursor.

### Livré

1. `app/confluence/` — `FamilyWeightsConfig` versionné (`family_weights_v0`) + `observe_family_weights(pipeline)`
2. Familles = StageId pipeline (direction/participation/structure/location/regime)
3. `ScreenerRow.family_weights` + serializers summary/detail ; agent `get_family_weights`
4. Tests `tests/confluence/` (invariants + non-mutation pipeline)

### Non-faits (volontaire)

Aucun changement decision/confidence/combiner/gates ; T5b backtest poids ; chat NL ; T6 Auditor ; T7 Monte Carlo.

---

## 2026-09-23 — T4d MERGÉ (#33) — filtre régime overlay

- Branche : `cursor/t4d-regime-overlay-filter-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/33 — **MERGÉE** `079f4cd`
- Statut : CI verte ; merge Cursor (solo).

### Livré

1. `regime_labels` au signal bar (`classify_regimes`) sur trades / rejected
2. Filtre AND `regime_label` (TRENDING/RANGING/BULL/…) API + agent + sheet
3. OpenAPI golden refresh

### Non-faits

T5a family weights ; chat NL ; changement fills.

---

## 2026-09-23 — T4b MERGÉ (#32) — filtre overlay

- Branche : `cursor/t4b-overlay-filter-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/32 — **MERGÉE**
- Statut : CI verte (OpenAPI golden fix) ; merge Cursor.

---

### Livré

1. `chart_objects/filter_trades.py` — filtres AND outcome / exit_reason / direction / why_entered_key
2. API overlay étendue + `filters` echo + `n_trades_filtered`
3. Agent read-only `filter_backtest_overlay`
4. Sheet : selects Sortie / Sens (pas de chat NL)
5. Tests unitaires + API

### Non-faits

Filtres régime ; T5 confluence ; chat NL dans le sheet ; changement fills/metrics.

---

## 2026-09-23 — T4c MERGÉ (#31) — WHY overlay

- Branche : `cursor/t4c-why-overlay-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/31 — **MERGÉE**
- Statut : CI verte ; merge Cursor.

---

### Livré

1. `evaluator.explain_group` — trace pass/fail par feuille (`all`/`any`) sans changer le match
2. `RulesetTradeDetail.why_entered` / `why_exited` ; `RejectedSignal` + `RulesetBacktestResult.rejected`
3. Overlay API : `why_*` sur trades + liste `rejected` ; markers chart `kind=rejected`
4. UI sheet : détail WHY ENTERED / EXITED + liste rejetés
5. Tests `test_t4c_why.py` + parity T4a (golden backtest **inchangé**)

### Non-faits

T4b filtre conversationnel ; filtres régime ; T5 confluence ; aucun changement de fills/metrics.

---

## 2026-09-23 — EVENT INTELLIGENCE PHASE 7 — correlate + SymbolNews → MAIN

- Branche : `cursor/event-correlate-context-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/29 — **MERGÉE**
- Statut : CI verte ; merge Cursor (Claude absente). EIL phases 1–7 observation **terminées**.

### Livré

1. Types : `EventCategory`, `ExternalEventRef`, `EventContextBundle`
2. `app/events/news.py` — SymbolNews causal (`published_at ≤ T` + relevance symbole)
3. `app/events/classifier.py` — taxonomie heuristique (jamais BUY/SELL)
4. `app/events/macro.py` — calendar → candidats causals
5. `app/events/correlate.py` — match → `EVENT_MARKET` si confidence ≥ seuil ; sinon `UNKNOWN_EVENT`
6. Branchement observation-only `scan_symbol` + serializers `event_context` ; agent `get_event_context`
7. Tests anti-lookahead news future / lag / weak match

### Non-faits (hors EIL observation)

Promotion seuils live (walk-forward), FinBERT, CorporateEventProvider scrapers, UI, changement de gates pipeline.

---

## 2026-09-23 — EVENT INTELLIGENCE PHASE 6 — regime study + calibration → MAIN

- Branche : `cursor/event-regime-study-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/28 — **MERGÉE**
- Statut : CI verte ; merge Cursor (Claude absente).

### Livré

1. `app/events/regime_study.py` — event-study PIPELINE stratifié par `NORMAL_MARKET` / `UNKNOWN_EVENT` (MFE/MAE, horizons, deltas observés)
2. `app/events/calibrate.py` — quantiles causaux → suggestions p99 **sans** muter les seuils live
3. Agent read-only : `run_anomaly_regime_study`, `calibrate_anomaly_thresholds`
4. Tests `tests/events/test_regime_study.py`
5. CDC PHASE 6 coché

### Non-faits (ouverts en PHASE 7)

SymbolNews, EventClassifier, `EVENT_MARKET`, changement de gates, UI.

---

## 2026-09-23 — EVENT INTELLIGENCE PHASE 5 — Anomaly Detector (observation-only)

- Branche : `cursor/event-anomaly-detector-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/27 (**draft**)
- Statut : **ATTENTE Claude** — CI **VERTE** ; Cursor solo jusqu’à 18:10 puis revue.
### Livré

1. `app/events/` — `detect_anomaly` causal (past-only z-scores, range/gap vs ATR, RVOL)
2. Régimes : `NORMAL_MARKET` | `UNKNOWN_EVENT` (pas de `EVENT_MARKET` sans match news — PHASE 6+)
3. Branchement `ScreenerRow.market_anomaly` + serializers summary/detail — **n’altère pas** decision/confidence/pipeline
4. Tests `tests/events/test_anomaly.py` (lookahead / shock / quiet)
5. CDC : T0-CALC + EIL audit + PHASE 5 cochés ; PHASE 6–7 ouverts

### Non-faits (volontaire)

News / earnings / FinBERT / vote pipeline / calibration empirique des seuils.

---

## 2026-09-23 — EVENT INTELLIGENCE LAYER — AUDIT (PHASES 1–4) → MAIN

- Branche : `cursor/event-intelligence-audit-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/26
- Doc : `docs/EVENT-INTELLIGENCE-LAYER-AUDIT.md`
- Statut : rebase sur main post-#25 ; merge Cursor (Claude absente) — **doc only**.

### Livré

1. Audit IchiVol : indicateurs / REGISTRY / pipeline / combiner / calendar+news / Claude / 3 pipelines / collision `EventObservation` Lab
2. KEEP/ADAPT/REJECT sur 7 repos de référence
3. Architecture : `EventAnomalyDetector` → régimes NORMAL/EVENT/UNKNOWN → context → Claude explain ; **EVENT ≠ SIGNAL**
4. Contrats Python (design) + plan phases 5–7

### Suite (Cursor solo jusqu’à 18:10)

PHASE 5 : `EventAnomalyDetector` causal + tests anti-lookahead + branchement **observation-only** (pas de vote pipeline).

---

## 2026-09-23 — T0-CALC MERGÉ (#25) — Cursor (Claude absente)

- Branche : `cursor/t0-calc-scenarios-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/25 — **MERGÉE**
- Statut : intégrée au chantier V3 (scénarios historiques fiche d’achat + positions). CI verte. Brief Claude respecté.

---

## 2026-09-23 — T0-METRICS-2 VALIDÉ par Claude — MERGÉ (#24)

- Branche : `cursor/t0-metrics-2-engine-costs-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/24 — **MERGÉE** `351dbe9`
- Statut : **validé par Claude** (`eod_return` séparé de `bar_returns` ; `test_engine_lookahead.py` **identique à main** ; 300 séquences aléatoires ; suite Postgres 0 échec).
- Remarque Claude : ne jamais affaiblir un test de non-fuite — corriger le code, pas le test.

---

## 2026-09-23 — T0-METRICS-2 EN COURS — frais engine (flip / EOD / close)

- Branche : `cursor/t0-metrics-2-engine-costs-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/24 (**draft**)
- Commit(s) : `96e5696` (feat) ; fix `eod_return` (voir HEAD)
- Statut : **ATTENTE CI** puis **ATTENTE CLAUDE**.

### Corrections `run_backtest`

1. **Flip** L↔S : `r -= 2 × one_way` ; attribution `one_way` sortie + `one_way` entrée
2. **EOD** : frais de sortie + mark-to-close dans **`BacktestResult.eod_return`** (pas dans `bar_returns`)
3. **Prix unique EOD** : trade @ `last.close` ; `eod_return = sign × log(last.close/last.open) − one_way`
4. **`bar_returns` strictement open→open** — propriété de troncature restaurée (test lookahead **inchangé**)

### Comptabilité

- Invariant : `Σ net_log_return(trades) == Σ bar_returns + eod_return` (1e-9)
- `metrics.total_return = exp(Σ bars + eod) − 1` ; max DD inclut un dernier point d’equity avec `eod_return`

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

- Invariant 1e-9 : mid-close, EOD close≠open, flip L→S / S→L, flips enchaînés
- Propriété : 200 séquences aléatoires
- Lookahead truncation : **strict** (aucune exclusion de barre)
- Local : `pytest tests/backtest tests/indicators tests/strategy_lab` — **0 échec**

### `metrics_basis`

- Engine / experiments / evidence / agent cmd → **`net_v2`**
- `ruleset_backtest` reste **`net_v1`**
- UI : labels distincts ; alerte si mélange brut / v1 / v2

### Impact (bougies synthétiques seed 42, 500 bars, coûts 5+3 bps) — confirmé après `eod_return`

| experiment | n | flips | eod | tot avant→après | dd avant→après | WR avant→après | Exp avant→après |
|------------|---|-------|-----|-----------------|----------------|----------------|-----------------|
| `ICHIMOKU_ONLY` | 40 | 6 | 1 | -28.32% → -28.94% | 32.25% → 32.57% | 5.00% → 5.00% | -0.83% → -0.85% |
| `ICHIMOKU_RVOL_ENTRY_GATE` | 31 | 0 | 1 | -24.57% → -24.86% | 29.90% → 29.90% | 3.23% → 3.23% | -0.91% → -0.91% |
| `PIPELINE` | 5 | 0 | 0 | -2.22% → -2.22% | 3.17% → 3.17% | 20.00% → 20.00% | -0.44% → -0.44% |

### Goldens

- `ruleset_backtest_golden.json` : **inchangé**

### Attente

CI verte → **ATTENTE Claude**.

---

## 2026-09-23 — T0-METRICS VALIDÉ par Claude — MERGÉ (#23)

- Branche : `cursor/t0-metrics-net-a2fe`
- PR : https://github.com/samiriggui-code/IchiVol/pull/23 — **MERGÉE** `7d74fa1`
- Statut : **validé par Claude** (WR/exp/PF nets ; `*_gross` ; invariant ; `metrics_basis=net_v1` ; alembic unique).

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

### CI Actions

- **VERTE** (HEAD `d90883f`) : https://github.com/samiriggui-code/IchiVol/actions/runs/35864600608
  - `pytest (Postgres 16)` success
  - `frontend (npm build)` success

### Attente

**Cursor s’arrête ici** jusqu’à la revue Claude.

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
