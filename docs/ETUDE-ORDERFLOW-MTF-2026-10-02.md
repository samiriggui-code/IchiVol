# Étude — Heatmap de liquidité / order flow et tableau de tendance multi-horizons

**Date :** 2026-10-02 · **Base :** `main` @ `44fca7c` · **Auteur :** Claude (session cloud), sur demande de Samir.
**Nature :** étude, **aucun code modifié**. Chaque constat cite le fichier qui le prouve.
**Règle suivie :** rien n'est considéré comme existant parce qu'un nom apparaît dans un type, une interface ou un bouton. On vérifie que c'est calculé, alimenté et utilisé.

---

## 0. Résumé et avis

1. **Heatmap de carnet : IchiVol n'a aujourd'hui aucune donnée de carnet.** Pas de profondeur, pas de snapshot, pas de mise à jour incrémentale, pas de WebSocket.
   - Une heatmap historique **ne peut pas** être construite à partir de ce que nous stockons (OHLCV + `taker_buy_volume`). Elle demande une **collecte dédiée**.
   - Ce qui existe déjà en order flow est exact, mais à l'échelle de la barre : delta et CVD par bougie (Binance), et un fetch d'aggTrades à la demande, sans stockage.
2. **Order flow et rendement : deux éléments de preuve existent déjà, et aucun n'est favorable.**
   - OF-0 (`docs/RS-08-OF0-RAPPORT.md`, BTC 1h, 2021–2024) : les mesures intrabarre n'ont **aucun lien détectable** avec le rendement 4h suivant (|IC| < 0,01). Le verdict formel n'a pas été rendu : approximation 1 s jugée fragile.
   - Le CVD par barre est calculé depuis la V2, mais il n'a **jamais** décidé quoi que ce soit (`decision/pipeline.py:110`).
3. **Le multi-horizons existe à moitié :**
   - un seul horizon supérieur (`15m→1h`, `1h→4h`, `4h→1d`), sans hebdomadaire, réduit à un booléen `mtf_aligned` ;
   - la règle a déjà été testée comme filtre (B5 de VP3) : **0 EDGE**, effet mitigé, et l'essentiel de l'effet vient de **moins de trades** (§6.3).
4. **Mon avis, en bref :**
   - **À développer d'abord : le panneau multi-horizons explicable.**
     - Les données sont déjà là et le coût est faible.
     - Il améliore la **compréhension**, et il expose les contradictions aux agents.
     - Il ne promet aucun gain de stratégie. Comme filtre, il est déjà largement réfuté.
   - **Heatmap de carnet : seulement une collecte limitée, en observation, avant toute UI.**
     - Périmètre : BTCUSDT spot, Binance, quelques semaines.
     - La seule utilité plausible à court terme est la **qualité d'exécution** : spread, profondeur et slippage au moment d'un ordre déjà décidé.
     - Ce n'est pas une source de signaux sur bougies horaires.
     - La heatmap visuelle complète, façon Bookmap, est un projet coûteux. Rien ne montre aujourd'hui qu'il paierait. Je ne la recommande pas tant que la collecte n'a pas montré un usage mesurable.

---

## 1. État des lieux vérifié dans le code

### 1.1 Données de marché

| Donnée | État | Preuve |
|---|---|---|
| OHLCV crypto | **Existant**, REST `data-api.binance.vision`, polling | `engine/app/market_data/binance.py` |
| `taker_buy_volume` par bougie (côté agresseur agrégé) | **Existant**, stocké en base (nullable) | `db/models.py:87` (`Candle.taker_buy_volume`) |
| OHLCV FX / métaux / indices | Existant, **volume tick** (pas de volume réel) | `market_data/biquote.py`, `capabilities.py` |
| Meilleur bid/ask | **Incomplet** : `bookTicker` REST codé, **sans horodatage exchange** (heure de réception utilisée) ; non stocké ; utilisé seulement par le chemin `quote_paper` | `market_data/binance_quotes.py`, `brokerage/quote_paper.py`, `paper/broker.py:237` |
| Profondeur sur plusieurs niveaux | **Absent** (`depth=False  # unused`) | `market_data/capabilities.py:41` |
| Snapshots du carnet | **Absent** | aucune occurrence de `/depth` dans le dépôt |
| Mises à jour incrémentales (diff depth) | **Absent** | aucun client WebSocket (`streaming=False  # REST poll only today; WS unused`) |
| Transactions individuelles | **Incomplet** : `/api/v3/trades` (100 dernières) et `/api/v3/aggTrades` paginé, **à la demande** ; aucun stockage | `binance_quotes.py`, `microstructure/binance_trades.py`, `paper/protection.py:666` |
| Côté agresseur | **Existant** au niveau trade (`m` / `isBuyerMaker`) et bougie (`taker_buy`) | idem |
| Historique rejouable de trades | **Absent** côté app. Côté recherche : klines 1 s Binance Vision 2021–2024 téléchargées pour OF-0 (fichiers locaux, hors app) | `docs/RS-08-OF0-RAPPORT.md` |
| Historique rejouable de carnet | **Absent**, nulle part | — |
| OI / funding (futures) | Existant, historique 5 min via REST, en contexte seulement | `market_data/binance_futures.py`, `indicators/oi_funding.py` |
| Liquidations | **Absent** (pas d'historique gratuit, noté dans le handoff) | `HANDOFF-LOCAL-CLAUDE.md` |

**Limites connues du fetch aggTrades :**
- `binance_trades.py` plafonne à `max_pages=20`, soit 20 000 trades (≈ 20 min de BTC).
- Les barres suivantes restent à `None` **sans signal de troncature**. C'est le ticket CVD-LAB-FIX, encore ouvert.

### 1.2 Calculs order flow présents

| Calcul | État | Preuve |
|---|---|---|
| Delta par barre `2×taker_buy − volume` | **Existant, exact** : égal à Σ aggTrades agresseurs (vérifié sur BTC le 2024-03-01) | `indicators/cvd.py`, `RS-07` |
| CVD cumulé + biais glissant | Existant, calculé à chaque scan, **affiché**, **ne décide pas** (code de contexte dans l'étape Participation seulement) | `decision/pipeline.py:107-117` |
| CVD depuis les trades | Existant en **Lab** (`compare_kline_vs_trade_cvd`, endpoint de recherche). Biais non comparables avec le CVD kline (ticket CVD-LAB-FIX) | `microstructure/trade_cvd.py`, `api/strategy_lab_research.py:363` |
| Footprint intrabarre | Recherche seulement (`rs/of0/`), approximé 1 s | `RS-07`, `RS-08` |
| Volume profile / HVN / LVN / VWAP / AVWAP | **Existant et décisif** (étape Location) | `indicators/location.py`, `pipeline.py:_location_stage` |
| Calque « Liquidity » (BSL / SSL) | **Absent côté moteur** : le type `ChartObjectLayer.LIQUIDITY` et `LiquidityDrawing.tsx` existent, **aucun producteur**. Job CI-LIQ-CONF en file, pas commencé (`indicators/liquidity.py` n'existe pas) | `chart_objects/types.py:50`, `HANDOFF-CURSOR-V3.md:652` |

**Distinction à garder partout :**
- Le futur calque « Liquidity » CI est fait de **zones déduites des prix** : des pools de swing highs et lows.
- Le LVN de `location.py` est un **creux de volume exécuté**.
- Ni l'un ni l'autre n'est de la **liquidité affichée dans le carnet**. Une heatmap de carnet serait une troisième chose, et il ne faut jamais les fusionner sous le même nom.

### 1.3 Multi-horizons présent

| Élément | État | Preuve |
|---|---|---|
| Table des horizons supérieurs | `{"15m":"1h","1h":"4h","4h":"1d"}`, **pas de 1d→1w** | `market_data/timeframes.py:12` |
| Direction de l'horizon supérieur dans le pipeline live | **Existant** : 2ᵉ fetch, bougies **closes** seulement, Ichimoku, booléen `mtf_aligned`. Un `mtf_opposed` ne fait que rétrograder l'étape Structure en `WATCH` | `screener/service.py:86-101,201-216`, `pipeline.py:_structure_stage` |
| Twelve Data | MTF **sauté** (économie de crédits) | `screener/service.py:197` |
| Fiche agent « Direction MTF » | Existant (AG-S1), avec garde causale `htf.open + durée ≤ décision` | `agents/analyst_cards.py:176-290` |
| Alignement HTF en backtest | Existant, causal (barre HTF retenue seulement quand elle est close) | `backtest/experiments.py:143-162` |
| Matrice 1h / 4h / 1d / 1w | **Absent** | — |
| Bougies closes seulement | **Existant** (`decide_on_closed_candles=True`), `signal_timing` (lag, late, stale) | `config.py:30`, `screener/timing.py` |
| Pivots avec date de confirmation | **Existant** (`fractal_confirmed_at`), utilisé par structure et impulse | `indicators/pivots.py:36` |
| `known_at` / replay `as_of` des objets graphiques | **Existant**, recalcul sur bougies ≤ `as_of`, pas de filtrage côté client | `chart_intelligence/service.py:8-12,452-496` |

### 1.4 Frontend

- **Il n'existe pas de composant nommé `ChartEngine`.** Le rendu graphique repose sur **lightweight-charts v5** :
  - `components/PriceChart.tsx` : page Marché, overlays en price lines ;
  - `components/chart-intelligence/IntelligenceChart.tsx` : bougies + volume + Ichimoku, **projection temps/prix → px partagée** (`chartProjection.ts`) ;
  - `DrawingLayer.tsx` : surface SVG au-dessus du canvas, une couche par composant.
- `ChartIntelligencePanel` est monté en **source API** dans `Root.tsx` et `PortfolioPage.tsx`, avec replay (`ReplayControls.tsx`), « Pourquoi ? » (`WhyPanel.tsx`) et inspecteur.
- Le pipeline est affiché par `DecisionPipelinePanel.tsx` (étapes pass / fail / watch / pending, codes).
- Les intervalles UI sont `15m / 1h / 4h / 1d` (`MarketPage.tsx:160`).
- **Aucun flux temps réel vers le navigateur** : pas de WebSocket ni de SSE, sauf le SSE du chat agent (`server/src/agent/route.ts:234`). Tout le reste est du polling REST.

### 1.5 Traçabilité de ce que le moteur savait

- **Position paper :**
  - `entry_signal` et `exit_signal` (JSON) gardent le pipeline, l'ATR, le RVOL et le portefeuille au moment de l'action (`db/models.py:285-290`) ;
  - le journal garde les `SIGNAL_REJECTED` avec leurs codes.
- **`signal_evidence` :** contexte à t0, versions des règles et des features (`db/models.py:623`).
- **Agents :** les faits avec provenance passent par AG-FS0 (`agents/factsheet.py`).
- **Point d'attention, nommage :** la colonne `decisions.probability` reprend `ichimoku_agent._probability`, une **heuristique documentée comme bon marché** (`agents/ichimoku_agent.py:10`). Ce n'est pas une probabilité calibrée. Il ne faut pas l'afficher sous ce nom.

---

## 2. Tableau existant / incomplet / absent

| Besoin | Existant | Incomplet | Absent |
|---|:-:|:-:|:-:|
| OHLCV + volume réel crypto | ✔ | | |
| Delta / CVD par barre (côté agresseur exact) | ✔ | | |
| Delta / CVD depuis les trades | | ✔ (Lab, troncature silencieuse) | |
| Bulles de transactions (trades individuels horodatés, stockés) | | ✔ (fetch à la demande, rien de stocké) | |
| Meilleur bid/ask | | ✔ (REST, sans horodatage exchange, non stocké) | |
| Profondeur multi-niveaux | | | ✔ |
| Snapshot + deltas synchronisés (séquences) | | | ✔ |
| Historique de carnet rejouable | | | ✔ |
| États « synchronisé / partiel / périmé / indisponible » du carnet | | | ✔ (seul `signal_timing` existe, pour les bougies) |
| Heatmap, histogramme de profondeur, bulles (UI) | | | ✔ |
| Zones déduites des prix (S/R, FVG, BOS, Fibo) | ✔ | | |
| Pools BSL/SSL (prix) | | ✔ (type + UI, pas de producteur) | |
| Direction de l'horizon supérieur (1 niveau) | ✔ | | |
| Matrice 1h / 4h / 1d / 1w avec état et méthode | | | ✔ |
| Accord / contradiction entre horizons, restitution en phrase | | ✔ (code `mtf_opposed` seulement) | |
| Contexte volume / volatilité (RVOL, ATR, ADX, Donchian) | ✔ | | |
| Critères d'entrée, de retard et de refus | ✔ (étapes + codes + `SIGNAL_REJECTED`) | | |
| Motifs de sortie | ✔ (`exit_reason`, `exit_signal`) | | |
| Séparer le signal analytique de l'action portefeuille | ✔ (`allow_short=False`, `exit_mode=direction` : SELL = sortie du long) | ✔ (non dit dans l'UI) | |
| Replay `as_of` des objets graphiques | ✔ | | |
| Faits structurés pour les agents | ✔ (FactSheet) | ✔ (rien sur le MTF étendu ni le carnet) | |

---

## 3. Concept 1 : heatmap de liquidité et order flow

### 3.1 Trois natures de données, jamais confondues

| Nature | Ce que c'est | Ce que ça ne prouve pas |
|---|---|---|
| **Liquidité affichée** | Ordres limites présents dans le carnet d'**une** plateforme, à un instant | Que ces ordres seront exécutés. Qu'ils représentent tout le marché |
| **Volume exécuté** | Transactions réalisées, avec côté agresseur | L'intention du passif. Qui est derrière |
| **Disparition d'un niveau** | Quantité affichée en baisse entre deux états | **Exécution ou annulation** : on ne le sait qu'en rapprochant les trades au même prix sur la même fenêtre. Une annulation ne prouve pas une manipulation |

Toute mesure de §3.2 porte trois champs obligatoires : `venue` (ex. `binance-spot`), `instrument` (ex. `BTCUSDT`) et `book_state`. **Une heatmap de carnet n'est ni une carte de liquidations ni une carte des stops** : les stops ne sont pas visibles dans un carnet spot public.

### 3.2 Détections : définitions mesurables

**Notations :**
- `mid` = (bid + ask) / 2 ;
- `tick` = pas de prix de l'instrument ;
- **bucket** = regroupement de prix de largeur `b` ;
- par défaut `b = max(tick, k × mid)`, avec `k` figé a priori, par exemple 1 bp pour BTC ;
- **fenêtre d'observation** `Δ` (ex. 1 s) ;
- `Q(p, t)` = quantité affichée dans le bucket `p` à l'instant `t`, carnet synchronisé seulement ;
- `X(p, Δ)` = volume exécuté au prix `p` pendant `Δ`, par côté agresseur.

| # | Détection | Définition mesurable | Données | Limite à afficher |
|---|---|---|---|---|
| D1 | Concentration acheteuse / vendeuse | Bucket `p` dans un rayon `R` du mid (ex. 1 % ou n × ATR 1 min) dont `Q(p,t)` ≥ quantile 95 % des `Q` du même côté et du même rayon sur les 30 dernières min | Carnet synchronisé | Relative à la plateforme et au rayon observé |
| D2 | Persistance | Durée continue pendant laquelle D1 reste vrai pour `p` (tolérance d'un bucket) ; on publie `first_seen`, `last_seen`, `duration_s` | idem | Un mur peut être déplacé à chaque tick : on suit le **niveau**, pas un ordre (les ordres ne sont pas identifiés en spot public) |
| D3 | Renforcement / retrait | `ΔQ(p) = Q(p,t) − Q(p,t−Δ)`. **Retrait non exécuté** = `−ΔQ − X(p,Δ)` > 0 ; **consommation** = la part de la baisse expliquée par `X(p,Δ)` | Carnet + trades **synchronisés au même horloge** | Le rapprochement est approché si les horodatages trades et carnet diffèrent (Binance : temps d'événement des deux flux) |
| D4 | Déséquilibre de profondeur | `OBI_N = (ΣQ_bid − ΣQ_ask) / (ΣQ_bid + ΣQ_ask)` sur les N premiers niveaux, ou dans ±x % du mid ; publier N et x | Carnet | Très bruité, change en millisecondes ; ne montrer qu'en moyenne sur `Δ` |
| D5 | Achats / ventes agressifs | Somme des trades par côté agresseur (`m` Binance) sur `Δ` ; **gros agresseur** = trade (ou aggTrade) ≥ quantile 99 % des tailles sur 24 h | aggTrades | Un aggTrade agrège plusieurs fills du même ordre taker au même prix, ce n'est pas « un ordre » au sens strict |
| D6 | Delta / CVD | `delta(Δ) = Σ taille agresseur acheteur − Σ vendeur` ; CVD = cumul **depuis une ancre explicite** (ouverture de session UTC, ou début de la fenêtre affichée) | aggTrades (barres : déjà disponible) | Le CVD dépend de son ancre ; toujours l'afficher |
| D7 | Situation **compatible avec** une absorption | Sur `Δ` : volume agresseur d'un côté ≥ quantile 95 %, **et** le prix progresse de ≤ 1 bucket dans ce sens, **et** la quantité affichée au niveau opposé touché ne baisse pas plus vite que le volume exécuté (`Q` reconstitué). Étiquette : « compatible avec absorption » | Carnet + trades | Ne prouve pas l'intention ; une grosse bulle seule ne suffit **jamais** |
| D8 | Traversée de niveaux | Nombre de buckets franchis par le mid en `Δ` ≥ `n` (ex. 5), avec le volume exécuté par bucket traversé | Carnet + trades | — |
| D9 | Cassure avec échanges soutenus | Clôture 1 min au-delà d'un niveau de référence (D1, ou un niveau **prix** existant : swing, Kijun, VAH/VAL) **et** volume agresseur dans le sens de la cassure ≥ quantile 80 % sur les k minutes suivantes **et** prix toujours au-delà après k minutes | Trades (+ carnet pour D1) | Le niveau de référence doit être daté (`known_at`) |
| D10 | Rejet au contact d'une zone | Le prix touche la zone (mèche dans ±1 bucket) puis s'en écarte d'au moins `m × ATR(1 min)` dans les `k` minutes sans clôture au-delà | Trades / klines 1 min | « Rejet » est une description a posteriori sur k minutes : publiable seulement à `t + k` |
| D11 | Zone de faible profondeur | Intervalle contigu de buckets dans ±x % du mid où `Q` < quantile 10 % (des deux côtés), de largeur ≥ w | Carnet | Un vide peut se remplir instantanément ; ce n'est pas une prévision d'amplitude |

**Chaque détection publie :**
- `detected_at` : moment où la condition devient vraie, avec les données disponibles à cet instant ;
- `window` ;
- `params_version` ;
- `book_state` ;
- `venue` / `instrument` ;
- les valeurs brutes utilisées.

Les seuils sont **figés avant collecte**. Les changer ensuite crée une nouvelle version.

### 3.3 Collecte du carnet (ce qu'il faudrait construire)

**Périmètre minimal :** Binance **spot**, BTCUSDT, puis ETH et SOL si utile. C'est la plateforme dont le moteur lit déjà les bougies, ce qui garde la cohérence avec le reste du pipeline.

**Flux publics (sans compte) :**
- `<symbol>@depth@100ms` (diff depth) ;
- `<symbol>@aggTrade` ;
- `<symbol>@bookTicker` ;
- snapshot REST `/api/v3/depth?limit=1000` (ou 5000).

À vérifier en phase 0 : l'accessibilité depuis le VPS de `data-stream.binance.vision` (WS) et de `/depth` sur `data-api.binance.vision`.

**Synchronisation snapshot / deltas (procédure Binance spot) :**
1. Ouvrir le flux diff et **bufferiser** les événements.
2. Prendre le snapshot REST et retenir son `lastUpdateId`.
3. Jeter les événements avec `u ≤ lastUpdateId`.
4. Le premier événement appliqué doit vérifier `U ≤ lastUpdateId + 1 ≤ u`. Sinon, reprendre un snapshot.
5. Pour chaque événement suivant, exiger `U == u_précédent + 1`. Tout trou met le carnet en `PARTIAL` et déclenche une resynchronisation (nouveau snapshot).
6. Une quantité 0 supprime le niveau. Un niveau hors de la profondeur du snapshot reste **inconnu**, pas vide.

**Trades :** l'`aggTrade id` (`a`) est consécutif. Un trou est comblé par REST `/api/v3/aggTrades?fromId=`, sinon il est marqué. Un doublon (même `a`) est ignoré.

**Déconnexions :**
- reconnexion avec backoff ;
- la période sans données est enregistrée comme `gap` (début, fin, cause) ;
- elle n'est **jamais interpolée** ;
- Binance coupe les WS au bout de 24 h : reconnexion planifiée.

**État du carnet, publié à chaque mesure :**

| État | Condition |
|---|---|
| `SYNCED` | Snapshot appliqué, séquence continue, dernier événement reçu il y a < 2 s |
| `PARTIAL` | Trou de séquence détecté, resynchronisation en cours, ou mesure hors de la profondeur couverte |
| `STALE` | Aucun événement depuis > 2 s (seuil figé), alors que le flux est censé être ouvert |
| `UNAVAILABLE` | Pas de collecte pour cet instrument ou cette période (historique avant le début de la collecte inclus) |

**Stockage proposé, en deux niveaux :**
1. **Brut** : fichiers journaliers par instrument, append-only, compressés (NDJSON + zstd ou Parquet).
   - Contenu : snapshot + deltas + aggTrades + bookTicker + événements `gap` / `resync`, avec `exchange_time` et `received_at`.
   - Hors Postgres, pour ne pas charger la base applicative.
   - Rétention : 30 à 90 jours au départ.
   - C'est la seule base qui permette un **replay fidèle**.
2. **Agrégé** : grille `bucket de prix × pas de temps` (ex. 1 s pour l'écran, 1 min pour l'historique) avec `Q_bid`, `Q_ask`, `X_buy`, `X_sell` et `book_state` par cellule.
   - Calculée **depuis le brut**, versionnée, servie à l'UI et aux agents.
   - Postgres convient pour l'agrégé 1 min ; l'agrégé 1 s reste en fichiers ou en mémoire.

Les volumes réels seront mesurés pendant la phase 0 avant tout dimensionnement. Je ne les invente pas ici.

**Processus :** un collecteur **séparé** de l'engine (nouveau service dans `docker-compose`).
- Un plantage du collecteur ne doit pas arrêter le pipeline, et inversement.
- Leçon du 28/09 : vérifier le Dockerfile et tester le build avant déploiement.

**Interdit :** reconstruire une heatmap passée depuis les OHLCV, ou remplir une période `UNAVAILABLE` par extrapolation.

---

## 4. Concept 2 : tableau de tendance multi-horizons explicable

### 4.1 Ce qu'on reprend de l'idée, et ce qu'on ne reprend pas

- **Repris :** montrer côte à côte la tendance de plusieurs horizons, leurs contradictions, et le contexte volume / volatilité.
- **Non repris :**
  - la formule du ruban, des signaux et du score « AI Confidence », qui est inconnue ;
  - le vocabulaire « AI » et « confidence » pour un score qui n'est pas calibré.

### 4.2 Définition IchiVol (à partir du moteur existant)

**Horizons :** 1h, 4h, 1d, 1w. Le 1w se fetch aujourd'hui avec le même provider, mais le code ne le gère pas encore, voir §4.4.

**Pour chaque horizon `h`, à l'instant `t`, on publie :**

| Champ | Définition | Source |
|---|---|---|
| `direction` | `LONG` / `SHORT` / `NEUTRAL` = sortie d'`ichimoku_agent.analyze` sur les **bougies closes** de `h` | même agent que l'étape Direction |
| `method` | Texte figé : « Ichimoku 9/26/52, direction de la dernière bougie close » (+ score Ichimoku) | `IchimokuParams` |
| `bar_close` | Clôture de la dernière bougie close utilisée | `closed_candles` |
| `state` | `CONFIRMED` (bougie close à jour) · `LATE` (`lag_bars = 1` hors délai de grâce) · `STALE` (`lag_bars ≥ 2`) · `UNAVAILABLE` (pas de données, ou provider sans cet horizon) | `screener/timing.py` |
| `provisional` | Optionnel, **affiché à part, jamais utilisé** : direction calculée en incluant la bougie en formation, étiquetée « provisoire, peut changer » | — |
| `rvol`, `atr_regime`, `adx` | Valeurs de la dernière bougie close de `h` | REGISTRY |

**Accords et contradictions, sans score :**
- `parent` = horizon supérieur de l'horizon de décision. On réutilise `HIGHER_TIMEFRAME`, pour rester identique au pipeline.
- `relation(decision_tf, h)` ∈ {`aligné`, `opposé`, `neutre`, `inconnu`}, pour chaque autre horizon.
- **Restitution en phrase, déterministe, construite depuis les champs :**
  > « Tendance 1h haussière (Ichimoku, bougie close 14:00 UTC), contexte 4h baissier (close 12:00), RVOL 0,6× (< 0,7, seuil LOW) : entrée non confirmée (étapes Structure WATCH `mtf_opposed`, Participation FAIL `rvol_low`). »
- La partie « entrée non confirmée » ne se calcule pas dans le panneau : elle **reprend les étapes et codes du pipeline réel** (`PipelineResult.stages`). Le panneau ne peut donc pas contredire le moteur.

**Signal analytique et action du portefeuille, séparés :**
- **Signal :** BUY / SELL / WATCH / NO_TRADE, issu du pipeline.
- **Action BASELINE :** `allow_short=False` et `exit_mode=direction`.
  - Un SELL veut dire « **sortie du long** s'il y en a un, sinon rien ».
  - Ce n'est jamais une ouverture de short.
- Le panneau affiche les deux lignes : « Signal : SELL (Ichimoku 1h SHORT) » / « Portefeuille : sortie de la position longue ouverte le … » ou « aucune action (short désactivé) ».

### 4.3 Marqueurs d'entrée et de sortie explicables

- On utilise ce qui est **déjà stocké** :
  - `paper_positions.entry_signal` et `exit_signal`, `exit_reason` ;
  - les `SIGNAL_REJECTED` du journal.
- Un marqueur affiche :
  - l'heure de la **bougie close** de la décision ;
  - l'heure d'**exécution** (ouverture suivante, ou prix live) ;
  - le prix et l'état de chaque étape ;
  - les codes ;
  - la matrice MTF **telle qu'elle était**. Elle sera ajoutée à `entry_signal` dès que la matrice existe. Pour les positions plus anciennes : « non enregistré ».
- On ne recalcule rien pour l'historique : un marqueur montre **ce que le moteur savait**, pas ce qu'un recalcul dirait aujourd'hui.

### 4.4 Points techniques à corriger avant le 1w

- `TF_SECONDS` n'a pas `1w` (`timeframes.py:17`). L'ajouter est **sans risque** pour `closed_candles` (`c.time + tf ≤ now`).
- En revanche, `compute_signal_timing` calcule la frontière attendue par `now − now % tf_seconds` (`timing.py:50`). Pour 604 800 s, cette frontière tombe un **jeudi** (époque Unix), alors que les bougies hebdomadaires Binance ouvrent le **lundi 00:00 UTC**.
- `lag_bars`, `data_late` et `stale` seraient donc **faux** en 1w. Il faut une frontière ancrée sur l'ouverture réelle des bougies, avec un test.
- **Ne pas** ajouter `"1d": "1w"` à `HIGHER_TIMEFRAME` : cela changerait le pipeline live des scans 1d (`mtf_aligned`). La matrice d'affichage doit avoir **sa propre liste** d'horizons.
- `_closed_only` renvoie la série **non filtrée** quand il reste moins de 2 bougies closes (`screener/service.py:83`). C'est sans effet avec 300 bougies, mais la matrice doit plutôt renvoyer `UNAVAILABLE` dans ce cas.

---

## 5. Scores et absence de repainting trompeur

### 5.1 Faut-il un score ?

**Ma recommandation : pas de score unique dans la V1.** On affiche la matrice et le décompte : « 2 horizons alignés, 1 opposé, 1 neutre ».

**Si un score est demandé :**
- **Nom :** « indice d'alignement », jamais « probabilité » ni « confidence ».
- **Composantes :** une seule famille, la **direction** par horizon. RVOL, ATR et ADX restent affichés à côté, hors score.
- **Valeurs :** LONG +1, SHORT −1, NEUTRAL 0.
- **Poids figés a priori,** par exemple égaux. Pas de pondération optimisée sur l'historique.
- **Données manquantes :** l'horizon est retiré du dénominateur et le score porte `n_horizons = 3/4`. Il n'est jamais imputé à 0.
- **Information comptée plusieurs fois :**
  - Ichimoku, ADX et Donchian disent tous « tendance » : ils ne s'additionnent pas.
  - Les directions 1h et 4h sont elles-mêmes corrélées. Le score se lit comme un décompte, pas comme des votes indépendants.
- **Probabilité :** un nom de ce type exigerait de définir l'événement prédit (ex. « rendement 24h > 0 ») et de valider la calibration sur des données **indépendantes**. Le protocole VP0 l'interdit hors pré-enregistrement, et le holdout 2026 est fermé.

Le module `confluence/` a déjà des poids par famille (`weights.py`), **documentés comme des placeholders interdits dans les décisions**. Le même statut s'applique ici.

### 5.2 Causalité : ce qui est déjà garanti, et ce qu'il faut garder

| Exigence | État actuel | À faire pour la matrice |
|---|---|---|
| Bougies closes seulement | ✔ `decide_on_closed_candles`, `closed_candles` | Idem, par horizon |
| Disponibilité réelle de l'horizon supérieur | ✔ live : 2ᵉ fetch filtré ; backtest : barre HTF retenue à sa clôture (`experiments.py:159`) ; agents : `_htf_closed_as_of` | Une fonction unique `htf_closed_as_of(t)` partagée par live, backtest, replay et agents |
| Pas de données futures | ✔ tests de troncature existants (CVD, structure, OF-0) | Test de troncature : matrice à `t` identique que la série s'arrête à `t` ou continue |
| Pivot : date d'origine ≠ date de confirmation | ✔ `fractal_confirmed_at`, `known_at` CI | Toute zone ou rejet issu d'un pivot porte `origin_time` **et** `confirmed_at` ; le backtest n'agit qu'après `confirmed_at` |
| Direct ≠ historique recalculé | ✔ replay CI recalcule sur bougies ≤ `as_of` | Persister la matrice dans `entry_signal` au moment de l'action ; l'historique lit ce qui a été stocké |
| Order flow (§3) | — | `detected_at` = arrivée de la dernière donnée utilisée (pas l'heure du bucket) ; D10 publiable à `t + k` seulement |

Une remarque sur l'Ichimoku : la direction utilise le Chikou (clôture comparée au prix 26 barres **avant**) et le nuage projeté. Les deux sont causaux sur des bougies closes. Le risque de repaint d'un indicateur TradingView (`request.security` sur une barre HTF ouverte) ne s'applique pas tant qu'on garde les bougies closes.

---

## 6. Complémentarité avec IchiVol

### 6.1 Ce que chaque concept peut apporter aux moteurs réels

| Moteur (vérifié actif) | Panneau MTF | Order flow / carnet |
|---|---|---|
| Direction (Ichimoku) | Montre les autres horizons à côté de celui qui décide | Rien sur l'horizon 1h |
| Participation (RVOL décide ; CVD et OI/funding en contexte) | Affiche le RVOL par horizon | Le delta par barre existe déjà et est exact. Le CVD trades n'apporte rien de plus **par barre** (même somme) |
| Structure (swings, BOS) + `mtf_aligned` | Remplace le booléen par la matrice, en affichage | Les zones de prix restent les zones de référence ; le carnet pourrait dire si de la liquidité est **affichée** près d'elles, à un instant donné |
| Location (VP, VWAP, HVN/LVN) | — | Ne pas confondre le LVN (volume exécuté passé) et D11 (carnet vide maintenant) |
| Régime (ATR, ADX, Donchian) | Régime par horizon | Spread et profondeur = régime de **liquidité** au moment de l'exécution |
| Paper / exécution | — | **Seul raccord plausible** (§6.2) |
| Agents (FactSheet AG-FS0, fiches AG-S1) | Faits `mtf.<h>.direction`, `.state`, `.bar_close` avec provenance | Faits `ob.*` avec `book_state`, `venue`, fenêtre |

### 6.2 Le raccord entre les horizons (secondes contre bougies horaires)

- La stratégie BASELINE décide **à la clôture 1h** et exécute ensuite. Un phénomène de quelques secondes ne peut agir que sur trois choses :
  1. **Le prix d'exécution** d'une entrée ou d'une sortie **déjà décidée**. Exemple : attendre jusqu'à N minutes si le spread dépasse X bps ou si la profondeur dans ±0,1 % est sous un seuil, puis exécuter de toute façon.
  2. **Le retard ou l'annulation** d'une entrée déjà décidée. On le teste comme une règle, avec le risque de rater les meilleurs trades (les cassures franches sont souvent les plus « illiquides » à l'instant T).
  3. **Le placement du stop** : éviter un niveau juste au-delà d'un vide (D11). C'est spéculatif : l'état du carnet au moment de l'entrée ne dit rien de celui à l'instant où le stop sera touché.
- **Ordre de grandeur :**
  - Le paper suppose 2 bps de spread + 3 bps de slippage par côté, plus 7,5 bps de commission (`strategy_profiles.py`).
  - En 1h, B7 fait environ 200 trades sur la période de développement de VP3. Gagner quelques bps par côté représente au mieux une fraction de point de rendement par an.
  - **Cela ne peut pas transformer une stratégie sans edge en stratégie gagnante** : B7 a déjà un SR négatif sur BTC, ETH et SOL 1h avec les coûts de base, avant même le profil adverse.
- **Information intrabarre comme signal :** OF-0 n'a trouvé aucun lien avec le rendement 4h, même pour F4 et F5, qui ne dépendent pas de l'approximation. Un nouvel essai demanderait un **nouveau pré-enregistrement** (+N au registre T10b) et des données tick, pas des klines 1 s.

### 6.3 Ce que VP3 dit déjà du filtre multi-horizons (B5 = B2 + « HTF close ≠ short »)

SR annualisé, profil de coûts de base, période de développement (`docs/VP3-REPORT-FINAL.md`) :

| Symbole · TF | B2 SR (trades) | B5 SR (trades) | B0 buy & hold SR |
|---|---|---|---|
| BTC 1h | −0,12 (129) | +0,19 (99) | 0,78 |
| BTC 4h | +0,54 (22) | +0,84 (14) | 0,82 |
| ETH 1h | −0,11 (119) | −0,02 (91) | 0,50 |
| ETH 4h | −0,74 (21) | −0,71 (17) | 0,51 |
| SOL 1h | +0,82 (98) | +0,66 (80) | 0,93 |
| SOL 4h | +0,88 (26) | +0,40 (17) | 0,94 |

**Lecture :**
- Le filtre multi-horizons améliore 4 cas sur 6 et en dégrade 2.
- Il retire **toujours** des trades (−20 à −35 %).
- Il ne bat B0 nulle part de façon significative. Verdict final : **0 EDGE**.
- C'est exactement le piège signalé dans la demande : une partie de l'« amélioration » vient d'une exposition plus faible.

**Conséquence :** le panneau MTF doit être vendu comme un outil de **compréhension**, pas comme un filtre de performance.

---

## 7. Intégration dans le produit existant

### 7.1 Moteur (Python)

| Élément | Où | Réutilise |
|---|---|---|
| `mtf_matrix` (calcul pur, sans I/O) | `app/indicators/mtf_matrix.py` ou `app/analysis/mtf.py`, enregistré selon la règle T1e (REGISTRY) si c'est un indicateur | `ichimoku_agent`, `closed_candles`, `compute_signal_timing` (corrigé 1w), RVOL / ATR / ADX |
| Fetch multi-horizons | Côté screener / CI, **jamais** dans la boucle paper (règle #161) | `resolve_and_fetch`, `fetch_with_accumulation` |
| Route | `GET /mtf/{symbol}?decision_tf=1h&as_of=` (lecture seule, même préfixe engine, passthrough Node existant) | conventions `api/chart_intelligence.py` |
| Persistance | Ajout de la matrice dans `entry_signal` / `exit_signal` des positions et dans `signal_evidence.context_json` (JSON, **sans migration**) | `paper/engine.py:sync_position` |
| Agents | Faits FactSheet `mtf.*` avec `source`, `as_of`, `state` ; le validateur Eve s'applique déjà aux chiffres cités | `agents/factsheet.py` |
| Order flow (phase 3+) | Service `collector-ob` séparé ; module de lecture `app/microstructure/book_*.py` qui sert l'agrégé ; `ProviderCapabilities.depth/streaming` passés à `True` **seulement** quand c'est câblé | `microstructure/`, `capabilities.py` |

### 7.2 Frontend (React)

| Élément | Comment | Réutilise |
|---|---|---|
| Panneau tendances multi-horizons | Carte à côté de `DecisionPipelinePanel` : une ligne par horizon (direction, méthode, close, état, RVOL / ATR), la phrase de §4.2, puis « Signal » / « Portefeuille » | `.card`, `.tag green/amber/red/gray`, `labelPipelineGate`, `decisionLabels.ts` |
| Marqueurs explicables | Markers lightweight-charts depuis `entry_signal` / `exit_signal` ; clic → inspecteur | `DrawingInspector`, `WhyPanel`, `paperLabels.ts` |
| État et fraîcheur | Badge par horizon (`CONFIRMÉ` / `EN RETARD` / `PÉRIMÉ` / `INDISPONIBLE`) | même mécanique que `signal_timing` |
| Couche heatmap (phase 4) | **Canvas** superposé (pas SVG : milliers de cellules), qui lit `ChartProjection` (`x(time)`, `y(price)`, `rev`). Activable dans `LayerControls`. Visible seulement en 1m / 5m sur la plage collectée ; sinon « historique indisponible » | `chartProjection.ts`, `LayerControls`, `chartColors.ts` |
| Bulles de transactions | SVG dans `DrawingLayer`, **agrégées** (bucket × pas de temps ; seuil de taille) ; couleur par côté agresseur (`--bull` / `--bear`) | `DrawingLayer` |
| Profondeur actuelle | Histogramme latéral dans la gouttière droite (bid / ask), avec badge `venue · instrument · état` | `drawingContext.ts` (gouttière) |
| Replay | Objets graphiques et MTF : `as_of` existant. Carnet : seulement sur la plage enregistrée, lu depuis l'agrégé ; hors plage = « non enregistré » | `ReplayControls`, `useChartIntelligence` |

**Volume de données à l'écran :**
- seulement l'agrégé ;
- au plus quelques milliers de cellules visibles ;
- fenêtre limitée (ex. 2 h en 1 s, 3 jours en 1 min) ;
- abonnement aux seuls instruments collectés ;
- un flux temps réel vers le navigateur (SSE via le serveur Node, comme pour l'agent) seulement si la vue est ouverte.

Le frontend ne calcule aucune détection : il lit les mesures du moteur, comme `WhyPanel`.

---

## 8. Mesurer l'apport réel

### 8.1 Trois bénéfices distincts, trois méthodes

| Bénéfice | Mesure | Faisable quand |
|---|---|---|
| **Compréhension** | Qualitative et traçable : les contradictions affichées correspondent aux codes du pipeline (test automatique de cohérence) ; Eve cite des faits `mtf.*` validés | Dès le panneau MTF |
| **Qualité d'exécution** | Pour chaque ordre paper, on enregistre au moment de la décision et de l'exécution : `mid`, spread, profondeur ±0,1 %, `book_state`. On calcule `IS = (prix exécuté − mid à la décision) / mid` en bps, comparé à l'hypothèse 2 + 3 bps du profil | Dès la collecte (phase 3), en **observation** (shadow), sans changer les ordres |
| **Stratégie** | Backtest pré-enregistré (§8.2) | MTF : maintenant, sur données existantes (sous protocole) · carnet : **impossible** sans historique |

### 8.2 Comparaison des variantes

**Mêmes conditions pour toutes :**
- périodes, capital (5 000) et règles de taille (0,5 % de risque, plafonds) ;
- frais (`commission_bps_by_symbol`), spread et slippage (`friction_bps_by_symbol`), profils base et adverse ;
- symboles BTC / ETH / SOL, en 1h et 4h.

| Variante | Définition | Données |
|---|---|---|
| V0 | Stratégie existante (B7 / BASELINE fidèle, cf. VP-P #159) | existantes |
| V1 | V0 + contexte MTF explicite, règle figée a priori (ex. pas d'entrée si ≥ 2 horizons supérieurs opposés) | existantes |
| V2 | V0 + règle d'exécution carnet (§6.2 point 1) | **collecte requise** → paper shadow seulement |
| V3 | V1 + V2, seulement si V1 et V2 montrent chacune un apport | idem |

**À reporter pour chaque variante :**
- le résultat net et le drawdown maximal ;
- le nombre de trades, l'**exposition** (temps investi) et la rotation ;
- la sensibilité : ±1 cran sur chaque seuil, sans réoptimiser ;
- **un contrôle d'exposition** : V0 avec le même nombre de trades retirés **au hasard** (placebo, 1 000 tirages). Si V1 ne bat pas ce placebo, l'amélioration vient seulement de la réduction d'activité ;
- un contrôle buy & hold « B0 pondéré par l'exposition » (déjà utilisé : `VAL_B0E_WEIGHT` dans RS-D1).

**Contraintes de protocole déjà en vigueur :**
- programme VP en pause ;
- holdout 2026 fermé ;
- chaque test = une ligne au registre T10b, avec amendement VP0 **avant** le run.

Le test V1 recoupe largement B5 (§6.3). S'il est rejoué, il doit se démarquer explicitement de B5, par exemple avec plusieurs horizons, et l'écrire avant le run.

**Carnet :**
- aucun backtest possible faute d'historique ;
- on ne fabrique pas d'historique depuis les OHLCV ;
- **séquence :** collecte (N semaines) → replay de la règle V2 sur les données enregistrées → paper shadow → seulement ensuite, décision.

---

## 9. Périmètre initial et étapes

| Phase | Contenu | Pourquoi maintenant | Sortie | Coût estimé |
|---|---|---|---|---|
| **P1 — Matrice MTF moteur** | `mtf_matrix` (1h / 4h / 1d / 1w), correction de la frontière 1w de `compute_signal_timing`, route lecture seule, tests de troncature et de cohérence avec `PipelineResult` | Données déjà là ; corrige un manque de lisibilité réel (booléen → matrice) ; aucun effet sur les décisions | PR draft + tests | Faible |
| **P2 — Panneau UI + marqueurs + faits agents** | Carte MTF, phrase restituée, « Signal » / « Portefeuille », marqueurs depuis `entry_signal`, faits FactSheet `mtf.*`, matrice persistée dans `entry_signal` | Compréhension ; traçabilité de ce que le moteur savait | PR draft | Faible à moyen |
| **P3 — Collecte carnet, observation** | Service `collector-ob` BTCUSDT spot, synchro snapshot / deltas, états, brut + agrégé 1 min, tableau de bord qualité (trous, resyncs, % `SYNCED`) | Sans historique, aucune question carnet n'a de réponse ; la collecte est la condition de tout le reste | 2 à 4 semaines de données propres | Moyen (service, stockage, exploitation) |
| **P4 — Mesure d'exécution (shadow)** | `IS` réel contre l'hypothèse 2 + 3 bps, aux décisions BASELINE et RS-D1 | Première utilité mesurable du carnet | Rapport chiffré | Faible une fois P3 en place |
| **P5 — Visualisation carnet** | Couche heatmap canvas, bulles, profondeur, replay sur la plage enregistrée | Seulement si P4 montre un écart d'exécution exploitable, ou si Samir veut l'outil de lecture pour lui-même | UI | Élevé |
| **P6 — Détections D1–D11** | En observation (`used_by_decision=False`, `NON_VALIDE`), seuils figés a priori | Après P3 ; aucune n'entre dans le pipeline sans protocole | Mesures + journal | Moyen |

**Hors périmètre :** liquidations, multi-plateformes, futures, actions et FX (pas de carnet accessible dans le dépôt), score « probabilité ».

---

## 10. Avis argumenté

1. **Panneau multi-horizons : oui, en premier.**
   - C'est l'évolution qui a le meilleur rapport utilité / coût : les calculs existent et la causalité est déjà maîtrisée (bougies closes, garde HTF). Il manque surtout une **présentation honnête** et la traçabilité.
   - Il répond à un vrai défaut actuel : la contradiction entre horizons est réduite à un code `mtf_opposed` que personne ne voit.
   - Il faut le présenter comme un outil de lecture. VP3 a déjà montré qu'un filtre de ce type ne crée pas d'edge, et qu'il réduit surtout l'exposition.
2. **Heatmap de carnet : pas maintenant comme produit ; oui à une collecte limitée.**
   - L'intérêt pour une stratégie qui décide en 1h n'est pas démontré : OF-0 est négatif à titre descriptif, et le CVD exact par barre n'a jamais servi.
   - Le seul usage défendable à court terme est la **mesure de la qualité d'exécution** (P3 → P4). Il a un critère de réussite simple : l'écart réel contre l'hypothèse de coûts du paper.
   - La visualisation façon Bookmap n'a de sens qu'ensuite. Elle sert à la compréhension en temps réel, sur une plateforme, un instrument et une période enregistrée, toujours avec son état.
3. **Garde-fous à inscrire dans le code et l'UI, quelle que soit la suite :**
   - les noms (« compatible avec absorption », « indice d'alignement », jamais « probabilité ») ;
   - la plateforme et l'instrument sur chaque mesure carnet ;
   - « indisponible » plutôt qu'interpolé ;
   - SELL = sortie du long en BASELINE ;
   - `detected_at` et `confirmed_at` partout.
4. **À corriger en passant, indépendamment de ce projet :**
   - le nom de `decisions.probability` (heuristique non calibrée) ;
   - la troncature silencieuse de `fetch_binance_agg_trades` (CVD-LAB-FIX) ;
   - la frontière 1w de `compute_signal_timing`, avant d'utiliser cet horizon.

**Décision demandée à Samir :** lancer P1 + P2 (MTF), et dire si P3 (collecte carnet BTCUSDT, service séparé sur le VPS) est autorisée.
