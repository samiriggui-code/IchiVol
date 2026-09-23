# Handoff Cursor ↔ Claude — IchiVol V3

Canal unique entre Cursor (implémentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff de la PR associée.

**Convention** : à chaque PR, ajouter une nouvelle entrée **en haut** ; ne jamais effacer les anciennes.

---

## 2026-09-23 — T1b — Front servi par le moteur (Ichimoku / RVOL / kumo projeté)

- Branche : `v3/t1b-front-engine-indicators`
- PR : https://github.com/samiriggui-code/IchiVol/pull/7 (prête — hors draft, en attente revalidation Claude)
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
  - Revalidation des 3 corrections (warmup, chikou, REGISTRY) avant merge.
  - Smoke Marché BTCUSDT 1h authentifié (nuage à droite de la dernière bougie).

- Non fait / reste à faire :
  - Structure unifiée, découpage `routes.py`, `ChartObject` (hors périmètre T1b).
  - **Ne pas merger** tant que Claude n’a pas revalidé.

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
