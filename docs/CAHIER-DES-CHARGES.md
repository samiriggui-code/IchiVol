# IchiVol — Grand cahier des charges

**Statut : VIVANT** — document maître produit (à enrichir, pas à dupliquer).  
**Dernière maj :** 2026-09-16  

Les décisions **verrouillées** vivent dans les docs listées ci-dessous. Ce CDC **orchestre** : vision, périmètre, backlog, hors-scope.

| Doc north star | Contenu |
|----------------|---------|
| [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) | 5 questions, pipeline à portes, data ≠ execution |
| [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md) | Méthodes CORE → V3 |
| [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) | Feeds gratuits, adapters |
| [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md) | Pages front + rôles LLM |
| [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md) | StrategyAgents ≠ Copilot |
| [`OPTIONS-ABC.md`](./OPTIONS-ABC.md) | Glossaire Option A/B/C (combiner vs portes) — **lire avant tout handoff « Option C »** |
| [`HANDOFF-CURSOR-SESSION-2026-09-16.md`](./HANDOFF-CURSOR-SESSION-2026-09-16.md) | État front session (seuils, multi-classe, journal) |
| [`HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md`](./HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md) | Soir : Matrice, watch+cloche, explain_decision, LLM table |
| [`HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md`](./HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md) | Alerte Claude — échelle V1→V3, agents, watch Journal |
| [`HANDOFF-CLAUDE-SESSION-2026-09-16-SOIR2.md`](./HANDOFF-CLAUDE-SESSION-2026-09-16-SOIR2.md) | Soir 2 : paper multi-classe, `/decisions/batch`, `/correlations` — état constaté refonte notifs Cursor |

---

## 1. Vision produit

> Ichimoku trouve la direction, RVOL exige la participation, la location dit si l’emplacement est bon, ATR mesure le régime/risque — le reste confirme ou invalide, jamais ne dilue en salade de votes.

IchiVol = **cockpit multi-marchés** (crypto d’abord, puis forex / métaux / indices / actions via adapters) : screener + chart + décision structurée + journal + paper (V2).  
**Pas** une usine à indicateurs, **pas** une app broker Binance, **pas** un clone Grace/GRC.

---

## 2. Chaîne d’analyse (moteur)

```
Direction → Participation → Structure/MTF → Location → Régime/Risque
        → BUY | SELL | WATCH | NO_TRADE  (portes)
        → badge table = combiner legacy tant que Option A
```

| Question | Couche | CORE |
|----------|--------|------|
| Où va la structure ? | Ichimoku (+ PA / MTF) | V1 |
| Est-ce participé ? | RVOL (+ CVD / OI-Funding crypto V2) | V1 |
| Où est le prix ? | VP / VWAP / AVWAP | V1.5 |
| Tradable ? | ATR | V1 |
| Taille / stop ? | ATR + risk caps | V1.5–V2 |

### 2.1 Deux couches « agents » (figé)

| Couche | Qui | Rôle | LLM ? |
|--------|-----|------|-------|
| **A. StrategyAgents** | Python `engine/app/agents/` + indicateurs | Calculent la décision (pipeline à portes) | **Non** |
| **B. Copilot** | TS `server/src/agent/` + chat UI | Expliquer, citer KB, skills **confirmés** | **Oui** |

**Règle :** le moteur décide ; le LLM explique / alerte. Jamais l’inverse. Détail : [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md).

---

## 3. Cartographie pages (direction UI)

| Page | Job |
|------|-----|
| Overview | Santé cockpit + teaser macro crypto |
| Marché | Chart + univers multi-classe + pipeline moteur |
| Contexte | Climat **crypto** (CoinGecko + F&G) — ne vote pas ; pas encore multi-marchés |
| Décisions | Screener multi-classe + sheet ; **Confirmer → Journal + Paper** (crypto) |
| Journal | Trace Prisma des confirmations · V2 : watch + notifs cloche |
| Paper | Positions virtuelles + perf (auto screener / mes confirms) |
| Backtests | Comparatif Ichimoku / RVOL / PIPELINE (univers câblé) |
| Settings | Clés LLM, seuils RVOL/ATR, sources |

Détail : [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md).

---

## 4. Échelle de versions (officiel — **pas de « V2+ »**)

Il n’existe **pas** de jalon nommé « V2+ » dans ce CDC. L’ordre est strictement :

| Version | Intention |
|---------|-----------|
| **V1** | Pipeline natif usable, labels FR, seuils, journal confirm (snapshot) |
| **V1.5** | Location + Matrice de portes UI (Décisions) |
| **V2** | Paper + perf + watch/notifs + Copilot enrichi ; CVD/OI crypto (moteur déjà amorcé) |
| **V3 / expérimental** | Méthodes additionnelles + consensus multi-agents **après preuve** |
| **Hors cœur** | Broker live hardcodé, salade d’indicateurs, multi-personas LLM qui votent |

---

## 5. Backlog priorisé

### Fait / en cours

- [x] Auth + Settings LLM  
- [x] Engine Ichimoku + RVOL + screener + decisions API  
- [x] Pipeline UI 5 portes (natif quand engine expose `pipeline`)  
- [x] **Marché branché moteur** : panneau Lecture = pipeline natif + colonne Moteur (crypto) ; univers multi-classe  
- [x] **Option A** dual label : badge table = combiner legacy ; verdict portes = `pipeline.decision`  
- [x] Overview branchée screener  
- [x] Contexte = détail Overview (top marchés, F&G 7j) — crypto only  
- [x] Décisions : sheet scrollable + filtres/tri + onglets classe  
- [x] Backtests : colonnes PIPELINE + univers multi-classe  
- [x] Journal page `/app/journal` (séparé de Décisions)  
- [x] Pipeline étages Structure/MTF/Location/ATR exposés moteur  
- [x] **Option B tranchée (2026-09-16)** : un seul verdict consommé par un humain ou un agent = `pipeline.decision` (colonne PORTES) ; le combiner legacy (BADGE) reste consultable seulement comme détail diagnostique, plus comme badge d'action concurrent. Raison : ce n'est pas deux méthodes avec un edge chacune — BADGE est un sous-ensemble strict de PORTES (Direction+Participation seulement) et ne bat pas Ichimoku seul en backtest non plus. Reste **front à faire** (Cursor) : retirer/relabelliser la colonne BADGE dans la Matrice — voir `docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md` §14.  
- [ ] Combiner × → portes comme seule vérité produit (Option C — **toujours non justifiée**, revérifié sur sweep élargi 2026-09-16 : 24 runs (12 symboles × 1h/4h), `PIPELINE` avec gate Donchian bat `ICHIMOKU_ONLY` en Sharpe sur seulement 11/24 — pas un edge. En revanche drawdown réduit dans **24/24 sans exception** (moyenne 30.1%→5.1%) : argument produit solide pour `PIPELINE` comme moteur de gestion du risque, pas comme générateur d'edge de rendement. Voir `ichivol-app/engine/README.md` §Sweep élargi.)
- [x] **Terrain broker préparé (2026-09-16)** : `POST /api/engine/paper/positions` est déjà générique (rescane en live, ouvre sur `pipeline.decision`, aucune dépendance au Journal) — un bouton d'action sur une ligne de la Matrice peut l'appeler directement. Nouveau champ `risk: {atr, regime, suggested_stop_distance}` ajouté à chaque ligne `/screener` et `/decisions/{symbol}` pour donner à un agent/bouton de quoi agir sans parser le texte du stage Régime. Pas de sizing ni de brocker réel — juste les ingrédients (`price` + `suggested_stop_distance`). Voir `docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md` §14.

### V1 (maintenant) — bouclé côté intent

- [x] Stabiliser decision pipeline natif partout (UI + labels FR) — sheet + BiasPanel ; labels Location ; lecture PA/MTF/ATR  
- [x] Price Action + MTF + ATR visibles et fiables  
- [x] Persist / journal décisions utilisateur (confirm) — API Prisma + page Journal  
- [x] Seuils RVOL/ATR configurables Settings  

### V1.5

- [x] Volume Profile + VWAP / AVWAP (location) — moteur livré  
- [x] Matrice de portes (voir §6.1) — vue Liste | Matrice sur Décisions (`GateMatrix`)  

### V2

**Moteur / data (crypto-first pour dérivés) :**

- [x] CVD + OI/Funding — enrichissent Participation, ne votent jamais (crypto Binance) ; backtest OI/Funding encore partiel  
- [x] Paper trading (moteur) — `app/paper/engine.py`, table `paper_positions` (positions virtuelles, jamais un ordre réel). Deux origines : `auto_watchlist` (auto sur le cycle screener) et `user_confirmed` (déclenché par le serveur depuis le Journal). Routes `GET/POST /api/engine/paper/positions`, `POST .../close`. Vérifié en live. Voir `ichivol-app/engine/README.md`.  

**Produit / UI :**

- [x] Paper trading UI — `/app/paper` + `lib/paper.ts` ; confirm Décisions → journal + `POST paper/positions` (crypto) ; proxy Express POST `/api/engine/*`  
- [x] Performance affichée sur Paper (`GET /paper/performance`) — calibration seuils = plus tard ; redémarrer le moteur si 404  
- [x] Graphe corrélations (voir §6.2) — moteur + UI (2026-09-16) : `GET /api/engine/correlations` + `CorrelationHeatmap` sur `/app/context` (crypto Binance, Focus + matrice Pearson, lecture seule, hors pipeline).  
- [x] **Journal watch + notifications header** (voir §6.3) — table Prisma + cloche + job poll 5 min  
- [x] Copilot enrichi : skill « Expliquer cette décision » (`explain_decision` + boutons Décisions/Journal)  
- [x] Multi-marchés V2 : paper sur forex·métaux·actions — garde crypto-only levé dans `POST /api/engine/paper/positions` (2026-09-16, voir `ichivol-app/engine/README.md` §Paper multi-classe) ; `auto_watchlist` couvrait déjà biquote (forex/métal/index/énergie) sans qu'on l'ait noté. Contexte multi-actifs (page dédiée) reste backlog ultérieur, pas bloquant.
- [x] `POST /decisions/batch` — endpoint optionnel livré (2026-09-16) pour que le job watch Journal fetch ses symboles confirmés en un appel concurrent au lieu de N×1 (voir `ichivol-app/engine/README.md` §`POST /decisions/batch`) ; pas encore branché côté server (optionnel tant que le poll actuel reste rapide).

### V3 / expérimental

- [x] ADX — moteur livré (`app/indicators/adx.py`), backtesté honnêtement (3 fenêtres réelles, filtre ADX≥TRENDING) : Sharpe et drawdown améliorés dans les 3 tests → edge prouvé → **promu en gate actif** dans `_regime_stage` (régime normal mais tendance non confirmée → NO_TRADE, ne vote jamais la direction). Ne bat pas le verdict Option C (PIPELINE toujours sous Ichimoku seul dans l'absolu). Voir `ichivol-app/engine/README.md`.  
- [x] **Synthetic Market Lab** (2026-09-16) — générateur seedé (`app/synthetic/generator.py`) + 5 scénarios catalogués bullish/bearish/faux breakout/bullish-volume-faible/range (`app/synthetic/scenarios.py`) + moteur de validation (`app/synthetic/validation.py`) qui rejoue le VRAI pipeline (mêmes fonctions que `screener/service.py`) sur des données fabriquées dont le ground truth est connu à l'avance mais jamais transmis au moteur. But : détecter les faiblesses d'interprétation avant les données réelles, pas remplacer le backtest historique. 14 tests verts (`tests/synthetic/`) ; a déjà servi une fois en conditions réelles : a révélé qu'un générateur trop bruyant produisait de vrais retournements locaux (le moteur avait raison, le scénario était mal calibré) et que la classification de régime ATR compare un ATR **absolu** à son propre historique (pas ATR/prix) — une tendance qui compound fort peut dériver vers EXTREME par la seule croissance du prix, sans vraie expansion de volatilité relative. Noté comme limite connue, pas corrigé (hors scope de ce chantier).  
- [x] Wyckoff / Donchian — **backtestés (2026-09-16)**. **Donchian** (`app/indicators/donchian.py`) : 3 fenêtres initiales déjà prometteuses (drawdown amélioré dans les 3, Sharpe sur 2/3) → **promu en gate actif** dans `app/decision/pipeline.py::_regime_stage` par décision produit explicite (pas le "3/3 sans exception" strict d'ADX, mais jugé suffisant). Revalidé ensuite sur un sweep élargi (24 runs, 12 symboles × 1h/4h) : ne bat toujours pas Ichimoku seul en Sharpe (11/24), mais réduit le drawdown dans **24/24 runs sans exception** (30.1%→5.1% en moyenne) — argument produit solide comme moteur de gestion du risque. **Wyckoff** (`app/indicators/wyckoff.py`, spring/upthrust, "logique maison") : pas d'edge démontré (pire sur 2/3 fenêtres) → **pas promu**, reste en backtest seul (`PIPELINE_WYCKOFF_FILTER`). Détail : `ichivol-app/engine/README.md` §Donchian + Wyckoff et §Sweep élargi.  
- [x] **Agent command channel READ v1** (2026-09-16) — `app/agent_channel/` : `GET /agent/tools`, `GET /agent/capabilities` (stub), `POST /agent/command` `{cmd,args}`, `POST /agent/batch` (max 20, concurrent, ordre stable). Allowlist de 9 commandes read-only (`scan_market`, `get_symbol_context`, `detect_signal`, `compare_timeframes`, `run_backtest`, `get_correlations`, `calculate_ichimoku`, `calculate_rvol`, `list_tools`), toutes des wraps de fonctions déjà existantes/testées — zéro LLM, zéro nouvelle logique de décision. Payloads identiques à `/screener`/`/decisions`/`/backtest`/`/correlations`. WRITE (paper) explicitement hors scope de ce lot. Pas de front, pas de Copilot dans ce lot — Cursor branche son client en parallèle sur ce contrat. 14 tests (`tests/api/test_agent_channel_routes.py`), suite complète verte (330). Détail : `ichivol-app/engine/README.md` §Agent command channel.  
- [x] **Adapters context (news/calendrier), opt-in** (2026-09-16) — `app/context/news.py` (RSS CoinDesk+CoinTelegraph, gratuit/sans clé) + `app/context/calendar.py` (flux JSON communautaire ForexFactory, gratuit/sans clé). Best-effort : une panne réseau dégrade vers une liste vide, jamais une exception. Routes `GET /context/news`, `GET /context/calendar` + commandes agent `get_news`/`get_calendar`. **`app/decision/pipeline.py` n'importe ni l'un ni l'autre — zéro vote, zéro effet sur Ichimoku×RVOL**, exactement la règle demandée. Vérifié en live contre les vrais flux. 11 tests (`tests/context/`). Détail : `ichivol-app/engine/README.md` §Adapters contexte.  
- [x] **T0-CALC — scénarios historiques paper** (2026-09-23) — `app/paper/scenarios.py` : Objectif/Stop = `preview_manual_buy` ; Crash = pire mouvement adverse causal ; durée/espérance via PIPELINE `net_v2` (n≥30) ; API preview + `positions/{id}/scenarios` ; UI fiche d’achat + Synthèse. **Pas une prévision.** PR #25.
- [x] **Event Intelligence — audit architecture** (2026-09-23) — `docs/EVENT-INTELLIGENCE-LAYER-AUDIT.md` : EVENT≠SIGNAL ; KEEP/ADAPT/REJECT repos externes ; contrats. PR #26.
- [x] **Event Intelligence — Anomaly Detector PHASE 5** (2026-09-23) — `app/events/` : features causales (`return_z`, `volume_z`, range/gap vs ATR, RVOL) ; régimes `NORMAL` / `UNKNOWN_EVENT` (sans news) ; exposé en `market_anomaly` sur décisions/screener **sans toucher** `_final_decision`. Seuils `event_anomaly_v0_placeholder` à calibrer. Tests anti-lookahead `tests/events/`.
- [x] **Event Intelligence — PHASE 6 research harness** (2026-09-23) — `regime_study.py` : event-study PIPELINE stratifié NORMAL vs UNKNOWN_EVENT (MFE/MAE/horizons) ; `calibrate.py` : suggestions p99 **sans** appliquer ; agent `run_anomaly_regime_study` / `calibrate_anomaly_thresholds`. **Ne change aucune gate.**
- [x] **Event Intelligence — PHASE 7 correlate** (2026-09-23) — SymbolNews + classifier heuristique + macro calendar → `correlate_events` ; promotion `UNKNOWN_EVENT` → `EVENT_MARKET` si match causal (pub ≤ T) ; exposé `event_context` + agent `get_event_context`. **Ne change aucune gate / pas de vote.** Seuils live + FinBERT + corporate provider = plus tard.
- [x] **T4c — WHY ENTERED / REJECTED / EXITED** (2026-09-23) — traces conditions sur overlay backtest (explainability only ; golden fills inchangés). PR #31.
- [x] **T4b — filtre overlay structuré** (2026-09-23) — agent `filter_backtest_overlay` + API exit_reason/direction/why_entered_key (pas de chat NL). PR #32.
- [x] **T4d — filtre régime overlay** (2026-09-23) — `regime_labels` au signal + filtre `regime_label`. PR #33.
- [x] **T5a — family weights observation** (2026-09-23) — config versionnée + `family_weights` sur décisions ; **ne change pas** decision/confidence. PR #34.
- [x] **T5b — profils poids backtestables** (2026-09-23) — catalogue + compare + étude forward ; observation only. PR #35.
- [ ] **T6 — AuditReport** (en cours) — post-outcome ; hypothèses `proposed` only.
- [x] **Collecte automatique de preuve backtest (condition 1 du gate broker live)** (2026-09-17) — `app/backtest/evidence.py` : job d'arrière-plan (même pattern que `ScreenerCache`, pas de conteneur cron) qui relance `experiments.compare()` sur tout l'univers crypto × [1h,4h] et persiste dans `backtest_snapshots`, pour qu'une tendance devienne visible sans script manuel. **Ne décide jamais rien** — logue seulement, un humain/Claude juge si c'est une preuve. `GET /api/engine/backtest/evidence` alimente la tuile Overview "Preuve edge (C1)" (construite en parallèle par Cursor, contrat JSON convergé indépendamment des deux côtés). Vérifié en live : 865 lignes, `pipeline_beats_ichimoku_sharpe: 20/40` (~50%, cohérent avec le reste de la nuit — pas d'edge de rendement). 9 tests. Détail : `ichivol-app/engine/README.md` §Collecte automatique de preuve backtest.  
- [x] **Notifications système : watchdog santé + digest quotidien** (2026-09-17) — `ichivol-app/server/src/notifications/{systemWatchdog,digest}.ts`, même pattern `setInterval` que le job watch Journal, aucun vote/décision. Watchdog : ping le même check que `GET /api/health` (DB + moteur) toutes les 5 min, alerte seulement sur **changement d'état** (jamais de spam pendant que ça reste cassé). Digest : résumé quotidien des 2 conditions du gate broker live (paper trading + preuve backtest). Les deux créent une notification in-app (cloche header, nouveaux `kind: system_alert | system_digest`) **et** un email optionnel (SMTP configurable, template React Email rendu via `@react-email/render`) si `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` sont renseignés — sinon dégrade silencieusement, jamais d'exception. `GET /api/health` durci au passage : teste vraiment DB + moteur (`checks: {database, engine}`, HTTP 503 si l'un est down) au lieu de renvoyer `{ok:true}` inconditionnel — nécessaire pour qu'un monitor externe (UptimeRobot etc.) détecte un vrai incident. Détail : `ichivol-app/server/README.md` §Notifications système.  
- [ ] Consensus multi-agents StrategyAgents — **seulement après preuve** backtest (pas de bureau multi-LLM)  
- [ ] Live execution adapter (venue au choix) — **gate explicite, décision produit 2026-09-17**, les 3 conditions doivent être réunies avant d'ouvrir ce chantier (pas juste "après paper + preuve" vague) :
  1. **Edge de rendement prouvé** par backtest honnête (Sharpe/CAGR net qui bat Ichimoku seul dans l'absolu) — une réduction de drawdown seule (cas actuel de Donchian/ADX) **ne suffit pas**.
  2. **Historique de paper trading stable sur la durée** (pas un test ponctuel) — le paper doit avoir tourné et prouvé sa fiabilité en conditions réelles avant qu'on lui fasse confiance avec du vrai capital.
  3. **Architecture adaptateur propre**, jamais câblé en dur sur un exchange précis — même contrat d'interchangeabilité que `MarketDataProvider` (`app/market_data/provider.py`), pas un raccourci Binance-only.

  Jamais confondre avec MarketData (data ≠ lieu d'exécution, §7). Tant que les 3 conditions ne sont pas réunies simultanément, ce chantier reste fermé — pas oublié, délibérément mis de côté.  

### Hors cœur (pas de vote auto)

RSI, MACD, Stochastic, CCI, salade d’indicateurs, broker Binance hardcodé, multi-personas LLM qui votent la direction.

---

## 6. Item backlog — Graph / Matrix / Watch

**Décision produit (2026-09-15) :**

> Le concept Graph/Matrix (réf. Grace *Asset Relationships*) est **pertinent seulement réinterprété** (corrélations marché / états du pipeline). **Pas** d’import de topologie GRC.

### 6.1 Matrice de portes (V1.5)

| Champ | Contenu |
|-------|---------|
| **Quoi** | Grille symboles × portes — pastilles OK / BLOQUÉ / PRUDENCE / BIENTÔT |
| **Pourquoi** | Lecture rapide multi-paires sans ouvrir chaque sheet |
| **Où** | Page Décisions (vue “Matrice”) ou Overview |
| **Dépend de** | Pipeline natif stable + API screener enrichie (status par stage) |
| **Pas** | Force-directed graph, nested boxes Grace |

### 6.2 Graphe de corrélations (V2 optionnel)

| Champ | Contenu |
|-------|---------|
| **Quoi** | Nœuds = symboles ; arêtes = corrélation / co-mouvement |
| **Pourquoi** | “Qu’est-ce qui bouge avec BTC ?” |
| **Où** | Contexte ou sous-vue Marché |
| **Dépend de** | Historique OHLCV en DB + calcul Python |
| **Pas** | Topologie d’actifs non-marché |
| **Statut** | Moteur + UI livrés (2026-09-16) : `GET /api/engine/correlations` + `CorrelationHeatmap` sur Contexte (crypto only — overlap horaires FX/indices trop faible pour une matrice globale). |

### 6.3 Journal watch + notifications header (V2 — intent 2026-09-16)

**Décision produit :**

> Aujourd’hui le Journal = **snapshot figé**. En V2 : les entrées **confirmées** deviennent une **watchlist active**. Un **job serveur** (cron / worker — **pas** le LLM qui vote) re-lit le pipeline sur ces symboles+TF. Changement matériel → **notification cloche header**. Aussi : notif à chaque nouvel enregistrement journal.

| Champ | Contenu |
|-------|---------|
| **Quoi** | (1) Notif à la confirm · (2) Agent watch sur `status=confirmed` · (3) Inbox cloche |
| **Pourquoi** | Alerter **sur tes sélections**, pas sur tout le screener |
| **Où** | Header `IconBell` + Journal |
| **Dépend de** | Journal Prisma (fait) · engine decisions · table `notifications` (Prisma server) · job poll |
| **Règles** | Observe / explique / alerte — **ne vote pas**. Pas d’ordre broker. Inbox in-app d’abord (pas mobile/email en V2.0) |
| **Lien** | Même panier → Paper trading ; watch+notif peut livrer **avant** le paper |

### 6.4 Explicitement hors scope Graph/Matrix

- Clone UI Grace / GRC asset graph  
- Matrice de couverture “protects / monitors”  
- Remplacer le pipeline linéaire par un graphe d’étapes  

**Tickets :** `CDC-VIZ-001` Matrice portes · `CDC-VIZ-002` Graphe corrélations · `CDC-WATCH-001` Journal watch + notifs.

---

## 7. Données & exécution

- Market data : Binance Vision (crypto) · Biquote (FX/métaux/indices) · Twelve Data (equities) — **≠** lieu d’exécution  
- Indicateurs : **toujours** calculés en Python  
- Contexte macro page : **crypto only** pour l’instant  
- Live trading : hors scope jusqu’à paper + preuve  

Voir [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md).

---

## 8. Critères d’acceptation produit (rappel)

1. Un signal Ichimoku sans RVOL suffisant ≠ trade actionnable.  
2. ATR / Location / CVD / OI ne votent pas LONG/SHORT.  
3. LLM n’invente pas OHLC / RVOL ; n’exécute pas d’ordre.  
4. Paper avant live.  
5. Pas de salade RSI/MACD en votes.  
6. Pas de jalon « V2+ » — seulement V1 → V1.5 → V2 → V3.

---

## 9. Comment faire vivre ce CDC

1. Toute nouvelle idée → une ligne backlog ici **avant** code.  
2. Si ça contredit une north star → mettre à jour la north star **d’abord** (avec accord user).  
3. Handoffs Claude/Cursor pointent ici pour le “quoi construire ensuite”.  
4. Ne pas inventer de versions intermédiaires (« V2+ ») : étendre **V2** ou ouvrir **V3**.
