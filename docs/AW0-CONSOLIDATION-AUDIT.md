# AW0 — Consolidation audit (duplication map)

**Date:** 2026-09-26  
**Tip:** `main` @ `6634438` (GEL CI + T-CYCLE + VP0 handoff)  
**Branch:** `cursor/vp-aw0-docs-a2fe`  
**Périmètre:** lecture seule — inventaire des assemblages dupliqués avant toute raffactor AW1+.  
**Livrable:** ce fichier uniquement.

---

## 0. Verdict en une phrase

Le **math** (indicateurs / `build_pipeline` / producteurs ChartObject) est déjà centralisé ; ce qui est dupliqué, c’est l’**assemblage** (fetch → agents → REGISTRY → pipeline → objets → labels tendance / front).

---

## 1. Pipeline assembly duplicates

### 1.1 Canonical building blocks (déjà SSOT)

| Bloc | Path | Rôle |
|------|------|------|
| Registry | `ichivol-app/engine/app/indicators/registry.py` | `REGISTRY.compute` / `compute_many` |
| Agents | `…/agents/ichimoku_agent.py`, `…/agents/rvol_agent.py` | `analyze()` → `StrategyAgentOutput` via REGISTRY |
| Pipeline | `…/decision/pipeline.py` | `build_pipeline(...)` → `PipelineResult` |

Tout chemin décisionnel **doit** finir par `build_pipeline`. Les duplications ci‑dessous concernent **comment** on prépare les arguments.

### 1.2 Live screener — `scan_symbol`

**Path:** `ichivol-app/engine/app/screener/service.py`  
**Fn:** `scan_symbol` (≈ L157–222)

Assemble pour **la dernière barre fermée** :

1. `ichimoku_agent.analyze` / `rvol_agent.analyze` → `[-1]`
2. `combine_ichimoku_rvol` (legacy badge)
3. `REGISTRY.compute_many(["structure","atr","location","cvd","adx","donchian"], …)`
4. MTF best-effort (`_mtf_direction`) + OI/funding
5. `build_pipeline(ichimoku=…, rvol=…, structure=…, …)`
6. Evidence / anomaly (observation only)

**Callers:** API screener/decisions, `agent_channel.commands.cmd_detect_signal` / `cmd_get_symbol_context` / `cmd_compare_timeframes`, paper intent, watchlist.

### 1.3 Backtest — `prepare_variants` / `pipeline_positions`

**Path:** `ichivol-app/engine/app/backtest/experiments.py`  
**Fns:** `pipeline_positions` (L168–218), `prepare_variants` (L248–331)

Même famille, **série complète** :

1. Agents full-series
2. `REGISTRY.compute_many([…, "wyckoff"])` (extra vs live)
3. MTF via `_align_mtf_directions`
4. Par barre : `build_pipeline(...)` → positions BUY/SELL only

**Callers:** `experiments.compare`, Strategy Lab event study.

### 1.4 Research lab — `compute_bar_signals`

**Path:** `ichivol-app/engine/research_lab/signals.py`  
**Fn:** `compute_bar_signals` (L78–112)

Docstring dit « same components as screener / prepare_variants », **mais** :

- appelle `compute_structure` / `compute_atr` / `compute_location` / `compute_cvd` / `compute_adx` / `compute_donchian` **directement** (pas `REGISTRY`)
- pas d’OI/funding ; HTF via `_align_mtf_directions` importé de experiments
- produit `BarSignal` (fail codes / primary) pour le harness

**Risque drift :** un changement de params / wrapper REGISTRY peut diverger du live.

### 1.5 Autres assembleurs (même motif)

| Path | Fn | Note |
|------|-----|------|
| `…/chart_intelligence/service.py` | `_build_analysis_and_state` (L262–328) | Agents + REGISTRY + `build_pipeline` pour **analyse CI** (observe) |
| `…/evidence/catalog.py` | `build_in_window_catalog` | Agents + REGISTRY (structure/atr) + `build_pipeline` allégé |
| `…/confluence/study.py` | profile study loop | Agents + REGISTRY full + `build_pipeline` |
| `…/synthetic/validation.py` | `run_pipeline_over_candles` | REGISTRY sans MTF/CVD/OI (volontaire) |
| `…/research_lab/replica.py` | `live_like_signal` | Direct `compute_*` comme signals.py |

### 1.6 Qui appelle quoi (résumé)

```text
REGISTRY.compute*     ← agents, screener, experiments, CI, catalog, confluence,
                        synthetic, api/indicators, chart_objects producers, …
ichimoku_agent.analyze / rvol_agent.analyze
                      ← screener, experiments, research_lab, CI, catalog,
                        confluence, synthetic, replica, tests parity
build_pipeline        ← screener, experiments.pipeline_positions, research_lab,
                        CI._build_analysis_and_state, catalog, confluence,
                        synthetic, paper tests, …
```

### 1.7 SSOT recommandé

**Module unique** (nouveau) du type :

`ichivol-app/engine/app/decision/assemble.py`

- `compute_stage_inputs(candles, params) → StageInputs` — **toujours** via agents + `REGISTRY.compute_many`
- `pipeline_at(inputs, i | last, mtf_aligned=…, oi=…) → PipelineResult`
- Variantes live / series / research = wrappers minces (MTF, OI, step, closed-only)

`research_lab/signals.py` et `replica.py` doivent **arrêter** les imports directs `compute_*` indicateurs.

**Garder :** `build_pipeline` comme pure function de stages (inchangé).

---

## 2. Chart object assembly

### 2.1 HTTP / agent collect

**Path:** `ichivol-app/engine/app/chart_objects/collect.py`  
**Fn:** `collect_chart_objects` (L36–109), `parse_sources` (L20–33)

Pour `source=engine` :

1. `resolve_and_fetch` + `detect_market_structure`
2. `structure_to_chart_objects`
3. `breaks_to_chart_objects(..., snapshot=snap)` — **defaults** `max_events=40`, `include_breakouts=True`
4. `fvg_to_chart_objects`
5. `fibonacci_to_chart_objects(..., key_only=True)`
6. Merge store USER/CLAUDE si demandé

**Callers:** `api/chart_objects.py`, `agent_channel.commands.cmd_get_chart_objects`.

### 2.2 Chart Intelligence — `_collect_engine_objects`

**Path:** `ichivol-app/engine/app/chart_intelligence/service.py`  
**Fn:** `_collect_engine_objects` (L231–259)

**Même producteurs**, différences :

| | `collect.py` | CI `_collect_engine_objects` |
|--|--------------|------------------------------|
| Fetch | oui (API) | non (fenêtre déjà fournie) |
| Breakouts | inclus | **exclus** (`include_breakouts=False`) |
| Cap BOS/CHoCH | 40 | **16** (`max_events=16`) |
| Enrichissement | non | `_enrich_object` + `known_at` / `producer` / slim frames |
| Pipeline / ichi / market_state | non | oui (`_build_analysis_and_state`) |
| Persistés | oui si sources | oui, filtrés `as_of ≤ effective_as_of` |

Overlap = **copier-coller** des 4 `*_to_chart_objects` calls.

### 2.3 SSOT recommandé

Extraire dans `chart_objects/collect.py` (ou `engine_bundle.py`) :

```text
collect_engine_objects(window, symbol, timeframe, *, include_pytrendline,
                       max_break_events=40, include_breakouts=True) -> list[ChartObject]
```

- `collect_chart_objects` = fetch + `collect_engine_objects` + store  
- CI = `collect_engine_objects(..., max_break_events=16, include_breakouts=False)` + enrichissement replay

Producers (`from_structure` / `from_breaks` / `from_fvg` / `from_fibonacci`) restent la vérité mathématique.

---

## 3. Trend / market_state recalculés

### 3.1 CI `_trend_label`

**Path:** `…/chart_intelligence/service.py` L178–186, branché L299–304

```text
close > tenkan > kijun → "bullish"
close < tenkan < kijun → "bearish"
else → "range"
```

Recalcule depuis `REGISTRY.compute("ichimoku")` **indépendamment** de `ichimoku_agent` direction.

### 3.2 Ailleurs (sémantiques différentes)

| Path | Fn / champ | Sémantique |
|------|------------|------------|
| `…/agents/ichimoku_agent.py` | `_direction` (L56–63) | `price_vs_kumo` + `score` → LONG/SHORT/NEUTRAL (pipeline Direction) |
| `…/src/lib/signals.ts` | `biasFromIchi` (L103–107) | `aboveCloud` / `belowCloud` → bull/bear/neutral (**display**) |
| `…/src/components/PriceChart.tsx` | `onLive` bias (L625, L670) | consomme `biasFromIchi` |
| `…/cycle/engine.py` | `methods["trend"]` (L153–158) | efficiency_ratio / r² — **autre** « trend » (cycle study) |
| `…/chart_intelligence/service.py` | `_structure_label` (L153–167) | HH_HL / LH_LL depuis `origin.kind == "swing"` |

**Écart important :** aucun producer live n’émet `origin.kind == "swing"` (seulement le mock UI). Donc `market_state.structure` live tombe quasi toujours sur `"MIXED"`.

### 3.3 SSOT recommandé

1. **Trend ichimoku UI/CI** : une fn unique `trend_label_from_ichi(state) → bullish|bearish|range` dans `indicators/ichimoku.py` (ou analytics), consommée par CI ; **ne pas** la confondre avec `ichimoku_agent.direction` (vote pipeline).
2. Documenter explicitement : pipeline Direction ≠ CI trend ≠ PriceChart bias ≠ cycle efficiency.
3. Si `structure` HH_HL est voulu : producer Marker/Text swing dans `from_structure` (ou lire swings du snapshot) — sinon retirer / renommer `_structure_label`.

---

## 4. Front calculations

### 4.1 `signals.ts`

**Path:** `ichivol-app/src/lib/signals.ts`

| Fn | Rôle | Finance ? |
|----|------|-----------|
| `buildVolumePulse` (L15–101) | Couleurs histogramme + marqueurs TK/cloud **décoratifs** à partir des séries **moteur** déjà fetchées | **Non** — pas de recalcul Ichimoku/RVOL (commentaire L12–13) |
| `biasFromIchi` (L103–107) | Bias cloud | Display |
| `signalLabel` | Labels UI | Display |

Les « signaux » `tk_long` / `brk_*` sont des **markers chart**, pas `pipeline.decision`.

### 4.2 PriceChart

**Path:** `ichivol-app/src/components/PriceChart.tsx`  
**Import:** `buildVolumePulse` depuis `../lib/signals` (L36) ; usage ≈ L608.

Ne redéfinit **pas** `buildVolumePulse`. Charge overlays via `fetchChartOverlays` (`engineIndicators.ts`) — client IndicatorRegistry : « le chart ne calcule plus Ichimoku/RVOL localement ».

### 4.3 SSOT recommandé

- **Garder** front = display-only (état actuel OK).
- Ne **pas** promouvoir `buildVolumePulse` markers en vérité trading.
- Option AW1 : si CI `market_state.trend` doit aligner le badge live, consommer le champ engine plutôt que `biasFromIchi` (cloud ≠ TK stack).

**Tests :** aucun test front dédié `buildVolumePulse` aujourd’hui — **à ajouter** (fixtures séries engine → volumes/signals stables).

---

## 5. `draw_*` agent — free levels vs ChartObject ids

### 5.1 Surface actuelle

| Path | Rôle |
|------|------|
| `…/agent_channel/commands.py` | `cmd_draw_*` → `_draw_and_persist` (L1271–1347) |
| `…/agent_channel/registry.py` | ToolSpecs (L565+) — args `price` / `points[{time,price}]` libres |
| `…/chart_objects/draw.py` | `build_from_draw_args` — construit ChartObject, `origin.via=agent_draw` |
| `…/chart_objects/grounding.py` | `assert_object_grounded` — bande large 0.5×–1.5× high/low (anti-absurdité, **pas** ancrage exact) |
| `…/chart_objects/types.py` | `deterministic_chart_object_id` — id = hash(type, source, symbol, tf, coords, subtype) |

L’agent invente donc des **valeurs libres** (price/time), persistées `source=claude`, puis grounding soft.

### 5.2 Comment l’id ChartObject pourrait remplacer les free values

1. Agent appelle `get_chart_objects` → choisit un objet ENGINE (zone Fib, S/R, FVG…) par **`id`** ou **`origin.lineage_key`**.
2. Nouveau contrat (proposition AW1) :

```text
draw_horizontal_line({ symbol, timeframe, ref_object_id: "<24hex>" , label? })
# ou ref_lineage_key: "fib:…:0.618"
```

3. Serveur résout l’objet ENGINE, copie `price` / `price_low`/`price_high` / points, stamp `origin.ref_object_id` + `origin.ref_lineage_key`, source reste `claude`.
4. L’id du nouvel objet CLAUDE reste déterministe sur ses coords (inchangé) ; la **provenance** lie au niveau moteur.

Bénéfice : plus d’hallucination de niveaux « proches » ; alignement replay / known_at via lineage du parent.

**Garder** free `price` pour annotations purement humaines (notes), mais tools stop/entry/target devraient préférer `ref_*`.

---

## 6. Provenance ChartObject (`origin`, `known_at`, `lineage_key`)

### 6.1 Modèle

**Path:** `ichivol-app/engine/app/chart_objects/types.py`

- Champ `origin: dict` libre (L241) — sérialisé tel quel
- `projected` dans origin autorise points `time > as_of` (validation L207–213)
- `round_chart_coord` pour bounds stables dans lineage (L90–92)
- **`id` ≠ `lineage_key`** : id change si coords/as_of changent (ex. FVG end=`as_of`) ; lineage stable pour CI-R8

### 6.2 Producers — `lineage_key` (pas de `known_at` à l’émission)

| Producer | Path | Exemple `lineage_key` |
|----------|------|------------------------|
| Structure zones | `from_structure.py` L183 | `zone:{side}:{pl}:{ph}` |
| Structure TL | `from_structure.py` L140–143 | `trendline:{det}:{side}:{t0}:{t1}` |
| Breaks events | `from_breaks.py` L71 | `structure_event:{type}:{swing_time}` |
| Breakouts | `from_breaks.py` L109 | `breakout:{side}:{as_of}` (éphémère) |
| FVG | `from_fvg.py` L51 | `fvg:{dir}:{t0}:{pl}:{ph}` |
| Fib | `from_fibonacci.py` L48–82 | `fib:{impulse}:{anchor}:{bars}:{swings}` (= `group_id`) |
| Agent draw | `draw.py` L83–84 | `via=agent_draw` — **pas** de lineage_key par défaut |
| User trades | `user_write.py` | `via=user_mark_trade`, `setup_id` optionnel |

### 6.3 `known_at` — CI only

**Path:** `chart_intelligence/service.py`

- `_enrich_object` (L128–150) : injecte `known_at` seulement si fourni (replay) ; n’invente **pas** depuis anchor times (CI-R1)
- `build_chart_intelligence_replay` : première apparition d’un `lineage_key` → `known_at_by_lineage[lk] = T`
- Live snapshot : souvent **sans** `known_at` producteur

### 6.4 SSOT recommandé

- Producers : **obligatoires** `origin.kind` + `origin.lineage_key` (+ `producer` optionnel).
- `known_at` : reste responsabilité du walk-forward CI (ou champ producteur explicite si détection bar connue, ex. Fib `known_bar` → time) — ne pas dériver du point d’ancrage.
- Agent draw : si `ref_lineage_key`, propager dans origin ; sinon générer `lineage_key=claude:{id}`.

---

## 7. Matrice SSOT (AW0 → AW1)

| Domaine | Dupliqués aujourd’hui | SSOT cible |
|---------|----------------------|------------|
| Indicateurs | — | `REGISTRY` + modules `indicators/*` |
| Agents Ichi/RVOL | — | `ichimoku_agent` / `rvol_agent` |
| Pipeline stages | — | `decision/pipeline.build_pipeline` |
| **Assemblage inputs** | screener, experiments, research_lab, CI, catalog, confluence, synthetic | **`decision/assemble.py`** (nouveau) |
| **Bundle ChartObjects ENGINE** | `collect.py` vs CI `_collect_engine_objects` | **`collect_engine_objects(...)`** partagé |
| Trend CI | `_trend_label` local | `ichimoku.trend_label` (ou analytics) |
| Bias front | `biasFromIchi` | display-only OK ; ne pas fusionner avec pipeline |
| Draw levels | free price | `ref_object_id` / `ref_lineage_key` + free fallback |
| Provenance | producers + CI enrich | producers=`lineage_key` ; CI=`known_at` |

---

## 8. Tests — garder / ajouter

### Garder (régressions actuelles)

| Test | Couvre |
|------|--------|
| `engine/tests/screener/test_scan_symbol_golden.py` | Assemblage live + REGISTRY |
| `engine/tests/screener/test_service.py` | scan_symbol |
| `engine/tests/backtest/test_prepare_variants_golden.py` | prepare_variants |
| `engine/tests/research_lab/test_signals_causal.py` | causalité bar signals |
| `engine/tests/strategy_lab/test_t12b_lab_live_parity.py` | Lab vs live pipeline |
| `engine/tests/synthetic/test_run_pipeline_golden.py` | synthetic same pipeline |
| `engine/tests/api/test_chart_intelligence_route.py` | CI collect + known_at + lineage (CI-R1/R8) |
| `engine/tests/chart_objects/test_chart_objects.py` | types / from_structure |
| `engine/tests/chart_objects/test_from_breaks.py` | breaks producers |
| `engine/tests/chart_objects/test_t2b_store_and_agent.py` | draw_* + store |
| `engine/tests/chart_objects/test_grounding.py` | grounding free draws |
| `engine/tests/api/test_agent_channel_routes.py` | draw commands HTTP |
| `engine/tests/decision/test_pipeline.py` | build_pipeline pur |
| `engine/tests/indicators/test_registry*.py` | REGISTRY ratchet |

### Ajouter (quand AW1 commence)

1. **Parity assemble** — `assemble.pipeline_at(last)` == `scan_symbol(...).pipeline` sur fixture candles (sans réseau).
2. **Parity research vs REGISTRY** — `compute_bar_signals` après bascule REGISTRY ≡ golden actuel.
3. **Shared collect** — objets ENGINE de `collect_engine_objects` == CI (mêmes kwargs) bit-identique hors enrichissement.
4. **`trend_label` unitaire** — table close/tenkan/kijun → label ; CI consomme la même fn.
5. **`ref_object_id` draw** — draw stop depuis Fib ENGINE → prix égal + `origin.ref_*`.
6. **Front** — unit test `buildVolumePulse` (pas de finance) + snapshot markers.
7. **`_structure_label`** — soit test d’émission swing, soit assert documenté MIXED jusqu’à producer.

---

## 9. Hors scope AW0

- Changer `build_pipeline` stages / seuils
- Nouveaux producteurs ChartObject
- Promo décision / paper
- Régénération goldens RVOL (#135)

---

## 10. Prochaine étape proposée (AW1)

1. Extraire `collect_engine_objects` (diff collect↔CI = kwargs only).  
2. Extraire `decision/assemble` ; brancher screener + experiments ; migrer research_lab hors `compute_*` directs.  
3. Spécifier contrat `ref_object_id` sur `draw_stop` / `draw_entry` / `draw_target`.  
4. Clarifier trend labels (doc + fn unique) ; décider du sort de `_structure_label` / swings.
