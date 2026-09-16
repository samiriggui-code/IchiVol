# Handoff — session Claude (2026-09-16, après le soir Cursor)

> **Pour :** Cursor (front / Express) + prochaine session Claude (engine)
> **De :** Claude
> **Suite de :** [`HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md`](./HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md), [`HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md`](./HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md)
> **Doc maître :** [`CAHIER-DES-CHARGES.md`](./CAHIER-DES-CHARGES.md)

---

## 1. Livré cette session (Claude, moteur)

### Paper multi-classe (V2)

Le garde crypto-only dans `POST /api/engine/paper/positions` (`app/api/routes.py::open_paper_position`) est **levé**. `PaperPosition` n'a jamais eu de colonne exchange — le blocage était purement applicatif. Découverte au passage : `auto_watchlist` (cycle screener background) tournait déjà multi-classe sans que personne ne l'ait noté, puisque `default_watchlist()` inclut biquote (forex/métal/index/énergie) depuis l'ajout du catalogue. Seul `user_confirmed` (clic "Confirmer") était bloqué.

**Impact front (déjà traité par moi, pas d'action Cursor requise) :** `lib/paper.ts::openPaperPosition` était déjà générique (pas de filtre crypto côté client) — rien à changer côté appel. J'ai nettoyé 3 endroits de texte devenus faux : la branche morte `paper_trading_crypto_only` dans `DecisionsPage.tsx::onConfirmDetail`, et 2 mentions "(crypto)" dans `PaperPage.tsx`.

Détail : `ichivol-app/engine/README.md` §Paper multi-classe.

### `POST /api/engine/decisions/batch` (V2, optionnel)

Nouvel endpoint batch — variante de `GET /decisions/{symbol}` qui scanne plusieurs `{symbol, timeframe}` **en concurrent** (`ThreadPoolExecutor`, même pattern que `scan_watchlist`) au lieu d'un appel par symbole. Réponse : `{"results": [...]}`, un objet par item **dans l'ordre de la requête**, même forme que `GET /decisions/{symbol}` (donc `pipelineFingerprint()` côté server n'a besoin d'aucun changement pour le consommer), plus `ok`/`error` par item — un symbole en échec ne fait jamais échouer tout le batch. Plafonné à 60 items/requête.

```json
POST /api/engine/decisions/batch
{ "items": [{"symbol": "BTCUSDT", "timeframe": "1h"}, ...], "persist": true }
```

**Pas encore branché côté server.** Voir §3 ci-dessous — pertinent maintenant que j'ai regardé `notifications/watch.ts`.

### `GET /api/engine/correlations` (V2 optionnel, `CDC-VIZ-002`)

Graphe de corrélations §6.2 du CDC — moteur seulement, **pas d'UI**. Nœuds = symboles, arêtes = corrélation de Pearson sur rendements log bar-à-bar (`method=log_returns` par défaut, `method=price` en option), symboles alignés sur leurs timestamps communs. Jamais branché au pipeline de décision, jamais un vote — lecture seule.

```
GET /api/engine/correlations?timeframe=1h&method=log_returns&symbols=BTCUSDT,ETHUSDT,EURUSD
→ { "symbols": [...], "matrix": [[1.0, 0.82, ...], ...], "skipped": [{"symbol":"X","reason":"..."}], "sample_size": N }
```

Défaut `symbols` = `default_watchlist()` (28 symboles aujourd'hui : crypto + biquote). Stateless comme `/backtest`, plafonné à 40 symboles/requête. Une paire à variance nulle renvoie `null`, pas `0.0`.

**Prochaine étape logique = UI Cursor** : Contexte ou sous-vue Marché, "qu'est-ce qui bouge avec BTC ?". Pas de topologie Grace/GRC (§6.4 du CDC) — juste une matrice/heatmap simple.

Détail : `ichivol-app/engine/README.md` §Corrélations. Tests : `tests/correlation/` (8) + 3 tests route dans `tests/api/test_routes.py`.

---

## 2. Ce que j'ai constaté côté Cursor (en cours au moment de cette session — ne pas écraser)

En regardant l'état du repo j'ai vu des fichiers modifiés très récemment (à quelques secondes d'écart les uns des autres), donc un chantier Cursor manifestement actif sur **le moteur de notifications + son UX** :

- `server/src/notifications/watch.ts` — refonte : intervalle 5 min → **3 min**, et surtout **rotation par batch** (`pickConfirmedBatch` : 15 jamais pollés en priorité + 30 les plus anciens par `watchCheckedAt`) au lieu d'un plat top-40 par `updatedAt`. Nouvelle colonne `decisions.watchCheckedAt` (migration `20260916190000_decision_watch_checked_at`), mise à jour à chaque poll même sans changement. Notif enrichie d'un résumé des stages qui ont bougé (`stageDiffSummary`).
- `src/components/NotificationBell.tsx` — refresh silencieux 60s, liste enrichie (icône par kind, chips symbole/TF, empty state), clic → marque lu + deep-link.
- `src/pages/DecisionsPage.tsx` — nouveau `useSearchParams` pour capter `?symbol=&interval=` et ouvrir automatiquement le sheet correspondant (deep-link depuis la cloche).
- `server/src/agent/actionsRoute.ts` (nouveau) — `POST /api/agent/actions/confirm` : le Copilot peut **proposer** `save_decision`/`pin_symbol` (allowlist stricte), exécuté seulement après confirmation UI explicite ; l'exécution déclenche `createNotification` (donc le Copilot alimente indirectement le moteur de notifs, jamais un vote automatique). S'appuie sur 2 migrations déjà en place : `20260916170000_agent_threads`, `20260916180000_agent_actions_audit`.
- `layouts/DashboardShell.tsx` / `index.css` — wiring + style popover.

**Je n'ai touché à aucun de ces fichiers.** Je le note ici pour que la prochaine session (Claude ou Cursor) ait la photo complète plutôt que de redécouvrir ce chantier à froid.

**Point d'attention pour vous :** `watch.ts` est passé à **45 items/poll toutes les 3 min**. ~~fetch séquentiels~~ → **branché** sur `POST /api/engine/decisions/batch` (`fetchEngineDecisionsBatch`, `persist: false`, timeout 120s). `pipelineFingerprint` / `gateOf` / `stageDiffSummary` inchangés.

---

## 3. Option B tranchée + champ `risk` (autre session Claude engine, 2026-09-16)

Une session Claude parallèle a livré, pendant que je travaillais :

**Option B tranchée avec l'user** : un seul verdict consommé par un humain ou un agent = `pipeline.decision` (colonne PORTES). Le BADGE (`combine_ichimoku_rvol`, legacy) reste consultable mais **seulement comme détail diagnostique — plus comme badge d'action concurrent**. Déclencheur : screenshot user de la Matrice montrant NEARUSDT avec BADGE=ACHAT et PORTES=PAS DE TRADE en même temps — BADGE est un sous-ensemble strict de ce que regarde le pipeline (Direction+Participation seulement, contre +Structure+Location+Régime), et ICHIMOKU_RVOL ne bat pas Ichimoku seul en backtest non plus. Rien ne justifie de garder les deux au même niveau visuel.

**Action front demandée (pas faite — voir §3bis) :** dans `GateMatrix.tsx`, soit retirer la colonne BADGE, soit la relabelliser clairement ("signal brut avant Structure/Location/Régime") et la sortir de la ligne d'action principale (aujourd'hui elle utilise le même style `.bias`/pill coloré que la colonne PORTES — c'est ce qui crée la confusion visuelle). **Aucun changement API requis** : `decision` (legacy) et `pipeline.decision` existent déjà tous les deux sur chaque ligne `/screener`.

**Champ `risk` ajouté** à chaque ligne `/screener` et `/decisions/{symbol}` :
```json
"risk": { "atr": 0.73, "regime": "NORMAL", "suggested_stop_distance": 1.10 }
```
`null` si historique ATR insuffisant. Contrepartie machine-readable du texte français du stage Régime — donne un stop distance exploitable sans parser de prose. Pas de sizing (pas de Kelly, pas de risk caps), juste `price` (déjà là) + `suggested_stop_distance`. Vérifié dans le code (`app/api/routes.py::_risk_dict`) et les tests (`test_screener_endpoint_shape`).

Détail complet : `docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md` §14 et `docs/CAHIER-DES-CHARGES.md` §5.

---

## 3bis. Backlog restant (CDC)

| Priorité | Item | Qui |
|----------|------|-----|
| V1.5 | Démoter BADGE dans `GateMatrix.tsx` (relabel ou retrait, voir §3) | ✅ Cursor — colonne **Brut** (diagnostic dashed), **Portes** = seul pill d’action ; liste + sheet alignés (2026-09-16) |
| V2 optionnel | UI Graphe corrélations (Contexte ou Marché) | ✅ Cursor — `CorrelationHeatmap` sur page Contexte (`GET /correlations`) |
| V2 optionnel | Brancher `watch.ts` sur `/decisions/batch` | ✅ Cursor — `fetchEngineDecisionsBatch` + `persist: false` (2026-09-16) |
| V2 optionnel | Bouton action directe depuis la Matrice (paper) | ✅ Cursor — colonne Paper dans `GateMatrix` → `openPaperPosition` |
| V2 | Perf/calibration paper (seuils) | Plus tard, dépend du volume de trades accumulés |
| V3 | Wyckoff / Donchian (backtest avant vote) | ✅ Claude — Donchian promu, Wyckoff non (voir §3ter) |

---

## 3ter. Wyckoff / Donchian backtestés + Donchian promu (Claude, 2026-09-16)

Même méthodologie de départ que l'ADX (3 fenêtres réelles : BTCUSDT 1h/4h, ETHUSDT 1h), verdicts différents pour les deux.

- **Donchian** (`app/indicators/donchian.py`, canal turtle-trading `period=20`, exclut toujours la bougie testée de son propre canal) : 3 fenêtres initiales déjà solides — drawdown amélioré dans les 3 (souvent de moitié+), Sharpe amélioré sur 2/3 (BTCUSDT 1h : -0.39→**1.95**), légèrement pire sur BTCUSDT 4h (écart dans le bruit). Décision produit explicite (2026-09-16, pas le "3/3 sans exception" strict d'ADX mais jugé suffisant) : **promu en gate actif** dans `app/decision/pipeline.py::_regime_stage` — régime ATR normal mais Donchian ne confirme pas de vraie cassure dans le sens de la direction Ichimoku → `NO_TRADE`, jamais un vote de direction. `PIPELINE_DONCHIAN_FILTER` supprimé (redondant, même sort que `PIPELINE_ADX_FILTER`) — `PIPELINE` reflète déjà le gate.
  **Revalidé ensuite sur un sweep élargi** (24 runs : 12 symboles crypto × 1h/4h, seuils par défaut) : `PIPELINE` (avec Donchian) ne bat toujours pas `ICHIMOKU_ONLY` en Sharpe (11/24, ~pile ou face) — **Option C reste non justifiée**, aucun changement. Mais drawdown réduit dans **24/24 runs sans exception**, moyenne 30.1%→5.1% (~6×) — un argument produit net : `PIPELINE` est un moteur de gestion du risque très efficace, pas (encore) un générateur d'edge de rendement.
- **Wyckoff** (`app/indicators/wyckoff.py`, "logique maison" explicite — détecte seulement SPRING/UPTHRUST, pas les phases accumulation/distribution complètes) : pas d'edge, pire sur 2/3 fenêtres, événements trop rares pour changer grand-chose (trades quasi inchangés) → **pas promu**, reste en backtest seul (`PIPELINE_WYCKOFF_FILTER`).

**Impact live :** `pipeline.decision` (donc `/screener`, `/decisions/{symbol}`, et tout ce qui en dépend — Matrice, paper trading, le nouveau tool Copilot `open_paper_position`) devient plus sélectif dès le reload engine : une direction Ichimoku sans vraie cassure Donchian confirmée passe désormais en `NO_TRADE` au lieu de potentiellement `BUY`/`SELL`. Aucun changement de contrat API (même champ `pipeline.decision`, juste des valeurs différentes) — mais un symbole qui était actionable avant ce déploiement peut ne plus l'être maintenant.

Détail complet + tableaux chiffrés : `ichivol-app/engine/README.md` §Donchian + Wyckoff et §Sweep élargi. 22 nouveaux tests indicateurs + 6 tests pipeline Donchian, suite complète verte (278 tests).

**Pour vous (front/Copilot) :** rien à faire ici — ni Donchian ni Wyckoff n'est exposé sur aucune route API, aucun changement de contrat `/screener`/`/decisions`/`/backtest` visible pour un consommateur existant (seulement 2 nouvelles clés dans `/backtest/{symbol}`'s `experiments` : `PIPELINE_DONCHIAN_FILTER`, `PIPELINE_WYCKOFF_FILTER`, additif, purement backtest — pas sur `/screener` ou `/decisions`).

---

## 4. Message court à coller

```
Handoff Claude 2026-09-16 (soir 2) — lis docs/HANDOFF-CLAUDE-SESSION-2026-09-16-SOIR2.md

Livré moteur : paper multi-classe (garde crypto-only levé), POST /decisions/batch (optionnel,
déjà branché par vous sur watch.ts), GET /correlations (CDC-VIZ-002, moteur only — UI à faire),
champ risk sur /screener et /decisions (atr/regime/suggested_stop_distance).
Option B tranchée avec l'user : PORTES = seul verdict d'action, BADGE = diagnostic seulement.
Action front prioritaire : démoter/relabelliser BADGE dans GateMatrix.tsx (§3) — laissé pour
vous exprès, pas touché par moi. Aucun changement API requis.
```

---

## 5. Fichiers touchés (session Claude)

```
ichivol-app/engine/app/api/routes.py
ichivol-app/engine/app/paper/engine.py
ichivol-app/engine/app/db/models.py
ichivol-app/engine/app/correlation/__init__.py
ichivol-app/engine/app/correlation/engine.py
ichivol-app/engine/tests/api/test_routes.py
ichivol-app/engine/tests/correlation/test_engine.py
ichivol-app/engine/README.md
ichivol-app/src/pages/DecisionsPage.tsx   (cleanup texte crypto-only, avant le chantier Cursor)
ichivol-app/src/pages/PaperPage.tsx       (cleanup texte crypto-only)
docs/CAHIER-DES-CHARGES.md
docs/HANDOFF-CLAUDE-SESSION-2026-09-16-SOIR2.md
```
