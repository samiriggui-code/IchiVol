# RS-09 — RS-D1 en paper live : choix de conception (écrits avant le code)

**Statut :** note de conception · job 2 transmis par ichivol-95 (feu vert de Samir) · 2026-09-28 · aucun code écrit à la date de ce commit.
**Objectif :** faire vivre RS-D1 ([RS-03](./RS-03-DONCHIAN-4H-SPEC.md)) en paper sur les données live dans un portefeuille séparé, `RS_D1_PAPER_V1`, sans ouvrir le holdout (on observe 2026 en temps réel, on ne rejoue pas 2026).
**Pas d'amendement :** il n'y a aucune nouvelle hypothèse. C'est une observation forward, pas un verdict.

---

## 1. Une seule implémentation des règles

**Constat :** `rs/donchian.py::simulate` est une boucle monolithique. `paper_broker.open_capital_position` redimensionne l'ordre avec `risk.size_position` sur l'equity **marquée**, alors que RS-03 §5 dimensionne sur l'equity **au coût**. L'appeler créerait une seconde règle de taille.

**Choix :**
- **Extraction sans changement de comportement.** L'état et les étapes de `simulate` vont dans `rs/book.py` :
  - `Book` porte l'état : cash, positions, ordres en attente, dernière sortie, dernier close, verrou journalier, **état du `random.Random(7)`**, rejets, journal ;
  - quatre étapes, **dans l'ordre exact actuel** :
    1. `fill_pending(t)` : sorties de canal puis entrées, à l'open ;
    2. `check_stops(t)` : stop intrabarre ;
    3. `on_close(t)` : valorisation, stop suiveur, décision de sortie de canal, equity, verrou journalier ;
    4. `decide(t)` : entrées, avec le tirage aléatoire de l'ordre de traitement.
  - `simulate()` devient une boucle qui appelle ces étapes.
- **Preuve de non-régression :** `rs.run` et `rs.validate` produisent des artefacts JSON **identiques octet pour octet** avant et après (hors horodatage de génération). Le diff sera joint à la PR.
- **Le live appelle le même `Book`.** Le runner ne contient **aucune** règle. Il fait trois choses : il fournit les barres, il persiste le `Book`, et il recopie les effets du `Book` dans les tables paper.

## 2. Écritures paper : pré-dimensionnées

- **Entrée.** Nouvelle fonction `paper_broker.open_presized_position(...)`. Elle écrit position, ordre, ledger et journal avec la quantité, le fill, la commission et le stop **calculés par le `Book`** (`rs.size_entry`, `SymbolCost`). C'est un ajout : aucune fonction existante du broker n'est modifiée.
- **Sortie.** `paper_broker.close_capital_position(price=raw)` existant. Sa formule, fill = `raw × (1 − friction)` puis commission sur `qty × fill`, est **identique** à `SymbolCost.fill/fee`. Un test le vérifie.
- **Coûts.** Profil paper RS-03 §6 : 7,5 bps, plus une friction par côté de 1,0 (BTC), 1,0 (ETH) et 1,5 (SOL), recopiée dans le `strategy_profile` du portefeuille.

## 3. Stop intrabarre en live : monitor de protection existant (klines 1 min)

- Le monitor exige aujourd'hui un take-profit, et RS-D1 n'en a pas. **Changement minimal** dans `protection.py` : une position dont `take_profit_price` est nul **et** dont le profil du portefeuille déclare `engine = "rs_d1"` est surveillée avec un objectif infini. Les autres positions gardent exactement le comportement actuel.
- Le monitor **ne modifie jamais** le stop d'une position RS : pas de trail, pas de partiel, pas de renfort. Il n'y a pas de clés T0-MANAGE dans le profil RS.
- **Écart assumé entre live et backtest :**
  - le monitor exécute au stop, ou **à l'open de la minute** en cas de gap intrabarre ;
  - `simulate` exécute au stop, ou à l'open de la barre **4h** en cas de gap à l'ouverture.
  - L'écart est documenté et journalisé (`granularity` dans le payload de sortie). Le test de parité (§8) passe par les barres 4h et n'est donc pas concerné.
- **Réconciliation :** à chaque cycle, une position RS que le monitor a fermée est retirée du `Book`, avec le prix et le motif réels, avant toute nouvelle décision. **La base est la référence** pour le cash et les positions.

## 4. Calendrier live

- **Boucle de fond `RsD1Runner`** : un thread, comme `ProtectionMonitor`, qui s'active toutes les 60 s. Pas de LLM, rien dans le pipeline ni le screener.
- **Barres :** klines 4h Binance spot **fermées uniquement** (`close_time < maintenant`), BTC / ETH / SOL. On garde un historique de 200 barres pour Donchian 55 et ATR 14.
- **À la clôture d'une nouvelle barre `t`**, toutes paires présentes :
  1. `on_close(t)` puis `decide(t)`, exactement comme `simulate` ;
  2. puis, sans attendre, `fill_pending(t+1)` au **prix d'ouverture de la barre 4h `t+1`** (champ `open` de la kline en cours, fixé dès le premier trade). C'est l'équivalent de `open(t+1)` en backtest.
- **Démarrage (point ambigu de RS-03 en live) :**
  - le `Book` démarre **vide**, avec 5 000 € ;
  - la barre en cours au démarrage n'est **jamais** décidée ;
  - la première décision a lieu à la première clôture **postérieure** au démarrage ;
  - **aucune entrée rétroactive** sur une cassure antérieure au démarrage. Si le prix est déjà au-dessus de U55, l'entrée n'a lieu que si `close > U55` est vrai à cette première clôture. C'est la règle d'état de RS-03 §3, appliquée normalement.
- **Arrêt ou panne (cycles manqués) :**
  - au redémarrage, les barres fermées manquées sont traitées **dans l'ordre** : stops suiveurs, décisions de canal, verrou journalier ;
  - une **entrée** dont la barre d'exécution est dépassée de plus d'une barre est **annulée** (rejet `stale_entry`) : on ne trade pas dans le passé ;
  - une **sortie** en retard est exécutée au premier prix disponible (motif conservé, `late_fill=true`).
- **Journée :** clé = jour UTC de la **fin** de barre, comme `simulate::_day`.

## 5. Séparation des portefeuilles

- Nouveau profil `RS_D1_PAPER_V1` dans `strategy_profiles.py` :
  - `engine = "rs_d1"` ;
  - `sync_auto = False` ;
  - `auto_timeframes = []` ;
  - `allow_short = False` ;
  - coûts RS ;
  - aucune clé T0-MANAGE.
  - Il n'est **pas** ajouté à `syncable_profile_codes()`, qui reste `[BASELINE]`.
- Le cash, les positions, le kill switch et le verrou de perte journalière sont déjà **par portefeuille** (`portfolio_id`, colonnes de `paper_portfolios`).
- **`ICHIVOL_BASELINE_V1` n'est pas touché** : ni son profil, ni `auto_timeframes = ["1h"]`, ni sa ligne en base.
- **Garde-fous côté serveur :**
  - la boucle Ichimoku, le sync et l'achat manuel refusent le code `RS_D1_PAPER_V1` ;
  - le runner RS ne lit ni n'écrit que ce portefeuille.
  - Tests croisés : une action sur l'un ne modifie pas l'autre.

## 6. Persistance de l'état RS

- Table `rs_book_state`, via une migration alembic : `portfolio_code`, `last_bar_time`, `state_json` (ordres en attente, `highest_close`, `last_exit_time`, jour et verrou, état du `random`, compteurs de rejet) et `updated_at`.
- Chaque cycle s'exécute dans **une transaction** : écritures paper et état du `Book` ensemble. Le cycle est idempotent par `last_bar_time`.
- Le stop courant est aussi écrit sur `paper_positions.stop_price`, pour que le monitor l'utilise, avec un événement de journal `RS_TRAIL_STOP`.

## 7. Journal et UI

- **Événements :**
  - `RS_DECISION` (entrée ou sortie décidée, niveaux U55, L20 et ATR) ;
  - `RS_REJECTED` (motif RS-03 : `open_risk_cap`, `daily_loss_halt`, `insufficient_cash`, `stale_entry`…) ;
  - `RS_TRAIL_STOP` ;
  - `RS_CYCLE` (barre traitée), écrit seulement quand une barre est traitée.
- **UI minimale :** la page Portefeuille reçoit un sélecteur de portefeuille. `RS_D1_PAPER_V1` y apparaît avec le libellé « RS-D1 — validé 2025, holdout 2026 non ouvert ». Pour ce portefeuille, **aucun bouton d'achat ni de fermeture manuelle**. L'API renvoie 403 sur `/paper/positions` (POST) et `/close` pour ce code.

## 8. Tests exigés

1. **Parité :** rejouer 2024 (VP1 4h) par le chemin live (runner + base SQLite ou Postgres + `Book`) doit donner des trades **identiques** à `rs.simulate` : symbole, heures, prix, quantités, motifs.
2. **Non-régression :** `rs.run` et `rs.validate` identiques octet pour octet.
3. **Troncature :** aucune décision à `t` ne lit de barre non fermée ; la barre en cours au démarrage est ignorée.
4. **Séparation** des portefeuilles (dans les deux sens), refus de l'achat manuel, surveillance sans TP par le monitor pour les positions RS seulement.
5. **Retard :** entrée périmée annulée, sortie tardive exécutée.
6. `pytest` complet sur Postgres, `npm test`, `npx tsc -b`.

## 9. Hors périmètre

- Aucun déploiement : il se fera après la revue d'ichivol-95.
- Aucune modification de `app/agents/` ni de `server/src/agent/` (chantier AG-FS0).
- Aucun changement du pipeline, des gates, du screener ni du portefeuille baseline.
