# Handoff Cursor ↔ Claude — IchiVol V3

Canal unique entre Cursor (implémentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff de la PR associée.

**Convention** : à chaque PR, ajouter une nouvelle entrée **en haut** ; ne jamais effacer les anciennes.

---

## 2026-09-23 — T1d — Chemin live via le REGISTRY

- Branche : `v3/t1d-live-path-registry`
- PR : https://github.com/samiriggui-code/IchiVol/pull/9 (draft)
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

- Doutes / points à vérifier par Claude :
  - Screener a aussi migré cvd/adx/donchian (nécessité cliquet) — OK vs brief qui ne citait que structure/atr/location ?

- Non fait / reste à faire :
  - T1e : api/routes, agent_channel, backtest/experiments, strategy_lab/regime, synthetic/validation, structure/atr_utils
  - CONDITION_SCHEMA, structure unifiée
  - **Ne pas merger** avant revue Claude.

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
