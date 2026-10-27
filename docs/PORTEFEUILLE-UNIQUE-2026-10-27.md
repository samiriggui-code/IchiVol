# Portefeuille unique ICHIVOL_MAIN_V1 — 50 000 € virtuels (2026-10-27)

Décision du propriétaire : « on vire tous les portefeuilles et on part sur un nouveau seul portefeuille qui
trade tout, 50 000 euros de monnaie virtuelle » ; « tu concentres toute la technologie IchiVol dans un seul
portefeuille ; tu m'enlèves tous les autres ; je trade sur un seul ; les affichages UX doivent suivre ».
Paper uniquement : jamais d'ordre réel.

Sauvegarde faite avant le changement (pg_dump -Fc des bases `ichivol_engine` et `ichivol`) :
`~/Sauvegardes/ichivol/2026-10-27_avant_portefeuille_unique/`.

## 1. Ce qui alimentait des portefeuilles avant (carte de l'existant)

| Moteur | Où | Comptes alimentés |
|---|---|---|
| Scan automatique 1h (Ichimoku × RVOL) | `screener/cache.py` → `paper/engine.py:sync_auto_watchlist` | tous les codes de `syncable_profile_codes()` : BASELINE + `PARALLEL_SYNCED_CODES` (SESSIONS, FUTURES_CRYPTO, SHORTS, 4H, WIDE, COMBO) |
| Ève + JEV (autopilote) | `eve/autopilot.py` ← propositions du scan quand `EVE_PAPER_AUTONOMY` est vrai ; `eve/paper_submit.py` | chaque compte où le moteur proposait ; sans code, « tous les comptes actifs » (`list_portfolios`) |
| JEV | `app/jev/` (adaptateur LLM) | aucun directement : conseiller d'Ève (Analyste, Challenger, Guardian, audit Shadow, porte d'entrée) |
| Ordres manuels `user_confirmed` | `api/paper_orders.py` → `open_user_confirmed` | n'importe quel compte passé en `portfolio_code` (WIDE : 64 trades sur 69 en manuel) |
| RS-D1 (Donchian 4h) | `paper/rs_d1_runner.py` (boucle propre) | RS_D1_PAPER_V1 seul ; son livre `rs/book.py` tient sa propre caisse |
| Futures & Crypto | profil dédié + `api/futures_crypto.py` (vue, réglage BTC) | FUTURES_CRYPTO_V1 : YM, MGC, BTC (spot/perp/CME) |
| Front | Desk, Portefeuille « Tous », `allBooks.ts`, `equityTrajectory.ts` (`BOOK_SLOT`), `rsPortfolio.ts`, `FuturesCryptoPanel` | 8 comptes additionnés et colorés |

Défauts relevés : un compte existant ne relisait jamais son profil (`ensure_portfolio` garde la ligne en base,
d'où des réglages en base différents du code, ex. WIDE 25 000 €, risque 2 %) ; `is_active=false` n'arrêtait pas
la synchronisation ; une simple lecture d'API (`/paper/portfolios/{code}`, `/shadow/stats`) recréait un compte.

## 2. Architecture retenue

* Un seul code synchronisé : `syncable_profile_codes() == ["ICHIVOL_MAIN_V1"]`.
* `ensure_main_portfolio` crée le compte à 50 000 € et **réaligne son profil stocké sur `MAIN_PROFILE`** à chaque
  appel (sans toucher à la caisse), avec un événement de journal `PROFILE_SYNC` : le compte suit toujours le
  profil documenté.
* Les 8 anciens codes (`RETIRED_CODES`) : jamais synchronisés, jamais listés comme actifs (`list_portfolios`
  filtre sur le code, pas sur `is_active`), jamais recréés (`lookup_portfolio` ne crée que le compte unique),
  refusés pour trader (`retired_portfolio`, 403). Leurs définitions restent dans `strategy_profiles.py`
  (lecture de l'historique, backtests).
* Scan 1h, Ève + JEV et ordres manuels visent ce compte. `virtual_portfolio_codes()` = le compte unique.
* Route `/paper/futures-crypto` supprimée ; YM rejoint le compte unique.
* RS-D1 : boucle coupée par défaut (`enable_rs_d1_paper=False`). Son livre (`rs/book.py`) calcule sa taille sur
  sa propre caisse et ne peut pas partager le compte sans adaptation ; le code RS, ses tests et ses backtests
  restent. Choix retenu le 27/10 (réglages laissés à notre jugement par le propriétaire).
* Nouvelle route `GET /paper/portfolios/{code}/breakdown` : bilan par décideur (Ève / moteur contre Ève / moteur
  seul / manuel) et par classe d'actifs, drawdown, règles et univers du compte (`app/paper/breakdown.py`).

## 3. Profil du compte (`MAIN_PROFILE`, `app/paper/strategy_profiles.py`)

| Réglage | Valeur | Origine |
|---|---|---|
| Capital de départ | 50 000 € | décision du propriétaire |
| Risque par trade | 0,5 % (250 € au départ) | baseline 2026-09-21 |
| Lot max (notionnel) | 10 % du capital (5 000 €), aussi par symbole | baseline |
| Positions ouvertes max | 10 | baseline |
| Risque ouvert total max | 4 % (2 000 €) | baseline |
| Arrêt des entrées | −3 % sur la journée (verrou persistant) | baseline |
| Objectif | 2 R ; sortie au changement de direction Ichimoku, stop ATR obligatoire | baseline |
| Vente à découvert | **oui sur CFD (forex, métaux, indices, pétrole) et YM, jamais sur la crypto au comptant** | comme un vrai courtier (décision du propriétaire, 27/10) ; `short_symbols` du profil |
| Horizon automatique | boucle 1h | baseline |
| Notionnel minimum | 50 € | prudent |
| Frais crypto spot | commission 7,5 bps + friction par paire (tableau documenté) | baseline / FWD |
| Frais CFD (forex, métaux, indices, pétrole) | spread seul + financement de nuit (hypothèse) | baseline |
| Frais YM | commission 0,1 bp, friction 0,5 bp, pas de swap | `futures_crypto.py` (hypothèses) |
| Univers élargi | friction **supposée** 3 à 8 bps par côté selon la paire | nouveau, prudent, à vérifier sur fills |

### Univers (38 instruments)

* Crypto de base (19) : BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK, DOT, LTC, ATOM, UNI, NEAR, APT, ARB, OP,
  SUI, TON (USDT).
* Univers élargi (11) : TRX, BCH, ETC, FIL, INJ, AAVE, HBAR, ICP, SEI, XLM, TIA (USDT).
* Forex : EURUSD, GBPUSD. Métaux : XAUUSD, XAGUSD. Indices : SPX, NDX. Énergie : WTI. Futures : YM.

Exclus, avec la raison (rendue aussi par `/breakdown`) :

| Instrument | Raison |
|---|---|
| PEPEUSDT | friction 14,6 bps par côté > 12 bps (règle de liquidité) |
| USDJPY | coté en JPY : pas de conversion de devise de cotation, taille fausse |
| AAPL, TSLA | actions Twelve Data : quota gratuit trop faible pour la boucle de fond |
| MGC | même cotation que XAUUSD : deux lots sur le même prix |
| BTCPERP, BTCCME | même sous-jacent que BTCUSDT (déjà tradé en spot) ; pas de flux CME |

### Règle de liquidité minimale

1. **Statique** (univers) : friction documentée obligatoire et ≤ 12 bps par côté ; sinon exclu.
2. **Dynamique** (boucle 1h) : une paire Binance spot n'ouvre rien si son volume des 24 dernières heures est
   < 5 M USDT (code de refus `illiquid_24h_volume`, journalisé). Le lot déjà ouvert reste géré (stop, objectif,
   signal). Les CFD (volume de ticks) ne sont pas concernés.
3. Ordres manuels : refusés sur un instrument exclu pour une raison documentée ; ailleurs, choix de l'utilisateur.

## 4. Règle d'arbitrage entre moteurs

**Un seul lot ouvert par symbole dans le compte, tous sens, horizons et décideurs confondus ; le premier arrivé
le possède.** (Code déjà présent, désormais documenté et testé : `_lock_symbol` (verrou consultatif PostgreSQL
par compte et symbole) + `_get_open_by_symbol` dans `sync_position` et `open_user_confirmed`.)

* Un autre moteur qui veut ouvrir le même symbole (même sens ou sens opposé) n'ouvre rien : le scan journalise
  `position_already_open`, Ève reçoit `already_open`, un ordre manuel reçoit le lot existant.
* Aucun moteur ne retourne une position : pas de sortie-puis-entrée en sens opposé.
* Le signal du scan ne ferme jamais un lot ouvert par un autre décideur (Ève, manuel) ; seuls son stop, son
  objectif, la surveillance de protection ou un ordre explicite le ferment. En mode « Ève décide », le scan ne
  propose ni ouverture ni fermeture sur un lot qu'il ne possède pas.
* Ensuite, le Risk Kernel a le dernier mot pour chaque ouverture (positions max, risque ouvert, perte du jour,
  kill switch, caisse).

Tests : `tests/paper/test_main_portfolio.py` (arbitrage Ève → scan → manuel, scan → Ève, short refusé sur crypto, short ouvert sur CFD).

## 5. Toute la technologie travaille pour ce compte

Aucun indicateur ni outil n'est retiré. Ce qui n'existait que dans un compte retiré est rattaché au compte
unique :

| Méthode | Avant | Maintenant |
|---|---|---|
| Ichimoku × RVOL (pipeline), ATR | tous les comptes | décide les entrées et sorties du compte unique |
| Structure (MVPP + trendln), Fibonacci, RSI, CMF/OBV, régime ATR | compte « Tout combiné » (filtres bloquants) | calculés sur chaque signal du compte unique, **en observation** : verdict enregistré dans `entry_signal.filters_observed` (aurait refusé ou non), aucun refus tant qu'aucun avantage n'est démontré |
| Fenêtres de sessions Tokyo / Londres / New York | compte Sessions | calculées en observation : `entry_signal.decision_event` |
| Ventes à découvert | compte Shorts | ouvertes sur CFD et YM ; sur crypto au comptant, refusées (`short_not_allowed`, journalisées) |
| Horizon 4h | compte 4h | toujours analysé (screener, matrice multi-horizons `mtf_matrix` enregistrée sur chaque signal) |
| Univers élargi | compte Wide | dans l'univers du compte unique |
| YM | Futures & Crypto | dans l'univers du compte unique |
| Donchian RS-D1 | compte RS-D1 | code, tests et backtests gardés ; boucle paper coupée (choix retenu le 27/10) |
| Ève, JEV, audit Shadow, porte d'entrée, Risk Kernel | autopilote multi-comptes | autopilote sur le compte unique |
| Registre d'indicateurs (17), Strategy Lab, backtests, preuves, prédictions, graphiques | inchangés | inchangés |

Garde-fou : `tests/indicators/test_registry_inventory.py` échoue si un indicateur du registre, une porte de
filtre ou un moteur d'analyse disparaît.

**Emplacement prévu pour le VWAP** (plan d'intégration rendu par la recherche VWAP, pas intégré ici) : un filtre
de plus dans la chaîne de `sync_auto_watchlist` (structure → Fibonacci → contexte → *VWAP*), d'abord en
observation comme les autres ; côté Ève, un fait de plus dans le contexte (`eve/context.py`) lu par l'Analyste.

## 6. Ève : nouvelle règle de synthèse (commit séparé)

Avant, le choix du Challenger passait en premier et son ABSTAIN (« pas de meilleure alternative ») écrasait
l'Analyste : 100 % d'abstentions sur 174 dossiers. Maintenant : alerte critique du Guardian → ABSTAIN ;
fragilité ≥ 0,7 → ABSTAIN ; contradiction explicite du Challenger → on le suit ; sinon l'Analyste.
`synthesis.decision_rule` dit quelle règle a tranché.

Effet attendu : Ève proposera des directions. Sur un CFD ou YM, un avis SHORT d'Ève peut ouvrir une vente à
découvert ; sur une crypto au comptant, il ne peut pas (Risk Kernel : `short_not_allowed`) et, face à une
proposition LONG du moteur, reste un désaccord (le moteur trade « contre Ève »). Un avis SHORT sur un lot LONG
ouvert vaut accord pour le fermer (`eve_accepts`), donc plus de clôtures décidées par Ève qu'avant.

## 7. Procédure de mise en production

1. Fusionner **#195** (`fix/caisse-ordres-simultanes`), puis la branche **`portefeuille-unique-50k`**.
2. Déployer (moteur + front). Au démarrage, le moteur crée `ICHIVOL_MAIN_V1` à 50 000 €. Vérifier :
   `GET /api/engine/paper/portfolios` ne rend que `ICHIVOL_MAIN_V1` ; `/breakdown` répond.
3. `docker compose stop engine`.
4. `psql -v ON_ERROR_STOP=1 -d ichivol_engine -f scripts/repairs/2026-10-27_portefeuille_unique_suppression_anciens.sql`
   (ROLLBACK par défaut) ; comparer les blocs AVANT / APRÈS avec la sauvegarde.
5. Remplacer la dernière ligne par `COMMIT;`, relancer le script, puis `docker compose start engine`.
6. Si l'autonomie d'Ève est voulue sur ce compte : `EVE_PAPER_AUTONOMY=true` (inchangé).
