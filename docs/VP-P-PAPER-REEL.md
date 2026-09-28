# VP-P — Ce que le paper exécute réellement (audit code + production)

**Date :** 2026-09-27 · **Auteur :** Claude (local) · **Branche :** `claude/vp-p-paper-fidele` (base `main` @ `99ffc66`)
**Portée :** portefeuille `ICHIVOL_BASELINE_V1`, seul portefeuille actif (`SINGLE_PORTFOLIO_MODE = True`).
**Méthode :** lecture du code exécuté par le moteur, puis contrôle en lecture seule de la base de production
(`ichivol_engine` sur le VPS) : profil stocké, positions depuis le reset du 2026-09-21 09:06 UTC, journal des rejets.
Aucune écriture en production.

> Ce document décrit l'implémentation. Quand il diverge d'une description du protocole ou d'un handoff,
> **c'est le code qui fait foi** et l'écart est signalé (colonne « Écart vs descriptions »).

---

## 1. Chaîne d'exécution

```
ScreenerCache._loop (thread, toutes les 300 s, TF par défaut 1h)          app/screener/cache.py
  └─ scan_watchlist(DEFAULT_WATCHLIST, "1h")                               app/screener/service.py
       └─ scan_symbol : 300 bougies, on retire la bougie en formation      (_closed_only, decide_on_closed_candles=True)
            └─ build_pipeline(...) → décision BUY / SELL / WATCH / NO_TRADE + direction Ichimoku
  └─ paper_tradable_rows : fournisseurs binance + biquote, sauf USDJPY
  └─ sync_auto_watchlist → sync_position(portefeuille baseline)            app/paper/engine.py
       ├─ position ouverte : stop/TP au prix courant, puis sortie « direction »
       └─ pas de position : Risk Kernel (gates) → open_capital_position       app/paper/risk_kernel.py, broker.py
ProtectionMonitor (thread, toutes les 60 s) : stop/TP sur bougies 1 min    app/paper/protection.py
```

Le profil réellement stocké en base (`paper_portfolios.strategy_profile`, lu le 2026-09-27) est **identique**
à `BASELINE_PROFILE` du code (`app/paper/strategy_profiles.py`), hormis les clés de financement CFD absentes
(sans effet sur la crypto spot).

## 2. Entrées

| Élément | Implémentation | Écart vs descriptions |
|---------|----------------|-----------------------|
| Signal | `decision == "BUY"` du pipeline (`build_pipeline`), sur la dernière bougie **close** | — |
| Direction | `ichimoku_agent` LONG requis ; shorts refusés (`allow_short=False`, rejet `short_not_allowed`) | — |
| Filtres **bloquants** (statut FAIL) | Régime : ATR ni `DEAD` (< p15) ni `EXTREME` (> p90) sur 100 barres, **ADX** tendance confirmée (TRENDING/STRONG), **Donchian** cassure haussière ; Participation : RVOL `anomaly_level == LOW` ; Structure : BOS baissier ; Location : congestion HVN, sous la value area, ou sous l'AVWAP | — |
| Filtres **non bloquants** | MTF 4h opposée, structure opposée, RVOL non confirmé → statut WATCH seulement : **ne bloquent jamais** un BUY | Le filtre « MTF » est souvent décrit comme un filtre d'entrée : dans le pipeline live, **il n'en est pas un** |
| OI / funding | Ajoutent des codes, ne changent jamais un statut | Sans effet sur la décision |
| Unité de temps | Boucle automatique : **1h** uniquement | **Écart production :** un appel UI `GET /screener?timeframe=15m|4h|1d` relance le scan **avec synchronisation paper** sur ce TF (`screener_cache.refresh(tf)`). 8 positions automatiques sur 39 de la première semaine viennent de là (15m ×5, 4h ×2, 1d ×1). Comportement non systématique, dépend de la navigation |
| Univers | 20 cryptos Binance (`A_UNIVERSE`) + marchés biquote (EURUSD, GBPUSD, XAUUSD, XAGUSD, SPX, NDX, WTI) | 8 positions automatiques 1h sur 31 étaient non-crypto (SPX, NDX, WTI) |
| Fenêtre de calcul | 299 bougies closes par décision (300 demandées, la bougie en formation est retirée) | Mesuré (voir rapport) : décisions identiques au calcul sur tout l'historique sur l'échantillon testé |

## 3. Sorties (ordre de priorité réel)

1. **Stop / objectif** — deux chemins : (a) à chaque cycle de 5 min, au prix courant (`check_stop_or_tp`) ;
   (b) `ProtectionMonitor` chaque minute sur bougies 1 min (et ticks pour lever l'ambiguïté d'une minute qui
   touche les deux niveaux ; sinon **stop d'abord**). Gap au-delà du niveau → exécution à l'ouverture de la minute.
2. **Changement de direction** (`exit_mode="direction"`) : si la direction Ichimoku de la dernière bougie close
   n'est plus LONG (NEUTRAL ou SHORT), sortie au prix courant du cycle. Un simple retour à WATCH/NO_TRADE **ne ferme pas**.
   Seulement pour une position ouverte par la même source et le même TF.
3. **Manuel** (`manual_close`) : 10 des 43 positions de la première semaine.

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| Stop | `entry_fill − 1.5 × ATR(14)` de la barre signal (niveau ancré sur le **prix d'exécution**, frictions incluses) | `risk.size_position` |
| Objectif | `entry_fill + 2 × 1.5 × ATR(14)` (2R) | idem |
| Time-stop | **aucun** | — |
| Trailing / prise partielle / renfort | **désactivés** pour les positions automatiques (opt-in `user_confirmed` seulement, absents du profil) | `protection_trail/partial_tp/reinforce` |

## 4. Taille des positions et limites

| Règle | Valeur | Effet mesuré en production (1ʳᵉ semaine) |
|-------|--------|------------------------------------------|
| Risque visé | 0,5 % de l'equity « au coût » (`cash + notionnels ouverts`, **sans** réévaluation) | — |
| Plafond par position | 10 % de cette equity | **Toujours atteint en crypto** : notionnel ≈ 500 € sur 5 000 €, risque réel 9–15 € soit **0,2–0,3 %**, pas 0,5 % |
| Positions simultanées | 10 max | jamais atteint la 1ʳᵉ semaine |
| Risque ouvert cumulé | ≤ 4 % de l'equity | jamais atteint |
| Une position par symbole | oui (tous TF / sources confondus) | 32 rejets `position_already_open` |
| Une entrée par « série » de signal | oui (mémoire **en RAM**, perdue au redémarrage) | 101 rejets `signal_already_processed` |
| Perte journalière | 3 % → **verrou persistant**, réouverture humaine uniquement | jamais déclenché |
| Cash insuffisant | ordre réduit au cash disponible ; refusé s'il tombe sous 25 % de la taille visée ; minimum 10 € | — |

Conséquence directe : l'exposition maximale est de 10 × 10 % = 100 % du capital, mais chaque position ne pèse que
10 % ; une stratégie qui gagne sur une position ne fait progresser le capital que de ~10 % de ce gain.

## 5. Coûts et exécution

| Élément | Crypto (valeurs réelles du profil) |
|---------|------------------------------------|
| Commission | 7,5 bps par côté (BNB) |
| Spread + slippage | **remplacés** par une friction par symbole (1,0 bps BTC/ETH/BNB, 1,5 SOL … 14,6 PEPE), slippage 0 |
| Moment d'entrée | premier cycle de 5 min après la clôture de la barre signal, au dernier prix échangé (≈ ouverture t+1, avec 0–5 min de décalage + latence de scan) |
| Moment de sortie « direction » | idem (décision sur barre close, exécution au cycle suivant) |
| Valorisation | USDT = EUR (proxy) |

## 6. Ce que la simulation reproduit / ne peut pas reproduire

| # | Élément | Reproduit ? | Impact potentiel |
|---|---------|-------------|------------------|
| 1 | Pipeline BUY sur 1h barre close, 20 cryptos | Oui (mêmes fonctions `build_pipeline`) | — |
| 2 | Taille 0,5 % / plafond 10 % / 10 positions / 4 % risque ouvert / equity au coût | Oui (`research_lab/sim.py`, options VP-P) | — |
| 3 | Stops ancrés sur l'exécution, TP 2R, sortie direction, pas de time-stop | Oui | — |
| 4 | Coûts par symbole (7,5 bps + friction) | Oui (`cost_by_symbol`) | — |
| 5 | Stop/TP surveillés à la minute (+ ticks) | **Approché** : barres 1h, stop d'abord si les deux niveaux sont dans la même barre | Pessimiste sur les barres ambiguës (comptées dans le rapport) |
| 6 | Exécution à 0–5 min après la clôture | **Approché** : ouverture t+1 | Faible en moyenne, non mesuré |
| 7 | Marchés non-crypto (biquote) | **Non** : pas de données VP historiques reproductibles | Sous-estime la concurrence pour les 10 places et le capital ; ignore leur P&L |
| 8 | Scans UI 15m/4h/1d | **Non** (dépend de la navigation) | Positions supplémentaires hors stratégie 1h |
| 9 | Clôtures et achats manuels | **Non** | Hors stratégie |
| 10 | Mémoire « une entrée par série » perdue au redémarrage | **Non** (le sim ne redémarre jamais) | Le live peut ré-entrer dans une même série après redémarrage |
| 11 | Verrou perte journalière persistant | **Approché** : levé le jour UTC suivant | Nombre de déclenchements reporté ; si > 0, le live aurait été bloqué plus longtemps |
| 12 | Ordre de traitement quand la place manque | **Approché** : ordre aléatoire (seed 7) ; live = tri par décision / confiance | Reporté via les rejets `max_positions` |
| 13 | Sélection de l'univers | Univers choisi en 2026 (survivants) ; APT, ARB, OP, SUI, PEPE, TON listés après 2021 entrent à leur 299ᵉ barre | Biais de survie en faveur des actifs encore listés |
| 14 | Direction HTF (étiquette MTF) | Décalage d'1h dans le sim | Sans effet sur la décision (WATCH seulement) ; affecte seulement l'étiquette de diagnostic |

## 7. Rappel production (non utilisé comme résultat)

Première semaine depuis le reset (2026-09-21 → 2026-09-27) : 43 positions, dont **23 seulement** relèvent de la
stratégie systématique reproductible (auto, 1h, crypto). Répartition de ces 23 sorties : stop 11, objectif 5,
direction 3, manuel 4. Trop peu pour une conclusion de performance ; cité pour montrer quelle part du paper
la simulation représente.
