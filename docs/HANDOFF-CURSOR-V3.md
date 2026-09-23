# Handoff Cursor ↔ Claude — IchiVol V3

Canal unique entre Cursor (implémentation) et Claude (supervision).  
Claude lit ce fichier sur GitHub et relit le diff de la PR associée.

**Convention** : à chaque PR, ajouter une nouvelle entrée **en haut** ; ne jamais effacer les anciennes.

---

## 2026-09-23 — T1b — Front servi par le moteur (Ichimoku / RVOL / kumo projeté)

- Branche : `v3/t1b-front-engine-indicators`
- PR : https://github.com/samiriggui-code/IchiVol/pull/7 (draft)
- Commit(s) : `25e2249` (code T1b), `417da25` (ce handoff)

- Livré :
  - `docs/HANDOFF-CURSOR-V3.md` — canal handoff V3 (entrée T1 + T1b)
  - `ichivol-app/engine/app/indicators/ichimoku.py` — `compute_projected_kumo` (display-only ; ne touche pas `IchimokuState` / `compute_ichimoku`)
  - `ichivol-app/engine/app/api/indicators.py` — `GET /indicators/ichimoku/{symbol}/projection`
  - `ichivol-app/engine/tests/indicators/test_projected_kumo.py` — égalité projection ↔ senkou affiché à `i+d` + garde d’import
  - `ichivol-app/src/lib/engineIndicators.ts` — `getIndicatorSeries`, `getIchimokuProjection`, mapping snake_case → types chart
  - `ichivol-app/src/lib/signals.ts` — `buildVolumePulse` (couleurs / signaux depuis séries moteur ; plus de RVOL local)
  - `ichivol-app/src/components/PriceChart.tsx` — overlays async moteur ; prix seul si erreur
  - `ichivol-app/src/pages/MarketPage.tsx` — props `symbol`/`timeframe`/`onLive` ; plus de `computeIchimoku`
  - `ichivol-app/src/index.css` — message discret overlays
  - `ichivol-app/src/lib/ichimoku.ts` — **supprimé** (grep `computeIchimoku|donchianMid` vide dans `src/`)

- Tests :
  - `cd ichivol-app/engine && .venv/bin/python -m pytest tests/indicators/test_projected_kumo.py tests/api/test_indicators_route.py -q` → **9 passed**
  - `cd ichivol-app/engine && .venv/bin/python -m pytest -q` → **4 failed** (Postgres connus, connexion refusée `127.0.0.1:5432`) : `test_backtest_evidence_route_*` ×2, `test_persist_and_attach_outcome`, `test_propose_intent_blocked_when_watch`
  - `cd ichivol-app && npm run build` → **OK** (`tsc -b && vite build`)
  - `grep -rn "computeIchimoku\|donchianMid" ichivol-app/src` → vide

- Choix faits :
  - Nuage futur via helper séparé + endpoint dédié (pas de changement de `compute_ichimoku`) pour ne pas casser lookahead / features.
  - Span A/B du chart = série **projection** (temps `i+d` / extrapolé) ; tenkan/kijun/cloudTop/Bot et flags cloud viennent des states ichimoku ; RVOL de l’indicateur `rvol`.
  - Chikou = close décalé `displacement` **côté front uniquement** (affichage).
  - Params Settings → JSON moteur : `senkouB`→`senkou_b`, `rvolLen`→`primary_window`.
  - En erreur overlay : pas de repli sur calcul local (prix + message discret).

- Doutes / points à vérifier par Claude :
  - Alignement exact chikou affichage vs ancienne `ichimoku.ts` (décalage index).
  - Volume histogramme pendant chargement : volumes bruts gris, puis couleurs moteur — OK produit ?
  - Auth : le front passe par `/api/engine/*` (proxy Express `requireAuth`) ; la démo handoff a frappé le moteur en direct.

- Non fait / reste à faire :
  - Structure unifiée, découpage `routes.py`, `ChartObject` (hors périmètre T1b).
  - Sortir la PR du draft + merge après validation Claude.
  - Vérifier en app authentifiée (Marché BTCUSDT 1h) que le nuage projeté s’affiche à droite de la dernière bougie.

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
