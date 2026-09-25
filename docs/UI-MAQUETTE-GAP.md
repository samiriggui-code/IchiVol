# UI — écarts maquette ↔ React (UI-11p)

**Date** : 2026-09-25  
**Maquette** : `design-reference/ichivol-workspace/` (`app.js`, `style.css`, `world-map.svg`, `index.html`)  
**React** : `ichivol-app/src/pages/*`, chrome `layouts/DashboardShell.tsx`, routes `lib/workspaceNav.ts`  
**Lib / API** : chemins réels sous `ichivol-app/src/lib/*.ts` (proxy `/api/…`)

### Règles rappel

- Pas de données de démonstration inventées côté React.
- Ne pas copier `app.js` dans le front ; porter l’intention UI, brancher le moteur / le serveur existants.
- `engine/` et `server/` intouchables dans le cadre de ce portage UI (lecture seule pour inventaire).
- Préférer les endpoints déjà exposés ; si aucune source : « aucune donnée → à décider ».

### Chrome (hors pages, pour contexte)

| Élément maquette | React (`DashboardShell`) | Statut |
|---|---|---|
| Sidebar 4 groupes Trading / Recherche / Automatisation / Système | `NAV_GROUPS` dans `workspaceNav.ts` | présente |
| Badge moteur + pill PAPER · DÉMO | `LlmHeaderBadge` + kill switch ; pas de pill « DEMO » | partielle |
| Arrêt d’urgence | `KillSwitchButton` / `KillLockBanner` | présente |
| Lien Paramètres + avatar | menu utilisateur + lien Paramètres | présente |
| Footer « données démo · bougies 1H » | absent | absente |
| Breadcrumb WORKSPACE / page | eyebrow par page (`iv-page-eyebrow`) | partielle |
| Tab bar mobile Desk · Opportunités · Portefeuille · Copilot · Plus | `MOBILE_PRIMARY_*` | présente |

---

## Par page

### Desk (maquette → OverviewPage)

Route React : `/app/desk` · `OverviewPage.tsx`  
APIs : `GET /api/engine/screener`, `GET /api/engine/paper/portfolios/{code}/overview`, `GET /api/engine/activity/summary`, `GET /api/engine/activity/feed`, `GET /api/engine/backtest/evidence`, `GET /api/engine/paper/portfolios` ; aperçu crypto via `ContextPanel` → CoinGecko / Fear & Greed (proxies `/coingecko`, `/feargreed`).

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **KPIs** Capital total / Disponible / P&L du jour / Risque utilisé | partielle | bloc « Capital · BASELINE » + métriques tête (libellés différents : marchés, opportunités, WATCH…) | `/api/engine/paper/portfolios/{code}/overview` ; compteurs screener |
| **Sessions de marché** (carte monde + Tokyo / Londres / NY) | absente | — | aucune donnée → à décider (horaires sessions ; `world-map.svg` maquette) |
| **Marchés principaux** (tickers + lien Marché) | absente | — (proche : Top opportunités / Livre live) | `/api/engine/screener` ou `/api/engine/universe` + OHLCV |
| **Lecture du marché** (régime, volatilité, dominance BTC, concentration) | partielle | `ContextPanel` compact en bas de page | `/coingecko/api/v3/global`, `/feargreed/fng/` ; régime concentration : aucune donnée → à décider |
| **Trajectoire du portefeuille** (courbe + périodes 1J/1S/1M/3M) | partielle | `EquitySpark` sur overview paper (sans sélecteur de période) | `equity_curve` dans overview paper |
| **À surveiller** (liste opportunités + lien) | présente | « Top opportunités » / « Livre live · 1h » | `/api/engine/screener` |
| **Notice fraîcheur données** (ex. TONUSDT périmé → Opérations) | absente | — | aucune donnée → à décider (qualité / staleness par symbole) |
| **Positions ouvertes** (table + lien Portefeuille) | présente | « Livre ouvert » | overview paper `positions` |
| **Votre budget de risque** (progress exposition / jour / slots) | partielle | KPI « Risque engagé » ; détail dans Portefeuille → Risque | `overview.risk` (`open_risk_*`, positions) |
| **Derniers événements** (timeline) | présente | « Tape » | `/api/engine/activity/feed` |
| **Le prochain contrôle** (checkpoint clôture 1H, RVOL BTC) | absente | — | partielle via screener / décision symbole ; packaging « prochain contrôle » → à décider |
| **État du système** (moteur, source, Risk Kernel, exécution réelle) | absente | erreur moteur si 502 ; LLM badge dans le shell | santé moteur : implicite ; Risk Kernel / lock : `/api/engine/paper/portfolios/{code}/risk-lock` (shell) |
| **Répartition du capital** (anneau engagé / disponible) | partielle | KPIs cash / engagé | overview paper `account` |
| **Concentration des positions** (anneau par actif) | absente | — (liste positions sans % exposition) | calculable depuis `positions` overview ; UI manquante |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Market pulse (donut BUY/SELL/WATCH/NO TRADE) | garder |
| Pipeline health (compteurs par porte) | garder |
| Circuit 24 h (décisions / paper / lab) | garder (proche Opérations) |
| Preuves & opérations (renvoi Lab / Opérations) | garder |
| Labs paper (table multi-portefeuilles) | garder |
| ContextPanel compact | garder (compense Lecture du marché) |

---

### Marché (maquette → MarketPage)

Route : `/app/market` · `MarketPage.tsx`  
APIs : `/api/engine/universe`, `/api/engine/ohlcv/{symbol}`, `/api/engine/decisions/{symbol}`, `/api/engine/chart-objects/…`, `/api/engine/strategy-lab/backtest-overlay`, `/api/watchlist`, sources exchange via proxies Binance/Bybit/OKX.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Watchlist latérale** (liste actifs + variation) | présente | `MarketWatchlist` (colonne droite / tiroir mobile) | universe + screener rows + `/api/watchlist` |
| **En-tête symbole** + timeframe 15M/1H/4H/1D | présente | top bar + `INTERVAL` / TF group | prefs locales + OHLCV |
| **Résumé PRIX / 24H / RVOL** | partielle | prix + % 24h ; RVOL surtout dans `BiasPanel` | OHLCV / ticker source ; RVOL moteur via décision |
| **Graphique bougies** | présente | `PriceChart` | `/api/engine/ohlcv/{symbol}` (+ overlays) |
| **Calques** Ichimoku / supports-résistances (checkboxes) | présente | `MarketLayersMenu` + prefs | indicateurs / chart-objects moteur |
| **Lecture du marché** (5 portes + setup + CTAs) | partielle | `BiasPanel` (« Lecture » + pipeline moteur) | `/api/engine/decisions/{symbol}` |
| **Préparer le trade →** (modal décision) | partielle | marquage trade / paper CTA mobile ; pas de modal maquette | chart-objects USER + paper propose |
| **Ajouter à la watchlist** | présente | pin watchlist | `/api/watchlist` |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Dock bas Backtest / Marquer un trade / Journal | garder (Journal stub « bientôt » → à décider) |
| Tiroir mobile Liste / Analyse / Backtest | garder |
| Recherche symbole + filtres classe | garder |
| Overlay backtest (`BacktestOverlaySheet`) | garder |
| `MarkTradeSheet` | garder |

---

### Opportunités (maquette → DecisionsPage)

Route : `/app/opportunites` (legacy `/app/decisions`) · `DecisionsPage.tsx`  
APIs : `/api/engine/screener`, `/api/engine/decisions/{symbol}`, paper propose/confirm, `/api/decisions` (journal user), agent explain.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Toolbar** recherche + filtres WATCH/ARMED/TRIGGERED | partielle | filtres TF / symbole / décision / RVOL / actionnables ; pas les libellés cycle ARMED/TRIGGERED | screener `pipeline` + `decision` |
| **Matrice de décision** (table 5 portes + cycle + confiance) | présente | vue « matrice » / liste screener + colonnes portes | `/api/engine/screener` |
| **De l’observation à la décision** (flux WATCH→…→REFUSÉ) | partielle | `dec-method` (stats par porte) ; pas le ruban d’états maquette | agrégats screener |
| **Pourquoi {symbole} ?** (carte mise en avant) | absente | — (sélection sheet à la place) | détail `/api/engine/decisions/{symbol}` |
| **Fiche décision** (modal : portes, RVOL, déclenchement, invalidation, CTAs) | présente | sheet détail : verdict, `TradePlanCard`, `ProposePaperTradePanel`, `DecisionPipelinePanel`, `SignalEvidenceCard` | même endpoint détail + paper |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Onglets classe d’actif (forex/crypto/…) | garder |
| Stats Achats / Ventes / Surveillance / Scannées | garder |
| Agents bruts Ichimoku / RVOL (details) | garder |
| Deep-link Copilot « Expliquer » | garder |

---

### Portefeuille (maquette → PortfolioPage)

Route : `/app/portefeuille` · `PortfolioPage.tsx` (+ embeds `SynthesePage`, `PaperPage`)  
APIs : `/api/engine/paper/portfolios/{code}/overview`, positions, performance, shadow stats, reconcile, risk fields dans overview.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **KPIs** Capital / Exposition / Disponible / Drawdown | partielle | Synthèse → compte + KPIs ; drawdown non mis en avant comme carte dédiée | overview paper |
| **Risk Kernel** (verdict + progress limites) | partielle | onglet **Risque** (capital, exposé, risque utilisé, slots, refus) ; pas le grand verdict « PASSE » ni barres % trade/jour/exposition max comme maquette | `overview.risk` ; limites max dans payload si présentes |
| **Allocation du capital** (donut engagé / liquidités) | partielle | Synthèse « Investissements » / cash-engagé | overview `account` |
| **Positions ouvertes** (table) | présente | onglet **Positions** → `PaperPage` | `/api/engine/paper/positions` |
| **Concentration des positions** (% par symbole) | absente | — | dérivable des positions ; UI absente |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Onglets Synthèse / Compte / Positions / Risque / Tests | garder |
| Réconciliation comptable | garder |
| Progression du test en direct | garder |
| Bénéfice net et frais | garder |
| Courbe equity + timeframe | garder |
| Mouvements paper / Historique clôtures | garder |
| ShadowBroker counterfactuels | garder |
| Performance (% trades) | garder |

---

### Strategy Lab (maquette → BacktestsPage)

Route : `/app/strategy-lab` · `BacktestsPage.tsx`  
APIs : `/api/engine/strategy-lab/*` (experiments, compare, ablation, regime-slices, walk-forward, walk-forward-opt, backtest-overlay), `/api/engine/backtest/*`, `/api/engine/rulesets`, `labResearch` (family-weights, audit-report, monte-carlo, propose-experiment-plan).

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Onglets** Backtests / Ablations / Walk-forward / Régimes / Matrice A–F | partielle | onglets Compare / Regimes / Experiments / Live / Research (libellés et découpe différents) | endpoints strategy-lab listés ci-dessus |
| **Notice** résultats illustratifs | absente (volontaire) | pas de bandeau « démo » | — |
| **KPIs** Univers / Fenêtre / Validation / Hypothèse | absente | métadonnées dans panels par run | coverage `/api/engine/backtest/coverage` (Opérations) ; Lab n’affiche pas la même strip |
| **Table Expériences comparées** (A–F Ichimoku×…) | partielle | Experiments / Compare / Live ; matrice A–F narrative maquette non reproduite telle quelle | `/api/engine/strategy-lab/experiments`, compare, backtest runs |
| **Configurer une expérience** | partielle | formulaires Live + `propose-experiment-plan` (Research) | `POST`-like via clients `labResearch` / strategy-lab |
| **Comparer les trajectoires** (courbes equity) | partielle | métriques tables ; pas la carte « illustration » multi-courbes maquette | compare / walk-forward payloads |
| **De l’idée à la preuve** (étapes 01–04) | absente | — | contenu éditorial ; à décider (statique OK si non démo chiffrée) |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Event Study / Ruleset study | garder |
| Ablation / Régimes / Walk-forward / Walk-forward opt | garder |
| Performance DB | garder |
| Historique automatique (sheet) | garder |
| Collecte automatique (evidence) | garder |
| `LabResearchPanel` (poids familles, audit, MC) | garder |

---

### Journal (maquette → JournalPage)

Route : `/app/journal` · `JournalPage.tsx`  
APIs : `/api/decisions` (Prisma user), `/api/engine/decisions/{symbol}` (refresh), Copilot nav.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Onglets** Trades / Décisions sauvegardées | partielle | onglets Trades / Décisions / Archivées ; Trades = stub vers Portefeuille | `/api/decisions` ; trades paper ailleurs |
| **Recherche symbole** | absente | — | filtrable côté client sur rows existantes → à décider |
| **Exporter CSV** | absente | — | aucune donnée → à décider (export client des `/api/decisions`) |
| **Table** DATE / ACTIF / SENS / RÉSULTAT / PERF / SORTIE | partielle | table décisions (date, symbole, TF, gate, RVOL, actions) ; pas R/perf/sortie trade | `/api/decisions` |
| **Rejouer une décision** (carte récit) | absente | actions Expliquer / Actualiser / Archiver | détail moteur + Copilot |
| **Note personnelle** (textarea localStorage) | absente | — | aucune donnée → à décider (local ou API notes) |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Archivées | garder |
| ConfirmDialog archive/suppression | garder |
| Lien Copilot par ligne | garder |
| Stub « Trades paper → Portefeuille » | garder ou fusionner avec historique Synthèse — à décider |

---

### Contexte (maquette → ContextPage)

Route : `/app/context` · `ContextPage.tsx`  
APIs : `/api/engine/context/news`, `/api/engine/context/calendar`, `/api/engine/context/{symbol}`, `/api/engine/correlations`, `/api/engine/universe`, CoinGecko / Fear & Greed.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **KPIs climat** (Tendance, Dominance BTC, Volatilité, Régime crypto) | partielle | « Climat crypto » (mcap, volume, F&G, dominance) — crypto only | CoinGecko + F&G ; « Tendance / Régime prudence » maquette non mappés 1:1 |
| **Agenda économique** | présente | `ContextFeedsPanel` calendrier | `/api/engine/context/calendar` |
| **Régime par classe d’actifs** (Crypto/Forex/Métaux/…) | partielle | onglets classe + « Régime technique » par flagships (ATR/RSI) ; pas une ligne de badges par classe | `/api/engine/context/{symbol}` |
| **Corrélations · 30 jours** | présente | `CorrelationHeatmap` | `/api/engine/correlations` |
| **Points de vigilance** (3 tips éditoriaux) | absente | note de bas de page générique | contenu éditorial → à décider |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Actualités crypto (RSS) | garder |
| Sélecteur classe d’actif | garder |
| Filtres impact calendrier | garder |

---

### Copilot (maquette → AgentPage)

Route : `/app/agent` · `AgentPage.tsx` + `AgentPanel`  
APIs : `/api/agent/chat`, `/api/agent/actions/confirm` ; contexte session décisions.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Chat** « Une seconde lecture » + log + input | présente | « Conversation » + `AgentPanel` | `/api/agent/chat` |
| **Prompts suggestion** (3 questions démo) | partielle | deep-links depuis Décisions/Journal ; pas la carte de 3 boutons maquette | prompts via `useCopilotNav` / session |
| **Capacités** Lire contexte / Expliquer refus / Passer un ordre (badges) | absente | pills rôles Moteur / Claude / Toi | capacités outils agent côté serveur ; UI badges → à décider |
| **Badge** APERÇU / Claude non connecté | partielle | état LLM dans shell + Settings | `/api/settings`, status LLM |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Chip session symbole/TF | garder |
| Raccourcis Opportunités / Journal / Contexte / Marché | garder |
| Modes expliquer / rechercher (AgentPanel) | garder |

---

### Agents (maquette → AgentsPage)

Route : `/app/agents` · `AgentsPage.tsx`  
APIs : aucune exécution agent ; `useLlmStatus` (settings).

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Notice** supervision illustrative | présente | `agents-notice` | — (éditorial) |
| **6 cartes agents** (Observateur… Session) + mode / permission | présente | grille 6 rôles + périmètre / limite | aucune runtime → à décider si un registry agents arrive |
| **Voir les permissions →** | partielle | liens vers pages métier (contexte, opportunités, risque…) | navigation interne |
| **Chaîne d’autorité** | présente | liste Observation → … → Exécution | — |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Bloc Copilot · connexion LLM | garder |
| Lien Paramètres LLM | garder |

---

### Opérations (maquette → ActivityPage)

Route : `/app/operations` (legacy `/app/activite`) · `ActivityPage.tsx`  
APIs : `/api/engine/activity/summary`, `/api/engine/activity/feed`, `/api/engine/backtest/runs`, `/api/engine/backtest/coverage`, `/api/engine/evidence/outcomes`, `/api/engine/shadow/stats`.

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Filtres** Tous / PASSE / PRUDENCE / REFUSÉ + recherche | partielle | filtres Tout / Trades papier / Filtres / Backtests ; pas PASSE/PRUDENCE ni search | feed + runs |
| **Journal d’audit** (table heure/niveau/source/événement) | partielle | « Historique » timeline groupée par jour | `/api/engine/activity/feed` (+ runs) |
| **Qualité des données** (Binance, symbole stale, doublons, trous) | absente | — | aucune donnée → à décider |
| **Ce que la trace explique** (Décision / Protection / Reproductibilité) | partielle | « Ce que ça prouve » (filtres, edge backtest, signaux) — autre angle | shadow stats, outcomes, runs |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Circuit 5 étapes (Décisions → Suivi signaux) | garder |
| Détail run backtest expansible | garder |
| Couverture multi-classes | garder |

---

### Paramètres (maquette → SettingsPage)

Route : `/app/settings` · `SettingsPage.tsx`  
APIs : `/api/settings`, `/api/settings/llm-test`, push `/api/notifications/push-*`, seuils indicateurs via settings payload ; pas d’UI « Limites de risque » dédiée (limites côté Risk Kernel / paper).

| Section maquette | Statut | React | Donnée |
|---|---|---|---|
| **Onglet Marché et univers** (univers, TF, seuil RVOL) | partielle | section **Indicateurs** (Ichimoku / RVOL) ; univers non éditable comme select maquette | `/api/settings` + seuils ; univers = `/api/engine/universe` lecture |
| **Onglet LLM** | présente | section **Agent LLM** | `/api/settings`, llm-test |
| **Onglet Alertes** (checkboxes événements) | partielle | **Alertes push** (abonnement téléphone) ; pas les 4 toggles Signal/Refus/Périmé/Stop | `/api/notifications/push-*` ; types d’alertes fin → à décider |
| **Onglet Limites de risque** (trade/jour/exposition/slots) | absente | visibles en lecture sur Portefeuille → Risque | payload risk overview ; écriture limites : aucune donnée UI → à décider |
| **Onglet Connexions** (moteur, broker) | partielle | **Feeds marché** (Vision/Bybit/OKX) + Twelve Data ; pas « connexion moteur » texte | settings sources |
| **Environnement** (mode PAPER, exécution bloquée, identité) | absente | implicite (paper only, kill switch) | — |
| **Enregistrer préférences** (localStorage maquette) | présente | POST `/api/settings` | `/api/settings` |

#### React hors maquette

| Section React | Recommandation |
|---|---|
| Table LLM multi-providers + test latence | garder |
| Twelve Data (actions) | garder |
| Thème (dans Indicateurs / ThemeToggle shell) | garder |

---

## Synthèse

| Écart majeur | Pages | Bloqueur données |
|---|---|---|
| Carte / sessions de marché | Desk | Pas d’API sessions ; asset `world-map.svg` maquette seulement |
| Qualité / fraîcheur des données (notice Desk + carte Opérations) | Desk, Opérations | Pas d’endpoint staleness / gaps bougies exposé au front |
| Concentration & anneaux d’allocation | Desk, Portefeuille | Calculable depuis overview paper ; UI manquante |
| « Prochain contrôle » / checkpoint 1H | Desk | Packaging manquant (RVOL/seuils déjà dans screener) |
| Matrice A–F narrative + funnel pédagogique Lab | Strategy Lab | Endpoints lab réels existent ; IA maquette A–F non portée |
| Limites de risque éditables (Paramètres) | Paramètres, Portefeuille | Lecture `overview.risk` ; pas d’API settings risque côté UI inventoriée |
| Journal : CSV, notes, replay trade, perf R | Journal | Notes / export absents ; trades = paper ailleurs |
| Cycle ARMED/TRIGGERED comme dans maquette | Opportunités | Pipeline portes réel ≠ libellés démo maquette |
| Points de vigilance / copy éditoriale Contexte | Contexte | Contenu statique possible sans faux chiffres |
| Agents runtime (permissions live) | Agents | Page descriptive volontaire ; pas de runtime |

**Points déjà bien alignés** : navigation 11 pages (`workspaceNav`), Opportunités/screener, Marché chart+lecture moteur, Copilot chat réel, Agents structure 6 rôles, Contexte feeds+corrélations, Opérations circuit+historique, Portefeuille paper/risk, Settings LLM/feeds.

**Rappel** : toute valeur chiffrée de la maquette est illustrative ; le portage doit brancher les chemins ci-dessus ou marquer explicitement « à décider », jamais réintroduire les constantes de `app.js`.
