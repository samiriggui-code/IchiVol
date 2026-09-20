# Plan de release ordonné — à valider par l'utilisateur (rien n'est appliqué)

Auteur : session ichivol-49. Statut : **brouillon pour validation**. Aucune étape ci-dessous n'a été exécutée ; chaque étape marquée ⛔ exige un « oui » explicite de l'utilisateur.

## 0. État de départ (lu, pas supposé)

| Élément | Valeur constatée |
|---|---|
| Base de production (`ichivol_engine`) | Alembic `d4e5f6a7b8c9` ; 12 portefeuilles, aucune table `ledger_*` |
| Image `ichivol-engine` en marche | créée 2026-09-20 17:34:07 UTC, démarrée 17:34:14, 0 redémarrage ; **sans** `timing.py`, **sans** verrou par symbole, **sans** surveillance |
| Arbre hôte `/opt/ichivol` | contient déjà `brokerage/*`, `binance_quotes`, `contracts`, `quality`, migration `e5f6a7b8c9d0`, `models.py`/`routes.py`/`types.py` du local (rsync de 17:47) |
| Danger | `docker-entrypoint.sh` fait `alembic upgrade head` : **toute reconstruction de l'image du moteur activerait ledger + double écriture** |
| Reliquats VPS supprimés du dépôt | `market_data/mt5.py`, `pages/PaperTechPage.tsx` |

## 1. Confirmation : `DECIDE_ON_CLOSED_CANDLES=true` en production

Lu sur le VPS (lecture seule) :

- Conteneur `ichivol-engine` : créé `2026-09-20T17:34:07Z`, **démarré `2026-09-20T17:34:14Z`**, `RestartCount=0`.
- `settings.decide_on_closed_candles` chargé dans le processus = `True` ; aucune variable d'environnement ne la surcharge (`printenv` : aucune ligne `DECIDE_ON_CLOSED_CANDLES` ; absente aussi de `deploy/vps/.env` et de `docker-compose.yml`) → c'est la **valeur par défaut du code**.
- `service.py` de l'image contient `_closed_only` (4 occurrences).
- **Instant précis** : le comportement « bougies clôturées » est celui du processus depuis **17:34:14 UTC (19:34:14 heure de Paris)** ; la première synchronisation issue de ce mode est celle de **17:34:36** (les 13 ouvertures automatiques de cette seconde). Avant : comportement intrabougie (dernière bougie en formation incluse).
- Sensibilité : dans ce mode, `candles[-1]` est la dernière bougie **clôturée** (donc ne plus utiliser « `candles[-1].time + tf > now` » pour détecter une bougie en formation) ; `price` reste le cours live.
- **Attention** : la version en production n'a **pas** `signal_timing` ni le garde de péremption (voir §2).

## 2. Confirmation : le garde de péremption refuse TONUSDT

Vérifié sur données Binance réelles (local, code non déployé) :

- Dernière bougie TONUSDT 1h : ouverture `2026-06-30 02:00 UTC` (confirmé par l'API brute).
- `scan_symbol("TONUSDT","1h")` → `lag_bars = 1984`, `data_late = True`, **`stale = True`**, décision NO_TRADE.
- **Trou trouvé et corrigé** : `propose_order_intent` refusait déjà (`stale_data`), mais la synchronisation automatique et `POST /paper/positions` **ne consultaient pas** `stale`. Ajout (local, testé) : `sync_auto_watchlist` ignore les lignes périmées (ni ouverture, ni fermeture sur signal, ni valorisation à un prix figé) et la route d'ouverture répond `422 stale_data`. Tests : `test_stale_signal_refused_with_reason_and_no_effect`, `test_auto_sync_skips_stale_rows`.
- En production **aujourd'hui** : le garde n'existe pas (image sans `timing.py`) ; TONUSDT ne s'y ouvre pas parce que sa décision est NO_TRADE, pas parce qu'il est refusé comme périmé.

## 3. Ordre des commits (un commit = un objet vérifiable, chacun avec ses tests)

| # | Contenu | Auteur / propriétaire | Schéma | Dépend de |
|---|---|---|---|---|
| C1 | `paper/counters.py`, `paper/gates.py` + tests. **Opt-in `log_rejections` seulement pour de nouveaux profils expérimentaux** ; aucun des 12 profils existants ne définit ce drapeau (vérifié : aucune occurrence dans `strategy_profiles.py`) ⇒ code déployé sans effet sur eux | ichivol-69 | aucun | — |
| C2 | Bougies clôturées + datation : `config.py`, `screener/service.py`, `screener/timing.py`, `market_data/quality.py`, `api/serializers.py` + tests | 49 | aucun | — |
| C3 | Chemin d'ouverture : `paper/risk.py` (lot minimal), `paper/intent.py`, `paper/engine.py` (verrou par symbole, garde périmé, hooks de C1), `api/routes.py` (garde périmé, `already_open`, aperçu `open_entry_fees`) + `tests/api/test_open_flow.py` | 49 (+ hooks 69, routes Cursor) | aucun | C1, C2 |
| C4 | Front : `DecisionsPage.tsx` (ouvrir puis journal), `PaperConfirmSheet.tsx` (bannière) ; Synthèse/BrokerAccount de Cursor en commit séparé | 49 / Cursor | aucun | C3 |
| C5 | Journal comptable : `db/models.py`, migration `e5f6a7b8c9d0`, `brokerage/*`, `market_data/{contracts,binance_quotes}.py`, `universe/types.py`, `paper/broker.py` (double écriture, `at`, `protection_monitored`, frais versionnés) + tests | 49 | **oui (additif)** | C3 |
| C6 | Surveillance des protections : `paper/protection.py`, `main.py`, drapeaux de `config.py` + tests | 49 | aucun | C5 |
| — | Réparation LINK : `scripts/repairs/…archive_orphan_link_confirmation.sql` (hors code) | 49 | données | — |

Règle : `paper/engine.py`, `routes.py` et `DecisionsPage.tsx` mélangent plusieurs auteurs ; chaque auteur committe ses hunks (`git add -p`) dans l'ordre ci-dessus, sans réécrire ceux des autres. Le VPS ne doit plus jamais recevoir un `rsync` de l'arbre de travail : il reçoit un **commit** (`git archive <sha>` vers `/opt/ichivol/releases/<sha>`, bascule par lien symbolique), pour que le code déployé soit reproductible.

## 4. Étapes de déploiement (chacune ⛔ : validation utilisateur, sauvegarde préalable, retour arrière)

Prérequis communs à chaque étape : `pg_dump -Fc ichivol_engine` archivé hors du conteneur ; comparaison à trois (script `threeway.py`) montrant **aucun** fichier « VPS modifié » hors de la release ; les autres sessions confirment qu'elles ne déploient pas.

### D1 ⛔ — C1 → C4 (aucun changement de schéma)
- Construire `engine` et `web` **depuis le commit** ; le commit ne contient **pas** la migration `e5f6a7b8c9d0` (elle est en C5) et l'hôte doit être nettoyé du rsync de 17:47 (fichiers ledger/brokerage/models retirés de l'arbre construit), sinon `alembic` s'exécuterait.
- Vérifications après : `alembic current` = `d4e5f6a7b8c9` ; `GET /paper/propose` sur LINK/TON (lecture seule) montre `signal_timing`, TON refusé `stale_data` ; **aucune** ouverture de test en production (l'essai d'ouverture réel se fait sur la copie/staging).
- Retour arrière : relancer l'image précédente (`ichivol-engine:latest` de 17:34 conservée sous une étiquette datée avant reconstruction) ; aucune donnée modifiée.

### D2 ⛔ — C5 (migration additive + double écriture)
- Avant : essai de la migration sur une copie **fraîche** de la production (déjà fait le 20/09 : empreintes positions/portefeuilles/ordres/journal inchangées, aller-retour OK) ; `python -m app.brokerage.reconcile` doit afficher `ok`/`no_ledger` sur la copie.
- Application : `alembic upgrade head` (2 tables) puis démarrage du moteur ; les portefeuilles reçoivent une écriture d'ouverture `CORRECTION` à leur première opération (jamais un faux dépôt).
- Vérification : `python -m app.brokerage.reconcile` = tous `ok`/`no_ledger` ; après la première ouverture/fermeture automatique, `ok` pour le portefeuille concerné. **Une seule source de vérité reste `paper_portfolios.cash`** ; le journal est dérivé et réconcilié.
- Retour arrière : `alembic downgrade d4e5f6a7b8c9` (supprime seulement `ledger_*`, testé) + image D1.

### D3 ⛔ — C6 (protections)
1. **Essai à blanc en production, sans écriture** : `python -m app.paper.protection --dry-run` dans le conteneur ; attendu : APT `legacy_watermark_initialised` avec `history_breach = take_profit_hit à 2026-09-19T04:15:00Z`, NEAR sans franchissement, LTC/AVAX `unprotected_legacy_no_levels`. L'utilisateur relit le rapport.
2. **Activation** : `ENABLE_PROTECTION_MONITOR=true` (défaut) ; les positions historiques reçoivent un repère « à partir de maintenant » et **ne sont pas fermées d'après l'historique**. Toute fermeture d'APT reste une décision de gestion séparée de l'utilisateur.
3. Surveillance : événements `PROTECTION_CHECKED` dans le journal, logs `protection:`. Retour arrière : `ENABLE_PROTECTION_MONITOR=false` + redémarrage (aucune écriture à défaire ; les fermetures déjà effectuées restent dans l'historique comme des sorties normales).

### D4 ⛔ — Réparation LINK (données)
- Enregistrement : `decisions.id = b263c134-40fb-432d-9b1a-ad1449a00406` (LINKUSDT 1h, `confirmed`, gate WATCH). Vérifié : 0 position `user_confirmed` sur LINK, 0 position/ordre du portefeuille de base sur LINK le 18/09 entre 19:35 et 19:50, aucun mouvement financier.
- Action : `confirmed → archived` + note, avec garde et retour arrière (dans le script). Indépendante de D1–D3.

## 5. Ce qui reste hors périmètre de cette release
Cotations bid/ask dans le flux normal, frais de financement, marge, règlement, plafonds d'exposition globale et de perte journalière ; barème Binance (0,10 %) toujours une hypothèse non vérifiée ; vérification visuelle dans un navigateur (aucun accès authentifié depuis les sessions).
