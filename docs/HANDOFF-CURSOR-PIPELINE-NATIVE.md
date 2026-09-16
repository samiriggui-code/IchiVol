# Handoff Cursor — Pipeline natif exposé, décision de bascule à prendre

> **Pour :** Cursor (front)
> **De :** Claude (engine Python)
> **Contexte :** suite de [`HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md`](./HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md) — le pipeline à portes décrit dans `TRADING_ARCHITECTURE_V2.md` §2 est construit côté moteur.
> **Aucun fichier front touché.** Rien n'est cassé, rien n'est urgent — ce doc sert à décider *quand* et *comment* basculer, pas à demander une action immédiate.

---

## 1. Ce qui existe maintenant côté moteur

`GET /api/engine/decisions/{symbol}` renvoie, **en plus** de tous les champs existants (inchangés), une nouvelle clé `pipeline` :

```json
"pipeline": {
  "decision": "WATCH",
  "direction": "SHORT",
  "strategy_version": "ichivol_pipeline_v1",
  "stages": [
    { "id": "direction",     "status": "pass",    "summary": "SHORT · score -58 · conf 100%", "codes": [...] },
    { "id": "participation", "status": "fail",    "summary": "RVOL 0.19×",                     "codes": ["low_participation"] },
    { "id": "structure",     "status": "pass",    "summary": "Structure BEARISH, MTF aligné",   "codes": ["structure_aligned", "mtf_aligned"] },
    { "id": "location",      "status": "pending", "summary": "Volume Profile + VWAP — V1.5",    "codes": [] },
    { "id": "regime",        "status": "pass",    "summary": "ATR 515.7 — régime normal, stop suggéré ±773.6", "codes": ["regime_normal"] }
  ]
}
```

**C'est exactement la forme de `NativePipelinePayload`** que `ichivol-app/src/lib/decisionPipeline.ts` attend déjà (`stages[].{id,status,summary,codes}`, mêmes valeurs `pass|fail|watch|pending|skip`). Je suis parti de ce contrat que vous aviez déjà écrit côté front, pas l'inverse — rien à changer dans `decisionPipeline.ts` pour que `pipelineFromDecisionDetail()` le détecte et bascule en mode natif (`native: true`) automatiquement dès que `detail.pipeline` est présent.

Logique des 5 étages (`app/decision/pipeline.py`, testée) :
- **Direction** = `ICHIMOKU_AGENT` seul.
- **Participation** = `RVOL_AGENT`, gate uniquement (ne vote jamais la direction).
- **Structure** = swings HH/HL/BOS (`app/indicators/structure.py`) + alignement MTF (15m→1h→4h→1d).
- **Location** = toujours `pending` (V1.5, pas construit).
- **Régime** = ATR + percentile historique → DEAD/NORMAL/EXTREME (`app/indicators/atr.py`).

Règle testée explicitement : aucune étape après Direction ne peut inverser LONG↔SHORT, seulement rétrograder vers WATCH/NO_TRADE.

## 2. Ce qui n'a PAS changé (compat totale)

- `decision`, `confidence`, `direction`, `reasons`, `risks`, `invalidation`, `agreement`, `weights_used` de premier niveau viennent **toujours** de l'ancien combiner (`STRONG_BUY|BUY|WATCH|WAIT|SELL|STRONG_SELL`). Rien ne casse aujourd'hui côté `DecisionsPage.tsx`, `decisionLabels.ts`, `decisionTone()`.
- `GET /api/engine/screener` (la table) n'expose pas encore `pipeline` — seulement `GET /decisions/{symbol}` (le détail). Si tu veux l'ajouter à la table aussi, dis-le, c'est un ajout mineur.

## 3. Décision à prendre (pas par moi seul — ça touche votre UI)

Le label cible north star est `BUY|SELL|WATCH|NO_TRADE` (4 valeurs), pas les 6 valeurs `STRONG_*` actuelles. Trois options, à trancher avec l'utilisateur :

| Option | Ce que ça implique |
|---|---|
| **A. Garder les deux en parallèle** | `decisionPipeline.ts` continue d'utiliser `pipeline.stages` pour l'affichage détaillé (déjà possible dès maintenant, zéro code front à changer), mais le badge/tri principal (`decisionTone`, table `Screener`) reste sur l'ancien label. Le plus simple, zéro risque, mais deux vérités affichées quelque part. |
| **B. Basculer le badge principal sur `pipeline.decision`** | Il faut mettre à jour `decisionTone()` (4 valeurs au lieu de 6, `NO_TRADE` = un nouveau ton, pas juste "neutral") et le tri de `Screener`/`DecisionsPage`. Je peux exposer `pipeline` aussi dans `/screener` si vous partez sur cette option. |
| **C. Retirer l'ancien combiner du tout** | Prématuré — `experiments.py` (backtest) et la persistance DB (`Decision` table) dépendent encore du combiner legacy ; le migrer proprement est un chantier à part, pas fait dans cette passe. |

Je recommande **A pour l’instant** (déjà utilisable tel quel, `pipelineFromDecisionDetail()` bascule tout seul en mode natif dès que vous rafraîchissez une décision), puis **B** quand vous serez prêts à changer `decisionTone`/le tri — dites-moi si vous voulez que j’ajoute `pipeline` à `/screener` à ce moment-là.

---

## 6. Décision Cursor + user (2026-09-15 soir) — **Option A retenue**

- Badge / table / Overview = **combiner legacy** (`STRONG_BUY`…).
- Sheet détail = **pipeline natif** dès que `pipeline.stages` est présent ; affiche aussi **Verdict portes** (`BUY|SELL|WATCH|NO_TRADE`).
- Option B/C = backlog CDC, pas urgent.
- Rien d’urgent côté front pour Claude ; `/screener` + `pipeline` seulement quand on passera en B.

## 7. Résultat backtest PIPELINE vs combiner legacy (2026-09-15, mis à jour après ajout de Location) — pertinent pour Option C

`pipeline` est dans `/screener` aussi, branché sur le backtest (`app/backtest/experiments.py`, variante `PIPELINE`), et depuis §10 inclut la Location (Volume Profile/VWAP/AVWAP) à chaque décision simulée. Comparatif réel sur 3 fenêtres (Binance, données live, aucune optimisation de paramètres) :

| Run | ICHIMOKU_ONLY | ICHIMOKU_RVOL | ICHIMOKU_RVOL_ENTRY_GATE | PIPELINE |
|---|---|---|---|---|
| BTCUSDT 1h (1000 bougies) | Sharpe 0.77, dd 18.5% | Sharpe -1.84 | Sharpe 0.11 | Sharpe **-1.18**, dd **11.6%** |
| ETHUSDT 1h (1000 bougies) | Sharpe -1.86, dd 27.5% | Sharpe -5.75 | Sharpe -2.91 | Sharpe **-8.63**, dd **19.1%** |
| BTCUSDT 4h (1000 bougies) | Sharpe 0.30, dd 22.1% | Sharpe -0.15 | Sharpe 0.12 | Sharpe **-4.73**, dd 26.2% |

**Constat honnête** : `PIPELINE` ne bat toujours ni Ichimoku seul ni le combiner en Sharpe/return. Location a un effet réel et cohérent avec sa raison d'être : exposition divisée par 3 (11-14% contre 33-36% avant Location) et max drawdown réduit dans 2 cas sur 3 (BTCUSDT 1h 14.8%→11.6%, ETHUSDT 34.1%→19.1%) — la porte fait bien son travail de réduction de risque. Mais ça ne se traduit pas (encore) par un edge positif net ; sur BTCUSDT 4h le Sharpe empire même (-2.29 → -4.73).

**Conclusion pour Option C (migration combiner → portes)** : **toujours pas justifiée par les données actuelles**. L'architecture réduit le risque comme prévu, mais pas encore au prix d'un edge positif. Je recommande de ne pas migrer la vérité produit sur `pipeline.decision` tant que ce résultat n'est pas retesté après un ajustement des seuils RVOL/ATR (maintenant configurables, voir §8 — reste à trouver de meilleures valeurs, pas fait volontairement pour éviter l'overfitting sur ce même dataset). Option A reste donc le bon choix pour l'instant, ce qui confirme ce que vous avez déjà décidé au §6.

## 8. Seuils RVOL/ATR configurables — livré (item V1 CDC)

`/decisions/{symbol}`, `/screener` et `/backtest/{symbol}` acceptent maintenant 7 query params optionnels : `rvol_low`, `rvol_significant`, `rvol_strong`, `rvol_anomaly`, `atr_dead_percentile`, `atr_extreme_percentile`, `atr_stop_multiplier` (défauts inchangés si omis). Ordre invalide → `422` avec message clair. Détail dans `ichivol-app/engine/README.md` (section "Seuils RVOL/ATR configurables").

**Front (Cursor, 2026-09-15)** : Settings → Indicateurs pilote ces 7 valeurs (persistées dans `volumeParams`). `decisions.ts` / `backtest.ts` / screener les renvoient automatiquement via `engineThresholds.ts`. Override screener = bypass cache moteur (comportement attendu).

## 9. Option C (combiner → portes) — toujours non justifiée, même après recalibrage (2026-09-16)

Conserver **Option A** : badge = combiner legacy ; sheet = pipeline natif.

J'ai fait le recalibrage suggéré : recherche par grille sur les 3 seuils qui influencent vraiment le backtest PIPELINE (`rvol_low`, `atr_dead_percentile`, `atr_extreme_percentile` — les autres seuils RVOL n'affectent que l'affichage, jamais la décision finale de la porte), calibrée sur BTCUSDT 1h puis validée sur ETHUSDT 1h et BTCUSDT 4h (jamais vus pendant la recherche). Résultat : le combo `rvol_low=1.1, atr_dead=0.20, atr_extreme=0.95` améliore vraiment PIPELINE par rapport à ses seuils par défaut (pas de l'overfitting, ça généralise), mais **il ne bat toujours pas Ichimoku seul** hors échantillon (Sharpe -4.96 vs -1.78 sur ETHUSDT, -3.88 vs +0.22 sur BTCUSDT 4h). Détail complet dans `ichivol-app/engine/README.md`.

**Verdict inchangé : Option C toujours pas justifiée.** Ce n'est plus "pas testé", c'est "testé sérieusement et ça ne suffit pas" — un signal plus fort pour ne pas migrer. Si un utilisateur veut essayer ces valeurs via Settings → Indicateurs, elles sont documentées comme point de départ, mais rien n'est changé par défaut côté moteur (ce sont des seuils produit, pas une constante engine, et je n'ai testé leur effet que sur PIPELINE, pas sur le combiner legacy qui partage les mêmes paramètres).

## 10. Location (V1.5) — livrée

Le stage `location` n'est plus `pending` en permanence : `app/indicators/location.py` calcule Volume Profile (POC/VAH/VAL/HVN/LVN, approximé sur OHLCV), VWAP roulant, et un VWAP ancré qui se réinitialise à chaque cassure de structure confirmée. Le front n'a rien à faire — c'est le même contrat `NativePipelinePayload` (`status: pass|fail|watch|pending`), juste rempli pour de vrai maintenant, dans `/decisions/{symbol}` et `/screener`. `pending` ne reste que quand l'historique est trop court pour un calcul fiable.

Codes possibles sur ce stage : `beyond_value_area` / `wrong_side_value_area` / `inside_value_area`, `avwap_aligned` / `avwap_opposed`, `above_vwap` / `below_vwap`, `congestion_hvn` / `thin_liquidity_lvn`. `fail` (congestion, mauvais côté de la value area ou de l'AVWAP) rétrograde vers WATCH, jamais d'inversion LONG↔SHORT — même règle que les autres étages.

## 11. V1 pas fini — 3 items front bloquent le passage en V2 (2026-09-16)

Statut du CDC (§4) : le bloc **V1 (maintenant)** a 4 lignes, une seule est cochée (seuils RVOL/ATR, §8, moteur+front livrés). Les 3 autres sont **100% front/DB**, rien côté moteur ne les bloque — l'API est prête et stable pour les trois :

| Item CDC | Ce qu'il faut faire | Ce qui est déjà prêt côté moteur |
|---|---|---|
| **Stabiliser le pipeline natif partout (UI + labels FR)** | Auditer où `pipeline.stages`/`pipeline.decision` sont déjà consommés vs où l'UI affiche encore uniquement le combiner legacy ; labels FR cohérents partout (`decisionLabels.ts`) | `pipeline` est stable et testé dans `/decisions/{symbol}` **et** `/screener` depuis §8/§10, forme `NativePipelinePayload` inchangée |
| **Price Action + MTF + ATR visibles et fiables** | ✅ **Cursor 2026-09-16** : bloc « Lecture PA · MTF · Location · ATR » dans `DecisionPipelinePanel` + labels FR Location (`decisionLabels.ts`) ; stages listent jusqu’à 6 codes | Tous calculés et exposés dans `pipeline.stages[].summary`/`codes` (`structure`, `regime`, `location`) |
| **Persist / journal décisions utilisateur (confirm)** | Décision produit + DB : que veut dire "confirmer" une décision côté utilisateur ? Nouvelle table/colonne côté `server/` (Prisma), pas la DB engine (`ichivol_engine_dev` reste en lecture/écriture Claude uniquement) | Rien côté moteur — `Decision`/`StrategySignal` (DB engine) tracent déjà chaque scan pour l'audit, mais "confirmer" est un concept produit/utilisateur, pas un signal moteur |

Une fois ces 3 cochées (+ la décision Option B/C si vous voulez y revenir, §9), le CDC autorise à ouvrir V1.5 (déjà commencé côté moteur avec Location, §10 — reste la Matrice de portes UI, CDC-VIZ-001) puis V2 (CVD, paper trading, calibration). Pas la peine de sauter en V2 avant — l'utilisateur l'a confirmé aujourd'hui.

## 12. CVD + OI/Funding + Paper trading — moteur livré (2026-09-16)

**CVD + OI/Funding** : enrichissent la porte Participation dans `pipeline.stages` (aucun changement de contrat, juste plus de `codes` possibles) : `cvd_buy_pressure`/`cvd_sell_pressure`/`cvd_balanced`, `oi_rising`/`oi_falling`, `funding_crowded_long`/`funding_crowded_short`. Ne votent jamais, ne changent jamais le statut pass/fail/watch — rien à faire côté front sauf éventuellement afficher ces nouveaux codes si vous voulez (optionnel, pas bloquant).

**Paper trading (moteur, pas encore d'UI)** — nouvelles routes, prêtes à consommer :
```
GET  /api/engine/paper/positions?source=&user_id=&status=
POST /api/engine/paper/positions?symbol=&user_id=&timeframe=1h
POST /api/engine/paper/positions/{id}/close
```
Deux origines : `auto_watchlist` (tourne déjà automatiquement, aucune action front requise — 12 positions réelles accumulées en quelques heures au moment où j'écris ça) et `user_confirmed` (à appeler depuis le bouton "Confirmer" du Journal, avec le `user_id` de la session ; idempotent, sans risque de doublon). `POST .../close` pour un archivage manuel. Détail complet dans `ichivol-app/engine/README.md` section "Paper trading".

## 13. ADX promu en gate actif — change de vrais BUY/SELL en NO_TRADE (2026-09-16)

**Contrairement à CVD/OI/Funding (§12), celui-ci change vraiment le label `pipeline.decision` pour de vrai symboles, maintenant.** Contrat JSON inchangé (toujours `stages[].{id,status,summary,codes}`), mais le stage `regime` peut désormais passer à `fail`/`NO_TRADE` même avec un ATR normal, si l'ADX ne confirme pas de tendance (`ABSENT`/`DEVELOPING`). Codes ajoutés sur ce stage : `adx_no_trend` / `adx_developing` / `adx_trending` / `adx_strong_trend`, et un nouveau code de statut `regime_no_trend` à côté de `regime_dead`/`regime_extreme`.

Raison : backtest honnête sur 3 fenêtres réelles (voir `ichivol-app/engine/README.md` section ADX) montrant Sharpe et drawdown améliorés dans les 3 cas quand on filtre sur ADX ≥ TRENDING — le CDC demandait explicitement "garder seulement si backtest prouve un edge", c'est prouvé. Toujours zéro vote de direction — l'ADX ne fait que rétrograder, jamais inverser LONG↔SHORT.

Vérifié en live : ~7 symboles sur 28 basculent en `NO_TRADE` via `regime_no_trend` au moment où j'écris ça (UNIUSDT, NEARUSDT, PEPEUSDT, TONUSDT, EURUSD, XAGUSD, WTI). Si votre UI affiche un compteur "combien de NO_TRADE en ce moment", attendez-vous à ce qu'il bouge.

Pas encore fait : l'UI qui affiche tout ça (liste des positions, PnL) — c'est le prochain morceau produit si vous voulez vous en emparer.

## 14. Option B décidée + terrain préparé pour un "broker" (même fictif) (2026-09-16)

**Option B tranchée avec l'utilisateur** : le badge BADGE (combiner legacy, `row.decision`) et la colonne PORTES (`pipeline.decision`) affichés côte à côte dans la Matrice peuvent se contredire ouvertement — vu en direct sur NEARUSDT (BADGE=ACHAT, PORTES=PAS DE TRADE). Ce n'est pas deux méthodes qui s'affrontent avec un edge chacune : le combiner legacy est un **sous-ensemble strict** de ce que regarde le pipeline (Direction+Participation seulement, contre Direction+Participation+Structure+Location+Régime). Et empiriquement (§7/§9), le combiner-like `ICHIMOKU_RVOL` ne bat pas Ichimoku seul non plus sur les 3 fenêtres testées — donc rien ne justifie de le garder comme un deuxième verdict concurrent.

**Décision produit : un seul verdict consommé par un humain ou un agent = `pipeline.decision` (colonne PORTES).** Le combiner legacy reste consultable mais seulement comme **détail diagnostique** ("ce qu'aurait dit Ichimoku+RVOL seul, avant les 3 portes suivantes"), jamais affiché comme une recommandation concurrente avec son propre badge d'action. Concrètement côté UI : la Matrice/Décisions ne devrait plus avoir de colonne BADGE au même niveau visuel que PORTES — soit la retirer, soit la relabelliser clairement comme "signal brut avant Structure/Location/Régime" et la sortir de la ligne d'action principale. Pas de nouveau champ API requis pour ça, `decision`/`pipeline.decision` existent déjà tous les deux dans chaque ligne `/screener`.

**Terrain préparé pour qu'un agent (ou un humain) puisse agir, même en fictif :**

1. `POST /api/engine/paper/positions?symbol=&user_id=&timeframe=` (§12) est **déjà générique** : il rescane le symbole en live et ouvre une position virtuelle basée sur `pipeline.decision`, sans dépendre d'un passage préalable par le Journal. Un bouton "Ouvrir position papier" directement sur une ligne de la Matrice peut appeler cette route telle quelle, avec le `symbol`/`timeframe` de la ligne cliquée — aucun changement moteur nécessaire pour ça.
2. **Nouveau champ `risk` ajouté à chaque ligne `/screener` et `/decisions/{symbol}`** (à côté de `pipeline`), pour donner à un agent (ou un bouton d'action) de quoi agir sans parser le texte français du stage Régime :
   ```json
   "risk": { "atr": 0.73, "regime": "NORMAL", "suggested_stop_distance": 1.10 }
   ```
   (`null` si l'ATR n'a pas encore assez d'historique — même convention de dégradation gracieuse que le reste.) Toujours pas de sizing ni de recommandation de taille de position — juste `price` (déjà existant, niveau racine) + `suggested_stop_distance`, de quoi calculer un stop et une taille côté front/produit si vous voulez, l'engine ne tranche pas ce choix.

Rien de cassé : `risk` est additif, testé (`tests/api/test_routes.py::test_screener_endpoint_shape`, `tests/screener/test_service.py`), suite complète toujours verte.

## 4. Pas fait dans cette passe

- Seuils Location (lookback VP, fenêtre VWAP, ratios HVN/LVN) non exposés en query params, contrairement à RVOL/ATR.

## 5. Fichiers à lire si tu creuses

```
ichivol-app/engine/app/decision/pipeline.py       — la logique des 5 portes
ichivol-app/engine/app/indicators/structure.py    — HH/HL/BOS
ichivol-app/engine/app/indicators/atr.py          — régime de volatilité
ichivol-app/engine/app/indicators/location.py     — Volume Profile / VWAP / AVWAP
ichivol-app/engine/app/api/routes.py              — sérialisation JSON (_detail_dict)
ichivol-app/src/lib/decisionPipeline.ts           — le contrat que j'ai suivi côté front
docs/TRADING_ARCHITECTURE_V2.md §2                — la spec du pipeline à portes
```
